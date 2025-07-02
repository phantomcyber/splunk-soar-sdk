import abc
from typing import TypeVar, Generic, Optional
import jinja2 as j2
import ast
from collections.abc import Iterator


ContextT = TypeVar("ContextT")


class Renderer(Generic[ContextT], abc.ABC):
    """
    Abstract base class for rendering code using Jinja2 templates.
    """

    def __init__(
        self, context: ContextT, jinja_env: Optional[j2.Environment] = None
    ) -> None:
        self.context = context
        self.jinja_env = jinja_env or j2.Environment(
            loader=j2.PackageLoader("soar_sdk.code_renderers", "templates"),
            autoescape=j2.select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )

    @abc.abstractmethod
    def render(self) -> str:
        """
        Render the code using the provided context and Jinja2 templates.
        """
        pass


class AstRenderer(Generic[ContextT], abc.ABC):
    """
    Abstract base class for rendering code as an AST (Abstract Syntax Tree).
    """

    def __init__(self, context: ContextT) -> None:
        self.context = context

    @abc.abstractmethod
    def render_ast(self) -> Iterator[ast.stmt]:
        """
        Generate a list of AST nodes for the code to be rendered.
        """
        pass
