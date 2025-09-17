import typing
from importlib import import_module

if typing.TYPE_CHECKING:
    from .commondao import (
        Commondao,
        Paged,
        QueryDict,
        RowDict,
        connect,
        is_query_dict,
        is_row_dict,
    )
    from .error import (
        EmptyPrimaryKeyError,
        MissingParamError,
        NotFoundError,
        NotTableError,
        TooManyResultError,
    )

__all__ = (
    "Commondao",
    "NotFoundError",
    "NotTableError",
    "MissingParamError",
    "TooManyResultError",
    "EmptyPrimaryKeyError",
    "Paged",
    "QueryDict",
    "RowDict",
    "connect",
    "is_query_dict",
    "is_row_dict",
)

# A mapping of {<member name>: (package, <module name>)} defining dynamic imports
_dynamic_imports: 'dict[str, tuple[str|None, str]]' = {
    "Commondao": (__name__, ".commondao"),
    "NotFoundError": (__name__, ".error"),
    "NotTableError": (__name__, ".error"),
    "MissingParamError": (__name__, ".error"),
    "TooManyResultError": (__name__, ".error"),
    "EmptyPrimaryKeyError": (__name__, ".error"),
    "Paged": (__name__, ".commondao"),
    "QueryDict": (__name__, ".commondao"),
    "RowDict": (__name__, ".commondao"),
    "connect": (__name__, ".commondao"),
    "is_query_dict": (__name__, ".commondao"),
    "is_row_dict": (__name__, ".commondao"),
}


def __getattr__(attr_name: str) -> object:
    dynamic_attr = _dynamic_imports.get(attr_name)
    if dynamic_attr is None:
        raise AttributeError(f"module '{__name__}' has no attribute '{attr_name}'")

    package, module_name = dynamic_attr

    if module_name == '__module__':
        result = import_module(f'.{attr_name}', package=package)
        globals()[attr_name] = result
        return result
    else:
        if module_name.startswith('.'):
            module = import_module(module_name, package=package)
        else:
            module = import_module(module_name, package=package)
        result = getattr(module, attr_name)
        g = globals()
        for k, (_, v_module_name) in _dynamic_imports.items():
            if v_module_name == module_name:
                g[k] = getattr(module, k)
        return result


def __dir__() -> 'list[str]':
    return list(__all__)
