import pytest
from pydantic import BaseModel, ValidationError

from soar_sdk.asset import AssetField, BaseAsset
from soar_sdk.networking import Host, format_url_host


class HostModel(BaseModel):
    host: Host


class HostAsset(BaseAsset):
    host: Host = AssetField()


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        (" Splunk.Example.COM. ", "splunk.example.com"),
        ("splunk.example.com/", "splunk.example.com"),
        ("splunk.example.com///", "splunk.example.com"),
        ("192.0.2.10", "192.0.2.10"),
        ("[2001:0DB8:0:0::1]", "2001:db8::1"),
        ("2001:0DB8:0:0::1", "2001:db8::1"),
        ("splunk", "splunk"),
        (
            "m\N{LATIN SMALL LETTER U WITH DIAERESIS}nich.example",
            "m\N{LATIN SMALL LETTER U WITH DIAERESIS}nich.example",
        ),
        ("Bad_Host.Example.", "bad_host.example"),
    ],
)
def test_host_normalizes_valid_values(host, expected):
    value = HostModel(host=host).host

    assert value == expected
    assert type(value) is str


@pytest.mark.parametrize(
    "host",
    [
        "",
        "///",
        "https://splunk.example.com",
        "HTTP://splunk.example.com",
        "ftp://splunk.example.com",
        "splunk.example.com:8089",
        "splunk.example.com/services",
        "/splunk.example.com",
        "splunk example.com",
        "!@#$%",
        "[not-an-ip]",
        "[not-an-ip",
        "a" * 254,
    ],
)
def test_host_rejects_non_host_values(host):
    with pytest.raises(
        ValidationError, match="Value must be a valid IP address or hostname"
    ):
        HostModel(host=host)


@pytest.mark.parametrize("host", [None, 123])
def test_host_rejects_non_string_values(host):
    with pytest.raises(ValidationError, match="Input should be a valid string"):
        HostModel(host=host)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("2001:db8::1", "[2001:db8::1]"),
        ("192.0.2.10", "192.0.2.10"),
        ("splunk.example.com", "splunk.example.com"),
    ],
)
def test_format_url_host(host, expected):
    assert format_url_host(host) == expected


def test_host_is_serialized_as_a_string_asset_field():
    schema = HostAsset.to_json_schema()

    assert schema["host"]["data_type"] == "string"
    assert HostAsset.model_json_schema()["properties"]["host"]["type"] == "string"
