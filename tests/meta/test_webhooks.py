import pytest

from soar_sdk.meta.webhooks import WebhookMeta


@pytest.mark.parametrize("ip", ("invalid_ip", "999.999.999.999/24", "gggg::ggg/24"))
def test_webhook_meta_invalid_ip(ip):
    with pytest.raises(ValueError, match="is not a valid IPv4 or IPv6 CIDR"):
        WebhookMeta(ip_allowlist=[ip])
