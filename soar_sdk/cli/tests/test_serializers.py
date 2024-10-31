from soar_sdk.params import Param, Params

from ..manifests.serializers import ParamsSerializer


def test_params_get_sorted_fields_keys_sorts_by_field_order_value():
    class SampleParams(Params):
        z: str = Param(2, "z param")
        d: str = Param(0, "d param")
        m: str = Param(1, "m param")

    assert ParamsSerializer.get_sorted_fields_keys(SampleParams) == ["d", "m", "z"]


def test_params_field_serialize_with_defaults():
    class SomeParams(Params):
        the_param: str = Param(0, "the_param param")

    assert ParamsSerializer.serialize_field_info(
        SomeParams.__fields__.get("the_param")
    ) == {
        "name": "the_param",
        "description": "the_param param",
        "data_type": "string",
        "contains": [],
        "required": True,
        "primary": True,
        "values_list": [],
        "allow_list": False,
        "default": "",
        "order": 0,
    }


def test_params_serialize_fields_info():
    class SampleParams(Params):
        name: str = Param(
            description="Some Description",  # required, starting with capital
            data_type="string",
            contains=["user name"],
            required=True,
            primary=True,
            values_list=[],
            default="",
            order=0,
            allow_list=False,
        )
        event_id: int = Param(
            description="Some id of the event",
            data_type="string",
            contains=["event id"],
            required=True,
            primary=True,
            values_list=[],
            default="",
            order=1,
            allow_list=False,
        )

    serialized_params = ParamsSerializer.serialize_fields_info(SampleParams)

    expected_params = {
        "name": {
            "name": "name",
            "description": "Some Description",
            "data_type": "string",
            "contains": ["user name"],
            "required": True,
            "primary": True,
            "values_list": [],
            "allow_list": False,
            "default": "",
            "order": 0,
        },
        "event_id": {
            "name": "event_id",
            "description": "Some id of the event",
            "data_type": "string",
            "contains": ["event id"],
            "required": True,
            "primary": True,
            "values_list": [],
            "allow_list": False,
            "default": "",
            "order": 1,
        },
    }

    for param in serialized_params:
        assert serialized_params[param] == expected_params[param]
