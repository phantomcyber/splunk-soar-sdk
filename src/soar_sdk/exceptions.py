__lazy_modules__ = {"soar_sdk.action_results", "typing"}

from typing import Any

from soar_sdk.action_results import ActionOutput, ActionResult


class ActionFailure(Exception):
    """An expected action failure, optionally carrying explicit partial results.

    Args:
        message: Explanation of the failure.
        action_name: Optional action name; set automatically by the SDK.
        data: Explicit partial results or vendor error objects. Typed outputs use
            the same serialization as successful results.
        summary: Failure-specific summary, replacing any current action summary.
            None uses the current action summary; an empty dict overrides it.
    """

    def __init__(
        self,
        message: str,
        action_name: str | None = None,
        *,
        data: list[ActionOutput | dict[str, Any]] | None = None,
        summary: ActionOutput | dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.action_name = action_name
        self.data = data
        self.summary = summary
        super().__init__(self.message)

    def _to_action_result(
        self, parameters: dict[str, Any], summary: ActionOutput | None
    ) -> ActionResult:
        result = ActionResult(status=False, message=str(self), param=parameters)
        for item in self.data or []:
            result.add_data(
                item.model_dump(by_alias=True)
                if isinstance(item, ActionOutput)
                else item
            )
        failure_summary = self.summary if self.summary is not None else summary
        if failure_summary is not None:
            result.set_summary(
                failure_summary.model_dump(by_alias=True)
                if isinstance(failure_summary, ActionOutput)
                else failure_summary
            )
        return result

    def set_action_name(self, action_name: str) -> None:
        """Set the name of the action that failed."""
        self.action_name = action_name

    def __str__(self) -> str:
        """Return a formatted error message."""
        return (
            f"Action failure in {self.action_name}: {self.message}"
            if self.action_name
            else f"Action failure: {self.message}"
        )


class AssetMisconfiguration(ActionFailure):
    """Exception raised when an asset is misconfigured."""

    def __str__(self) -> str:
        """Return a formatted error message."""
        return (
            f"Asset misconfiguration in {self.action_name}: {self.message}"
            if self.action_name
            else f"Asset misconfiguration: {self.message}"
        )


class SoarAPIError(ActionFailure):
    """Exception raised when there is an error with the SOAR REST API."""

    def __str__(self) -> str:
        """Return a formatted error message."""
        return (
            f"SOAR REST API error in {self.action_name}: {self.message}"
            if self.action_name
            else f"SOAR REST API error: {self.message}"
        )


class ActionRegistrationError(Exception):
    """Exception raised when there is an error registering an action."""

    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__(f"Error registering action: {action}")


class AppContextRequired(Exception):
    """Exception raised when trying to access certain features outside the proper context."""

    def __init__(self) -> None:
        super().__init__(
            "This feature is only available in the context of an action run or webhook handler."
        )


__all__ = [
    "ActionFailure",
    "ActionRegistrationError",
    "AssetMisconfiguration",
    "SoarAPIError",
]
