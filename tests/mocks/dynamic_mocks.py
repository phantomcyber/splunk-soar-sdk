from unittest import mock


class ArgReturnMock(mock.Mock):
    def __call__(self, *args, **kwargs):
        super_result = super().__call__(*args, **kwargs)
        if args:
            return args[0]
        return super_result
