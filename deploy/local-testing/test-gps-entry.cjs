const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,
    '../../collectra-hq/corehq/apps/cloudcare/static/cloudcare/js/form_entry/entries.js'), 'utf8');
const start = source.indexOf('function GeoPointEntry(');
const end = source.indexOf('GeoPointEntry.prototype =', start);
function observable(initial) {
    let value = initial;
    const listeners = [];
    function field(next) {
        if (arguments.length) { value = next; listeners.forEach(listener => listener(next)); }
        return value;
    }
    field.subscribe = listener => listeners.push(listener);
    return field;
}
let success, failure, options;
const context = {ko: {observable}, constants: {CONTROL_WIDTH: ''},
    initialPageData: {get: () => ''}, gettext: text => text,
    intpad: value => value, navigator: {geolocation: {getCurrentPosition(ok, error, opts) {
        success = ok; failure = error; options = opts;
    }}}, EntryArrayAnswer: function (question) { this.rawAnswer = question.answer; }};
vm.createContext(context);
vm.runInContext(source.slice(start, end) + '\nglobalThis.Entry = GeoPointEntry;', context);
const make = (value = []) => {
    const errors = [];
    const entry = new context.Entry({answer: observable(value), error: message => errors.push(message)}, {});
    return {entry, errors};
};
const values = entry => Array.from(entry.rawAnswer());

let {entry, errors} = make();
entry.afterRender();
assert.equal(errors.length, 0);
assert.equal(entry.mapAvailable(), false);
assert.ok(entry.mapNotice().includes('Map unavailable'));
// Missing token also leaves the GPS answer usable when Leaflet is loaded.
context.L = {};
entry.loadMap();
assert.equal(errors.length, 0);
assert.ok(entry.mapNotice().includes('Map not configured'));

entry.latitude('0'); entry.longitude('0'); entry.saveCoordinates();
assert.deepEqual(values(entry), [0, 0]);
assert.ok(!entry.formatLat().includes('?'));
assert.ok(!entry.formatLon().includes('?'));

for (const [lat, lon] of [['', '0'], ['91', '0'], ['0', '-181'], ['bad', '0']]) {
    entry.latitude(lat); entry.longitude(lon);
    assert.equal(entry.saveCoordinates(), false);
    assert.deepEqual(values(entry), [0, 0]);
    assert.ok(entry.locationError());
}

entry.captureLocation();
assert.equal(entry.locating(), true);
assert.equal(options.enableHighAccuracy, true);
assert.equal(options.timeout, 15000);
success({coords: {latitude: 5.6, longitude: -0.1, altitude: 32, accuracy: 7}});
assert.deepEqual(values(entry), [5.6, -0.1, 32, 7]);
assert.equal(entry.locating(), false);
entry.captureLocation(); failure({code: 1});
assert.ok(entry.locationError().includes('permission'));
assert.deepEqual(values(entry), [5.6, -0.1, 32, 7]);

entry.captureLocation(); const late = success;
entry.onClear(); late({coords: {latitude: 6, longitude: 1, altitude: 0, accuracy: 3}});
assert.deepEqual(values(entry), []);
assert.equal(entry.locating(), false);

({entry} = make([0, 0]));
entry.saveCoordinates();
assert.deepEqual(values(entry), [0, 0]);

entry.rawAnswer([5, 1, 32, 7]);
let center = {lat: 5, lng: 1};
entry.map = {getCenter: () => center}; entry.centerMarker = {setLatLng() {}};
entry.updateCenter(); assert.deepEqual(values(entry), [5, 1, 32, 7]);
center = {lat: 6, lng: 2};
entry.updateCenter(); assert.deepEqual(values(entry), [6, 2]);
assert.equal(entry.latitude(), 6);
assert.equal(entry.longitude(), 2);
console.log('GPS entry: fallback, coordinates, capture, errors, stale callbacks and map movement passed.');
