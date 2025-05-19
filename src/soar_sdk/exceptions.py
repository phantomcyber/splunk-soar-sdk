from typing import Optional


class ActionFailure(Exception):
    """Exception raised when an action fails to execute successfully."""

    def __init__(self, message: str, action_name: Optional[str] = None) -> None:
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


__all__ = ["ActionFailure", "AssetMisconfiguration"]
