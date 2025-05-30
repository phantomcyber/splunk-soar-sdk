"""
URL routing functionality for webhooks.

This module provides a router for mapping URL patterns to handler functions.
"""

import re
from dataclasses import dataclass
from typing import Callable, TypeVar, Generic, Optional
from collections.abc import Sequence

from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse
from soar_sdk.asset import BaseAsset


class RouteConflictError(Exception):
    """Raised when a route conflicts with a previously registered route."""


@dataclass
class Route:
    string_pattern: str
    regex_pattern: re.Pattern
    methods: list[str]
    handler: Callable[[WebhookRequest], WebhookResponse]
    parameter_indices: dict[int, str]


AssetType = TypeVar("AssetType", bound=BaseAsset)


class Router(Generic[AssetType]):
    """
    A router for mapping URL patterns to handler functions.

    URL patterns can include literal components and parameters in the form of <param_name>.
    For example: "/models/<model_id>/properties" would match "/models/123/properties"
    and provide "123" as the value for the "model_id" parameter.
    """

    def __init__(self) -> None:
        self._routes: list[Route] = []

    def add_route(
        self,
        pattern: str,
        handler: Callable[[WebhookRequest], WebhookResponse],
        methods: Optional[Sequence[str]] = None,
    ) -> None:
        """
        Register a new route with the router.

        Args:
            pattern: The URL pattern to match, e.g., "/models/<model_id>/properties"
            handler: The function to call when the pattern matches
            methods: HTTP methods allowed for this route (default: ["GET", "POST"])

        Raises:
            RouteConflictError: If the route conflicts with a previously registered route
        """
        if methods is None:
            methods = ["GET", "POST"]
        else:
            methods = [method.upper() for method in methods]
            for method in methods:
                if method not in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"}:
                    raise ValueError(f"Invalid HTTP method: {method}")

        # Convert URL pattern to regex
        regex_pattern, param_indices = self._pattern_to_regex(pattern)

        # Check for conflicts with existing routes
        for route in self._routes:
            # Check if patterns have the same structure (conflict)
            if self._patterns_conflict(pattern, route.string_pattern):
                raise RouteConflictError(
                    f"Route with pattern '{pattern}' conflicts with existing pattern '{route.string_pattern}'"
                )

        # Add route
        self._routes.append(
            Route(pattern, regex_pattern, methods, handler, param_indices)
        )

    def handle_request(self, request: WebhookRequest[AssetType]) -> WebhookResponse:
        """
        Find a matching route for the request and invoke its handler.

        Args:
            request: The webhook request to handle

        Returns:
            - The response from the matched handler if a route matches and the method is allowed
            - A 405 response if a route matches but the method is not allowed
            - A 404 response if no route matches the request path
        """
        path = request.path

        # Find matching route
        for route in self._routes:
            match = route.regex_pattern.fullmatch(path)

            if match:
                # Check if method is allowed
                if request.method.upper() not in route.methods:
                    return WebhookResponse.json_response(
                        {"error": f"Method {request.method} not allowed"},
                        status_code=405,
                        extra_headers={"Allow": ", ".join(route.methods)},
                    )

                # Extract parameters
                kwargs = {}
                for i, group_name in route.parameter_indices.items():
                    kwargs[group_name] = match.group(i)

                # Call handler
                return route.handler(request, **kwargs)

        # No matching route found
        return WebhookResponse.json_response({"error": "Not found"}, status_code=404)

    def _patterns_conflict(self, pattern1: str, pattern2: str) -> bool:
        """
        Check if two URL patterns conflict with each other.

        Patterns conflict if they have the same structure (same number of segments
        and the same segments are parameters vs literals), regardless of parameter names.

        Args:
            pattern1: The first URL pattern
            pattern2: The second URL pattern

        Returns:
            True if the patterns conflict, False otherwise
        """

        # Split into parts
        parts1 = pattern1.removeprefix("/").removesuffix("/").split("/")
        parts2 = pattern2.removeprefix("/").removesuffix("/").split("/")

        # If different number of segments, no conflict
        if len(parts1) != len(parts2):
            return False

        # Check each segment
        for part1, part2 in zip(parts1, parts2):
            is_param1 = part1.startswith("<") and part1.endswith(">")
            is_param2 = part2.startswith("<") and part2.endswith(">")

            # If one is a parameter and the other isn't, no conflict
            if is_param1 != is_param2:
                return False

            # If both are literals and they're different, no conflict
            if not is_param1 and not is_param2 and part1 != part2:
                return False

        # If we got here, the patterns have the same structure
        return True

    def _pattern_to_regex(self, pattern: str) -> tuple[re.Pattern, dict[int, str]]:
        """
        Convert a URL pattern to a regex pattern and extract parameter names.

        Args:
            pattern: The URL pattern to convert

        Returns:
            A tuple of (compiled regex pattern, dict mapping group index to param name)
        """
        # Split the pattern into parts
        parts = pattern.removeprefix("/").removesuffix("/").split("/")

        regex_parts = []
        param_indices = {}

        # Track the regex capture group index separately
        group_index = 1

        for part in parts:
            if part.startswith("<") and part.endswith(">"):
                # Parameter
                param_name = part[1:-1]
                regex_parts.append(r"([^/]+)")
                param_indices[group_index] = param_name
                group_index += 1
            else:
                # Literal
                regex_parts.append(re.escape(part))

        # Combine regex parts
        regex_pattern = "^" + "/".join(regex_parts) + "$"
        return re.compile(regex_pattern), param_indices
