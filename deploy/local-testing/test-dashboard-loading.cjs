// Run with: node deploy/local-testing/test-dashboard-loading.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname,
    '../../collectra-hq/corehq/apps/dashboard/static/dashboard/js/dashboard.js'), 'utf8');
function observable(value) {
    return function (next) { if (arguments.length) { value = next; } return value; };
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
const page = {$: dom, ko: {observable, observableArray: observable, pureComputed: fn => fn},
    _: {map: (items, fn) => items.map(fn), filter: (items, fn) => items.filter(fn)},
    initialPageData: {get: () => [], reverse: name => name},
    document: {hidden: false}, window: {setInterval: () => {}}};
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
console.log('Dashboard loading: 6 scenarios passed.');
