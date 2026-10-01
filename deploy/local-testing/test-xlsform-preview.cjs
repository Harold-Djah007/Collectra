const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname,
    '../../collectra-hq/corehq/apps/app_manager/static/app_manager/js/xlsform_preview.js'), 'utf8');
function node(name) {
    return {name, textContent: '', children: [], appendChild(child) { this.children.push(child); },
        addEventListener() {}};
}
const document = {createElement: node, implementation: {createDocument() {
    return {documentElement: node('data'), createElement: node};
}}};
const context = {$: () => {}, document, gettext: text => text, console};
vm.createContext(context);
vm.runInContext(source.replace(/^import .*;.*$/gm, '') + '\nglobalThis.Preview = XlsFormPreview;', context);
const row = (name, kind='question', raw_type='integer', path=[]) => ({
    name, kind, raw_type, path, default: '', relevant: '', required: '', constraint: '', calculation: '',
});
const rows = [row('visits', 'begin_repeat', 'begin repeat'), row('reading', 'question', 'integer', ['visits']),
    row('outside'), row('started', 'calculate', 'start'), row('day', 'calculate', 'today')];
const preview = () => new context.Preview(null, {rows, choices: [], default_language: 'en', languages: ['en']});

// Zero and false remain values in the XPath simulation document.
let model = preview();
model.answers.outside = 0;
assert.equal(model.buildDocument({}, null).nodes.outside.textContent, '0');
model.answers.outside = false;
assert.equal(model.buildDocument({}, null).nodes.outside.textContent, 'false');

// Removing the middle entry preserves the first and shifts the third entry.
model = preview();
model.repeatCounts.visits = 3;
model.answers = {'reading::visits:0': 10, 'reading::visits:1': 20, 'reading::visits:2': 30, outside: 0};
model.removeRepeatEntry(rows[0], {}, 1);
assert.equal(model.answers['reading::visits:0'], 10);
assert.equal(model.answers['reading::visits:1'], 30);
assert.equal(model.answers['reading::visits:2'], undefined);
assert.equal(model.answers.outside, 0);
assert.equal(model.repeatCounts.visits, 2);

// Start metadata stays fixed, and the date formatter uses the local calendar.
model = preview();
model.startedAt = '2026-10-01T11:00:00Z';
model.startedDate = '2026-10-01';
assert.equal(model.implicitCalculation(rows[3]), model.startedAt);
assert.equal(model.implicitCalculation(rows[4]), model.startedDate);
assert.equal(context.localDate({getFullYear: () => 2026, getMonth: () => 9, getDate: () => 1}), '2026-10-01');

// Unsupported expressions must not produce a false successful validation.
model = preview();
model.evaluate = () => ({value: true, error: 'Unsupported function'});
rows[2].required = 'custom()'; rows[2].constraint = 'custom()';
model.answers.outside = 1;
model.required(rows[2], {}); model.validateQuestion(rows[2], {});
assert.ok(model.expressionWarnings.size);
model.validationRequested = true;
const parent = node('parent');
model.addValidationControls(parent);
const messages = parent.children[0].children.map(child => child.textContent).join(' ');
assert.ok(messages.includes('Preview checks are incomplete'));
assert.ok(!messages.includes('Preview validation passed'));
// Repeated references resolve to the selected entry; totals outside use all entries.
model = preview();
const first = {nodeName: 'reading'}, second = {nodeName: 'reading'};
const state = {nodes: {'reading::visits:0': first, 'reading::visits:1': second},
    document: {documentElement: {children: [first, second]}}};
assert.equal(model.prepareExpression('${reading}', {visits: 1}, state), '/data/reading[2]');
assert.equal(model.prepareExpression('sum(${reading})', {}, state), 'sum(/data/reading)');

// Calculations are evaluated separately for every repeat entry.
const calculation = row('double', 'calculate', 'calculate', ['visits']);
calculation.calculation = '${reading} * 2';
model = new context.Preview(null, {rows: [...rows, calculation], choices: [], default_language: 'en'});
model.repeatCounts.visits = 2;
model.answers = {'reading::visits:0': 10, 'reading::visits:1': 20};
model.evaluate = (expression, field, position) => ({value: model.getAnswer(rows[1], position) * 2, error: ''});
model.recalculate();
assert.equal(model.answers['double::visits:0'], 20);
assert.equal(model.answers['double::visits:1'], 40);
// Nested repeat counts are independent for each parent entry.
const nestedRows = [row('parents', 'begin_repeat', 'begin repeat'),
    row('children', 'begin_repeat', 'begin repeat', ['parents']),
    row('child_reading', 'question', 'integer', ['parents', 'children'])];
model = new context.Preview(null, {rows: nestedRows, choices: [], default_language: 'en'});
model.repeatCounts = {parents: 2, 'children::parents:0': 2, 'children::parents:1': 1};
assert.equal(model.contextsFor(nestedRows[2]).length, 3);
model.answers = {'child_reading::parents:0|children:0': 10,
    'child_reading::parents:0|children:1': 20, 'child_reading::parents:1|children:0': 30};
model.removeRepeatEntry(nestedRows[1], {parents: 0}, 0);
assert.equal(model.answers['child_reading::parents:0|children:0'], 20);
assert.equal(model.answers['child_reading::parents:1|children:0'], 30);
assert.equal(model.repeatCounts['children::parents:1'], 1);
model.repeatCounts['children::parents:1'] = 3;
model.removeRepeatEntry(nestedRows[0], {}, 0);
assert.equal(model.repeatCounts['children::parents:0'], 3);
assert.equal(model.repeatCounts['children::parents:1'], undefined);
assert.equal(model.answers['child_reading::parents:0|children:0'], 30);
console.log('XLSForm preview: 7 scenarios passed.');
