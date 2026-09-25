import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import "hqwebapp/js/components/pagination";
import "hqwebapp/js/bootstrap5/main";  // post-link
import "hqwebapp/js/bootstrap5/knockout_bindings.ko";  // popover

var tileModel = function (options) {
    var self = {};
    self.title = options.title;
    self.slug = options.slug;
    self.icon = options.icon;
    self.cardClasses = 'collectra-card-' + options.slug;
    self.kicker = ({applications: '01 / BUILD', reports: '02 / MONITOR', data: '03 / EXPORT',
        users: '04 / TEAM'})[options.slug] || 'WORKSPACE';
    self.url = options.url;
    self.helpText = options.help_text;
    self.hasError = ko.observable(false);

    // Might get updated if this tile supports an item list but it's empty
    self.hasItemList = ko.observable(options.has_item_list);
    // The template evaluates `foreach: items` for every tile, including links
    // such as Users that do not have a paginator. Keep the binding defined for
    // those tiles so one link-only card cannot abort the entire dashboard.
    self.items = ko.observableArray();

    if (self.hasItemList()) {
        self.itemsPerPage = 5;

        // Set via ajax
        self.totalItems = ko.observable();
        self.totalPages = ko.observable();
    }

    // Control visibility of various parts of tile content
    self.showBackgroundIcon = ko.computed(function () {
        return self.hasItemList() && !self.hasError();
    });
    self.showSpinner = ko.computed(function () {
        // Show spinner if this is an ajax tile, it's still waiting for one or both requests,
        // and neither request has errored out
        return self.hasItemList()
               && (self.items().length === 0 || self.totalPages() === undefined)
               && !self.hasError();
    });
    self.showItemList = ko.computed(function () {
        return !self.showSpinner() && !self.hasError();
    });
    self.showIconLink = ko.computed(function () {
        return !self.hasItemList() || self.hasError();
    });

    // Paging
    if (self.hasItemList()) {
        self.goToPage = function (page) {
            // If request takes a noticeable amount of time, clear items, which will show spinner
            var done = false;
            _.delay(function () {
                if (!done) {
                    self.items([]);     // clear items to show spinner
                }
            }, 500);

            // Send request for items on current page
            $.ajax({
                method: "GET",
                url: initialPageData.reverse('dashboard_tile', self.slug),
                data: {
                    itemsPerPage: self.itemsPerPage,
                    currentPage: page,
                },
                success: function (data) {
                    self.items(data.items);
                    done = true;
                },
                error: function () {
                    self.hasError(true);
                },
            });

            // Total number of pages is also a separate request, but it only needs to run once
            // and then self.totalPages() never changes again
            if (self.totalItems() === undefined) {
                $.ajax({
                    method: "GET",
                    url: initialPageData.reverse('dashboard_tile_total', self.slug),
                    success: function (data) {
                        self.totalItems(data.total);
                        self.totalPages(Math.ceil(data.total / self.itemsPerPage));
                        if (data.total === 0) {
                            self.hasItemList(false);
                        }
                    },
                    error: function () {
                        self.hasError(true);
                    },
                });
            }
        };

        // Initialize with first page of data
        self.goToPage(1);
    }

    return self;
};

var dashboardModel = function (options) {
    var self = {};
    self.tiles = _.map(options.tiles, function (t) { return tileModel(t); });
    return self;
};

$(function () {
    $("#dashboard-tiles").koApplyBindings(dashboardModel({
        tiles: initialPageData.get("dashboard_tiles"),
    }));

    var alertsPanel = $("#operational-alerts");
    if (alertsPanel.length) {
        var alertsModel = {
            alerts: ko.observableArray([]),
            loading: ko.observable(true),
            error: ko.observable(false),
            lastUpdated: ko.observable(""),
            selectedSeverity: ko.observable("all"),
        };
        alertsModel.filteredAlerts = ko.pureComputed(function () {
            var selected = alertsModel.selectedSeverity();
            if (selected === "all") { return alertsModel.alerts(); }
            return _.filter(alertsModel.alerts(), function (alert) { return alert.severity === selected; });
        });
        alertsModel.showAll = function () { alertsModel.selectedSeverity("all"); };
        alertsModel.showUrgent = function () { alertsModel.selectedSeverity("urgent"); };
        alertsModel.showFollowUp = function () { alertsModel.selectedSeverity("follow_up"); };
        alertsModel.emptyTitle = ko.pureComputed(function () {
            if (alertsModel.selectedSeverity() === "urgent") { return "No urgent issues reported"; }
            if (alertsModel.selectedSeverity() === "follow_up") { return "No follow-up issues reported"; }
            return "No reported issues";
        });
        alertsModel.emptyDescription = ko.pureComputed(function () {
            return alertsModel.selectedSeverity() === "all"
                ? "No issues have been reported in these forms in the last 14 days."
                : "Select Reported issues to see all recent submissions needing attention.";
        });
        alertsModel.urgentCount = ko.pureComputed(function () {
            return _.filter(alertsModel.alerts(), function (alert) { return alert.severity === "urgent"; }).length;
        });
        alertsModel.followUpCount = ko.pureComputed(function () {
            return alertsModel.alerts().length - alertsModel.urgentCount();
        });
        alertsModel.refresh = function () {
            if (alertsModel.loading() && alertsModel.lastUpdated()) { return; }
            alertsModel.loading(true);
            alertsModel.error(false);
            $.getJSON(initialPageData.reverse("dashboard_operational_alerts"))
                .done(function (data) {
                    alertsModel.alerts(_.map(data.alerts, function (alert) {
                        alert.when = new Date(alert.received_on).toLocaleString();
                        return alert;
                    }));
                    alertsModel.lastUpdated("Updated " + new Date().toLocaleTimeString([], {
                        hour: "numeric", minute: "2-digit",
                    }));
                })
                .fail(function () {
                    alertsModel.error(true);
                })
                .always(function () {
                    alertsModel.loading(false);
                });
        };
        alertsPanel.koApplyBindings(alertsModel);
        alertsModel.refresh();
        window.setInterval(function () {
            if (!document.hidden) { alertsModel.refresh(); }
        }, 60000);
    }
});
