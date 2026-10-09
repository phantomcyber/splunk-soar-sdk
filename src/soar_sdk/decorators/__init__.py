"""This module provides class-based decorators for SOAR app development."""

__lazy_modules__ = {
    "soar_sdk.decorators.action",
    "soar_sdk.decorators.make_request",
    "soar_sdk.decorators.on_es_poll",
    "soar_sdk.decorators.on_poll",
    "soar_sdk.decorators.test_connectivity",
    "soar_sdk.decorators.view_handler",
    "soar_sdk.decorators.webhook",
}


from .action import ActionDecorator
from .make_request import MakeRequestDecorator
from .on_es_poll import OnESPollDecorator
from .on_poll import OnPollDecorator
from .test_connectivity import ConnectivityTestDecorator
from .view_handler import ViewHandlerDecorator
from .webhook import WebhookDecorator

__all__ = [
    "ActionDecorator",
    "ConnectivityTestDecorator",
    "MakeRequestDecorator",
    "OnESPollDecorator",
    "OnPollDecorator",
    "ViewHandlerDecorator",
    "WebhookDecorator",
]
