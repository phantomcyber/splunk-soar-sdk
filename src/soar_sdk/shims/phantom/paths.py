import os
from pathlib import Path

try:
    from phantom_common.paths import NGINX_CERT
except ImportError:
    NGINX_CERT = str(
        Path(os.getenv("PHANTOM_HOME", "/opt/phantom")) / "etc/ssl/certs/httpd_cert.crt"
    )

__all__ = ["NGINX_CERT"]
