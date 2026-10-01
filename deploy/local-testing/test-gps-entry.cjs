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
    setTimeout: callback => callback(),
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
let map, tiles, marker;
context.L = {
    map() {
        map = {events: {}, zoom: 2, setView(point, zoom) { this.center = point; this.zoom = zoom; return this; },
            getZoom() { return this.zoom; }, on(name, handler) { this.events[name] = handler; return this; },
            invalidateSize() {}, removeLayer(layer) { this.removed = layer; }};
        return map;
    },
    control: {zoom: () => ({addTo() {}})},
    tileLayer(url, options) {
        tiles = {url, options, events: {}, on(name, handler) { this.events[name] = handler; return this; },
            addTo() { return this; }};
        return tiles;
    },
    divIcon: options => options,
    marker(point, options) {
        marker = {point, options, events: {}, setLatLng(next) { this.point = next; return this; },
            getLatLng() { return {lat: this.point[0], lng: this.point[1]}; },
            addTo() { return this; }, on(name, handler) { this.events[name] = handler; return this; }};
        return marker;
    },
};
entry.loadMap();
assert.equal(errors.length, 0);
assert.equal(entry.mapAvailable(), true);
assert.equal(tiles.url, 'https://tile.openstreetmap.org/{z}/{x}/{y}.png');
assert.ok(tiles.options.attribution.includes('OpenStreetMap'));
assert.deepEqual(values(entry), []); // Opening or panning a map never chooses a point.
assert.equal(map.events.move, undefined);
tiles.events.loading(); tiles.events.tileerror(); tiles.events.load();
assert.ok(entry.mapNotice().includes('could not load'));
tiles.events.loading(); tiles.events.load();
assert.equal(entry.mapNotice(), '');

entry.latitude('0'); entry.longitude('0'); entry.saveCoordinates();
assert.deepEqual(values(entry), [0, 0]);
assert.ok(!entry.formatLat().includes('?'));
assert.ok(!entry.formatLon().includes('?'));
map.events.click({latlng: {lat: 5.68, lng: -0.05}});
assert.deepEqual(values(entry), [5.68, -0.05]);
assert.equal(marker.options.draggable, true);
marker.point = [5.7, -0.1]; marker.events.dragend();
assert.deepEqual(values(entry), [5.7, -0.1]);
entry.latitude('0'); entry.longitude('0'); entry.saveCoordinates();

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
assert.equal(entry.centerMarker, null);
assert.ok(map.removed);

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

// A configured Mapbox installation retains its existing tiles and search.
context.initialPageData.get = () => 'configured-token';
context.L.mapbox = {geocoder: () => ({query() {}})};
({entry} = make([5.68, -0.05]));
entry.loadMap();
assert.ok(tiles.url.includes('api.mapbox.com'));
assert.equal(entry.searchAvailable(), true);
assert.deepEqual(values(entry), [5.68, -0.05]);
entry.toggleMapSize(); assert.equal(entry.mapExpanded(), true);
entry.toggleMapSize(); assert.equal(entry.mapExpanded(), false);
console.log('GPS entry: maps, pin selection, coordinates, capture, errors and stale callbacks passed.');
