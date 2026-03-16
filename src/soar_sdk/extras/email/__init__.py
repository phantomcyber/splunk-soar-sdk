from soar_sdk.extras.email.base import EmailData, extract_email_data
from soar_sdk.extras.email.outlook import OutlookEmailData, extract_outlook_email_data
from soar_sdk.extras.email.processor import EmailProcessor, ProcessEmailContext
from soar_sdk.extras.email.rfc5322 import RFC5322EmailData, extract_rfc5322_email_data

__all__ = [
    "EmailData",
    "EmailProcessor",
    "OutlookEmailData",
    "ProcessEmailContext",
    "RFC5322EmailData",
    "extract_email_data",
    "extract_outlook_email_data",
    "extract_rfc5322_email_data",
]
