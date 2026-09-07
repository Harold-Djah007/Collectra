from pathlib import Path


BASE_TEMPLATE = Path(__file__).parents[1] / "templates" / "hqwebapp" / "base.html"


def test_base_template_has_one_complete_translation_fallback():
    template = BASE_TEMPLATE.read_text(encoding="utf-8")

    assert template.count("Keep local/demo pages usable") == 1
    assert "window.pluralidx = window.pluralidx ||" in template
    assert "window.interpolate = window.interpolate ||" in template


def test_translation_fallback_load_order():
    template = BASE_TEMPLATE.read_text(encoding="utf-8")

    catalog_position = template.index("{% statici18n LANGUAGE_CODE %}")
    fallback_position = template.index("window.interpolate = window.interpolate ||")
    webpack_position = template.index('{% include "hqwebapp/partials/webpack.html" %}')

    assert catalog_position < fallback_position < webpack_position
