hqDefine('locations/js/locations', function() {
    var initialPageData = hqImport('hqwebapp/js/initial_page_data');
    var LocationModels = hqImport('locations/js/location_tree');

    $(function() {
        var load_locs_url = initialPageData.get('api_root');

        var locs = initialPageData.get('locations'),
            can_edit_root = initialPageData.get('can_edit_root'),
            hierarchy = initialPageData.get('hierarchy'),
            show_inactive = initialPageData.get('show_inactive'),
            location_search_url = initialPageData.reverse('location_search');

        var enableLocationSearchSelect = function () {
            $('#location_search_select').select2({
                ajax: {
                    url: location_search_url,
                    dataType: 'json',
                    data: function (params) {
                        return {
                            q: params.term,
                            page_limit: 10,
                            page: params.page,
                            show_inactive: show_inactive,
                        };
                    },
                    processResults: function (data, params) {
                        var more = data.more || (params.page * 10) < data.total;
                        return { results: data.results, more: more };
                    },
                },
            });
        };

        var reloadLocationSearchSelect = function () {
            $('#location_search_select').select2('val', null);
            enableLocationSearchSelect();
        };

        var clearLocationSelection = function () {
            reloadLocationSearchSelect();
            tree_model.load(locs);
        };

        var options = {
            show_inactive: show_inactive,
            can_edit_root: can_edit_root,
            load_locs_url: load_locs_url,
            reloadLocationSearchSelect: reloadLocationSearchSelect,
            clearLocationSelection: clearLocationSelection,
        };

        var tree_model = new LocationModels.LocationTreeViewModel(hierarchy, options);

        $('#location_tree').koApplyBindings(tree_model);
        tree_model.load(locs);
        var model = new LocationModels.LocationSearchViewModel(tree_model, options);
        $('#location_search').koApplyBindings(model);

        enableLocationSearchSelect();
    });
});
