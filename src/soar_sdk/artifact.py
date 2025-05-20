#!/usr/bin/env python
from typing import Optional, Dict, Any, Union, List

class Artifact:
    """
    Represents an artifact to be created during on_poll.
    
    This class allows users to create and configure artifacts when yielding from an on_poll function.
    """
    
    def __init__(self, 
                 name: Optional[str] = None,
                 label: Optional[str] = None,
                 description: Optional[str] = None,
                 type: Optional[str] = None,
                 severity: Optional[str] = None,
                 source_data_identifier: Optional[str] = None,
                 container_id: Optional[int] = None,
                 data: Optional[Dict[str, Any]] = None,
                 run_automation: bool = False,
                 owner_id: Optional[Union[int, str]] = None,
                 cef: Optional[Dict[str, Any]] = None,
                 cef_types: Optional[Dict[str, List[str]]] = None,
                 ingest_app_id: Optional[Union[int, str]] = None,
                 tags: Optional[Union[List[str], str]] = None,
                 start_time: Optional[str] = None,
                 end_time: Optional[str] = None,
                 kill_chain: Optional[str] = None) -> None:
        
        self.artifact = {}
        
        if name is not None:
            self.artifact["name"] = name
        if label is not None:
            self.artifact["label"] = label
        if description is not None:
            self.artifact["description"] = description
        if type is not None:
            self.artifact["type"] = type
        if severity is not None:
            self.artifact["severity"] = severity
        if source_data_identifier is not None:
            self.artifact["source_data_identifier"] = source_data_identifier
        if container_id is not None:
            self.artifact["container_id"] = container_id
        if data is not None:
            self.artifact["data"] = data
        if run_automation is not None:
            self.artifact["run_automation"] = run_automation
        if owner_id is not None:
            self.artifact["owner_id"] = owner_id
        if cef is not None:
            self.artifact["cef"] = cef
        if cef_types is not None:
            self.artifact["cef_types"] = cef_types
        if ingest_app_id is not None:
            self.artifact["ingest_app_id"] = ingest_app_id
        if tags is not None:
            self.artifact["tags"] = tags
        if start_time is not None:
            self.artifact["start_time"] = start_time
        if end_time is not None:
            self.artifact["end_time"] = end_time
        if kill_chain is not None:
            self.artifact["kill_chain"] = kill_chain
                
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the artifact to a dictionary (needed for save_artifact).
        """
        return self.artifact
        
    def __getattr__(self, name: str) -> Any:
        if name in self.artifact:
            return self.artifact[name]
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def __setattr__(self, name: str, value: Any) -> None:
        if name == "artifact":
            super().__setattr__(name, value)
        else:
            if hasattr(self, "artifact"):
                self.artifact[name] = value
            else:
                super().__setattr__(name, value)
