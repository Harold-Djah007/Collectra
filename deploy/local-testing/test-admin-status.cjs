// Run with: node deploy/local-testing/test-admin-status.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function observable(value) {
    return function (next) { if (arguments.length) { value = next; } return value; };
}
const source = fs.readFileSync(path.join(__dirname,
    '../../collectra-hq/corehq/apps/hqadmin/static/hqadmin/js/system_info.js'), 'utf8');
function observableArray(value) {
    const result = observable(value);
    result.push = item => result().push(item);
    return result;
}
const context = {$() {}, ko: {observable, observableArray, computed: fn => fn},
    _: {each: (obj, fn) => Object.entries(obj).forEach(([key, value]) => fn(value, key)),
        has: (obj, key) => Object.hasOwn(obj, key), keys: Object.keys}};
vm.createContext(context);
vm.runInContext(source.replace(/^import .*;.*$/gm, ''), context);
assert.equal(context.pillowProgress('empty', 0, 0).width(), 100);
assert.equal(context.pillowProgress('rewind', 10, 20).width(), 100);
assert.equal(context.pillowProgress('new', 10, -1).width(), 0);
const model = context.pillowModel({name: 'worker', seq_format: 'json', seq: {}, offsets: {},
    hours_since_last: null, time_since_last: ''});
assert.equal(model.checkpointStatusCss(), 'label-default');
assert.equal(model.timeSinceLast(), 'No checkpoint recorded');
model.update({name: 'worker', seq_format: 'json', seq: {}, offsets: {},
    hours_since_last: 0, time_since_last: '0:01:00'});
assert.equal(model.checkpointStatusCss(), 'label-default');
model.update({name: 'worker', seq_format: 'json', seq: {'case,0':10}, offsets: {'case,0':10},
    hours_since_last: 500, time_since_last: '20 days'});
assert.equal(model.checkpointStatusCss(), 'label-success');
assert.equal(model.checkpointStatusText(), 'Caught up');
model.update({name: 'worker', seq_format: 'json', seq: {}, offsets: {},
    hours_since_last: 15, error: 'Missing topic'});
assert.equal(model.checkpointStatusCss(), 'label-danger');
assert.equal(model.overallStatus(), 'danger');
assert.equal(model.error(), 'Missing topic');
console.log('Admin status: progress boundaries, missing checkpoints and refreshed error states passed.');

assert.equal(context.pillowProgress('ahead', 10, 20).status(), 'progress-bar-danger');
assert.equal(context.pillowProgress('small backlog', 10, 9).status(), 'progress-bar-warning');
model.update({name: 'worker', seq_format: 'json', seq: {'case,0':20}, offsets: {'case,0':10}, hours_since_last: 0});
assert.equal(model.checkpointStatusText(), 'Checkpoint ahead of source');
assert.equal(model.overallStatus(), 'danger');
model.update({name: 'worker', seq_format: 'json', seq: {'case,0':9}, offsets: {'case,0':10}, hours_since_last: 0});
assert.equal(model.checkpointStatusText(), 'Pending changes');
model.update({name: 'worker', seq_format: 'json', seq: {'case,0':9}, offsets: {'case,0':10}, hours_since_last: 20});
assert.equal(model.checkpointStatusText(), 'Backlog needs attention');

model.update({name: 'alternative', managed: false, seq_format: 'json', seq: {'case,0':1},
    offsets: {'case,0':10000}, hours_since_last: 500});
assert.equal(model.checkpointStatusText(), 'Inactive / alternative');
assert.equal(model.checkpointStatusCss(), 'label-default');
assert.notEqual(model.checkpointStatusCss(), 'label-success');

model.update({name: 'worker', managed: true, runtime_state: 'stopped', seq_format: 'json',
    seq: {'case,0':10}, offsets: {'case,0':10}, hours_since_last: 0});
assert.equal(model.checkpointStatusText(), 'Worker not running');
assert.equal(model.checkpointStatusCss(), 'label-danger');
model.update({name: 'worker', managed: true, runtime_state: 'running', pending_errors: 2,
    seq_format: 'json', seq: {'case,0':10}, offsets: {'case,0':10}, hours_since_last: 0});
assert.equal(model.checkpointStatusText(), 'Processing errors need attention');
assert.equal(model.checkpointStatusCss(), 'label-danger');
