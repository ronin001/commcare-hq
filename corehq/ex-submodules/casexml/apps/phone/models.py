from collections import defaultdict
from copy import copy
from datetime import datetime
from couchdbkit.exceptions import ResourceConflict, ResourceNotFound
from dimagi.ext.couchdbkit import *
from django.db import models
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.couch import LooselyEqualDocumentSchema
from casexml.apps.case import const
from casexml.apps.case.sharedmodels import CommCareCaseIndex, IndexHoldingMixIn
from casexml.apps.phone.checksum import Checksum, CaseStateHash
import logging


class User(object):
    """ 
    This is a basic user model that's used for OTA restore to properly
    find cases and generate the user XML.
    """
    
    def __init__(self, user_id, username, password, date_joined,
                 user_data=None, additional_owner_ids=None, domain=None,
                 loadtest_factor=1):
        self.user_id = user_id
        self.username = username
        self.password = password
        self.date_joined = date_joined
        self.user_data = user_data or {}
        self.additional_owner_ids = additional_owner_ids or []
        self.domain = domain
        self.loadtest_factor = loadtest_factor

    def get_owner_ids(self):
        ret = [self.user_id]
        ret.extend(self.additional_owner_ids)
        return list(set(ret))

    @classmethod
    def from_django_user(cls, django_user):
        return cls(user_id=str(django_user.pk), username=django_user.username,
                   password=django_user.password, date_joined=django_user.date_joined,
                   user_data={})
    

class CaseState(LooselyEqualDocumentSchema, IndexHoldingMixIn):
    """
    Represents the state of a case on a phone.
    """

    case_id = StringProperty()
    type = StringProperty()
    indices = SchemaListProperty(CommCareCaseIndex)

    @classmethod
    def from_case(cls, case):
        if isinstance(case, dict):
            return cls.wrap({
                'case_id': case['_id'],
                'type': case['type'],
                'indices': case['indices'],
            })

        return cls(
            case_id=case.get_id,
            type=case.type,
            indices=case.indices,
        )

    def __repr__(self):
        return "case state: %s (%s)" % (self.case_id, self.indices)


class SyncLogAssertionError(AssertionError):

    def __init__(self, case_id, *args, **kwargs):
        self.case_id = case_id
        super(SyncLogAssertionError, self).__init__(*args, **kwargs)


LOG_FORMAT_LEGACY = 'legacy'
LOG_FORMAT_SIMPLIFIED = 'simplified'


class AbstractSyncLog(SafeSaveDocument, UnicodeMixIn):
    date = DateTimeProperty()
    # domain = StringProperty()
    user_id = StringProperty()
    previous_log_id = StringProperty()  # previous sync log, forming a chain
    duration = IntegerProperty()        # in seconds
    log_format = StringProperty()

    # owner_ids_on_phone stores the ids the phone thinks it's the owner of.
    # This typically includes the user id,
    # as well as all groups that that user is a member of.
    owner_ids_on_phone = StringListProperty()

    strict = True  # for asserts

    def _assert(self, conditional, msg="", case_id=None):
        if not conditional:
            if self.strict:
                raise SyncLogAssertionError(case_id, msg)
            else:
                logging.warn("assertion failed: %s" % msg)
                self.has_assert_errors = True

    @classmethod
    def wrap(cls, data):
        ret = super(AbstractSyncLog, cls).wrap(data)
        if hasattr(ret, 'has_assert_errors'):
            ret.strict = False
        return ret

    def phone_is_holding_case(self, case_id):
        raise NotImplementedError()

    def get_footprint_of_cases_on_phone(self):
        """
        Gets the phone's flat list of all case ids on the phone,
        owned or not owned but relevant.
        """
        raise NotImplementedError()

    def get_state_hash(self):
        return CaseStateHash(Checksum(self.get_footprint_of_cases_on_phone()).hexdigest())

    def get_payload_attachment_name(self, version):
        return 'restore_payload_{version}.xml'.format(version=version)

    def has_cached_payload(self, version):
        return self.get_payload_attachment_name(version) in self._doc.get('_attachments', {})

    def get_cached_payload(self, version, stream=False):
        try:
            return self.fetch_attachment(self.get_payload_attachment_name(version), stream=stream)
        except ResourceNotFound:
            return None

    def set_cached_payload(self, payload, version):
        self.put_attachment(payload, name=self.get_payload_attachment_name(version),
                            content_type='text/xml')

    def invalidate_cached_payloads(self):
        for name in copy(self._doc.get('_attachments', {})):
            self.delete_attachment(name)


class SyncLog(AbstractSyncLog):
    """
    A log of a single sync operation.
    """
    log_format = StringProperty(default=LOG_FORMAT_LEGACY)
    last_seq = StringProperty()         # the last_seq of couch during this sync

    # we need to store a mapping of cases to indices for generating the footprint
    # cases_on_phone represents the state of all cases the server
    # thinks the phone has on it and cares about.
    cases_on_phone = SchemaListProperty(CaseState)

    # dependant_cases_on_phone represents the possible list of cases
    # also on the phone because they are referenced by a real case's index
    # (or a dependent case's index).
    # This list is not necessarily a perfect reflection
    # of what's on the phone, but is guaranteed to be after pruning
    dependent_cases_on_phone = SchemaListProperty(CaseState)

    @classmethod
    def wrap(cls, data):
        # last_seq used to be int, but is now string for cloudant compatibility
        if isinstance(data.get('last_seq'), (int, long)):
            data['last_seq'] = unicode(data['last_seq'])
        return super(SyncLog, cls).wrap(data)

    @classmethod
    def last_for_user(cls, user_id):
        from casexml.apps.phone.dbaccessors.sync_logs_by_user import get_last_synclog_for_user
        return get_last_synclog_for_user(user_id)

    def get_previous_log(self):
        """
        Get the previous sync log, if there was one.  Otherwise returns nothing.
        """
        if not hasattr(self, "_previous_log_ref"):
            self._previous_log_ref = SyncLog.get(self.previous_log_id) if self.previous_log_id else None
        return self._previous_log_ref

    def phone_has_case(self, case_id):
        """
        Whether the phone currently has a case, according to this sync log
        """
        return self.get_case_state(case_id) is not None

    def get_case_state(self, case_id):
        """
        Get the case state object associated with an id, or None if no such
        object is found
        """
        filtered_list = self._case_state_map()[case_id]
        if filtered_list:
            self._assert(len(filtered_list) == 1,
                         "Should be exactly 0 or 1 cases on phone but were %s for %s" %
                         (len(filtered_list), case_id))
            return CaseState.wrap(filtered_list[0])
        return None

    def phone_has_dependent_case(self, case_id):
        """
        Whether the phone currently has a dependent case, according to this sync log
        """
        return self.get_dependent_case_state(case_id) is not None

    def get_dependent_case_state(self, case_id):
        """
        Get the dependent case state object associated with an id, or None if no such
        object is found
        """
        filtered_list = self._dependent_case_state_map()[case_id]
        if filtered_list:
            self._assert(len(filtered_list) == 1,
                         "Should be exactly 0 or 1 dependent cases on phone but were %s for %s" %
                         (len(filtered_list), case_id))
            return CaseState.wrap(filtered_list[0])
        return None

    @memoized
    def _dependent_case_state_map(self):
        return self._build_state_map('dependent_cases_on_phone')

    @memoized
    def _case_state_map(self):
        return self._build_state_map('cases_on_phone')

    def _build_state_map(self, list_name):
        state_map = defaultdict(list)
        # referencing the property via self._doc is because we don't want to needlessly call wrap
        # (which couchdbkit does not make any effort to cache on repeated calls)
        # deterministically this change shaved off 10 seconds from an ota restore
        # of about 300 cases.
        for case in self._doc[list_name]:
            state_map[case['case_id']].append(case)

        return state_map

    def _get_case_state_from_anywhere(self, case_id):
        return self.get_case_state(case_id) or self.get_dependent_case_state(case_id)

    def archive_case(self, case_id):
        state = self.get_case_state(case_id)
        self.cases_on_phone.remove(state)
        self._case_state_map.reset_cache(self)

        # I'm not quite clear on when this can happen, but we've seen it
        # in wild, so safeguard against it.
        if not self.phone_has_dependent_case(case_id):
            self.dependent_cases_on_phone.append(state)
            self._dependent_case_state_map.reset_cache(self)

    def _phone_owns(self, action):
        # whether the phone thinks it owns an action block.
        # the only way this can't be true is if the block assigns to an
        # owner id that's not associated with the user on the phone
        owner = action.updated_known_properties.get("owner_id")
        if owner:
            return owner in self.owner_ids_on_phone
        return True

    def update_phone_lists(self, xform, case_list):
        # for all the cases update the relevant lists in the sync log
        # so that we can build a historical record of what's associated
        # with the phone
        for case in case_list:
            actions = case.get_actions_for_form(xform.get_id)
            for action in actions:

                if action.action_type == const.CASE_ACTION_CREATE:
                    self._assert(not self.phone_has_case(case._id),
                                 'phone has case being created: %s' % case._id)
                    if self._phone_owns(action):
                        self.cases_on_phone.append(CaseState(case_id=case.get_id,
                                                             indices=[]))
                        self._case_state_map.reset_cache(self)
                elif action.action_type == const.CASE_ACTION_UPDATE:
                    self._assert(
                        self.phone_has_case(case._id),
                        "phone doesn't have case being updated: %s" % case._id,
                        case._id,
                    )

                    if not self._phone_owns(action):
                        # only action necessary here is in the case of
                        # reassignment to an owner the phone doesn't own
                        self.archive_case(case.get_id)
                elif action.action_type == const.CASE_ACTION_INDEX:
                    # in the case of parallel reassignment and index update
                    # the phone might not have the case
                    if self.phone_has_case(case.get_id):
                        case_state = self.get_case_state(case.get_id)
                    else:
                        self._assert(self.phone_has_dependent_case(case._id),
                                     "phone doesn't have referenced case: %s" % case._id)
                        case_state = self.get_dependent_case_state(case.get_id)
                    # reconcile indices
                    if case_state:
                        case_state.update_indices(action.indices)
                elif action.action_type == const.CASE_ACTION_CLOSE:
                    if self.phone_has_case(case.get_id):
                        self.archive_case(case.get_id)
        if case_list:
            try:
                self.save()
                self.invalidate_cached_payloads()
            except ResourceConflict:
                logging.exception('doc update conflict saving sync log {id}'.format(
                    id=self._id,
                ))
                raise

    def get_footprint_of_cases_on_phone(self):
        def children(case_state):
            return [self._get_case_state_from_anywhere(index.referenced_id)
                    for index in case_state.indices]

        relevant_cases = set()
        queue = list(self.cases_on_phone)
        while queue:
            case_state = queue.pop()
            # I don't actually understand why something is coming back None
            # here, but we can probably just ignore it.
            if case_state is not None and case_state.case_id not in relevant_cases:
                relevant_cases.add(case_state.case_id)
                queue.extend(children(case_state))
        return relevant_cases

    def phone_is_holding_case(self, case_id):
        """
        Whether the phone is holding (not purging) a case.
        """
        # this is inefficient and could be optimized
        if self.phone_has_case(case_id):
            return True
        else:
            cs = self.get_dependent_case_state(case_id)
            if cs and case_id in self.get_footprint_of_cases_on_phone():
                return True
            return False

    def reconcile_cases(self):
        """
        Goes through the cases expected to be on the phone and reconciles
        any duplicate records.

        Return True if any duplicates were found.
        """
        num_cases_on_phone_before = len(self.cases_on_phone)
        num_dependent_cases_before = len(self.dependent_cases_on_phone)

        self.cases_on_phone = list(set(self.cases_on_phone))
        self.dependent_cases_on_phone = list(set(self.dependent_cases_on_phone))

        if num_cases_on_phone_before != len(self.cases_on_phone) \
                or num_dependent_cases_before != len(self.dependent_cases_on_phone):
            self._case_state_map.reset_cache(self)
            self._dependent_case_state_map.reset_cache(self)
            return True

        return False

    def __unicode__(self):
        return "%s synced on %s (%s)" % (self.user_id, self.date.date(), self.get_id)


class SimplifiedSyncLog(AbstractSyncLog):
    """
    New, simplified sync log class that is used by ownership cleanliness restore.

    Just maintains a flat list of case IDs on the phone rather than the case/dependent state
    lists from the SyncLog class.
    """
    log_format = StringProperty(default=LOG_FORMAT_SIMPLIFIED)
    case_ids_on_phone = SetProperty()

    def phone_is_holding_case(self, case_id):
        """
        Whether the phone currently has a case, according to this sync log
        """
        return case_id in self.case_ids_on_phone

    def get_footprint_of_cases_on_phone(self):
        return self.case_ids_on_phone


def get_properly_wrapped_sync_log(doc_id):
    """
    Looks up and wraps a sync log, using the class based on the 'log_format' attribute.
    Defaults to the existing legacy SyncLog class.
    """
    doc = SyncLog.get_db().get(doc_id)
    return get_sync_log_class_by_format(doc.get('log_format')).wrap(doc)


def get_sync_log_class_by_format(format):
    return {
        LOG_FORMAT_LEGACY: SyncLog,
        LOG_FORMAT_SIMPLIFIED: SimplifiedSyncLog,
    }.get(format, SyncLog)


class OwnershipCleanlinessFlag(models.Model):
    """
    Stores whether an owner_id is "clean" aka has a case universe only belonging
    to that ID.

    We use this field to optimize restores.
    """
    domain = models.CharField(max_length=100, db_index=True)
    owner_id = models.CharField(max_length=100, db_index=True)
    is_clean = models.BooleanField(default=False)
    last_checked = models.DateTimeField()
    hint = models.CharField(max_length=100, null=True, blank=True)

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        self.last_checked = datetime.utcnow()
        super(OwnershipCleanlinessFlag, self).save(force_insert, force_update, using, update_fields)

    @classmethod
    def get_for_owner(cls, domain, owner_id):
        return cls.objects.get_or_create(domain=domain, owner_id=owner_id)[0]

    class Meta:
        unique_together = [('domain', 'owner_id')]
