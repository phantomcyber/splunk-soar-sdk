from ipaddress import ip_network

from pydantic import BaseModel, Field, field_validator


class WebhookRouteMeta(BaseModel):
    """Metadata for a webhook route, including the handler function and its properties."""

    url_pattern: str
    allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "POST"])
    declaration_path: str | None = None
    declaration_lineno: int | None = None


class WebhookMeta(BaseModel):
    """Metadata for a complex webhook definition which may contain multiple routes."""

    handler: str | None
    requires_auth: bool = True
    allowed_headers: list[str] = Field(default_factory=list)
    ip_allowlist: list[str] = Field(default_factory=lambda: ["0.0.0.0/0", "::/0"])
    routes: list[WebhookRouteMeta] = Field(default_factory=list)

    @field_validator("ip_allowlist")
    @classmethod
    def validate_ip_allowlist(cls, value: list[str]) -> list[str]:
        """Enforces all values of the 'ip_allowlist' field are valid IPv4 or IPv6 CIDRs."""
        for item in value:
            try:
                ip_network(item)
            except ValueError as e:
                raise ValueError(f"{item} is not a valid IPv4 or IPv6 CIDR") from e
        return value
