import httpx
from typing import Optional, Any
from collections.abc import Generator


def is_client_authenticated(client: httpx.Client) -> bool:
    """
    Check wether the httpx client is authenticated to SOAR
    """
    return client.headers.get("X-CSRFToken") is not None


def get_request_iter_pages(
    client: httpx.Client,
    endpoint: str,
    params: Optional[dict] = None,
    page_size: int = 50,
) -> Generator[Any, None, None]:
    """
    Iterate through REST JSON results using the provided paging.
    """
    params = params or {}

    params["page_size"] = page_size
    params["page"] = 0

    num_pages = 1
    while params["page"] < num_pages:
        response = client.get(endpoint, params=params)
        response.raise_for_status()
        response_json = response.json()

        num_pages = response_json["num_pages"]
        params["page"] += 1

        yield response_json["data"]


__all__ = ["get_request_iter_pages", "is_client_authenticated"]
