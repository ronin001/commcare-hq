from django.db import models

from corehq.warehouse.const import (
    USER_DIM_SLUG,
    GROUP_DIM_SLUG,
    LOCATION_DIM_SLUG,
    DOMAIN_DIM_SLUG,
    USER_LOCATION_DIM_SLUG,
    USER_GROUP_DIM_SLUG,
    USER_STAGING_SLUG,
    GROUP_STAGING_SLUG,
    LOCATION_STAGING_SLUG,
    DOMAIN_STAGING_SLUG,
)

from .shared import WarehouseTableMixin


class BaseDim(models.Model):
    domain = models.CharField(max_length=255)

    dim_last_modified = models.DateTimeField(auto_now=True)
    dim_created_on = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


class UserDim(BaseDim, WarehouseTableMixin):
    '''
    Dimension for Users

    Grain: user_id
    '''
    slug = USER_DIM_SLUG

    user_id = models.CharField(max_length=255)
    username = models.CharField(max_length=150)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=100)

    is_active = models.BooleanField()
    is_staff = models.BooleanField()
    is_superuser = models.BooleanField()

    last_login = models.DateTimeField()
    date_joined = models.DateTimeField()

    @classmethod
    def dependencies(cls):
        return [USER_STAGING_SLUG]


class GroupDim(BaseDim, WarehouseTableMixin):
    '''
    Dimension for Groups

    Grain: group_id
    '''
    slug = GROUP_DIM_SLUG

    group_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255)

    case_sharing = models.BooleanField()
    reporting = models.BooleanField()

    group_last_modified = models.DateTimeField()

    @classmethod
    def dependencies(cls):
        return [GROUP_STAGING_SLUG]


class LocationDim(BaseDim, WarehouseTableMixin):
    '''
    Dimension for Locations

    Grain: location_id
    '''
    slug = LOCATION_DIM_SLUG

    location_id = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    site_code = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255)
    supply_point_id = models.CharField(max_length=255, null=True)

    location_type_id = models.CharField(max_length=255)
    location_type_name = models.CharField(max_length=255)
    location_type_code = models.CharField(max_length=255)

    is_archived = models.BooleanField()

    latitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=10, null=True)

    location_last_modified = models.DateTimeField()
    location_created_on = models.DateTimeField()

    @classmethod
    def dependencies(cls):
        return [LOCATION_STAGING_SLUG]


class DomainDim(BaseDim, WarehouseTableMixin):
    '''
    Dimension for Domain

    Grain: domain_id
    '''
    slug = DOMAIN_DIM_SLUG

    domain_id = models.CharField(max_length=255)
    default_timezone = models.CharField(max_length=255)
    hr_name = models.CharField(max_length=255)
    creating_user_id = models.CharField(max_length=255)
    project_type = models.CharField(max_length=255)

    is_active = models.BooleanField()
    case_sharing = models.BooleanField()
    commtrack_enabled = models.BooleanField()
    is_test = models.BooleanField()
    location_restriction_for_users = models.BooleanField()
    use_sql_backend = models.BooleanField()
    first_domain_for_user = models.BooleanField()

    domain_last_modified = models.DateTimeField()
    domain_created_on = models.DateTimeField()

    @classmethod
    def dependencies(cls):
        return [DOMAIN_STAGING_SLUG]


class UserLocationDim(BaseDim, WarehouseTableMixin):
    '''
    Dimension for User and Location mapping

    Grain: user_id, location_id
    '''
    slug = USER_LOCATION_DIM_SLUG

    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    location_dim = models.ForeignKey('LocationDim', on_delete=models.CASCADE)


class UserGroupDim(BaseDim, WarehouseTableMixin):
    '''
    Dimension for User and Group mapping

    Grain: user_id, group_id
    '''
    slug = USER_GROUP_DIM_SLUG

    user_dim = models.ForeignKey('UserDim', on_delete=models.CASCADE)
    group_dim = models.ForeignKey('GroupDim', on_delete=models.CASCADE)
