import argparse
import json
import typing
from pprint import pprint
from typing import Optional, Any

import requests

if typing.TYPE_CHECKING:
    from .app import App  # pragma: no cover


class AppRunner:
    """
    Runner for local run of the actions handling with the app.

    Note: this is solely derived from the legacy connectors main() function generated
          by the app wizard in SOAR. Will be rewritten in the future so consider this
          a deprecated code at the moment. This functionality should be provided by
          SDK CLI instead.

    Should be run in the python script with the given arguments passed:
    :input_test_json: path to the input JSON file that will be used for handling the action
    :username: the SOAR instance username
    :password: the SOAR instance user password
    """

    def __init__(self, app: "App") -> None:
        self.app = app
        self.session_id: Optional[str] = None
        self.headers: dict = {}
        self.csrftoken: Optional[str] = None
        self.username: str = ""
        self.password: str = ""
        self.input_test_json: str = ""

    def parse_args(self) -> None:  # pragma: no cover
        argparser = argparse.ArgumentParser()

        argparser.add_argument("input_test_json", help="Input Test JSON file")
        argparser.add_argument("-u", "--username", help="username", required=False)
        argparser.add_argument("-p", "--password", help="password", required=False)

        args = argparser.parse_args()

        self.username = args.username
        self.password = args.password
        self.input_test_json = args.input_test_json

    def load_input_test_json(self) -> dict[str, Any]:  # pragma: no cover
        with open(self.input_test_json) as f:
            in_json = f.read()

        in_json_dict = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        return in_json_dict

    def login(self) -> None:  # pragma: no cover
        """Signs into SOAR to retrieve session ID and CSRF token for later API calls"""

        if self.username is not None and self.password is None:
            # User specified a username but not a password, so ask
            import getpass

            self.password = getpass.getpass("Password: ")

        if self.username and self.password:
            try:
                login_url = (
                    self.app.actions_provider.soar_client.get_soar_base_url() + "/login"
                )

                print("Accessing the Login page")
                r = requests.get(login_url, verify=False)
                self.csrftoken = r.cookies["csrftoken"]

                data = dict()
                data["username"] = self.username
                data["password"] = self.password
                data["csrfmiddlewaretoken"] = self.csrftoken

                headers = dict()
                headers["Cookie"] = "csrftoken=" + self.csrftoken
                headers["Referer"] = login_url

                print("Logging into Platform to get the session id")
                r2 = requests.post(login_url, verify=False, data=data, headers=headers)
                self.session_id = r2.cookies["sessionid"]
                self.headers = headers

                if self.session_id is not None:
                    self.app.actions_provider.soar_client.set_csrf_info(
                        self.csrftoken, self.headers["Referer"]
                    )

            except Exception as e:
                print("Unable to get session id from the platform. Error: " + str(e))
                exit(1)

    def run(self) -> None:
        self.parse_args()
        self.login()
        in_json = self.load_input_test_json()

        if self.session_id is not None:
            in_json["user_session_token"] = self.session_id

        ret_val = self.app.handle(json.dumps(in_json), None)
        pprint(json.loads(ret_val))
