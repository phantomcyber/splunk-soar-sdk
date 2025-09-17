from datetime import datetime, timedelta, timezone
import re

import pytest
from jinja2 import Environment
from soar_sdk.views import template_filters


def test_widget_uuid_format_and_length():
    val = template_filters.widget_uuid()
    assert re.match(r"^widget_[0-9a-f]{32}$", val)


def test_widget_uuid_is_unique():
    assert template_filters.widget_uuid() != template_filters.widget_uuid()


def test_datetime_minutes_conversion():
    td = timedelta(days=1, hours=2, minutes=30)
    assert template_filters.datetime_minutes(td) == 24 * 60 + 2 * 60 + 30


def test_human_datetime_relative():
    now = datetime.now(timezone.utc)
    past = now - timedelta(days=1, hours=2)
    result = template_filters.human_datetime(past, relative=True)
    assert result == "a day ago"


def test_human_datetime_absolute():
    dt = datetime(2023, 1, 15, 14, 30, tzinfo=timezone.utc)
    result = template_filters.human_datetime(dt, relative=False)
    assert result == "Jan 15, 2023 2:30 pm"


def test_human_timedelta():
    td = timedelta(days=2, hours=3)
    result = template_filters.human_timedelta(td)
    assert result == "2 days"


def test_sorteditems():
    d = {"b": 2, "a": 1, "c": 3}
    result = template_filters.sorteditems(d)
    assert result == [("a", 1), ("b", 2), ("c", 3)]


def test_batch_function():
    data = range(10)
    batched = list(template_filters.batch(data, 3))
    assert batched == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]


def test_dict_batch_function():
    data = {"a": 1, "b": 2, "c": 3, "d": 4}
    batched = list(template_filters.dict_batch(data, 2))
    assert batched == [[("a", 1), ("b", 2)], [("c", 3), ("d", 4)]]


def test_remove_empty():
    data = {"a": 1, "b": None, "c": "", "d": 4}
    cleaned = template_filters.remove_empty(data)
    assert cleaned == {"a": 1, "d": 4}


def test_by_key():
    data = {"a": 1, "b": 2}
    assert template_filters.by_key(data, "a") == 1
    assert template_filters.by_key(data, "c") == ""


def test_by_nested_key():
    data = {"a": {"b": {"c": 3}}}
    assert template_filters.by_nested_key(data, "a b") == {"c": 3}
    assert template_filters.by_nested_key(data, "a d") == ""
    assert template_filters.by_nested_key(data, "b c") is None


def test_is_list():
    assert template_filters.is_list([1, 2, 3]) is True
    assert template_filters.is_list("not a list") is False


def test_typeof():
    assert template_filters.typeof(123) is int
    assert template_filters.typeof("string") is str
    assert template_filters.typeof([1, 2, 3]) is list


def test_safe_intcomma():
    assert template_filters.safe_intcomma(1000000) == "1,000,000"
    assert template_filters.safe_intcomma("not a number") == "not a number"


def test_hash_function():
    assert (
        template_filters.hash_function("test", "abc")
        == "c7cb2b81ccbb686eaefafbfbcf61334fb75f8e5dcb3de8b86fec53ad1a5dd013c0c4c9cc3af7c59aed2afab59dd463f6a84d9531f46e2efeb3681bd79bf57a37"
    )


def test_startswith():
    assert template_filters.startswith("hello world", "hello") is True
    assert template_filters.startswith("hello world", "world") is False


def test_getattribute():
    class TestObj:
        def __init__(self):
            self.attr1 = "value1"
            self.attr2 = 123

    obj = TestObj()
    assert template_filters.getattribute(obj, "attr1") == "value1"
    assert template_filters.getattribute(obj, "attr2") == 123
    assert template_filters.getattribute(obj, "attr3") == ""


@pytest.mark.parametrize(
    "given,expected",
    [
        ("Hello World!", "Hello_World"),
        ("  Multiple   Spaces  ", "__Multiple___Spaces__"),
        ("Special_Characters*&^%$#@!", "Special_Characters"),
    ],
)
def test_superslug(given, expected):
    assert template_filters.superslug(given) == expected


def test_sformat():
    assert template_filters.sformat("Hello, %s!", "World") == "Hello, World!"
    assert template_filters.sformat("Value: %d", 123) == "Value: 123"


def test_jslist():
    assert template_filters.jslist([1, 2, 3]) == "['1','2','3']"
    assert template_filters.jslist([]) == "[]"
    assert template_filters.jslist(["a", "b", "c"]) == "['a','b','c']"


def test_to_json():
    data = {"a": 1, "b": 2}
    assert template_filters.to_json(data) == '{"a": 1, "b": 2}'


@pytest.mark.parametrize(
    "given,expected",
    [
        (-10, 10),
        (5.5, 5.5),
        (0, 0),
    ],
)
def test_absval(given, expected):
    assert template_filters.absval(given) == expected


def test_commasplit():
    assert template_filters.commasplit("a,b,c,d", 2) == "c"
    assert template_filters.commasplit("one,two,three", 0) == "one"


def test_slashsplit():
    assert template_filters.slashsplit("a/b/c") == ["a", "b", "c"]
    assert template_filters.slashsplit("/leading/slash/") == [
        "",
        "leading",
        "slash",
        "",
    ]


def test_strip_tenant_id():
    data = {"tenant_key": "tenant123_extra_info", "other_key": "no_tenant"}
    assert template_filters.strip_tenant_id(data, "tenant_key") == "tenant123"
    assert template_filters.strip_tenant_id(data, "other_key") == "no"
    assert template_filters.strip_tenant_id(data, "missing_key") == ""


@pytest.mark.parametrize(
    "dirty,cleaned",
    [
        (
            '<script>alert("xss")</script><p>Safe Content</p>',
            '&lt;script&gt;alert("xss")&lt;/script&gt;&lt;p&gt;Safe Content&lt;/p&gt;',
        ),
        ("<b>Bold</b> and <i>Italic</i>", "<b>Bold</b> and <i>Italic</i>"),
        (
            '<a href="http://example.com" onclick="evil()">Link</a>',
            '<a href="http://example.com">Link</a>',
        ),
    ],
)
def test_bleach_clean(dirty, cleaned):
    result = template_filters.bleach_clean(dirty)
    assert result == cleaned


def test_setup_jinja_env():
    env = Environment()
    env = template_filters.setup_jinja_env(env)

    # Check if a filter is added
    assert "human_datetime" in env.filters
    # Check if a global is added
    assert "widget_uuid" in env.globals
