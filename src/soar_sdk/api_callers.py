from typing import Optional, TYPE_CHECKING, Any

import requests
from bs4 import BeautifulSoup
from requests import Response

import soar_sdk.shims.phantom.app as phantom
from soar_sdk.shims.phantom.action_result import ActionResult as PhantomActionResult

if TYPE_CHECKING:
    from soar_sdk.connector import AppConnector


class RestApiCaller:  # pragma: no cover
    """
    This is the legacy REST API calling functionality which was provided by default
    with the App Wizard. It can be used for very basic API calls with the asset
    configuration, given the app meta file will provide such.
    """

    def __init__(self, connector: "AppConnector") -> None:
        self.connector = connector

    @staticmethod
    def process_empty_response(
        response: Response, action_result: PhantomActionResult
    ) -> tuple[bool, Optional[dict[Any, Any]]]:  # pragma: no cover
        if response.status_code == 200:
            return phantom.APP_SUCCESS, {}

        return (
            action_result.set_status(
                phantom.APP_ERROR,
                "Empty response and no information in the header",
            ),
            None,
        )

    @staticmethod
    def process_html_response(
        response: Response, action_result: PhantomActionResult
    ) -> tuple[bool, Optional[dict[Any, Any]]]:  # pragma: no cover
        # An html response, treat it like an error
        status_code = response.status_code

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            error_text = soup.text
            split_lines = error_text.split("\n")
            split_lines = [x.strip() for x in split_lines if x.strip()]
            error_text = "\n".join(split_lines)
        except Exception:
            error_text = "Cannot parse error details"

        message = f"Status Code: {status_code}. Data from server:\n{error_text}\n"

        message = message.replace("{", "{{").replace("}", "}}")
        return action_result.set_status(phantom.APP_ERROR, message), None

    @staticmethod
    def process_json_response(
        r: Response, action_result: PhantomActionResult
    ) -> tuple[bool, Optional[dict[Any, Any]]]:  # pragma: no cover
        # Try a json parse
        try:
            resp_json = r.json()
        except Exception as e:
            return (
                action_result.set_status(
                    phantom.APP_ERROR,
                    f"Unable to parse JSON response. Error: {e!s}",
                ),
                None,
            )

        # Please specify the status codes here
        if 200 <= r.status_code < 399:
            return phantom.APP_SUCCESS, resp_json

        # You should process the error returned in the json
        message = "Error from server. Status Code: {} Data from server: {}".format(
            r.status_code, r.text.replace("{", "{{").replace("}", "}}")
        )

        return action_result.set_status(phantom.APP_ERROR, message), None

    @classmethod
    def process_response(
        cls, r: Response, action_result: PhantomActionResult
    ) -> tuple[bool, Optional[dict[Any, Any]]]:  # pragma: no cover
        # store the r_text in debug data, it will get dumped in the logs if the action fails
        if hasattr(action_result, "add_debug_data"):
            action_result.add_debug_data({"r_status_code": r.status_code})
            action_result.add_debug_data({"r_text": r.text})
            action_result.add_debug_data({"r_headers": r.headers})

        # Process each 'Content-Type' of response separately

        # Process a json response
        if "json" in r.headers.get("Content-Type", ""):
            return cls.process_json_response(r, action_result)

        # Process an HTML response, Do this no matter what the api talks.
        # There is a high chance of a PROXY in between phantom and the rest of
        # world, in case of errors, PROXY's return HTML, this function parses
        # the error and adds it to the action_result.
        if "html" in r.headers.get("Content-Type", ""):
            return cls.process_html_response(r, action_result)

        # it's not content-type that is to be parsed, handle an empty response
        if not r.text:
            return cls.process_empty_response(r, action_result)

        # everything else is actually an error at this point
        message = "Can't process response from server. Status Code: {} Data from server: {}".format(
            r.status_code, r.text.replace("{", "{{").replace("}", "}}")
        )

        return action_result.set_status(phantom.APP_ERROR, message), None

    def call(
        self,
        endpoint: str,
        action_result: PhantomActionResult,
        method: str = "get",
        **kwargs: dict[str, Any],
    ) -> tuple[bool, Optional[dict[Any, Any]]]:  # pragma: no cover
        # **kwargs can be any additional parameters that requests.request accepts

        config = self.connector.get_config()

        resp_json = None  # FIXME: it is never changed

        try:
            request_func = getattr(requests, method)
        except AttributeError:
            return (
                action_result.set_status(
                    phantom.APP_ERROR, f"Invalid method: {method}"
                ),
                resp_json,
            )

        # Create a URL to connect to
        url = config.get("base_url", "") + endpoint

        try:
            r = request_func(
                url,
                verify=config.get("verify_server_cert", False),
                **kwargs,
            )
        except Exception as e:
            return (
                action_result.set_status(
                    phantom.APP_ERROR,
                    f"Error Connecting to server. Details: {e!s}",
                ),
                resp_json,
            )

        return self.process_response(r, action_result)
