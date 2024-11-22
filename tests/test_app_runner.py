from unittest import mock


def test_app_runner(simple_runner):
    simple_runner.parse_args = mock.Mock()
    simple_runner.login = mock.Mock()
    simple_runner.load_input_test_json = mock.Mock(return_value=dict())
    simple_runner.app.handle = mock.Mock(return_value="{}")

    simple_runner.run()

    assert simple_runner.parse_args.called == 1
    assert simple_runner.login.call_count == 1
    assert simple_runner.load_input_test_json.call_count == 1
    assert simple_runner.app.handle.call_count == 1


def test_app_runner_contains_session_id(simple_runner):
    simple_runner.parse_args = mock.Mock()
    simple_runner.login = mock.Mock()
    simple_runner.session_id = "some_session_id"
    simple_runner.load_input_test_json = mock.Mock(return_value=dict())
    simple_runner.app.handle = mock.Mock(return_value="{}")

    simple_runner.run()

    assert "user_session_token" in simple_runner.app.handle.call_args[0][0]
    assert "some_session_id" in simple_runner.app.handle.call_args[0][0]
