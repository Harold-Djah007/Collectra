// Run with: node deploy/local-testing/test-dashboard-loading.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname,
    '../../collectra-hq/corehq/apps/dashboard/static/dashboard/js/dashboard.js'), 'utf8');
function observable(value) {
    const state = function (next) { if (arguments.length) { value = next; } return value; };
    state.subscribe = () => {};
    return state;
}
const requests = [];
const $ = function () {}; // Skip DOM initialization; test the actual tile model.
$.ajax = options => { requests.push(options); return options; };
const context = {$, ko: {observable, observableArray: observable, computed: fn => fn},
    initialPageData: {reverse: (name, slug) => name + '/' + slug}};
vm.createContext(context);
vm.runInContext(source.replace(/^import .*;.*$/gm, ''), context);
function tile() {
    requests.length = 0;
    return context.tileModel({title: 'Applications', slug: 'applications', has_item_list: true});
}
function finish(request, data) { request.success(data); request.complete(); }

// An empty page with a nonzero total must finish loading.
let model = tile();
finish(requests[1], {total: 6});
finish(requests[0], {items: []});
assert.equal(model.showSpinner(), false);
assert.equal(model.showItemList(), true);

// A delayed older page cannot overwrite the page selected more recently.
model = tile();
const oldPage = requests[0];
finish(requests[1], {total: 20});
model.goToPage(2);
const newerPage = requests[2];
finish(newerPage, {items: [{name: 'Newer'}]});
finish(oldPage, {items: [{name: 'Older'}]});
assert.equal(model.items()[0].name, 'Newer');
assert.equal(model.showSpinner(), false);

// Timeouts end loading and provide a usable fallback link; retry can recover.
model = tile();
requests[0].error(); requests[0].complete();
requests[1].error(); requests[1].complete();
assert.equal(model.showSpinner(), false);
assert.equal(model.showIconLink(), true);
model.goToPage(1);
finish(requests[2], {items: [{name: 'Recovered'}]});
finish(requests[3], {total: 1});
assert.equal(model.hasError(), false);
assert.equal(model.items()[0].name, 'Recovered');

// One count request runs at a time; all requests have a finite timeout.
model = tile();
model.goToPage(2);
assert.equal(requests.filter(item => item.url.startsWith('dashboard_tile_total/')).length, 1);
assert.ok(requests.every(item => item.timeout === 15000));
context.dashboardJSON('/alerts', {view: 'pending'});
assert.equal(requests.at(-1).timeout, 15000);
assert.equal(requests.at(-1).dataType, 'json');

// Link-only cards have no AJAX loading state or requests.
requests.length = 0;
model = context.tileModel({title: 'Users', slug: 'users', has_item_list: false});
assert.equal(model.showSpinner(), false);
assert.equal(requests.length, 0);
// Initial alert refresh cannot overlap, and a failed request can be retried.
let initialize;
let alerts;
const pending = [];
const dom = function (target) {
    if (typeof target === 'function') { initialize = target; return; }
    return {length: target === '#operational-alerts' ? 1 : 0,
        koApplyBindings: model => { if (target === '#operational-alerts') { alerts = model; } }};
};
dom.ajax = options => {
    const callbacks = {};
    const request = {options, callbacks};
    for (const name of ['done', 'fail', 'always']) {
        request[name] = callback => { callbacks[name] = callback; return request; };
    }
    pending.push(request);
    return request;
};
let unexpectedTimerCount = 0;
const page = {$: dom, ko: {observable, observableArray: observable, pureComputed: fn => fn},
    _: {map: (items, fn) => items.map(fn), filter: (items, fn) => items.filter(fn)},
    initialPageData: {get: () => [], reverse: name => name},
    document: {hidden: false}, window: {setInterval: () => { unexpectedTimerCount++; }}};
vm.createContext(page);
vm.runInContext(source.replace(/^import .*;.*$/gm, ''), page);
initialize();
alerts.refresh();
assert.equal(pending.length, 1);
pending[0].callbacks.fail(); pending[0].callbacks.always();
assert.equal(alerts.loading(), false);
assert.equal(alerts.error(), true);
alerts.refresh();
assert.equal(pending.length, 2);
pending[1].callbacks.done({alerts: []}); pending[1].callbacks.always();
assert.equal(alerts.error(), false);
assert.equal(alerts.loading(), false);
assert.equal(alerts.loaded(), true);
assert.equal(unexpectedTimerCount, 0, 'Operational overview must not poll automatically');

// A failed manual refresh keeps the latest successfully fetched overview.
alerts.refresh();
assert.equal(pending.length, 3);
pending[2].callbacks.fail();
pending[2].callbacks.always();
assert.equal(alerts.error(), true);
assert.equal(alerts.loaded(), true);
assert.equal(alerts.alerts().length, 0);
alerts.refresh();
pending[3].callbacks.done({alerts: [{severity: 'urgent', received_on: '2026-10-19T11:00:00Z'}]});
pending[3].callbacks.always();
assert.equal(alerts.alerts().length, 1);
alerts.refresh();
pending[4].callbacks.fail();
pending[4].callbacks.always();
assert.equal(alerts.alerts().length, 1, 'Keep the previous results after a refresh error');

// Reopening requests should not refetch on tab reselect or lose an open review draft.
let initReopen;
let reopenModel;
const reopenPending = [];
const reopenDOM = function (target) {
    if (typeof target === 'function') { initReopen = target; return; }
    return {length: target === '#reopen-requests' ? 1 : 0,
        koApplyBindings: model => { if (target === '#reopen-requests') { reopenModel = model; } }};
};
reopenDOM.ajax = options => {
    const callbacks = {};
    const request = {options, callbacks};
    for (const name of ['done', 'fail', 'always']) {
        request[name] = callback => { callbacks[name] = callback; return request; };
    }
    reopenPending.push(request);
    return request;
};
const reopenPage = {$: reopenDOM, ko: {observable, observableArray: observable,
    pureComputed: fn => fn, computed: fn => fn},
_: {map: (items, fn) => items.map(fn), filter: (items, fn) => items.filter(fn)},
initialPageData: {get: () => [], reverse: name => name}};
vm.createContext(reopenPage);
vm.runInContext(source.replace(/^import .*;.*$/gm, ''), reopenPage);
initReopen();
assert.equal(reopenPending.length, 1);
const reopened = {form_id: 'form-A', bed: 'dry_bed_1', status: 'pending', received_on: '2026-10-19'};
reopenPending[0].callbacks.done({requests: [reopened]});
reopenPending[0].callbacks.always();
const draft = reopenModel.pendingRequests()[0];
draft.reviewOpen(true);
draft.caseId('case123');
reopenModel.refresh();
reopenPending[1].callbacks.done({requests: [{...reopened, reason: 'Updated note'}]});
reopenPending[1].callbacks.always();
assert.equal(reopenModel.pendingRequests()[0].caseId(), 'case123');
assert.equal(reopenModel.pendingRequests()[0].reviewOpen(), true);
assert.equal(reopenModel.pendingRequests()[0].reason, 'Updated note');
reopenModel.showPending();
assert.equal(reopenPending.length, 2, 'Clicking current tab must not refetch');
reopenModel.showHistory();
assert.equal(reopenPending.length, 3);
reopenPending[2].callbacks.done({requests: []});
reopenPending[2].callbacks.always();
reopenModel.showPending();
assert.equal(reopenPending.length, 3, 'Returning to loaded pending tab must not refetch');
console.log('Dashboard loading and refresh stability: 10 scenarios passed.');
