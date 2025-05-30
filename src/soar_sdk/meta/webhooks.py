from pydantic import BaseModel, Field, validator
from ipaddress import ip_network
from typing import Optional


class WebhookMeta(BaseModel):
    handler: Optional[str]
    requires_auth: bool = True
    allowed_headers: list[str] = Field(default_factory=list)
    ip_allowlist: list[str] = Field(default_factory=lambda: ["0.0.0.0/0", "::/0"])

    @validator("ip_allowlist", each_item=True)
    def validate_ip_allowlist(cls, value: str) -> str:
        try:
            ip_network(value)
        except ValueError as e:
            raise ValueError(f"{value} is not a valid IPv4 or IPv6 CIDR") from e

        return value
