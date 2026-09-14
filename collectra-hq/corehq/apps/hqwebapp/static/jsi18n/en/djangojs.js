/*
 * Collectra local fallback. `compilejsi18n` replaces this file with Django's
 * generated catalog in built images, but a source checkout still needs the
 * complete public API while webpack pages are being used locally.
 */
(function (globals) {
    "use strict";

    const django = globals.django = globals.django || {};

    django.pluralidx = django.pluralidx || function (count) {
        return count === 1 ? 0 : 1;
    };
    django.gettext = django.gettext || function (message) {
        return message;
    };
    django.ngettext = django.ngettext || function (singular, plural, count) {
        return django.pluralidx(count) === 0 ? singular : plural;
    };
    django.pgettext = django.pgettext || function (context, message) {
        return message;
    };
    django.gettext_noop = django.gettext_noop || function (message) {
        return message;
    };
    django.interpolate = django.interpolate || function (format, values, named) {
        if (named) {
            return format.replace(/%\(\w+\)s/g, function (match) {
                return String(values[match.slice(2, -2)]);
            });
        }

        let index = 0;
        return format.replace(/%s/g, function () {
            return String(values[index++]);
        });
    };

    globals.pluralidx = globals.pluralidx || django.pluralidx;
    globals.gettext = globals.gettext || django.gettext;
    globals.ngettext = globals.ngettext || django.ngettext;
    globals.pgettext = globals.pgettext || django.pgettext;
    globals.gettext_noop = globals.gettext_noop || django.gettext_noop;
    globals.interpolate = globals.interpolate || django.interpolate;
})(window);
