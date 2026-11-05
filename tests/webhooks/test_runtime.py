import os

import pytest

from soar_sdk.webhooks._runtime import capture_native_stdout


def test_capture_restores_stdout_when_flush_fails(mocker, capfd):
    libc = mocker.patch("soar_sdk.webhooks._runtime.ctypes.CDLL").return_value
    libc.fflush.side_effect = [0, RuntimeError("flush failure")]

    with pytest.raises(RuntimeError, match="flush failure"), capture_native_stdout():
        os.write(1, b"native-secret-canary")

    os.write(1, b"stdout restored")
    output = capfd.readouterr()
    assert output.out == "stdout restored"
    assert output.err == ""


def test_capture_supports_nested_calls(capfd):
    with capture_native_stdout():
        os.write(1, b"outer secret")
        with capture_native_stdout():
            os.write(1, b"inner secret")
        os.write(1, b"outer secret after nested call")

    os.write(1, b"stdout restored")
    output = capfd.readouterr()
    assert output.out == "stdout restored"
    assert "secret" not in output.err
    assert output.err.count("bytes of native stdout") == 2
