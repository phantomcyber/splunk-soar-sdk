import httpx
from pydantic import Field

from soar_sdk.models.finding import Finding


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
