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
const context = {$() {}, ko: {observable, observableArray: observable, computed: fn => fn},
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
assert.equal(model.checkpointStatusCss(), 'label-success');
assert.equal(model.timeSinceLast(), '0:01:00');
model.update({name: 'worker', seq_format: 'json', seq: {}, offsets: {},
    hours_since_last: 15, error: 'Missing topic'});
assert.equal(model.checkpointStatusCss(), 'label-danger');
assert.equal(model.overallStatus(), 'error');
assert.equal(model.error(), 'Missing topic');
console.log('Admin status: progress boundaries, missing checkpoints and refreshed error states passed.');
