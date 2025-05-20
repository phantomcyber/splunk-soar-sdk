from pydantic import BaseModel, Field
from typing import Optional


class WebhookMeta(BaseModel):
    handler: Optional[str]
    requires_auth: bool = True
    allowed_headers: list[str] = []
    ip_allowlist: list[str] = Field(default=["0.0.0.0/0", "::/0"])
