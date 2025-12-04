import inspect
from collections.abc import Callable, Iterator
from functools import wraps
from typing import TYPE_CHECKING, Any

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.async_utils import run_async_if_needed
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.models.attachment_input import AttachmentInput
from soar_sdk.models.container import Container
from soar_sdk.models.finding import Finding
from soar_sdk.params import OnESPollParams
from soar_sdk.types import Action, action_protocol

if TYPE_CHECKING:
    from soar_sdk.app import App


class OnESPollDecorator:
    """Class-based decorator for tagging a function as the special 'on es poll' action."""

    def __init__(self, app: "App") -> None:
        self.app = app

    def __call__(self, function: Callable) -> Action:
        """Decorator for the 'on es poll' action.

        The decorated function must be a generator (using yield) or return an Iterator that yields tuples of (Finding, list[AttachmentInput]). Only one on_es_poll action is allowed per app.

        Usage:
        Each yielded tuple creates a Container from the Finding metadata. All AttachmentInput items in the list are added as vault attachments to that container.
        """
        if self.app.actions_manager.get_action("on_es_poll"):
            raise TypeError(
                "The 'on_es_poll' decorator can only be used once per App instance."
            )

        is_generator = inspect.isgeneratorfunction(function)
        is_async_generator = inspect.isasyncgenfunction(function)
        signature = inspect.signature(function)

        has_iterator_return = (
            signature.return_annotation != inspect.Signature.empty
            and getattr(signature.return_annotation, "__origin__", None) is Iterator
        )

        if not (is_generator or is_async_generator or has_iterator_return):
            raise TypeError(
                "The on_es_poll function must be a generator (use 'yield') or return an Iterator."
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
                try:
                    action_params = validated_params_class.parse_obj(params)
                except Exception as e:
                    logger.info(f"Parameter validation error: {e!s}")
                    return self.app._adapt_action_result(
                        ActionResult(
                            status=False, message=f"Invalid parameters: {e!s}"
                        ),
                        self.app.actions_manager,
                    )

                kwargs = self.app._build_magic_args(function, soar=soar, **kwargs)

                result = function(action_params, *args, **kwargs)
                result = run_async_if_needed(result)

                for item in result:
                    if not isinstance(item, tuple) or len(item) != 2:
                        logger.info(
                            f"Warning: Expected tuple of (Finding, list[AttachmentInput]), got: {type(item)}"
                        )
                        continue

                    finding, attachments = item

                    if not isinstance(finding, Finding):
                        logger.info(
                            f"Warning: First element must be Finding, got: {type(finding)}"
                        )
                        continue

                    if not isinstance(attachments, list):
                        logger.info(
                            f"Warning: Second element must be list[AttachmentInput], got: {type(attachments)}"
                        )
                        continue

                    for attachment in attachments:
                        if not isinstance(attachment, AttachmentInput):
                            logger.info(
                                f"Warning: Attachment must be AttachmentInput, got: {type(attachment)}"
                            )
                            break
                    else:
                        finding_dict = finding.to_dict()
                        logger.info(
                            f"Processing finding: {finding_dict.get('rule_title', 'Unnamed finding')}"
                        )

                        # Send finding to ES and get finding_id back
                        finding_id = self.app.actions_manager.send_finding_to_es(
                            finding_dict
                        )

                        container = Container(
                            name=finding.rule_title,
                            description=finding.rule_description,
                            severity=finding.urgency or "medium",
                            status=finding.status,
                            owner_id=finding.owner,
                            sensitivity=finding.disposition,
                            tags=finding.source,
                            external_id=finding_id,
                            data={
                                "security_domain": finding.security_domain,
                                "risk_score": finding.risk_score,
                                "risk_object": finding.risk_object,
                                "risk_object_type": finding.risk_object_type,
                            },
                        )

                        ret_val, message, container_id = (
                            self.app.actions_manager.save_container(container.to_dict())
                        )
                        logger.info(
                            f"Creating container for finding: {finding.rule_title}"
                        )

                        if not ret_val:
                            logger.info(f"Failed to create container: {message}")
                            continue

                        for attachment in attachments:
                            try:
                                if attachment.file_content is not None:
                                    vault_id = soar.vault.create_attachment(
                                        container_id=container_id,
                                        file_content=attachment.file_content,
                                        file_name=attachment.file_name,
                                        metadata=attachment.metadata,
                                    )
                                else:
                                    vault_id = soar.vault.add_attachment(
                                        container_id=container_id,
                                        file_location=attachment.file_location,
                                        file_name=attachment.file_name,
                                        metadata=attachment.metadata,
                                    )
                                logger.info(
                                    f"Added attachment {attachment.file_name} with vault_id: {vault_id}"
                                )
                            except Exception as e:
                                logger.info(
                                    f"Failed to add attachment {attachment.file_name}: {e!s}"
                                )

                return self.app._adapt_action_result(
                    ActionResult(status=True, message="Finding processing complete"),
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
        self.app._dev_skip_in_pytest(function, inner)
        return inner
