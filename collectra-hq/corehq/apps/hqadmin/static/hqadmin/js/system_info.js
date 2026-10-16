import "commcarehq";
import $ from "jquery";
import ko from "knockout";
import _ from "underscore";
import initialPageData from "hqwebapp/js/initial_page_data";
import alertUser from "hqwebapp/js/bootstrap3/alert_user";

function formatDate(datestring) {
    //parse and format the date timestamps - seconds since epoch into date object
    var date = new Date(datestring * 1000);
    // hours part from the timestamp
    var hours = date.getHours();
    // minutes part from the timestamp
    var minutes = date.getMinutes();
    // seconds part from the timestamp
    var seconds = date.getSeconds(),
        secondStr;
    if (seconds < 10) {
        secondStr = "0" + seconds;
    } else {
        secondStr = seconds;
    }

    var year = date.getFullYear();
    var month = date.getMonth() + 1;
    var day = date.getDate();

    return  year + '/' + month + '/' + day + ' ' + hours + ':' + minutes + ':' +  secondStr;

}

function numberFix(num) {
    if (num !== null) {
        if (num.toFixed) {
            return num.toFixed(2);
        }
        if (num.toPrecision) {
            return num.toPrecision(2);
        }
        return num;
    }
}

function refreshableViewModel(url, model, interval, sortBy) {
    var self = {};
    self.error = ko.observable();
    self.models = ko.observableArray();
    self.autoRefresh = ko.observable(false);
    self.loading = ko.observable(false);
    self.timer = null;
    self.interval = interval;

    self.autoRefresh.subscribe(function (newVal) {
        if (newVal) {
            self.refresh();
        } else {
            self.clearTimer();
        }
    });

    self.clearTimer = function () {
        if (self.timer) {
            clearTimeout(self.timer);
            self.timer = null;
        }
    };

    self.refresh = function () {
        self.clearTimer();
        self.loading(true);
        $.getJSON(url, function (data) {
            self.error(null);
            var objects = _(data).map(function (item) {
                return new model(item);
            });
            if (sortBy) {
                objects = _(objects).sortBy(function (x) { return x[sortBy]; });
            }
            self.models(objects);
            if (self.autoRefresh()) {
                self.timer = setTimeout(self.refresh, self.interval);
            }
        })
            .fail(function (jqxhr) {
                var err = 'Unknown server error';
                /* eslint-disable no-empty */
                try {
                    err = JSON.parse(jqxhr.responseText).error;
                } catch (e) {
                    // this is fine
                }
                /* eslint-enable no-empty */
                self.error("Error: " + err);
                self.autoRefresh(false);
                self.timer = null;
            })
            .always(function () {
                self.loading(false);
            });
    };

    return self;
}

function activeTaskModel(data) {
    var self = {};
    self.pid = ko.observable(data.pid);
    self.type = ko.observable(data.type);
    self.database = ko.observable(data.database);
    self.progress = ko.observable(data.progress + "%");
    self.designDocument = ko.observable(data.design_document);
    self.startedOn = ko.observable(formatDate(data.started_on));
    self.updatedOn = ko.observable(formatDate(data.updated_on));
    self.totalChanges = ko.observable(data.total_changes);
    self.changesDone = ko.observable(data.changes_done);
    self.progressContribution = ko.observable(data.progress_contribution);
    return self;
}

function designDocModel(data) {
    var self = {};
    self.designDocument = ko.observable(data.design_document);
    self.detailsId = self.designDocument() + '_details';
    var tasks = _(data.tasks).map(function (task) {
        return activeTaskModel(task);
    });
    self.tasks = ko.observableArray(tasks);

    self.showDetails = function () {
        $('#' + self.detailsId).toggle();
    };
    return self;
}

function celeryTaskModel(data) {
    var self = {};
    this.name = ko.observable(data.name);
    this.uuid = ko.observable(data.uuid);
    this.state = ko.observable(data.state);
    this.received = ko.observable(formatDate(data.received));
    this.started = ko.observable(formatDate(data.started));
    this.timestamp = ko.observable(formatDate(data.timestamp));
    this.succeeded = ko.observable(formatDate(data.succeeded));
    this.retries = ko.observable(data.retries);
    this.args = ko.observable(data.args);
    this.kwargs = ko.observable(data.kwargs);
    this.runtime = ko.observable(numberFix(data.runtime));

    this.toggleArgs = function () {
        $('#' + self.uuid()).toggle();
    };
    return self;
}

function pillowOperationViewModel(pillowModel, operation) {
    var self = {};
    self.pillowModel = pillowModel;
    self.operation = operation;
    self.title = operation + ' for ' + pillowModel.name();

    self.go = function () {
        self.pillowModel.performOperation(operation);
    };
    return self;
}

function pillowProgress(name, dbOffset, seq) {
    var self = {};
    self.name = name;
    self.dbOffset = dbOffset;
    self.seq = seq;

    self.changesBehind = function () {
        return self.dbOffset - self.seq;
    };

    self.width = function () {
        return self.dbOffset > 0 ? Math.min(100, Math.max(0, (self.seq * 100) / self.dbOffset)) : 100;
    };

    self.status = function () {
        var lag = self.changesBehind();
        if (lag < 0 || self.seq < 0) { return 'progress-bar-danger'; }
        if (lag === 0) { return 'progress-bar-success'; }
        return lag >= 5000 ? 'progress-bar-danger' : 'progress-bar-warning';
    };
    return self;
}

function pillowModel(pillow) {
    var self = {};
    self.name = ko.observable();
    self.seq_format = ko.observable();
    self.seq = ko.observable();
    self.offsets = ko.observable();
    self.timeSinceLast = ko.observable();
    self.hoursSinceLast = ko.observable();
    self.error = ko.observable();
    self.operationInProgress = ko.observable(false);
    self.progress = ko.observableArray();
    self.managed = ko.observable(true);
    self.selectionNote = ko.observable('');
    self.runtimeState = ko.observable('unknown');
    self.pendingErrors = ko.observable(0);

    self.update = function (data) {
        self.name(data.name);
        self.seq_format(data.seq_format);
        self.seq(data.seq);
        self.offsets(data.offsets);
        self.timeSinceLast(data.time_since_last || 'No checkpoint recorded');
        self.hoursSinceLast(data.hours_since_last);
        self.error(data.error || '');
        self.managed(data.managed !== false);
        self.selectionNote(data.selection_note || '');
        self.runtimeState(data.runtime_state || 'unknown');
        self.pendingErrors(data.pending_errors || 0);

        self.progress([]);
        if (self.seq_format() === 'json') {
            _.each(self.offsets(), function (dbOffset, key) {
                var value;
                if (self.seq() === null || !_.has(self.seq(), key)) {
                    value = 0;
                } else {
                    value = self.seq()[key];
                }
                self.progress.push(pillowProgress(key, dbOffset, value));
            });
        } else {
            var key = _.keys(self.offsets())[0];
            self.progress.push(pillowProgress(key, self.offsets()[key], self.seq()));
        }
    };

    self.update(pillow);

    self.checkpointState = ko.computed(function () {
        if (!self.managed()) { return 'inactive'; }
        if (self.error()) { return 'unavailable'; }
        if (self.pendingErrors() > 0) { return 'failed'; }
        if (self.runtimeState() === 'stopped') { return 'stopped'; }
        var progress = self.progress();
        if (!progress.length) { return 'unknown'; }
        if (progress.some(function (p) { return p.changesBehind() < 0 || p.seq < 0; })) {
            return 'ahead';
        }
        var pending = progress.some(function (p) { return p.changesBehind() > 0; });
        if (!pending) { return self.seq() === null ? 'unknown' : 'caught_up'; }
        if (progress.some(function (p) { return p.changesBehind() >= 5000; }) || self.hoursSinceLast() > 12) {
            return 'stale';
        }
        return 'pending';
    });
    self.checkpointStatusCss = ko.computed(function () {
        switch (self.checkpointState()) {
            case 'caught_up': return 'label-success';
            case 'pending': return 'label-warning';
            case 'ahead':
            case 'stale':
            case 'unavailable': return 'label-danger';
            case 'stopped': return 'label-danger';
            case 'failed': return 'label-danger';
            default: return 'label-default';
        }
    });
    self.checkpointStatusText = ko.computed(function () {
        return {
            caught_up: 'Caught up', pending: 'Pending changes', ahead: 'Checkpoint ahead of source',
            stale: 'Backlog needs attention', unavailable: 'Status unavailable', unknown: 'Not measured',
            inactive: 'Inactive / alternative',
            stopped: 'Worker not running',
            failed: 'Processing errors need attention',
        }[self.checkpointState()];
    });
    self.overallStatus = ko.computed(function () {
        switch (self.checkpointStatusCss()) {
            case 'label-danger': return 'danger';
            case 'label-warning': return 'warning';
            case 'label-success': return 'success';
            default: return '';
        }
    });

    self.showPillowDialog = function (operation) {
        var element = $('#pillow_operation_modal').get(0);
        ko.cleanNode(element);
        $(element).koApplyBindings(pillowOperationViewModel(self, operation));
        $('#pillow_operation_modal').modal({
            backdrop: 'static',
            keyboard: false,
            show: true,
        });
    };

    self.refresh = function () {
        self.performOperation('refresh');
    };

    self.performOperation = function (operation) {
        self.operationInProgress(true);
        $.post(initialPageData.reverse("pillow_operation_api"), {
            'pillow_name': self.name,
            'operation': operation,
        }, function (data) {
            self.operationInProgress(false);
            self.update(data);

            if (!data.success) {
                alertUser.alert_user("Operation failed: " + data.operation + " on "
                        + data.pillow_name + ', ' + data.message, 'danger');
            }
        }, "json")
            .fail(function (jqxhr) {
                try {
                    JSON.parse(jqxhr.responseText).error;
                } catch (e) {
                    // do nothing
                }
                self.operationInProgress(false);
            }).always(function () {
                $('#pillow_operation_modal').modal('hide');
                $("#" + self.name() + " td").fadeTo("fast" , 0.5).fadeTo("fast" , 1);
            });
    };

    return self;
}

$(function () {
    var celeryUpdate = initialPageData.get("celery_update"),
        couchUpdate = initialPageData.get("couch_update"),
        systemAjaxUrl = initialPageData.reverse("system_ajax");
    var celeryViewModel = refreshableViewModel(systemAjaxUrl + "?api=flower_poll", celeryTaskModel, celeryUpdate);
    var couchViewModel;
    if (initialPageData.get("is_bigcouch")) {
        couchViewModel = refreshableViewModel(systemAjaxUrl + "?api=_active_tasks", designDocModel, couchUpdate, 'designDocument');
    } else {
        couchViewModel = refreshableViewModel(systemAjaxUrl + "?api=_active_tasks", activeTaskModel, couchUpdate);
    }
    var pillowtopViewModel = refreshableViewModel(systemAjaxUrl + "?api=pillowtop", pillowModel, couchUpdate, 'name');
    pillowtopViewModel.showInactive = ko.observable(false);
    pillowtopViewModel.inactiveCount = ko.computed(function () {
        return pillowtopViewModel.models().filter(function (model) { return !model.managed(); }).length;
    });
    pillowtopViewModel.visibleModels = ko.computed(function () {
        return pillowtopViewModel.models().filter(function (model) {
            return pillowtopViewModel.showInactive() || model.managed();
        });
    });

    var autoRefreshModel = function () {
        var self = {};
        self.refreshStatus = ko.observable(false);
        self.refreshStatusText = ko.observable('off');
        self.models = [];

        self.addModel = function (model) {
            self.models.push(model);
        };

        self.toggleRefresh = function () {
            self.refreshStatus(!self.refreshStatus());
            self.refreshStatusText(self.refreshStatus() ? 'on' : 'off');
            $.each(self.models, function (index, model) {
                model.autoRefresh(self.refreshStatus());
            });
        };

        self.refreshAll = function () {
            $.each(self.models, function (index, model) {
                model.refresh();
            });
        };

        return self;
    };

    var autoRefresh = autoRefreshModel();
    $("#celeryblock").koApplyBindings(celeryViewModel);
    $("#couchblock").koApplyBindings(couchViewModel);
    $('#pillowtop-status').koApplyBindings(pillowtopViewModel);
    autoRefresh.addModel(celeryViewModel);
    autoRefresh.addModel(couchViewModel);
    autoRefresh.addModel(pillowtopViewModel);

    autoRefresh.refreshAll();
    $('#autorefresh').koApplyBindings(autoRefresh);
});
