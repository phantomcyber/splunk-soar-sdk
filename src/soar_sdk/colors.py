class ANSIColor:
    def __init__(self, color_enabled: bool) -> None:
        self._color_enabled: bool = color_enabled
        self._colors: dict[str, str] = {
            "RESET": "\033[0m",
            "DIM": "\033[2m",
            "RED": "\033[31m",
            "BOLD_RED": "\033[1;31m",
            "BOLD_UNDERLINE_RED": "\033[1;4;31m",
            "GREEN": "\033[32m",
            "YELLOW": "\033[33m",
            "BLUE": "\033[34m",
            "MAGENTA": "\033[35m",
        }

    def __getattr__(self, name: str) -> str:
        if name in self._colors:
            return self._get_color(name)
        else:
            raise AttributeError

    def _get_color(self, name: str) -> str:
        if not self._color_enabled:
            return ""
        return self._colors[name]
