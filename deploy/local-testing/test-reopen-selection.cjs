const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,
    '../../collectra-hq/corehq/apps/dashboard/static/dashboard/js/dashboard.js'), 'utf8');
const start = source.indexOf('request.when =');
const end = source.indexOf('return request;', start);
function observable(value) {
    const listeners = [];
    const obs = function(next) {
        if (arguments.length) { value = next; listeners.forEach(fn => fn(value)); }
        return value;
    };
    obs.subscribe = fn => listeners.push(fn);
    return obs;
}
const calls = [];
const context = {ko: {observable, observableArray: observable},
    _: {map: (items, fn) => items.map(fn)},
    initialPageData: {reverse: name => name},
    dashboardJSON: (url, data) => {
        const call = {url, data};
        for (const name of ['done', 'fail', 'always']) {
            call[name] = fn => { call[name + 'Callback'] = fn; return call; };
        }
        calls.push(call);
        return call;
    }};
vm.createContext(context);
vm.runInContext('function decorate(request) {' + source.slice(start, end) + 'return request;}', context);
const request = context.decorate({name: 'Batch A', bed: 'dry_bed_1', form_id: 'request', status: 'pending'});
request.searchName('  Batch  ');
request.findCases();
assert.equal(calls[0].data.name, 'Batch');
request.chooseCase({case_id: 'first'});
assert.equal(calls[1].data.case_id, 'first');
request.chooseCase({case_id: 'second'});
calls[1].failCallback({responseJSON: {error: 'old failure'}});
calls[1].alwaysCallback();
assert.equal(request.reviewError(), '');
assert.equal(request.checking(), true);
calls[2].doneCallback({case_id: 'second', case_name: 'Batch B'});
calls[2].alwaysCallback();
assert.equal(request.candidate().case_name, 'Batch B');
request.findCases();
assert.equal(request.candidate(), null);
console.log('Name selection, automatic verification and stale-response checks passed.');
