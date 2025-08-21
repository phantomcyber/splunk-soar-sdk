from pydantic import BaseModel, Field, validator
from ipaddress import ip_network
from typing import Optional


class WebhookRouteMeta(BaseModel):
    """
    Metadata for a webhook route, including the handler function and its properties.
    """

    url_pattern: str
    allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "POST"])
    declaration_path: Optional[str] = None
    declaration_lineno: Optional[int] = None


class WebhookMeta(BaseModel):
    handler: Optional[str]
    requires_auth: bool = True
    allowed_headers: list[str] = Field(default_factory=list)
    ip_allowlist: list[str] = Field(default_factory=lambda: ["0.0.0.0/0", "::/0"])
    routes: list[WebhookRouteMeta] = Field(default_factory=list)

    @validator("ip_allowlist", each_item=True)
    def validate_ip_allowlist(cls, value: str) -> str:
        try:
            ip_network(value)
        except ValueError as e:
            raise ValueError(f"{value} is not a valid IPv4 or IPv6 CIDR") from e

        return value
