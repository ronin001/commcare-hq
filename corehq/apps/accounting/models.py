import datetime
from decimal import Decimal
import logging
from couchdbkit.ext.django.schema import DateTimeProperty, StringProperty

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models

from django_prbac.models import Role
from dimagi.utils.couch.database import SafeSaveDocument

from corehq.apps.accounting.exceptions import CreditLineError, AccountingError
from corehq.apps.accounting.utils import EXCHANGE_RATE_DECIMAL_PLACES, assure_domain_instance

global_logger = logging.getLogger(__name__)


class BillingAccountType(object):
    CONTRACT = "CONTRACT"
    USER_CREATED = "USER_CREATED"
    INVOICE_GENERATED = "INVOICE_GENERATED"
    CHOICES = (
        (CONTRACT, "Created by contract"),
        (USER_CREATED, "Created by user"),
        (INVOICE_GENERATED, "Generated by an invoice"),
    )


class FeatureType(object):
    USER = "User"
    SMS = "SMS"
    API = "API"
    CHOICES = (
        (USER, USER),
        (SMS, SMS),
    )


class SoftwareProductType(object):
    COMMCARE = "CommCare"
    COMMTRACK = "CommTrack"
    COMMCONNECT = "CommConnect"
    CHOICES = (
        (COMMCARE, COMMCARE),
        (COMMTRACK, COMMTRACK),
        (COMMCONNECT, COMMCONNECT),
    )

    @classmethod
    def get_type_by_domain(cls, domain):
        if domain.commtrack_enabled:
            return cls.COMMTRACK
        if domain.commconnect_enabled:
            return cls.COMMCONNECT
        return cls.COMMCARE


class SoftwarePlanEdition(object):
    COMMUNITY = "Community"
    STANDARD = "Standard"
    PRO = "Pro"
    ADVANCED = "Advanced"
    ENTERPRISE = "Enterprise"
    CHOICES = (
        (COMMUNITY, COMMUNITY),
        (STANDARD, STANDARD),
        (PRO, PRO),
        (ADVANCED, ADVANCED),
        (ENTERPRISE, ENTERPRISE),
    )


class SoftwarePlanVisibility(object):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CHOICES = (
        (PUBLIC, "Anyone can subscribe"),
        (INTERNAL, "Dimagi must create subscription"),
    )


class CreditAdjustmentReason(object):
    DIRECT_PAYMENT = "DIRECT_PAYMENT"
    SALESFORCE = "SALESFORCE"
    INVOICE = "INVOICE"
    LINE_ITEM = "LINE_ITEM"
    TRANSFER = "TRANSFER"
    MANUAL = "MANUAL"
    CHOICES = (
        (MANUAL, "manual"),
        (SALESFORCE, "via Salesforce"),
        (INVOICE, "invoice generated"),
        (LINE_ITEM, "line item generated"),
        (TRANSFER, "transfer from another credit line"),
        (DIRECT_PAYMENT, "payment from client received"),
    )


class Currency(models.Model):
    """
    Keeps track of the current conversion rates so that we don't have to poll the free, but rate limited API
    from Open Exchange Rates. Necessary for billing things like MACH SMS.
    """
    code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=25, db_index=True)
    symbol = models.CharField(max_length=10)
    rate_to_default = models.DecimalField(default=1.0, max_digits=20, decimal_places=EXCHANGE_RATE_DECIMAL_PLACES)
    date_updated = models.DateField(auto_now=True)

    @classmethod
    def get_default(cls):
        default, _ = cls.objects.get_or_create(code=settings.DEFAULT_CURRENCY)
        return default


class BillingAccountAdmin(models.Model):
    web_user = models.CharField(max_length=80, unique=True, db_index=True)


class BillingAccount(models.Model):
    """
    The key model that links a Subscription to its financial source and methods of payment.
    """
    name = models.CharField(max_length=40, db_index=True)
    salesforce_account_id = models.CharField(
        db_index=True,
        max_length=80,
        blank=True,
        null=True,
        help_text="This is how we link to the salesforce account",
    )
    created_by = models.CharField(max_length=80)
    date_created = models.DateField(auto_now_add=True)
    billing_admins = models.ManyToManyField(BillingAccountAdmin, null=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT)
    is_auto_invoiceable = models.BooleanField(default=False)
    account_type = models.CharField(
        max_length=25,
        default=BillingAccountType.CONTRACT,
        choices=BillingAccountType.CHOICES,
    )

    @property
    def balance(self):
        # todo compute
        return 0.0

    @classmethod
    def get_or_create_account_by_domain(cls, domain, created_by=None):
        """
        First try to grab the account used for the last subscription.
        If an account is not found, create it.
        """
        try:
            last_subscription = Subscription.objects.filter(subscriber__domain=domain).latest('date_end')
            return last_subscription.account, False
        except ObjectDoesNotExist:
            pass
        account = BillingAccount(
            name=domain,
            created_by=created_by,
            date_created=datetime.date.today(),
            currency=Currency.get_default(),
            account_type=BillingAccountType.INVOICE_GENERATED,
        )
        account.save()
        return account, True


class BillingContactInfo(models.Model):
    account = models.OneToOneField(BillingAccount, primary_key=True, null=False)
    first_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)
    emails = models.CharField(max_length=200, null=True)
    phone_number = models.CharField(max_length=20, null=True)
    company_name = models.CharField(max_length=50, null=True)
    first_line = models.CharField(max_length=50, null=False)
    second_line = models.CharField(max_length=50, null=True)
    city = models.CharField(max_length=50, null=False)
    state_province_region = models.CharField(max_length=50, null=False)
    postal_code = models.CharField(max_length=20, null=False)
    country = models.CharField(max_length=50, null=False)


class SoftwareProduct(models.Model):
    """
    Specifies a product name that can be included in a subscription. e.g. CommTrack Pro, CommCare Community, etc.
    """
    name = models.CharField(max_length=40, unique=True)
    product_type = models.CharField(max_length=25, db_index=True, choices=SoftwareProductType.CHOICES)

    def __str__(self):
        return "Software Product '%s' of type '%s'" % (self.name, self.product_type)


class SoftwareProductRate(models.Model):
    """
    Links a SoftwareProduct to a monthly fee.
    Once created, ProductRates cannot be modified. Instead, a new ProductRate must be created.
    """
    product = models.ForeignKey(SoftwareProduct, on_delete=models.PROTECT)
    monthly_fee = models.DecimalField(default=Decimal('0.00'), max_digits=10, decimal_places=2)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    @classmethod
    def new_rate(cls, product_name, monthly_fee, save=True):
        product, _ = SoftwareProduct.objects.get_or_create(name=product_name)
        rate = SoftwareProductRate(product=product, monthly_fee=monthly_fee)
        if save:
            rate.save()
        return rate


class Feature(models.Model):
    """
    This is what will link a feature type (USER, API, etc.) to a name (Users Pro, API Standard, etc.) and will be what
    the FeatureRate references to provide a monthly fee, limit and per-excess fee.
    """
    name = models.CharField(max_length=40, unique=True)
    feature_type = models.CharField(max_length=10, db_index=True, choices=FeatureType.CHOICES)

    def __str__(self):
        return "Feature '%s' of type '%s'" % (self.name, self.feature_type)


class FeatureRate(models.Model):
    """
    Links a feature to a monthly fee, monthly limit, and a per-excess fee for exceeding the monthly limit.
    Once created, Feature Rates cannot be modified. Instead, a new Feature Rate must be created.
    """
    feature = models.ForeignKey(Feature, on_delete=models.PROTECT)
    monthly_fee = models.DecimalField(default=Decimal('0.00'), max_digits=10, decimal_places=2)
    monthly_limit = models.IntegerField(default=0)
    per_excess_fee = models.DecimalField(default=Decimal('0.00'), max_digits=10, decimal_places=2)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return 'Feature Rate: $%s /month, $%s /excess, limit: %d' % (
            self.monthly_fee, self.per_excess_fee, self.monthly_limit
        )

    @classmethod
    def new_rate(cls, feature_name, feature_type,
                 monthly_fee=None, monthly_limit=None, per_excess_fee=None, save=True):
        feature, _ = Feature.objects.get_or_create(name=feature_name, feature_type=feature_type)
        rate = FeatureRate(feature=feature)

        if monthly_fee is not None:
            rate.monthly_fee = monthly_fee
        if monthly_limit is not None:
            rate.monthly_limit = monthly_limit
        if per_excess_fee is not None:
            rate.per_excess_fee = per_excess_fee

        if save:
            rate.save()
        return rate


class SoftwarePlan(models.Model):
    """
    Subscriptions are created for Software Plans. Software Plans can have many Software Plan Versions, which
    link the Software Plan to a set of permissions roles.
    """
    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True,
                                   help_text="If the visibility is INTERNAL, this description field will be used.")
    edition = models.CharField(
        max_length=25,
        default=SoftwarePlanEdition.ENTERPRISE,
        choices=SoftwarePlanEdition.CHOICES,
    )
    visibility = models.CharField(
        max_length=10,
        default=SoftwarePlanVisibility.INTERNAL,
        choices=SoftwarePlanVisibility.CHOICES,
    )

    def get_version(self):
        return self.softwareplanversion_set.filter(is_active=True).latest('date_created')


class DefaultProductPlan(models.Model):
    """
    This links a product type to its default SoftwarePlan (i.e. the Community Plan).
    The latest SoftwarePlanVersion that's linked to this plan will be the one used to create a new subscription if
    nothing is found for that domain.
    """
    product_type = models.CharField(max_length=25, choices=SoftwareProductType.CHOICES, unique=True)
    plan = models.ForeignKey(SoftwarePlan, on_delete=models.PROTECT)

    @classmethod
    def get_default_plan_by_domain(cls, domain):
        domain = assure_domain_instance(domain)
        product_type = SoftwareProductType.get_type_by_domain(domain)
        try:
            default_product_plan = DefaultProductPlan.objects.get(product_type=product_type)
            return default_product_plan.plan.get_version()
        except DefaultProductPlan.DoesNotExist:
            raise AccountingError("No default product plan was set up, did you forget to bootstrap plans?")


class SoftwarePlanVersion(models.Model):
    """
    Links a plan to its rates and provides versioning information.
    Once a new SoftwarePlanVersion is created, it cannot be modified. Instead, a new SofwarePlanVersion
    must be created.
    """
    plan = models.ForeignKey(SoftwarePlan, on_delete=models.PROTECT)
    product_rates = models.ManyToManyField(SoftwareProductRate, blank=True)
    feature_rates = models.ManyToManyField(FeatureRate, blank=True)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    role = models.ForeignKey(Role)

    def __str__(self):
        return "Software Plan Version For Plan '%s' with Role '%s'" % (self.plan.name, self.role.slug)


class SubscriberManager(models.Manager):

    def safe_get(self, *args, **kwargs):
        try:
            return self.get(*args, **kwargs)
        except Subscriber.DoesNotExist:
            return None


class Subscriber(models.Model):
    """
    The objects that can be subscribed to a Subscription.
    """
    domain = models.CharField(max_length=25, null=True, db_index=True)
    organization = models.CharField(max_length=25, null=True, db_index=True)

    objects = SubscriberManager()

    def __str__(self):
        if self.organization:
            return "ORGANIZATION %s" % self.organization
        return "DOMAIN %s" % self.domain


class Subscription(models.Model):
    """
    Links a Subscriber to a SoftwarePlan and BillingAccount, necessary for invoicing.
    """
    account = models.ForeignKey(BillingAccount, on_delete=models.PROTECT)
    plan_version = models.ForeignKey(SoftwarePlanVersion, on_delete=models.PROTECT)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.PROTECT)
    salesforce_contract_id = models.CharField(blank=True, null=True, max_length=80)
    date_start = models.DateField()
    date_end = models.DateField(blank=True, null=True)
    date_delay_invoicing = models.DateField(blank=True, null=True)
    date_created = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=False)

    @classmethod
    def _get_plan_by_subscriber(cls, subscriber):
        try:
            active_subscriptions = cls.objects.filter(subscriber=subscriber, is_active=True)
            if active_subscriptions.count() > 1:
                global_logger.error("There seem to be multiple ACTIVE subscriptions for the subscriber %s. "
                                    "Odd, right? The latest one by date_created was used, but consider this an "
                                    "issue." % subscriber)
            current_subscription = active_subscriptions.latest('date_created')
            return current_subscription.plan_version, current_subscription
        except Subscription.DoesNotExist:
            global_logger.error("A Subscriber object exists without a Subscription for the domain '%s'. "
                                "This seems strange." % subscriber)
        return None, None

    @classmethod
    def get_subscribed_plan_by_organization(cls, organization):
        """
        Returns SoftwarePlanVersion, Subscription for the given organization.
        """
        subscriber = Subscriber.objects.safe_get(organization=organization, domain=None)
        return cls._get_plan_by_subscriber(subscriber) if subscriber else None, None

    @classmethod
    def get_subscribed_plan_by_domain(cls, domain):
        """
        Returns SoftwarePlanVersion, Subscription for the given domain.
        """
        domain = assure_domain_instance(domain)
        subscriber = Subscriber.objects.safe_get(domain=domain.name, organization=None)
        plan_version, subscription = (cls._get_plan_by_subscriber(subscriber) if subscriber
                                      else cls.get_subscribed_plan_by_organization(domain.organization))
        if plan_version is None:
            plan_version =  DefaultProductPlan.get_default_plan_by_domain(domain)
        return plan_version, subscription


class Invoice(models.Model):
    """
    This is what we'll use to calculate the balance on the accounts based on the current balance
    held by the Invoice. Balance updates will be tied to CreditAdjustmentTriggers which are tied
    to CreditAdjustments.
    """
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT)
    tax_rate = models.DecimalField(default=Decimal('0.0000'), max_digits=10, decimal_places=4)
    balance = models.DecimalField(default=Decimal('0.0000'), max_digits=10, decimal_places=4)
    date_due = models.DateField(db_index=True)
    date_paid = models.DateField(blank=True, null=True)
    date_created = models.DateField(auto_now_add=True)
    date_received = models.DateField(blank=True, db_index=True, null=True)
    date_start = models.DateField()
    date_end = models.DateField()

    @property
    def subtotal(self):
        """
        This will be inserted in the subtotal field on the printed invoice.
        """
        if self.lineitem_set.count() == 0:
            return Decimal('0.0000')
        return sum([line_item.total for line_item in self.lineitem_set.all()])

    @property
    def applied_tax(self):
        return self.tax_rate * self.subtotal

    @property
    def applied_credit(self):
        if self.creditadjustment_set.count() == 0:
            return Decimal('0.0000')
        return sum([credit.amount for credit in self.creditadjustment_set.all()])

    def get_total(self):
        """
        This will be inserted in the total field on the printed invoice.
        """
        return self.subtotal + self.applied_tax + self.applied_credit

    def update_balance(self):
        self.balance = self.get_total()

    def calculate_credit_adjustments(self):
        """
        This goes through all credit lines that:
        - do not have feature/product rates, but specify the related subscription and billing account
        - do not have feature/product rates or a subscription, but specify the related billing account
        """
        # first apply credits to all the line items
        for line_item in self.lineitem_set.all():
            line_item.calculate_credit_adjustments()

        # finally, apply credits to the leftover invoice balance
        current_total = self.get_total()
        credit_lines = CreditLine.get_credits_for_invoice(self)
        CreditLine.apply_credits_toward_balance(credit_lines, current_total, dict(invoice=self))


class BillingRecord(models.Model):
    """
    This stores any interaction we have with the client in sending a physical / pdf invoice to their contact email.
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT)
    date_emailed = models.DateField(auto_now_add=True, db_index=True)
    emailed_to = models.CharField(max_length=254, db_index=True)
    pdf_data_id = models.CharField(max_length=48)

    @property
    def pdf(self):
        return InvoicePdf.get(self.pdf_data_id)


class InvoicePdf(SafeSaveDocument):
    invoice_id = StringProperty()
    date_created = DateTimeProperty()

    def generate_pdf(self, invoice):
        # todo generate pdf
        invoice.pdf_data_id = self._id
        # self.put_attachment(pdf_data)
        self.invoice_id = invoice.id
        self.date_created = datetime.datetime.now()


class LineItemManager(models.Manager):
    def get_products(self):
        return self.get_query_set().filter(feature_rate__exact=None)

    def get_features(self):
        return self.get_query_set().filter(product_rate__exact=None)

    def get_feature_by_type(self, feature_type):
        return self.get_query_set().filter(feature_rate__feature__feature_type=feature_type)


class LineItem(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT)
    feature_rate = models.ForeignKey(FeatureRate, on_delete=models.PROTECT, null=True)
    product_rate = models.ForeignKey(SoftwareProductRate, on_delete=models.PROTECT, null=True)
    base_description = models.TextField(blank=True, null=True)
    base_cost = models.DecimalField(default=Decimal('0.0000'), max_digits=10, decimal_places=4)
    unit_description = models.TextField(blank=True, null=True)
    unit_cost = models.DecimalField(default=Decimal('0.0000'), max_digits=10, decimal_places=4)
    quantity = models.IntegerField(default=1)

    objects = LineItemManager()

    @property
    def subtotal(self):
        return self.base_cost + self.unit_cost * self.quantity

    @property
    def applied_credit(self):
        """
        The total amount of credit applied specifically to this LineItem.
        """
        if self.creditadjustment_set.count() == 0:
            return Decimal('0.0000')
        return sum([credit.amount for credit in self.creditadjustment_set.all()])

    @property
    def total(self):
        return self.subtotal + self.applied_credit

    def calculate_credit_adjustments(self):
        """
        This goes through all credit lines that:
        - specify the related feature or product rate that generated this line item
        """
        current_total = self.total
        credit_lines = CreditLine.get_credits_for_line_item(self)
        CreditLine.apply_credits_toward_balance(credit_lines, current_total, dict(line_item=self))


class CreditLine(models.Model):
    """
    The amount of money in USD that exists can can be applied toward a specific account,
    a specific subscription, or specific rates in that subscription.
    """
    account = models.ForeignKey(BillingAccount, on_delete=models.PROTECT)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, null=True, blank=True)
    product_rate = models.ForeignKey(SoftwareProductRate, on_delete=models.PROTECT, null=True, blank=True)
    feature_rate = models.ForeignKey(FeatureRate, on_delete=models.PROTECT, null=True, blank=True)
    date_created = models.DateField(auto_now_add=True)
    balance = models.DecimalField(default=Decimal('0.0000'), max_digits=10, decimal_places=4)

    def adjust_credit_balance(self, amount, is_new=False, note=None, line_item=None, invoice=None):
        reason = CreditAdjustmentReason.MANUAL
        note = note or ""
        if line_item is not None and invoice is not None:
            raise CreditLineError("You may only have an invoice OR a line item making this adjustment.")
        if line_item is not None:
            reason = CreditAdjustmentReason.LINE_ITEM
        if invoice is not None:
            reason = CreditAdjustmentReason.INVOICE
        if is_new:
            note = "Initialization of credit line. %s" % note
        credit_adjustment = CreditAdjustment(
            credit_line=self,
            note=note,
            amount=amount,
            reason=reason,
            line_item=line_item,
            invoice=invoice,
        )
        credit_adjustment.save()
        self.balance += amount
        self.save()

    @classmethod
    def get_credits_for_line_item(cls, line_item):
        return cls.get_credits_by_subscription_and_features(
            line_item.invoice.subscription,
            product_rate=line_item.product_rate,
            feature_rate=line_item.feature_rate
        )

    @classmethod
    def get_credits_for_invoice(cls, invoice):
        return cls.get_credits_by_subscription_and_features(invoice.subscription)

    @classmethod
    def get_credits_by_subscription_and_features(cls, subscription, feature_rate=None, product_rate=None):
        return cls.objects.filter(
            models.Q(subscription=subscription) |
            models.Q(account=subscription.account, subscription__exact=None)
        ).filter(
            product_rate__exact=product_rate, feature_rate__exact=feature_rate
        ).all()

    @classmethod
    def add_account_credit(cls, amount, account, note=None):
        cls._validate_add_amount(amount)
        credit_line, is_created = cls.objects.get_or_create(
            account=account,
            subscription__exact=None,
            product_rate__exact=None,
            feature_rate__exact=None,
        )
        credit_line.adjust_credit_balance(amount, is_new=is_created, note=note)
        return credit_line

    @classmethod
    def add_subscription_credit(cls, amount, subscription, note=None):
        cls._validate_add_amount(amount)
        credit_line, is_created = cls.objects.get_or_create(
            account=subscription.account,
            subscription=subscription,
            product_rate__exact=None,
            feature_rate__exact=None,
        )
        credit_line.adjust_credit_balance(amount, is_new=is_created, note=note)
        return credit_line

    @classmethod
    def add_rate_credit(cls, amount, account, product_rate=None, feature_rate=None, subscription=None, note=None):
        if (feature_rate is None and product_rate is None) or (feature_rate is not None and product_rate is not None):
            raise ValueError("You must specify a product rate OR a feature rate")
        cls._validate_add_amount(amount)
        credit_line, is_created = cls.objects.get_or_create(
            account=account, subscription=subscription, product_rate=product_rate, feature_rate=feature_rate,
        )
        credit_line.adjust_credit_balance(amount, is_new=is_created, note=note)
        return credit_line

    @classmethod
    def apply_credits_toward_balance(cls, credit_lines, balance, adjust_balance_kwarg):
        for credit_line in credit_lines:
            if balance == Decimal('0.0000'):
                return
            if balance <= Decimal('0.0000'):
                raise CreditLineError("A balance went below zero dollars when applying credits.")
            adjustment_amount = min(credit_line.balance, balance)
            if adjustment_amount > Decimal('0.0000'):
                credit_line.adjust_credit_balance(-adjustment_amount, **adjust_balance_kwarg)
                balance -= adjustment_amount
        return balance

    @staticmethod
    def _validate_add_amount(amount):
        if not isinstance(amount, Decimal):
            raise ValueError("Amount must be a Decimal.")


class CreditAdjustment(models.Model):
    """
    A record of any addition (positive amounts) s or deductions (negative amounts) that contributed to the
    current balance of the associated CreditLine.
    """
    credit_line = models.ForeignKey(CreditLine, on_delete=models.PROTECT)
    reason = models.CharField(max_length=25, default=CreditAdjustmentReason.MANUAL,
                              choices=CreditAdjustmentReason.CHOICES)
    note = models.TextField()
    amount = models.DecimalField(default=Decimal('0.0000'), max_digits=10, decimal_places=4)
    line_item = models.ForeignKey(LineItem, on_delete=models.PROTECT, null=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, null=True)
    # todo payment_method = models.ForeignKey(PaymentMethod)
    date_created = models.DateField(auto_now_add=True)
    web_user = models.CharField(max_length=80, null=True)

    def clean(self):
        """
        Only one of either a line item or invoice may be specified as the adjuster.
        """
        if self.line_item and self.invoice is not None:
            raise ValidationError("You can't specify both an invoice and a line item.")
