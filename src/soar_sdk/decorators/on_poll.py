import inspect
from functools import wraps
from typing import Callable, Any
from collections.abc import Iterator

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.params import OnPollParams
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.types import Action, action_protocol
from soar_sdk.exceptions import ActionFailure
from soar_sdk.async_utils import run_async_if_needed
from soar_sdk.logging import getLogger


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from soar_sdk.app import App


class OnPollDecorator:
    """
    Class-based decorator for on_poll functionality.
    """

    def __init__(self, app: "App") -> None:
        self.app = app

    def __call__(self, function: Callable) -> Action:
        """
        Decorator for the on_poll action.

        The decorated function must be a generator (using yield) or return an Iterator that yields Container and/or Artifact objects. Only one on_poll action is allowed per app.

        Usage:
        If a Container is yielded first, all subsequent Artifacts will be added to that container unless they already have a `container_id`.
        If an `Artifact` is yielded without a container and no `container_id` is set, it will be skipped.
        """
        if self.app.actions_manager.get_action("on_poll"):
            raise TypeError(
                "The 'on_poll' decorator can only be used once per App instance."
            )

        # Check if function is generator function or has a return type annotation of iterator
        is_generator = inspect.isgeneratorfunction(function)
        is_async_generator = inspect.isasyncgenfunction(function)
        signature = inspect.signature(function)
        has_iterator_return = False

        # Check if the return annotation is an Iterator type
        if (
            signature.return_annotation != inspect.Signature.empty
            and hasattr(signature.return_annotation, "__origin__")
            and signature.return_annotation.__origin__ is Iterator
        ):
            has_iterator_return = True

        if not (is_generator or is_async_generator or has_iterator_return):
            raise TypeError(
                "The on_poll function must be a generator (use 'yield') or return an Iterator."
            )

        action_identifier = "on_poll"
        action_name = "on poll"

        # Use OnPollParams for on_poll actions
        validated_params_class = OnPollParams
        logger = getLogger()

        @action_protocol
        @wraps(function)
        def inner(
            params: OnPollParams,
            client: SOARClient = self.app.soar_client,
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> bool:
            # Lazy imports to avoid circular dependencies
            from soar_sdk.models.container import Container
            from soar_sdk.models.artifact import Artifact

            try:
                # Validate poll params
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

                kwargs = self.app._build_magic_args(function, client=client, **kwargs)

                result = function(action_params, *args, **kwargs)
                result = run_async_if_needed(result)

                # Check if container_id is provided in params
                container_id = getattr(params, "container_id", None)
                container_created = False

                for item in result:
                    # Check if the item is a Container
                    if isinstance(item, Container):
                        # TODO: Change save_container for incorporation with container.create()
                        container = item.to_dict()  # Convert for saving
                        ret_val, message, cid = self.app.actions_manager.save_container(
                            container
                        )
                        logger.info(f"Creating container: {container['name']}")

                        if ret_val:
                            container_id = cid
                            container_created = True
                            item.container_id = container_id

                        # Covered by test_on_poll::test_on_poll_yields_container_duplicate, but branch coverage detection on generator functions is wonky
                        if (
                            "duplicate container found" in message.lower()
                        ):  # pragma: no cover
                            logger.info(
                                "Duplicate container found, reusing existing container"
                            )

                        continue

                    # Check for Artifact
                    if not isinstance(item, Artifact):
                        logger.info(
                            f"Warning: Item is not a Container or Artifact, skipping: {item}"
                        )
                        continue

                    artifact_dict = item.to_dict()  # Convert for saving

                    if (
                        not container_id
                        and not container_created
                        and "container_id" not in artifact_dict
                    ):
                        # No container for this artifact
                        logger.info(
                            f"Warning: Artifact has no container, skipping: {item}"
                        )
                        continue

                    if container_id and "container_id" not in artifact_dict:
                        # Set the container_id
                        artifact_dict["container_id"] = container_id
                        item.container_id = container_id

                    # TODO: Change save_artifact for incorporation with artifact.create()
                    self.app.actions_manager.save_artifacts([artifact_dict])
                    logger.info(
                        f"Added artifact: {artifact_dict.get('name', 'Unnamed artifact')}"
                    )

                return self.app._adapt_action_result(
                    ActionResult(status=True, message="Polling complete"),
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
                logger.info(f"Error during polling: {e!s}")
                return self.app._adapt_action_result(
                    ActionResult(status=False, message=str(e)),
                    self.app.actions_manager,
                )

        inner.params_class = validated_params_class

        # Custom ActionMeta class for on_poll (has no output)
        class OnPollActionMeta(ActionMeta):
            def dict(self, *args: object, **kwargs: object) -> dict[str, Any]:
                data = super().dict(*args, **kwargs)
                # Poll actions have no output
                data["output"] = []
                return data

        inner.meta = OnPollActionMeta(
            action=action_name,
            identifier=action_identifier,
            description=inspect.getdoc(function) or action_name,
            verbose="Callback action for the on_poll ingest functionality",
            type="ingest",
            read_only=True,
            parameters=validated_params_class,
            versions="EQ(*)",
        )

        self.app.actions_manager.set_action(action_identifier, inner)
        self.app._dev_skip_in_pytest(function, inner)
        return inner
