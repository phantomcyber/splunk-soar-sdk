import base64
import contextlib
import email
import hashlib
import json
import mimetypes
import re
import shutil
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from email.header import decode_header, make_header
from email.message import Message
from html import unescape
from pathlib import Path
from typing import Any, TypedDict

from bs4 import BeautifulSoup, UnicodeDammit  # type: ignore[attr-defined]
from pydantic import HttpUrl, ValidationError
from requests.structures import CaseInsensitiveDict

from soar_sdk.abstract import SOARClient
from soar_sdk.extras.email.utils import (
    clean_url,
    create_dict_hash,
    decode_uni_string,
    get_file_contains,
    get_string,
    is_ip,
    is_sha1,
    remove_child_info,
)
from soar_sdk.logging import getLogger
from soar_sdk.shims import phantom
from soar_sdk.shims.phantom.app import APP_ERROR, APP_SUCCESS
from soar_sdk.shims.phantom.vault import VaultBase

logger = getLogger()


def validate_url(value: str) -> None:
    """Validate a URL using pydantic."""
    try:
        HttpUrl(value)
    except ValidationError as e:
        raise ValueError(f"Invalid URL: {e}") from e


_container_common = {"run_automation": False}
_artifact_common = {"run_automation": False}

DEFAULT_ARTIFACT_COUNT = 100
DEFAULT_CONTAINER_COUNT = 100
HASH_FIXED_PHANTOM_VERSION = "2.0.201"

PROC_EMAIL_JSON_FILES = "files"
PROC_EMAIL_JSON_BODIES = "bodies"
PROC_EMAIL_JSON_DATE = "date"
PROC_EMAIL_JSON_FROM = "from"
PROC_EMAIL_JSON_SUBJECT = "subject"
PROC_EMAIL_JSON_TO = "to"
PROC_EMAIL_JSON_START_TIME = "start_time"
PROC_EMAIL_JSON_EXTRACT_ATTACHMENTS = "extract_attachments"
PROC_EMAIL_JSON_EXTRACT_BODY = "add_body_to_header_artifacts"
PROC_EMAIL_JSON_EXTRACT_URLS = "extract_urls"
PROC_EMAIL_JSON_EXTRACT_IPS = "extract_ips"
PROC_EMAIL_JSON_EXTRACT_DOMAINS = "extract_domains"
PROC_EMAIL_JSON_EXTRACT_HASHES = "extract_hashes"
PROC_EMAIL_JSON_IPS = "ips"
PROC_EMAIL_JSON_HASHES = "hashes"
PROC_EMAIL_JSON_URLS = "urls"
PROC_EMAIL_JSON_DOMAINS = "domains"
PROC_EMAIL_JSON_MSG_ID = "message_id"
PROC_EMAIL_JSON_EMAIL_HEADERS = "email_headers"
PROC_EMAIL_CONTENT_TYPE_MESSAGE = "message/rfc822"

URI_REGEX = r"[Hh][Tt][Tt][Pp][Ss]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
EMAIL_REGEX = r"\b[A-Z0-9._%+-]+@+[A-Z0-9.-]+\.[A-Z]{2,}\b"
EMAIL_REGEX2 = r'".*"@[A-Z0-9.-]+\.[A-Z]{2,}\b'
HASH_REGEX = r"\b[0-9a-fA-F]{32}\b|\b[0-9a-fA-F]{40}\b|\b[0-9a-fA-F]{64}\b"
IP_REGEX = r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
IPV6_REGEX = r"\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|"
IPV6_REGEX += r"(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}"
IPV6_REGEX += (
    r"|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))"
)
IPV6_REGEX += r"|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})"
IPV6_REGEX += r"|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|"
IPV6_REGEX += r"(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})"
IPV6_REGEX += r"|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|"
IPV6_REGEX += r"(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})"
IPV6_REGEX += r"|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|"
IPV6_REGEX += r"(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})"
IPV6_REGEX += r"|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|"
IPV6_REGEX += r"(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})"
IPV6_REGEX += r"|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|"
IPV6_REGEX += (
    r"(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d"
)
IPV6_REGEX += r"|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))(%.+)?\s*"


class EmailBodyDict(TypedDict):
    """Type definition for email body dictionary."""

    file_path: str
    charset: str | None


@dataclass
class ProcessEmailContext:
    """Context object for email processing with SDK components."""

    soar: SOARClient
    vault: VaultBase
    app_id: str
    folder_name: str
    is_hex: bool
    action_name: str | None = None
    app_run_id: int | None = None


class EmailProcessor:
    """Email processor for parsing and extracting artifacts from RFC822 emails."""

    def __init__(self, context: ProcessEmailContext, config: dict[str, Any]) -> None:
        self.context = context
        self._config = config
        self._email_id_contains: list[str] = []
        self._container: dict[str, Any] = {}
        self._artifacts: list[dict[str, Any]] = []
        self._attachments: list[dict[str, Any]] = []
        self._external_headers: list[CaseInsensitiveDict] = []
        self._external_attachments: list[dict[str, Any]] = []
        self._parsed_mail: dict[str, Any] | None = None
        self._guid_to_hash: dict[str, str] = {}
        self._tmp_dirs: list[str] = []

    def _extract_urls_domains(
        self, file_data: str, urls: set[str], domains: set[str]
    ) -> None:
        if (not self._config[PROC_EMAIL_JSON_EXTRACT_DOMAINS]) and (
            not self._config[PROC_EMAIL_JSON_EXTRACT_URLS]
        ):
            return

        try:
            soup = BeautifulSoup(file_data, "html.parser")
        except Exception as e:
            logger.debug(f"Error occurred while extracting domains of the URLs: {e}")
            return

        uris = []
        links = soup.find_all(href=True)
        srcs = soup.find_all(src=True)

        if links:
            for x in links:
                uris.append(clean_url(x.get_text()))
                if not x["href"].startswith("mailto:"):
                    uris.append(x["href"])

        if srcs:
            for x in srcs:
                uris.append(clean_url(x.get_text()))
                uris.append(x["src"])

        file_data = unescape(file_data)
        regex_uris = re.findall(URI_REGEX, file_data)
        uris.extend(clean_url(x) for x in regex_uris)

        validated_urls = []
        for url in uris:
            try:
                validate_url(url)
                validated_urls.append(url)
            except Exception as e:
                logger.debug(f"URL validation failed for {url}: {e}")

        if self._config[PROC_EMAIL_JSON_EXTRACT_URLS]:
            urls |= set(validated_urls)

        if self._config[PROC_EMAIL_JSON_EXTRACT_DOMAINS]:
            for uri in validated_urls:
                domain = phantom.get_host_from_url(uri)  # type: ignore[attr-defined]
                if domain and (not is_ip(domain)):
                    domains.add(domain)
            if links:
                mailtos = [
                    x["href"] for x in links if (x["href"].startswith("mailto:"))
                ]
                for curr_email in mailtos:
                    domain = curr_email[curr_email.find("@") + 1 :]
                    if domain and (not is_ip(domain)):
                        if "?" in domain:
                            domain = domain[: domain.find("?")]
                        domains.add(domain)

    def _get_ips(self, file_data: str, ips: set[str]) -> None:
        for match in re.finditer(IP_REGEX, file_data):
            ip_candidate = match.group(0).strip()
            if is_ip(ip_candidate):
                ips.add(ip_candidate)

        for match in re.finditer(IPV6_REGEX, file_data):
            ip_candidate = match.group(0).strip()
            ips.add(ip_candidate)

    def _handle_body(
        self,
        body: EmailBodyDict,
        parsed_mail: dict[str, Any],
        body_index: int,
        email_id: str,
    ) -> int:
        local_file_path = body["file_path"]
        charset = body.get("charset")

        ips = parsed_mail[PROC_EMAIL_JSON_IPS]
        hashes = parsed_mail[PROC_EMAIL_JSON_HASHES]
        urls = parsed_mail[PROC_EMAIL_JSON_URLS]
        domains = parsed_mail[PROC_EMAIL_JSON_DOMAINS]

        file_data_raw: str | bytes | None = None
        try:
            with open(local_file_path) as f:
                file_data_raw = f.read()
        except Exception:
            with open(local_file_path, "rb") as f:
                file_data_raw = f.read()

        if (file_data_raw is None) or (len(file_data_raw) == 0):
            return APP_ERROR

        file_data: str = (
            UnicodeDammit(file_data_raw).unicode_markup.encode("utf-8").decode("utf-8")
        )

        self._parse_email_headers_as_inline(file_data, parsed_mail, charset, email_id)

        if self._config[PROC_EMAIL_JSON_EXTRACT_DOMAINS]:
            emails = []
            emails.extend(re.findall(EMAIL_REGEX, file_data, re.IGNORECASE))
            emails.extend(re.findall(EMAIL_REGEX2, file_data, re.IGNORECASE))

            for curr_email in emails:
                domain = curr_email[curr_email.rfind("@") + 1 :]
                domains.add(domain)

        self._extract_urls_domains(file_data, urls, domains)

        if self._config[PROC_EMAIL_JSON_EXTRACT_IPS]:
            self._get_ips(file_data, ips)

        if self._config[PROC_EMAIL_JSON_EXTRACT_HASHES]:
            hashs_in_mail = re.findall(HASH_REGEX, file_data)
            if hashs_in_mail:
                hashes |= set(hashs_in_mail)

        return APP_SUCCESS

    def _add_artifacts(
        self,
        cef_key: str,
        input_set: set[str],
        artifact_name: str,
        start_index: int,
        artifacts: list[dict[str, Any]],
    ) -> int:
        added_artifacts = 0
        for entry in input_set:
            if not entry:
                continue

            artifact: dict[str, Any] = {}
            artifact.update(_artifact_common)
            artifact["source_data_identifier"] = str(start_index + added_artifacts)
            artifact["cef"] = {cef_key: entry}
            artifact["name"] = artifact_name
            logger.debug(f"Artifact: {artifact}")
            artifacts.append(artifact)
            added_artifacts += 1

        return added_artifacts

    def _parse_email_headers_as_inline(
        self,
        file_data: str,
        parsed_mail: dict[str, Any],
        charset: str | None,
        email_id: str,
    ) -> int:
        email_text = re.sub(
            r"(?im)^.*forwarded message.*\r?\n", "", file_data.strip(), count=1
        )
        mail = email.message_from_string(email_text)
        self._parse_email_headers(parsed_mail, mail, charset, add_email_id=email_id)
        return APP_SUCCESS

    def _add_email_header_artifacts(
        self,
        email_header_artifacts: list[dict[str, Any]],
        start_index: int,
        artifacts: list[dict[str, Any]],
    ) -> int:
        added_artifacts = 0
        for artifact in email_header_artifacts:
            artifact["source_data_identifier"] = str(start_index + added_artifacts)
            artifacts.append(artifact)
            added_artifacts += 1
        return added_artifacts

    def _create_artifacts(self, parsed_mail: dict[str, Any]) -> int:
        ips = parsed_mail[PROC_EMAIL_JSON_IPS]
        hashes = parsed_mail[PROC_EMAIL_JSON_HASHES]
        urls = parsed_mail[PROC_EMAIL_JSON_URLS]
        domains = parsed_mail[PROC_EMAIL_JSON_DOMAINS]
        email_headers = parsed_mail[PROC_EMAIL_JSON_EMAIL_HEADERS]

        artifact_id = 0

        added_artifacts = self._add_artifacts(
            "sourceAddress", ips, "IP Artifact", artifact_id, self._artifacts
        )
        artifact_id += added_artifacts

        added_artifacts = self._add_artifacts(
            "fileHash", hashes, "Hash Artifact", artifact_id, self._artifacts
        )
        artifact_id += added_artifacts

        added_artifacts = self._add_artifacts(
            "requestURL", urls, "URL Artifact", artifact_id, self._artifacts
        )
        artifact_id += added_artifacts

        added_artifacts = self._add_artifacts(
            "destinationDnsDomain",
            domains,
            "Domain Artifact",
            artifact_id,
            self._artifacts,
        )
        artifact_id += added_artifacts

        added_artifacts = self._add_email_header_artifacts(
            email_headers, artifact_id, self._artifacts
        )
        artifact_id += added_artifacts

        return APP_SUCCESS

    def _get_container_name(self, parsed_mail: dict[str, Any], email_id: str) -> str:
        def_cont_name = f"Email ID: {email_id}"
        subject = parsed_mail.get(PROC_EMAIL_JSON_SUBJECT)

        if not subject:
            return def_cont_name

        try:
            return str(make_header(decode_header(subject)))
        except Exception:
            return decode_uni_string(subject, def_cont_name)

    def _handle_if_body(
        self,
        content_disp: str | None,
        content_id: str | None,
        content_type: str | None,
        part: Message,
        bodies: list[EmailBodyDict],
        file_path: str,
    ) -> tuple[int, bool]:
        process_as_body = False

        if content_disp is None or (
            content_disp.lower().strip() == "inline"
            and content_type
            and (("text/html" in content_type) or ("text/plain" in content_type))
        ):
            process_as_body = True

        if not process_as_body:
            return APP_SUCCESS, True

        part_payload = part.get_payload(decode=True)

        if not part_payload:
            return APP_SUCCESS, False

        with open(file_path, "wb") as f:
            f.write(part_payload)  # type: ignore[arg-type]

        bodies.append({"file_path": file_path, "charset": part.get_content_charset()})

        return APP_SUCCESS, False

    def _handle_attachment(self, part: Message, file_name: str, file_path: str) -> int:
        if self._parsed_mail is None:
            return APP_ERROR

        files = self._parsed_mail[PROC_EMAIL_JSON_FILES]

        if not self._config[PROC_EMAIL_JSON_EXTRACT_ATTACHMENTS]:
            return APP_SUCCESS

        part_base64_encoded = part.get_payload()

        headers = self._get_email_headers_from_part(part)

        attach_meta_info: dict[str, Any] = {}

        if headers:
            attach_meta_info = {"headers": dict(headers)}

        for curr_attach in self._external_attachments:
            if curr_attach.get("should_ignore", False):
                continue

            try:
                attach_content = curr_attach["content"]
            except Exception as e:
                logger.debug(f"Failed to get attachment content: {e}")
                continue

            if attach_content.strip().replace("\r\n", "") == str(
                part_base64_encoded
            ).strip().replace("\r\n", ""):
                attach_meta_info.update(dict(curr_attach))
                del attach_meta_info["content"]
                curr_attach["should_ignore"] = True

        part_payload = part.get_payload(decode=True)
        if not part_payload:
            return APP_SUCCESS

        try:
            with open(file_path, "wb") as f:
                f.write(part_payload)  # type: ignore[arg-type]
        except OSError as e:
            try:
                if "File name too long" in str(e):
                    new_file_name = "ph_long_file_name_temp"
                    file_path = "{}{}".format(
                        remove_child_info(file_path).rstrip(
                            file_name.replace("<", "").replace(">", "").replace(" ", "")
                        ),
                        new_file_name,
                    )
                    logger.debug(f"Original filename: {file_name}")
                    logger.debug(f"Modified filename: {new_file_name}")
                    with open(file_path, "wb") as long_file:
                        long_file.write(part_payload)  # type: ignore[arg-type]
                else:
                    logger.debug(f"Error occurred while adding file to Vault: {e}")
                    return APP_ERROR
            except Exception as e:
                logger.debug(f"Error occurred while adding file to Vault: {e}")
                return APP_ERROR
        except Exception as e:
            logger.debug(f"Error occurred while adding file to Vault: {e}")
            return APP_ERROR

        files.append(
            {
                "file_name": file_name,
                "file_path": file_path,
                "meta_info": attach_meta_info,
            }
        )

        return APP_SUCCESS

    def _handle_part(
        self,
        part: Message,
        part_index: int,
        tmp_dir: str,
        extract_attach: bool,
        parsed_mail: dict[str, Any],
    ) -> int:
        bodies: list[EmailBodyDict] = parsed_mail[PROC_EMAIL_JSON_BODIES]

        file_name = part.get_filename()
        content_disp = part.get("Content-Disposition")
        content_type = part.get("Content-Type")
        content_id = part.get("Content-ID")

        if file_name is None:
            name = f"part_{part_index}"
            extension = f".{part_index}"

            if content_type is not None:
                ext_guess = mimetypes.guess_extension(re.sub(";.*", "", content_type))
                if ext_guess:
                    extension = ext_guess

            if content_id is not None:
                name = content_id

            file_name = f"{name}{extension}"
        else:
            file_name = decode_uni_string(file_name, file_name)

        file_path = "{}/{}_{}".format(
            tmp_dir,
            part_index,
            file_name.translate(file_name.maketrans("", "", "".join(["<", ">", " "]))),
        )

        logger.debug(f"file_path: {file_path}")

        _status, process_further = self._handle_if_body(
            content_disp, content_id, content_type, part, bodies, file_path
        )

        if not process_further:
            return APP_SUCCESS

        if (content_type is not None) and (
            content_type.find(PROC_EMAIL_CONTENT_TYPE_MESSAGE) != -1
        ):
            return APP_SUCCESS

        self._handle_attachment(part, file_name, file_path)

        return APP_SUCCESS

    def _update_headers(self, headers: CaseInsensitiveDict) -> int:
        if not self._external_headers:
            return APP_SUCCESS

        if not headers:
            return APP_SUCCESS

        headers_ci = CaseInsensitiveDict(headers)

        for curr_header_lower in self._external_headers:
            if (
                headers_ci.get("message-id", "default_value1").strip()
                == curr_header_lower.get("message-id", "default_value2").strip()
            ):
                headers.update(curr_header_lower)

        return APP_SUCCESS

    def _get_email_headers_from_part(
        self, part: Message, charset: str | None = None
    ) -> CaseInsensitiveDict:
        email_headers = list(part.items())

        if not email_headers:
            return CaseInsensitiveDict()

        if charset is None:
            charset = part.get_content_charset() or "utf-8"

        headers: CaseInsensitiveDict = CaseInsensitiveDict()
        try:
            for header_item in email_headers:
                headers.update({header_item[0]: get_string(header_item[1], charset)})
        except Exception as e:
            logger.debug(
                f"Error converting header with charset {charset}: {e}. Using raw values."
            )
            for header_item in email_headers:
                headers.update({header_item[0]: header_item[1]})

        try:
            received_headers = [
                get_string(x[1], charset)
                for x in email_headers
                if x[0].lower() == "received"
            ]
        except Exception as e:
            logger.debug(f"Error converting received headers: {e}")
            received_headers = [
                x[1] for x in email_headers if x[0].lower() == "received"
            ]

        if received_headers:
            headers["Received"] = received_headers

        subject = headers.get("Subject")
        if subject:
            try:
                headers["decodedSubject"] = str(make_header(decode_header(subject)))
            except Exception:
                headers["decodedSubject"] = decode_uni_string(subject, subject)

        to_data = headers.get("To")
        if to_data:
            headers["decodedTo"] = decode_uni_string(to_data, to_data)

        from_data = headers.get("From")
        if from_data:
            headers["decodedFrom"] = decode_uni_string(from_data, from_data)

        cc_data = headers.get("CC")
        if cc_data:
            headers["decodedCC"] = decode_uni_string(cc_data, cc_data)

        return headers

    def _parse_email_headers(
        self,
        parsed_mail: dict[str, Any],
        part: Message,
        charset: str | None = None,
        add_email_id: str | None = None,
    ) -> int:
        email_header_artifacts = parsed_mail[PROC_EMAIL_JSON_EMAIL_HEADERS]

        headers = self._get_email_headers_from_part(part, charset)

        if not headers:
            return 0

        cef_artifact: dict[str, Any] = {}
        cef_types: dict[str, list[str]] = {}

        if headers.get("From"):
            cef_artifact.update({"fromEmail": headers["From"]})

        if headers.get("To"):
            cef_artifact.update({"toEmail": headers["To"]})

        message_id = headers.get("message-id")
        if (not cef_artifact) and (message_id is None):
            return 0

        cef_types.update({"fromEmail": ["email"], "toEmail": ["email"]})

        self._update_headers(headers)
        cef_artifact["emailHeaders"] = dict(headers)

        body = None

        for curr_key in list(cef_artifact["emailHeaders"].keys()):
            if curr_key.lower().startswith("body"):
                body = cef_artifact["emailHeaders"].pop(curr_key)
            elif curr_key in ("parentInternetMessageId", "parentGuid", "emailGuid"):
                curr_value = cef_artifact["emailHeaders"].pop(curr_key)
                cef_artifact.update({curr_key: curr_value})

        if self._config.get(PROC_EMAIL_JSON_EXTRACT_BODY, False) and not body:
            queue: list[Message] = [part]
            i = 1
            while len(queue) > 0:
                cur_part = queue.pop(0)
                payload = cur_part.get_payload()
                if isinstance(payload, list):
                    queue.extend(payload)  # type: ignore[arg-type]
                else:
                    encoding = cur_part["Content-Transfer-Encoding"]
                    if encoding:
                        if "base64" in encoding.lower():
                            payload = base64.b64decode(
                                "".join(str(payload).splitlines())
                            )
                        elif encoding != "8bit":
                            payload = cur_part.get_payload(decode=True)
                            payload = (
                                UnicodeDammit(payload)
                                .unicode_markup.encode("utf-8")
                                .decode("utf-8")
                            )
                    try:
                        json.dumps({"body": payload})
                    except (TypeError, UnicodeDecodeError):
                        try:
                            payload = payload.decode("UTF-8")  # type: ignore[union-attr]
                        except (UnicodeDecodeError, AttributeError):
                            logger.debug(
                                "Email body caused unicode exception. Encoding as base64."
                            )
                            if isinstance(payload, bytes):
                                payload = base64.b64encode(payload).decode("UTF-8")
                            else:
                                payload = base64.b64encode(
                                    str(payload).encode("UTF-8")
                                ).decode("UTF-8")
                            cef_artifact["body_base64encoded"] = True

                    cef_artifact.update({f"bodyPart{i}": payload if payload else None})
                    cef_artifact.update(
                        {
                            f"bodyPart{i}ContentType": cur_part["Content-Type"]
                            if cur_part["Content-Type"]
                            else None
                        }
                    )
                    i += 1

        if add_email_id:
            cef_artifact["emailId"] = add_email_id
            if self._email_id_contains:
                cef_types.update({"emailId": self._email_id_contains})

        artifact: dict[str, Any] = {}
        artifact.update(_artifact_common)
        artifact["name"] = "Email Artifact"
        artifact["cef"] = cef_artifact
        artifact["cef_types"] = cef_types
        email_header_artifacts.append(artifact)

        return len(email_header_artifacts)

    def _handle_mail_object(
        self,
        mail: Message,
        email_id: str,
        rfc822_email: str,
        tmp_dir: str,
        start_time_epoch: float,
    ) -> int:
        self._parsed_mail = {}

        tmp_dir_path = Path(tmp_dir)
        if not tmp_dir_path.exists():
            tmp_dir_path.mkdir(parents=True)

        extract_attach = self._config[PROC_EMAIL_JSON_EXTRACT_ATTACHMENTS]

        self._parsed_mail[PROC_EMAIL_JSON_SUBJECT] = mail.get("Subject", "")
        self._parsed_mail[PROC_EMAIL_JSON_FROM] = mail.get("From", "")
        self._parsed_mail[PROC_EMAIL_JSON_TO] = mail.get("To", "")
        self._parsed_mail[PROC_EMAIL_JSON_DATE] = mail.get("Date", "")
        self._parsed_mail[PROC_EMAIL_JSON_MSG_ID] = mail.get("Message-ID", "")
        self._parsed_mail[PROC_EMAIL_JSON_FILES] = files = []  # type: ignore[var-annotated]
        bodies: list[EmailBodyDict] = []
        self._parsed_mail[PROC_EMAIL_JSON_BODIES] = bodies
        self._parsed_mail[PROC_EMAIL_JSON_START_TIME] = start_time_epoch
        self._parsed_mail[PROC_EMAIL_JSON_EMAIL_HEADERS] = []

        if mail.is_multipart():
            for i, part in enumerate(mail.walk()):
                add_email_id = None
                if i == 0:
                    add_email_id = email_id

                self._parse_email_headers(
                    self._parsed_mail, part, add_email_id=add_email_id
                )

                if part.is_multipart():
                    continue
                try:
                    ret_val = self._handle_part(
                        part, i, tmp_dir, extract_attach, self._parsed_mail
                    )
                except Exception as e:
                    logger.debug(f"ErrorExp in _handle_part # {i}: {e}")
                    continue

                if ret_val == APP_ERROR:
                    continue

        else:
            self._parse_email_headers(self._parsed_mail, mail, add_email_id=email_id)
            file_path = f"{tmp_dir}/part_1.text"
            payload = mail.get_payload(decode=True)
            if payload:
                with open(file_path, "wb") as f:
                    f.write(payload)  # type: ignore[arg-type]
                bodies.append(
                    {"file_path": file_path, "charset": mail.get_content_charset()}
                )

        container_name = self._get_container_name(self._parsed_mail, email_id)

        if container_name is None:
            return APP_ERROR

        container: dict[str, Any] = {}
        container_data = dict(self._parsed_mail)

        del container_data[PROC_EMAIL_JSON_EMAIL_HEADERS]
        container.update(_container_common)

        if not self.context.is_hex:
            try:
                folder_hex = hashlib.sha256(self.context.folder_name)  # type: ignore[arg-type]
            except Exception:
                folder_hex = hashlib.sha256(self.context.folder_name.encode())

            folder_sdi = folder_hex.hexdigest()
        else:
            folder_sdi = self.context.folder_name

        self._container["source_data_identifier"] = f"{folder_sdi} : {email_id}"
        self._container["name"] = container_name
        self._container["data"] = {"raw_email": rfc822_email}

        self._parsed_mail[PROC_EMAIL_JSON_IPS] = set()
        self._parsed_mail[PROC_EMAIL_JSON_HASHES] = set()
        self._parsed_mail[PROC_EMAIL_JSON_URLS] = set()
        self._parsed_mail[PROC_EMAIL_JSON_DOMAINS] = set()

        for i, body in enumerate(bodies):
            if not body:
                continue

            try:
                self._handle_body(body, self._parsed_mail, i, email_id)
            except Exception as e:
                logger.debug(f"ErrorExp in _handle_body # {i}: {e!s}")
                continue

        self._attachments.extend(files)

        self._create_artifacts(self._parsed_mail)

        return APP_SUCCESS

    def _set_email_id_contains(self, email_id: str) -> None:
        email_id_str = str(email_id)

        if is_sha1(email_id_str):
            self._email_id_contains = ["vault id"]

    def _int_process_email(
        self, rfc822_email: str, email_id: str, start_time_epoch: float
    ) -> tuple[int, str, list[dict[str, Any]]]:
        mail = email.message_from_string(rfc822_email)

        tmp_dir = tempfile.mkdtemp(prefix="ph_email_")
        self._tmp_dirs.append(tmp_dir)

        try:
            ret_val = self._handle_mail_object(
                mail, email_id, rfc822_email, tmp_dir, start_time_epoch
            )
        except Exception as e:
            message = f"ErrorExp in self._handle_mail_object: {e}"
            logger.debug(message)
            return APP_ERROR, message, []

        results = [
            {
                "container": self._container,
                "artifacts": self._artifacts,
                "files": self._attachments,
                "temp_directory": tmp_dir,
            }
        ]

        return ret_val, "Email Parsed", results

    def process_email(
        self,
        base_connector: object,
        rfc822_email: str,
        email_id: str,
        config: dict[str, Any],
        epoch: float,
        container_id: int | None = None,
        email_headers: list[dict[str, Any]] | None = None,
        attachments_data: list[dict[str, Any]] | None = None,
    ) -> tuple[int, str]:
        """Process an email and extract artifacts."""
        self._config = config

        if email_headers:
            for curr_header in email_headers:
                self._external_headers.append(CaseInsensitiveDict(curr_header))

        if (config[PROC_EMAIL_JSON_EXTRACT_ATTACHMENTS]) and (
            attachments_data is not None
        ):
            self._external_attachments = attachments_data

        with contextlib.suppress(Exception):
            self._set_email_id_contains(email_id)

        ret_val, message, results = self._int_process_email(
            rfc822_email, email_id, epoch
        )

        if not ret_val:
            self._del_tmp_dirs()
            return APP_ERROR, message

        try:
            self._parse_results(results, container_id)
        except Exception:
            self._del_tmp_dirs()
            raise

        return APP_SUCCESS, "Email Processed"

    def _save_ingested(
        self, container: dict[str, Any], using_dummy: bool
    ) -> tuple[int, str, int | None]:
        if using_dummy:
            cid = container["id"]
            artifacts = container["artifacts"]
            for artifact in artifacts:
                artifact["container_id"] = cid
            try:
                _ids = self.context.soar.save_artifacts(artifacts)  # type: ignore[attr-defined]
                ret_val, message = APP_SUCCESS, "Success"
                logger.debug(
                    f"save_artifacts returns, value: {ret_val}, reason: {message}"
                )
            except Exception as e:
                ret_val, message = APP_ERROR, str(e)
                logger.debug(f"save_artifacts failed: {e}")
                return ret_val, message, None

            return ret_val, message, cid
        else:
            try:
                cid = self.context.soar.save_container(container)  # type: ignore[attr-defined]
                ret_val, message = APP_SUCCESS, "Success"
                logger.debug(
                    f"save_container (with artifacts) returns, value: {ret_val}, reason: {message}, id: {cid}"
                )
            except Exception as e:
                ret_val, message, cid = APP_ERROR, str(e), None
                logger.debug(f"save_container failed: {e}")

            return ret_val, message, cid

    def _handle_save_ingested(
        self,
        artifacts: list[dict[str, Any]],
        container: dict[str, Any] | None,
        container_id: int | None,
        files: list[dict[str, Any]],
    ) -> None:
        using_dummy = False

        if container_id:
            using_dummy = True
            container = {
                "name": "Dummy Container",
                "dummy": True,
                "id": container_id,
                "artifacts": artifacts,
            }
        elif container:
            container["artifacts"] = artifacts
        else:
            return

        for artifact in [
            x
            for x in container.get("artifacts", [])
            if not x.get("source_data_identifier")
        ]:
            self._set_sdi(artifact)

        if files and container.get("artifacts"):
            container["artifacts"][-1]["run_automation"] = False

        ret_val, message, container_id = self._save_ingested(container, using_dummy)

        if ret_val == APP_ERROR:
            message = f"Failed to save ingested artifacts, error msg: {message}"
            logger.debug(message)
            return

        if not container_id:
            message = "save_container did not return a container_id"
            logger.debug(message)
            return

        vault_ids: list[str] = []
        vault_artifacts_added = 0

        last_file = len(files) - 1
        for i, curr_file in enumerate(files):
            run_automation = i == last_file
            ret_val, added_to_vault = self._handle_file(
                curr_file,
                vault_ids,
                container_id,
                vault_artifacts_added,
                run_automation,
            )

            if added_to_vault:
                vault_artifacts_added += 1

    def _parse_results(
        self, results: list[dict[str, Any]], container_id: int | None = None
    ) -> int:
        container_count = DEFAULT_CONTAINER_COUNT
        results = results[:container_count]

        for result in results:
            if container_id is None:
                container = result.get("container")

                if not container:
                    continue

                container.update(_container_common)

            else:
                container = None

            artifacts = result.get("artifacts", [])
            for _j, artifact in enumerate(artifacts):
                if not artifact:
                    continue

                self._set_sdi(artifact)

            if not artifacts:
                continue

            len_artifacts = len(artifacts)

            for j, artifact in enumerate(artifacts):
                if not artifact:
                    continue

                if (j + 1) == len_artifacts:
                    artifact["run_automation"] = True

                cef_artifact = artifact.get("cef")
                if "parentGuid" in cef_artifact:
                    parent_guid = cef_artifact.pop("parentGuid")
                    if parent_guid in self._guid_to_hash:
                        cef_artifact["parentSourceDataIdentifier"] = self._guid_to_hash[
                            parent_guid
                        ]
                if "emailGuid" in cef_artifact:
                    del cef_artifact["emailGuid"]

            self._handle_save_ingested(
                artifacts, container, container_id, result.get("files", [])
            )

        for result in results:
            if result.get("temp_directory"):
                shutil.rmtree(result["temp_directory"], ignore_errors=True)

        return APP_SUCCESS

    def _add_vault_hashes_to_dictionary(
        self, cef_artifact: dict[str, Any], vault_id: str
    ) -> tuple[int, str]:
        try:
            vault_info_data = self.context.vault.get_attachment(vault_id=vault_id)
        except Exception:
            return APP_ERROR, "Could not retrieve vault file"

        if not vault_info_data:
            return APP_ERROR, "Vault ID not found"

        try:
            metadata = vault_info_data[0].get("metadata")
        except Exception:
            return APP_ERROR, "Failed to get vault item metadata"

        if metadata:
            with contextlib.suppress(Exception):
                cef_artifact["fileHashSha256"] = metadata["sha256"]

            with contextlib.suppress(Exception):
                cef_artifact["fileHashMd5"] = metadata["md5"]

            with contextlib.suppress(Exception):
                cef_artifact["fileHashSha1"] = metadata["sha1"]

        return APP_SUCCESS, "Mapped hash values"

    def _handle_file(
        self,
        curr_file: dict[str, Any],
        vault_ids: list[str],
        container_id: int,
        artifact_id: int,
        run_automation: bool = False,
    ) -> tuple[int, int]:
        file_name = curr_file.get("file_name")

        local_file_path = curr_file["file_path"]

        contains = get_file_contains(local_file_path)

        vault_attach_dict: dict[str, Any] = {}

        if not file_name:
            file_name = Path(local_file_path).name

        logger.debug(f"Vault file name: {file_name}")

        vault_attach_dict[phantom.APP_JSON_ACTION_NAME] = self.context.action_name  # type: ignore[attr-defined]
        vault_attach_dict[phantom.APP_JSON_APP_RUN_ID] = self.context.app_run_id  # type: ignore[attr-defined]

        file_name = decode_uni_string(file_name, file_name)

        try:
            vault_id = self.context.vault.add_attachment(
                container_id=container_id,
                file_location=local_file_path,
                file_name=file_name,
                metadata=vault_attach_dict,
            )
        except Exception as e:
            logger.debug(f"Error adding file to vault: {e}")
            return APP_ERROR, APP_ERROR

        cef_artifact = curr_file.get("meta_info", {})
        cef_artifact.update({"fileName": file_name})

        if vault_id:
            cef_artifact.update(
                {"vaultId": vault_id, "cs6": vault_id, "cs6Label": "Vault ID"}
            )
            self._add_vault_hashes_to_dictionary(cef_artifact, vault_id)

        artifact: dict[str, Any] = {}
        artifact.update(_artifact_common)
        artifact["container_id"] = container_id
        artifact["name"] = "Vault Artifact"
        artifact["cef"] = cef_artifact
        artifact["run_automation"] = run_automation
        if contains:
            artifact["cef_types"] = {"vaultId": contains, "cs6": contains}
        self._set_sdi(artifact)

        if "parentGuid" in cef_artifact:
            parent_guid = cef_artifact.pop("parentGuid")
            cef_artifact["parentSourceDataIdentifier"] = self._guid_to_hash[parent_guid]

        try:
            artifact_id_result = self.context.soar.save_artifact(artifact)  # type: ignore[attr-defined]
            ret_val, status_string = APP_SUCCESS, "Success"
            logger.debug(
                f"save_artifact returns, value: {ret_val}, reason: {status_string}, id: {artifact_id_result}"
            )
        except Exception as e:
            ret_val, status_string = APP_ERROR, str(e)
            logger.debug(f"save_artifact failed: {e}")

        return APP_SUCCESS, ret_val

    def _set_sdi(self, input_dict: dict[str, Any]) -> int:
        input_dict.pop("source_data_identifier", None)

        input_dict_hash = input_dict

        cef = input_dict.get("cef")

        curr_email_guid = None

        if cef is not None and (("parentGuid" in cef) or ("emailGuid" in cef)):
            input_dict_hash = deepcopy(input_dict)
            cef = input_dict_hash["cef"]
            if "parentGuid" in cef:
                del cef["parentGuid"]
            curr_email_guid = cef.get("emailGuid")
            if curr_email_guid is not None:
                del cef["emailGuid"]

        input_dict["source_data_identifier"] = create_dict_hash(input_dict_hash)

        if curr_email_guid:
            self._guid_to_hash[curr_email_guid] = input_dict["source_data_identifier"]

        return APP_SUCCESS

    def _del_tmp_dirs(self) -> None:
        """Remove any tmp_dirs that were created."""
        for tmp_dir in self._tmp_dirs:
            shutil.rmtree(tmp_dir, ignore_errors=True)
