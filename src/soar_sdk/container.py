#!/usr/bin/env python
from typing import Optional, Any, Union


class Container:
    """
    Represents a container to be created during on_poll.

    This class allows users to specify container properties when yielding from an on_poll function.
    """

    def __init__(
        self,
        name: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
        source_data_identifier: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        tags: Optional[Union[list[str], str]] = None,
        owner_id: Optional[Union[int, str]] = None,
        sensitivity: Optional[str] = None,
        artifacts: Optional[list[dict[str, Any]]] = None,
        asset_id: Optional[int] = None,
        close_time: Optional[str] = None,
        custom_fields: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
        due_time: Optional[str] = None,
        end_time: Optional[str] = None,
        ingest_app_id: Optional[int] = None,
        kill_chain: Optional[str] = None,
        role_id: Optional[Union[int, str]] = None,
        run_automation: bool = False,
        start_time: Optional[str] = None,
        open_time: Optional[str] = None,
        tenant_id: Optional[Union[int, str]] = None,
        container_type: Optional[str] = None,
        template_id: Optional[int] = None,
        authorized_users: Optional[list[int]] = None,
        artifact_count: Optional[int] = None,
    ) -> None:
        self.container: dict[str, Any] = {"name": name}

        if label is not None:
            self.container["label"] = label
        if description is not None:
            self.container["description"] = description
        if source_data_identifier is not None:
            self.container["source_data_identifier"] = source_data_identifier
        if severity is not None:
            self.container["severity"] = severity
        if status is not None:
            self.container["status"] = status
        if tags is not None:
            self.container["tags"] = tags
        if owner_id is not None:
            self.container["owner_id"] = owner_id
        if sensitivity is not None:
            self.container["sensitivity"] = sensitivity
        if artifacts is not None:
            self.container["artifacts"] = artifacts
        if asset_id is not None:
            self.container["asset_id"] = asset_id
        if close_time is not None:
            self.container["close_time"] = close_time
        if custom_fields is not None:
            self.container["custom_fields"] = custom_fields
        if data is not None:
            self.container["data"] = data
        if due_time is not None:
            self.container["due_time"] = due_time
        if end_time is not None:
            self.container["end_time"] = end_time
        if ingest_app_id is not None:
            self.container["ingest_app_id"] = ingest_app_id
        if kill_chain is not None:
            self.container["kill_chain"] = kill_chain
        if role_id is not None:
            self.container["role_id"] = role_id
        if run_automation is not None:
            self.container["run_automation"] = run_automation
        if start_time is not None:
            self.container["start_time"] = start_time
        if open_time is not None:
            self.container["open_time"] = open_time
        if tenant_id is not None:
            self.container["tenant_id"] = tenant_id
        if container_type is not None:
            self.container["container_type"] = container_type
        if template_id is not None:
            self.container["template_id"] = template_id
        if authorized_users is not None:
            self.container["authorized_users"] = authorized_users
        if artifact_count is not None:
            self.container["artifact_count"] = artifact_count

        self.container_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the container to a dictionary (needed for save_container).
        """
        return self.container

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        if name in self.container:
            return self.container[name]
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name: str, value: Any) -> None:  # noqa: ANN401
        if name == "container" or name == "container_id":
            super().__setattr__(name, value)
        else:
            if hasattr(self, "container"):
                self.container[name] = value
            else:
                super().__setattr__(name, value)
