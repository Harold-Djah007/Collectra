"""Retarget local testing download references without changing saved form data."""

import re
from urllib.parse import urlsplit


def retarget_local_mobile_xml(payload, domain, origin):
    if not origin:
        return payload
    parsed = urlsplit(origin)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('Local mobile origin must be an HTTPS origin')
    if parsed.username or parsed.password:
        raise ValueError('Local mobile origin cannot contain credentials')
    pattern = (rb'https?://(?:localhost|127\.0\.0\.1|[A-Za-z0-9-]+\.trycloudflare\.com)'
               rb'(?::[0-9]+)?(?=(?:/a/' + re.escape(domain.encode('utf-8'))
               + rb'/|/hq/multimedia/file/))')
    return re.sub(pattern, origin.encode('utf-8'), payload)
