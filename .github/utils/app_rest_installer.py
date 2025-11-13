"""
Installs an app tarball on a target Phantom instance over REST.
"""

import argparse
import logging
import os
import socket
import sys
from contextlib import contextmanager
from json import JSONDecodeError

import requests
from requests.exceptions import HTTPError

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NRI_PORT = 9999


def parse_args():
    help_str = " ".join(line.strip() for line in __doc__.splitlines())
    parser = argparse.ArgumentParser(description=help_str)
    parser.add_argument("tarball_path", help="Path to the app tarball to install")
    parser.add_argument("phantom_ip", help="IP of the target phantom instance")
    parser.add_argument("phantom_username", help="User for the target phantom instance")
    parser.add_argument("phantom_password", help="User password")

    return parser.parse_args()


def _is_port_in_use(host, port):
    """
    True if the port is in use on the host.

    Source: https://stackoverflow.com/a/52872579
    """
    logging.info(f"Checking if port {port} is in use on host {host}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex((host, port)) == 0


@contextmanager
def _open_phantom_session(phantom_instance_ip, phantom_username, phantom_password):
    session = requests.Session()
    base_url = f"https://{phantom_instance_ip}"
    login_url = f"{base_url}/login"

    try:
        # Get initial cookies
        session.get(login_url, verify=False)

        # Login
        login_body = {
            "username": phantom_username,
            "password": phantom_password,
            "csrfmiddlewaretoken": session.cookies["csrftoken"],
        }
        login_headers = {"referer": login_url}
        session.post(login_url, verify=False, data=login_body, headers=login_headers)

        # Update headers with session cookies
        session.headers.update(
            {
                "cookie": f"csrftoken={session.cookies['csrftoken']};sessionid={session.cookies['sessionid']}"
            }
        )
        session.base_url = base_url

        yield session
    finally:
        session.close()


def main(args):
    try:
        if _is_port_in_use(args.phantom_ip, NRI_PORT):
            phantom_ip = f"{args.phantom_ip}:{NRI_PORT}"
        else:
            phantom_ip = args.phantom_ip

        logging.info("Installing %s on instance %s", args.tarball_path, phantom_ip)

        if not os.path.isfile(args.tarball_path):
            logging.error(f"{args.tarball_path} not found")
            return 1

        with (
            _open_phantom_session(
                phantom_ip, args.phantom_username, args.phantom_password
            ) as session,
            open(args.tarball_path, "rb") as tarball,
        ):
            install_url = f"{session.base_url}/app_install"
            resp = session.post(
                install_url,
                verify=False,
                data={"csrfmiddlewaretoken": session.cookies["csrftoken"]},
                files={"app": tarball},
                headers={"referer": install_url},
            )

            logging.info("Install succeeded with response: %s", resp.json())
            return 0
    except HTTPError as ex:
        try:
            logging.error("Install failed with response: %s", ex.response.json())
        except JSONDecodeError:
            logging.error("Install failed with response: %s", ex.response.text)
        return 1
    except Exception as ex:
        logging.error("Install failed with error: %s", str(ex))
        return 1


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    sys.exit(main(parse_args()))
