import asyncio
import httpx
import time
from soar_sdk.abstract import SOARClient
from soar_sdk.params import Params, Param
from soar_sdk.action_results import ActionOutput
from ..app import Asset


class AsyncTestParams(Params):
    num_requests: int = Param(
        default=3, description="Number of concurrent HTTP requests"
    )


class AsyncTestOutput(ActionOutput):
    execution_time: float
    requests_completed: int
    status_codes: list[int]


async def async_process(
    params: AsyncTestParams, soar: SOARClient, asset: Asset
) -> AsyncTestOutput:
    start_time = time.time()

    async def fetch_request(client):
        url = "https://httpbin.org/delay/1"
        try:
            response = await client.get(url, timeout=10)
            return response.status_code
        except Exception:
            return 0

    # Make concurrent HTTP requests to demonstrate async
    async with httpx.AsyncClient() as client:
        tasks = [fetch_request(client) for _ in range(params.num_requests)]
        status_codes = await asyncio.gather(*tasks)

    end_time = time.time()
    execution_time = end_time - start_time

    return AsyncTestOutput(
        execution_time=execution_time,
        requests_completed=len(status_codes),
        status_codes=status_codes,
    )


class SyncTestParams(Params):
    num_requests: int = Param(
        default=3, description="Number of sequential HTTP requests"
    )


class SyncTestOutput(ActionOutput):
    execution_time: float
    requests_completed: int
    status_codes: list[int]


def sync_process(
    params: SyncTestParams, soar: SOARClient, asset: Asset
) -> SyncTestOutput:
    start_time = time.time()

    def fetch_request():
        url = "https://httpbin.org/delay/1"
        try:
            response = httpx.get(url, timeout=10)
            return response.status_code
        except Exception:
            return 0

    # Make sequential HTTP requests (slower)
    status_codes = []
    for _ in range(params.num_requests):
        status_code = fetch_request()
        status_codes.append(status_code)

    end_time = time.time()
    execution_time = end_time - start_time

    return SyncTestOutput(
        execution_time=execution_time,
        requests_completed=len(status_codes),
        status_codes=status_codes,
    )
