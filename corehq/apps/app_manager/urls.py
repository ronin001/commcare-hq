from django.conf.urls import url, include
from corehq.apps.app_manager.view_helpers import DynamicTemplateView
from corehq.apps.app_manager.views import (
    DownloadCCZ,
    AppSummaryView,
    AppDiffView,
    AppDataView,
    LanguageProfilesView,
    DownloadCaseSummaryView,
    DownloadFormSummaryView,
    DownloadAppSummaryView,
    PromptSettingsUpdateView,
    view_app,
    download_bulk_ui_translations, download_bulk_app_translations, upload_bulk_ui_translations,
    upload_bulk_app_translations, multimedia_ajax, releases_ajax, current_app_version, paginate_releases,
    release_build, view_module, view_module_legacy, view_form, view_form_legacy,
    get_form_datums, form_source, form_source_legacy, update_build_comment, export_gzip,
    xform_display, get_xform_source, form_casexml, app_source, import_app, app_from_template, copy_app,
    get_form_data_schema, new_module, new_app, default_new_app, new_form, drop_user_case, delete_app,
    delete_module, delete_form, copy_form, undo_delete_app, undo_delete_module, undo_delete_form, edit_form_attr,
    edit_form_attr_api, patch_xform, validate_form_for_build, rename_language, validate_language,
    edit_form_actions, edit_advanced_form_actions, edit_visit_schedule,
    edit_schedule_phases, multimedia_list_download, edit_module_detail_screens, edit_module_attr,
    edit_report_module, validate_module_for_build, commcare_profile, edit_commcare_profile, edit_commcare_settings,
    edit_app_langs, edit_app_attr, edit_app_ui_translations, get_app_ui_translations, rearrange, odk_qr_code,
    odk_media_qr_code, odk_install, short_url, short_odk_url, save_copy, revert_to_copy, delete_copy, list_apps,
    direct_ccz, download_index, download_file, get_form_questions, pull_master_app, edit_add_ons,
    update_linked_whitelist, overwrite_module_case_list, app_settings,
)
from corehq.apps.hqmedia.urls import application_urls as hqmedia_urls
from corehq.apps.hqmedia.urls import download_urls as media_download_urls

app_urls = [
    url(r'^languages/$', view_app, name='app_languages'),
    url(r'^languages/translations/download/$', download_bulk_ui_translations, name='download_bulk_ui_translations'),
    url(r'^languages/translations/upload/$', upload_bulk_ui_translations, name='upload_bulk_ui_translations'),
    url(r'^languages/bulk_app_translations/download/$', download_bulk_app_translations, name='download_bulk_app_translations'),
    url(r'^languages/bulk_app_translations/upload/$', upload_bulk_app_translations, name='upload_bulk_app_translations'),
    url(r'^multimedia_ajax/$', multimedia_ajax, name='app_multimedia_ajax'),
    url(r'^$', view_app, name='view_app'),
    url(r'^releases/$', view_app, name='release_manager'),
    url(r'^settings/$', app_settings, name='app_settings'),
    url(r'^add_ons/edit/$', edit_add_ons, name='edit_add_ons'),
    url(r'^releases_ajax/$', releases_ajax, name='release_manager_ajax'),
    url(r'^current_version/$', current_app_version, name='current_app_version'),
    url(r'^releases/json/$', paginate_releases, name='paginate_releases'),
    url(r'^releases/release/(?P<saved_app_id>[\w-]+)/$', release_build,
        name='release_build'),
    url(r'^releases/unrelease/(?P<saved_app_id>[\w-]+)/$', release_build,
        name='unrelease_build', kwargs={'is_released': False}),
    url(r'^releases/profiles/$', LanguageProfilesView.as_view(), name=LanguageProfilesView.urlname),
    url(r'^modules-(?P<module_id>[\w-]+)/$', view_module_legacy,
        name='view_module_legacy'),  # keep legacy around for docs
    url(r'^module/(?P<module_unique_id>[\w-]+)/$', view_module, name='view_module'),
    url(r'^modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/$',
        view_form_legacy, name='view_form_legacy'),  # keep legacy around for docs
    url(r'^form/(?P<form_unique_id>[\w-]+)/$', view_form, name='view_form'),
    url(r'^get_form_datums/$', get_form_datums, name='get_form_datums'),
    url(r'^get_form_questions/$', get_form_questions, name='get_form_questions'),
    url(r'^form/(?P<form_unique_id>[\w-]+)/source/$', form_source, name='form_source'),
    url(r'^modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/source/$',
        form_source_legacy, name='form_source_legacy'),
    url(r'^app_data/$', AppDataView.as_view(), name=AppDataView.urlname),
    url(r'^summary/$', AppSummaryView.as_view(), name=AppSummaryView.urlname),
    url(r'^summary/case/download/$', DownloadCaseSummaryView.as_view(), name=DownloadCaseSummaryView.urlname),
    url(r'^summary/form/download/$', DownloadFormSummaryView.as_view(), name=DownloadFormSummaryView.urlname),
    url(r'^summary/app/download/$', DownloadAppSummaryView.as_view(), name=DownloadAppSummaryView.urlname),
    url(r'^update_build_comment/$', update_build_comment,
        name='update_build_comment'),
    url(r'^copy/gzip$', export_gzip, name='gzip_app'),
    url(r'^update_prompts/$', PromptSettingsUpdateView.as_view(), name=PromptSettingsUpdateView.urlname),
]


urlpatterns = [
    url(r'^$', view_app, name='default_app'),
    url(r'^xform/(?P<form_unique_id>[\w-]+)/$', xform_display, name='xform_display'),
    url(r'^browse/(?P<app_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/source/$',
        get_xform_source, name='get_xform_source'),
    url(r'^casexml/(?P<form_unique_id>[\w-]+)/$', form_casexml, name='form_casexml'),
    url(r'^source/(?P<app_id>[\w-]+)/$', app_source, name='app_source'),
    url(r'^import_app/$', import_app, name='import_app'),
    url(r'^app_from_template/(?P<slug>[\w-]+)/$', app_from_template, name='app_from_template'),
    url(r'^copy_app/$', copy_app, name='copy_app'),
    url(r'^view/(?P<app_id>[\w-]+)/', include(app_urls)),
    url(r'^schema/form/(?P<form_unique_id>[\w-]+)/$',
        get_form_data_schema, name='get_form_data_schema'),
    url(r'^new_module/(?P<app_id>[\w-]+)/$', new_module, name='new_module'),
    url(r'^new_app/$', new_app, name='new_app'),
    url(r'^default_new_app/$', default_new_app, name='default_new_app'),
    url(r'^new_form/(?P<app_id>[\w-]+)/(?P<module_unique_id>[\w-]+)/$',
        new_form, name='new_form'),
    url(r'^drop_user_case/(?P<app_id>[\w-]+)/$', drop_user_case, name='drop_user_case'),
    url(r'^pull_master/(?P<app_id>[\w-]+)/$', pull_master_app, name='pull_master_app'),
    url(r'^linked_whitelist/(?P<app_id>[\w-]+)/$', update_linked_whitelist, name='update_linked_whitelist'),

    url(r'^delete_app/(?P<app_id>[\w-]+)/$', delete_app, name='delete_app'),
    url(r'^delete_module/(?P<app_id>[\w-]+)/(?P<module_unique_id>[\w-]+)/$',
        delete_module, name="delete_module"),
    url(r'^delete_form/(?P<app_id>[\w-]+)/(?P<module_unique_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/$',
        delete_form, name="delete_form"),

    url(r'^overwrite_module_case_list/(?P<app_id>[\w-]+)/(?P<module_unique_id>[\w-]+)/$',
        overwrite_module_case_list, name='overwrite_module_case_list'),
    url(r'^copy_form/(?P<app_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/$', copy_form, name='copy_form'),

    url(r'^undo_delete_app/(?P<record_id>[\w-]+)/$', undo_delete_app,
        name='undo_delete_app'),
    url(r'^undo_delete_module/(?P<record_id>[\w-]+)/$', undo_delete_module,
        name='undo_delete_module'),
    url(r'^undo_delete_form/(?P<record_id>[\w-]+)/$', undo_delete_form,
        name='undo_delete_form'),

    url(r'^edit_form_attr/(?P<app_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/(?P<attr>[\w-]+)/$',
        edit_form_attr, name='edit_form_attr'),
    url(r'^edit_form_attr_api/(?P<app_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/(?P<attr>[\w-]+)/$',
        edit_form_attr_api, name='edit_form_attr_api'),
    url(r'^patch_xform/(?P<app_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/$',
        patch_xform, name='patch_xform'),
    url(r'^validate_form_for_build/(?P<app_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/$',
        validate_form_for_build, name='validate_form_for_build'),
    url(r'^rename_language/(?P<form_unique_id>[\w-]+)/$', rename_language, name='rename_language'),
    url(r'^validate_langcode/(?P<app_id>[\w-]+)/$', validate_language, name='validate_language'),
    url(r'^edit_form_actions/(?P<app_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/$',
        edit_form_actions, name='edit_form_actions'),
    url(r'^edit_advanced_form_actions/(?P<app_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/$',
        edit_advanced_form_actions, name='edit_advanced_form_actions'),

    # Scheduler Modules
    url(r'^edit_visit_schedule/(?P<app_id>[\w-]+)/(?P<form_unique_id>[\w-]+)/$',
        edit_visit_schedule, name='edit_visit_schedule'),
    url(r'^edit_schedule_phases/(?P<app_id>[\w-]+)/(?P<module_unique_id>[\w-]+)/$',
        edit_schedule_phases,
        name='edit_schedule_phases'),

    # multimedia stuff
    url(r'^multimedia/(?P<app_id>[\w-]+)/download/$',
        multimedia_list_download, name='multimedia_list_download'),
    url(r'^(?P<app_id>[\w-]+)/multimedia/', include(hqmedia_urls)),
    url(r'^edit_module_detail_screens/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/$',
        edit_module_detail_screens, name='edit_module_detail_screens'),
    url(r'^edit_module_attr/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/(?P<attr>[\w-]+)/$',
        edit_module_attr, name='edit_module_attr'),
    url(r'^edit_report_module/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/$',
        edit_report_module, name='edit_report_module'),
    url(r'^validate_module_for_build/(?P<app_id>[\w-]+)/(?P<module_id>[\w-]+)/$',
        validate_module_for_build, name='validate_module_for_build'),

    url(r'^commcare_profile/(?P<app_id>[\w-]+)/$', commcare_profile, name='commcare_profile'),
    url(r'^edit_commcare_profile/(?P<app_id>[\w-]+)/$', edit_commcare_profile,
        name='edit_commcare_profile'),
    url(r'^edit_commcare_settings/(?P<app_id>[\w-]+)/$',
        edit_commcare_settings, name='edit_commcare_settings'),
    url(r'^edit_app_langs/(?P<app_id>[\w-]+)/$', edit_app_langs,
        name='edit_app_langs'),
    url(r'^edit_app_attr/(?P<app_id>[\w-]+)/(?P<attr>[\w-]+)/$',
        edit_app_attr, name='edit_app_attr'),
    url(r'^edit_app_ui_translations/(?P<app_id>[\w-]+)/$', edit_app_ui_translations,
        name='edit_app_ui_translations'),
    url(r'^get_app_ui_translations/$', get_app_ui_translations, name='get_app_ui_translations'),
    url(r'^rearrange/(?P<app_id>[\w-]+)/(?P<key>[\w-]+)/$', rearrange, name='rearrange'),

    url(r'^odk/(?P<app_id>[\w-]+)/qr_code/$', odk_qr_code, name='odk_qr_code'),
    url(r'^odk/(?P<app_id>[\w-]+)/media_qr_code/$', odk_media_qr_code, name='odk_media_qr_code'),
    url(r'^odk/(?P<app_id>[\w-]+)/install/$', odk_install, name="odk_install"),
    url(r'^odk/(?P<app_id>[\w-]+)/media_install/$', odk_install, {'with_media': True}, name="odk_media_install"),

    url(r'^odk/(?P<app_id>[\w-]+)/short_url/$', short_url, name='short_url'),
    url(r'^odk/(?P<app_id>[\w-]+)/short_odk_media_url/$', short_odk_url, {'with_media': True}),
    url(r'^odk/(?P<app_id>[\w-]+)/short_odk_url/$', short_odk_url),

    url(r'^save/(?P<app_id>[\w-]+)/$', save_copy, name='save_copy'),
    url(r'^revert/(?P<app_id>[\w-]+)/$', revert_to_copy, name='revert_to_copy'),
    url(r'^delete_copy/(?P<app_id>[\w-]+)/$', delete_copy, name='delete_copy'),

    url(r'^api/list_apps/$', list_apps, name='list_apps'),
    url(r'^api/download_ccz/$', direct_ccz, name='direct_ccz'),
    url(r'^download/(?P<app_id>[\w-]+)/$', download_index, name='download_index'),
    # the order of these download urls is important
    url(r'^download/(?P<app_id>[\w-]+)/CommCare.ccz$', DownloadCCZ.as_view(),
        name=DownloadCCZ.name),
    url(r'^download/(?P<app_id>[\w-]+)/multimedia/', include(media_download_urls)),
    url(r'^download/(?P<app_id>[\w-]+)/(?P<path>.*)$', download_file,
        name='app_download_file'),
    url(r'^download/(?P<app_id>[\w-]+)/',
        include('corehq.apps.app_manager.download_urls')),
    url(r'^ng_template/(?P<template>[\w-]+)', DynamicTemplateView.as_view(), name='ng_template'),

    url(r'^diff/(?P<first_app_id>[\w-]+)/(?P<second_app_id>[\w-]+)/$', AppDiffView.as_view(), name=AppDiffView.urlname),

    url(r'^', include('custom.ucla.urls')),
]
