import pytest

from corehq.apps.app_manager.local_mobile_urls import retarget_local_mobile_xml


def test_profile_and_suite_links_follow_current_testing_origin_only_for_same_project():
    source = (b'<profile update="http://localhost:8000/a/safisana/profile.ccpr">'
              b'<location>http://127.0.0.1:8012/a/safisana/suite.xml</location>'
              b'<location>https://old-tunnel.trycloudflare.com/a/safisana/media.xml</location>'
              b'<location>http://localhost:8000/a/another/suite.xml</location>'
              b'<location>https://external.example/a/safisana/image.jpg</location></profile>')
    result = retarget_local_mobile_xml(source, 'safisana', 'https://new.example')
    assert result.count(b'https://new.example/a/safisana/') == 3
    assert b'http://localhost:8000/a/another/suite.xml' in result
    assert b'https://external.example/a/safisana/image.jpg' in result
    assert retarget_local_mobile_xml(result, 'safisana', 'https://new.example') == result


def test_local_hq_media_downloads_follow_current_origin():
    source = b'<location>http://localhost:8000/hq/multimedia/file/CommCareImage/id/image.png</location>'
    assert retarget_local_mobile_xml(source, 'safisana', 'https://new.example') == (
        b'<location>https://new.example/hq/multimedia/file/CommCareImage/id/image.png</location>')


def test_disabled_testing_mode_preserves_original_build_bytes():
    source = b'http://localhost:8000/a/safisana/suite.xml'
    assert retarget_local_mobile_xml(source, 'safisana', None) is source


@pytest.mark.parametrize('origin', ['http://new.example', 'https://new.example/path',
                                  'https://user:secret@new.example', 'https://new.example?q=1'])
def test_rejects_invalid_configured_origin(origin):
    with pytest.raises(ValueError):
        retarget_local_mobile_xml(b'<profile/>', 'safisana', origin)
