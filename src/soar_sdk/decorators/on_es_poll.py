import asyncio
import inspect
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, get_args

from pydantic import ValidationError

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.es_client import ESClient
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.models.container import Container
from soar_sdk.models.finding import Finding
from soar_sdk.params import OnESPollParams
from soar_sdk.types import Action, action_protocol

if TYPE_CHECKING:
    from soar_sdk.app import App


ESPollingYieldType = Finding
ESPollingSendType = int | None


class OnESPollDecorator:
    """Class-based decorator for tagging a function as the special 'on es poll' action."""

    def __init__(self, app: "App") -> None:
        self.app = app

    def __call__(self, function: Callable) -> Action:
        """Decorator for the 'on es poll' action. The decorated function must be a Generator or AsyncGenerator. Only one on_es_poll action is allowed per app.

        Usage:
        The generator should yield a `Finding`. Upon receiving an event from the generator, the SDK will submit the Finding to Splunk Enterprise Security and create a linked SOAR Container.
        The generator should accept a "send type" of `int | None`. When a Finding is successfully delivered to ES and linked to a Container, the SDK will send the Container ID back into the generator. The Container is useful for storing large attachments included with the Finding.
        If the Finding cannot be successfully delivered to ES, the SDK will stop polling and return a failed result for the action run.
        """
        if self.app.actions_manager.get_action("on_es_poll"):
            raise TypeError(
                "The 'on_es_poll' decorator can only be used once per App instance."
            )

        is_generator = inspect.isgeneratorfunction(function)
        is_async_generator = inspect.isasyncgenfunction(function)

        generator_type = inspect.signature(function).return_annotation
        generator_type_args = get_args(generator_type)

        if not (is_generator or is_async_generator) or len(generator_type_args) < 2:
            raise TypeError(
                "The on_es_poll function must be a Generator or AsyncGenerator (use 'yield')."
            )

        yield_type = generator_type_args[0]
        send_type = generator_type_args[1]

        if yield_type != ESPollingYieldType:
            raise TypeError(
                f"@on_es_poll generator should have yield type {ESPollingYieldType}."
            )
        if send_type != ESPollingSendType:
            raise TypeError(
                f"@on_es_poll generator should have send type {ESPollingSendType}."
            )

        action_identifier = "on_es_poll"
        action_name = "on es poll"

        validated_params_class = OnESPollParams
        logger = getLogger()

        @action_protocol
        @wraps(function)
        def inner(
            params: OnESPollParams,
            soar: SOARClient = self.app.soar_client,
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> bool:
            try:
                action_params = validated_params_class.model_validate(params)
            except ValidationError as e:
                logger.info(f"Parameter validation error: {e!s}")
                return self.app._adapt_action_result(
                    ActionResult(status=False, message=f"Invalid parameters: {e!s}"),
                    self.app.actions_manager,
                )
            es = ESClient(params.es_base_url, params.es_session_key)
            kwargs = self.app._build_magic_args(function, soar=soar, **kwargs)
            generator = function(action_params, *args, **kwargs)

            if is_async_generator:

                def polling_step(
                    last_container_id: ESPollingSendType,
                ) -> ESPollingYieldType:
                    return asyncio.run(generator.asend(last_container_id))
            else:

                def polling_step(
                    last_container_id: ESPollingSendType,
                ) -> ESPollingYieldType:
                    return generator.send(last_container_id)

            last_container_id = None
            while True:
                try:
                    item = polling_step(last_container_id)
                except (StopIteration, StopAsyncIteration):
                    return self.app._adapt_action_result(
                        ActionResult(
                            status=True, message="Finding processing complete"
                        ),
                        self.app.actions_manager,
                    )
                except ActionFailure as e:
                    e.set_action_name(action_name)
                    return self.app._adapt_action_result(
                        ActionResult(status=False, message=str(e)),
                        self.app.actions_manager,
                    )
                except Exception as e:
                    self.app.actions_manager.add_exception(e)
                    logger.info(f"Error during finding processing: {e!s}")
                    return self.app._adapt_action_result(
                        ActionResult(status=False, message=str(e)),
                        self.app.actions_manager,
                    )

                if type(item) is not ESPollingYieldType:
                    logger.info(
                        f"Warning: expected {ESPollingYieldType}, got {type(item)}, skipping"
                    )
                    continue
                finding = es.findings.create(item)
                logger.info(f"Created finding {finding.finding_id}")

                container = Container(
                    name=finding.rule_title,
                    description=finding.rule_description,
                    severity=finding.urgency or "medium",
                    status=finding.status,
                    owner_id=finding.owner,
                    sensitivity=finding.disposition,
                    tags=finding.source,
                    external_id=finding.finding_id,
                    data={
                        "security_domain": finding.security_domain,
                        "risk_score": finding.risk_score,
                        "risk_object": finding.risk_object,
                        "risk_object_type": finding.risk_object_type,
                    },
                )
                ret_val, message, last_container_id = (
                    self.app.actions_manager.save_container(container.to_dict())
                )
                logger.info(f"Creating container for finding: {finding.rule_title}")
                if not ret_val:
                    raise ActionFailure(f"Failed to create container: {message}")

        inner.params_class = validated_params_class

        class OnESPollActionMeta(ActionMeta):
            def model_dump(self, *args: object, **kwargs: object) -> dict[str, Any]:
                data = super().model_dump(*args, **kwargs)
                data["output"] = []
                return data

        inner.meta = OnESPollActionMeta(
            action=action_name,
            identifier=action_identifier,
            description=inspect.getdoc(function) or action_name,
            verbose="Callback action for the on_es_poll ingest functionality",
            type="ingest",
            read_only=True,
            parameters=validated_params_class,
            versions="EQ(*)",
        )

        self.app.actions_manager.set_action(action_identifier, inner)
        self.app.actions_manager.supports_es_polling = True
        self.app._dev_skip_in_pytest(function, inner)
        return inner
