class ActionFailure(Exception):
    """Exception raised when an action fails to execute successfully."""

    def __init__(self, message: str, action_name: str | None = None) -> None:
        self.message = message
        self.action_name = action_name
        super().__init__(self.message)

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


class AttachmentApiError(ActionFailure):
    """Exception raised when the attachment runtime bridge fails.

    SDK-generated errors use fixed messages without retaining the upstream
    exception as ``__cause__`` or ``__context__``.
    """

    def __str__(self) -> str:
        """Return a formatted error message."""
        return (
            f"Attachment API error in {self.action_name}: {self.message}"
            if self.action_name
            else f"Attachment API error: {self.message}"
        )


class AttachmentUploadError(AttachmentApiError):
    """A sanitized upload failure with a code, attachment ID and HTTP status.

    ``status_code`` is absent if no HTTP response was received. ``attachment_id``
    is absent if the supplied target was invalid. No upload is retried.
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        attachment_id: str | None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.attachment_id = attachment_id
        self.status_code = status_code


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
    "AttachmentApiError",
    "AttachmentUploadError",
    "SoarAPIError",
]
