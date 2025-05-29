import pytest

from soar_sdk.meta.webhooks import WebhookMeta


def test_webhook_meta_invalid_ip():
    with pytest.raises(ValueError, match="is not a valid IPv4 or IPv6 CIDR"):
        WebhookMeta(ip_allowlist=["invalid_ip"])
    with pytest.raises(ValueError, match="is not a valid IPv4 or IPv6 CIDR"):
        WebhookMeta(ip_allowlist=["999.999.999.999/24"])
    with pytest.raises(ValueError, match="is not a valid IPv4 or IPv6 CIDR"):
        WebhookMeta(ip_allowlist=["gggg::ggg/24"])
