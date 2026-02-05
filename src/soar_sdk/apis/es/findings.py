import base64

import httpx
from pydantic import Field

from soar_sdk.models.finding import Finding

MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024  # 50 MB (till batching uploads is implemented)


class CreateFindingResponse(Finding):
    """The return type from creating a Finding."""

    time: str = Field(alias="_time")
    finding_id: str


class Findings:
    """Client for ES Findings API."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def create(self, finding: Finding) -> CreateFindingResponse:
        """Create a new Finding."""
        res = self._client.post(
            "/services/public/v2/findings",
            data=finding.model_dump(),
        )
        res.raise_for_status()
        return CreateFindingResponse(**res.json())

    def upload_attachment(
        self,
        finding_id: str,
        file_name: str,
        data: bytes,
    ) -> None:
        """Upload an attachment to a finding for SAA threat analysis."""
        if len(data) > MAX_ATTACHMENT_SIZE:
            raise ValueError(
                f"Attachment {file_name} exceeds 50 MB limit ({len(data)} bytes)"
            )
        encoded_data = base64.b64encode(data).decode("utf-8")
        res = self._client.post(
            f"/services/public/v2/findings/{finding_id}/attachments",
            json={
                "file_name": file_name,
                "file_size": len(data),
                "data": encoded_data,
            },
        )
        res.raise_for_status()
