"""Make HTTPS work on Python builds that ship without a CA bundle.

The python.org macOS installer does not use the system keychain, so every
urllib HTTPS call fails with CERTIFICATE_VERIFY_FAILED until the user runs
"Install Certificates.command". When that happens every collector silently
falls back to mock data. This module installs a global urllib opener that
uses certifi (if installed) or the OS CA bundle instead.
"""

import os
import ssl
import urllib.request

_CANDIDATE_BUNDLES = (
    "/etc/ssl/cert.pem",                    # macOS, Alpine
    "/etc/ssl/certs/ca-certificates.crt",   # Debian/Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",     # RHEL/Fedora
)


def _build_context():
    default = ssl.create_default_context()
    if default.cert_store_stats().get("x509_ca", 0) > 0:
        return None  # Python already has working CA certs
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    for path in _CANDIDATE_BUNDLES:
        if os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    return None


def install():
    ctx = _build_context()
    if ctx is not None:
        urllib.request.install_opener(
            urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        )


install()
