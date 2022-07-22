import os
from typing import Any
from typing import Callable
from typing import Dict
from typing import Generic
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
from typing import TypeVar
from typing import Union
from typing import cast
import warnings


class NoDefaultType(object):
    def __str__(self):
        return ""


NoDefault = NoDefaultType()
DeprecationInfo = Tuple[str, str, str]


T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

MapType = Union[Callable[[str], V], Callable[[str, str], Tuple[K, V]]]
HelpInfo = Tuple[str, str, str, str]


def _normalized(name):
    # type: (str) -> str
    return name.upper().replace(".", "_").rstrip("_")


def _check_type(value, _type):
    # type: (Any, Union[object, Type[T]]) -> bool
    if hasattr(_type, "__origin__"):
        return isinstance(value, _type.__args__)  # type: ignore[attr-defined,union-attr]

    return isinstance(value, _type)  # type: ignore[arg-type]


class EnvVariable(Generic[T]):
    def __init__(
        self,
        type,  # type: Union[object, Type[T]]
        name,  # type: str
        parser=None,  # type: Optional[Callable[[str], T]]
        validator=None,  # type: Optional[Callable[[T], None]]
        map=None,  # type: Optional[MapType]
        default=NoDefault,  # type: Union[T, NoDefaultType]
        deprecations=None,  # type: Optional[List[DeprecationInfo]]
        help=None,  # type: Optional[str]
        help_type=None,  # type: Optional[str]
        help_default=None,  # type: Optional[str]
    ):
        # type: (...) -> None
        if hasattr(type, "__origin__") and type.__origin__ is Union:  # type: ignore[attr-defined,union-attr]
            if not isinstance(default, type.__args__):  # type: ignore[attr-defined,union-attr]
                raise TypeError(
                    "default must be either of these types {}".format(type.__args__)  # type: ignore[attr-defined,union-attr]
                )
        elif default is not NoDefault and not isinstance(default, type):  # type: ignore[arg-type]
            raise TypeError("default must be of type {}".format(type))

        self.type = type
        self.name = name
        self.parser = parser
        self.validator = validator
        self.map = map
        self.default = default
        self.deprecations = deprecations

        self.help = help
        self.help_type = help_type
        self.help_default = help_default

    def _retrieve(self, env, prefix):
        # type: (Env, str) -> T
        source = env.source

        full_name = prefix + _normalized(self.name)
        raw = source.get(full_name)
        if raw is None and self.deprecations:
            for name, deprecated_when, removed_when in self.deprecations:
                full_deprecated_name = prefix + _normalized(name)
                raw = source.get(full_deprecated_name)
                if raw is not None:
                    deprecated_when_message = (
                        " in version %s" % deprecated_when
                        if deprecated_when is not None
                        else ""
                    )
                    removed_when_message = (
                        " and will be removed in version %s" % removed_when
                        if removed_when is not None
                        else ""
                    )
                    warnings.warn(
                        "%s has been deprecated%s%s. Use %s instead"
                        % (
                            full_deprecated_name,
                            deprecated_when_message,
                            removed_when_message,
                            full_name,
                        ),
                        DeprecationWarning,
                    )
                    break

        if raw is None:
            if not isinstance(self.default, NoDefaultType):
                return self.default

            raise KeyError("{} is not set".format(full_name))

        if self.parser is not None:
            parsed = self.parser(raw)
            if not _check_type(parsed, self.type):
                raise TypeError(
                    "parser returned type {} instead of {}".format(
                        type(parsed), self.type
                    )
                )
            return parsed

        if self.type is bool:
            return cast(T, raw.lower() in env.__truthy__)
        elif self.type in (list, tuple, set):
            collection = raw.split(env.__item_separator__)
            return cast(T, self.type(collection if self.map is None else map(self.map, collection)))  # type: ignore[call-arg,arg-type,operator]
        elif self.type is dict:
            d = dict(
                _.split(env.__value_separator__, 1)
                for _ in raw.split(env.__item_separator__)
            )
            if self.map is not None:
                d = dict(self.map(*_) for _ in d.items())
            return cast(T, d)

        if _check_type(raw, self.type):
            return cast(T, raw)

        if hasattr(self.type, "__origin__") and self.type.__origin__ is Union:  # type: ignore[attr-defined,union-attr]
            for t in self.type.__args__:  # type: ignore[attr-defined,union-attr]
                try:
                    return cast(T, t(raw))
                except TypeError:
                    pass

        return self.type(raw)  # type: ignore[call-arg,operator]

    def __call__(self, env, prefix):
        # type: (Env, str) -> T
        value = self._retrieve(env, prefix)

        if self.validator is not None:
            self.validator(value)

        return value


class DerivedVariable(Generic[T]):
    def __init__(self, type, derivation):
        # type: (Type[T], Callable[[Env], T]) -> None
        self.type = type
        self.derivation = derivation

    def __call__(self, env):
        # type: (Env) -> T
        value = self.derivation(env)
        if not _check_type(value, self.type):
            raise TypeError(
                "derivation returned type {} instead of {}".format(
                    type(value), self.type
                )
            )
        return value


class Env(object):
    """Env base class.

    This class is meant to be subclassed. The configuration is declared by using
    the ``Env.var`` and ``Env.der`` class methods. The former declares a mapping
    between attributes of the instance of the subclass with the environment
    variables. The latter declares derived attributes that are computed using
    a given derivation function.

    If variables share a common prefix, this can be specified with the
    ``__prefix__`` class attribute. Any dots in the prefix or the variable names
    will be replaced with underscores. The variable names will be uppercased
    before being looked up in the environment.

    By default, boolean variables evaluate to true if their lower-case value is
    one of ``true``, ``yes``, ``on`` or ``1``. This can be overridden by either
    passing a custom parser to the variable declaration, or by overriding the
    ``__truthy__`` class attribute, which is a set of lower-case strings that
    are considered to be a representation of ``True``.

    There is also basic support for collections. An item of type ``list``,
    ``tuple`` or ``set`` will be parsed using ``,`` as item separator.
    Similarly, an item of type ``dict`` will be parsed with ``,`` as item
    separator, and ``:`` as value separator. These can be changed by overriding
    the ``__item_separator__`` and ``__value_separator__`` class attributes
    respectively. All the elements in the collections, including key and values
    for dictionaries, will be of type string. For more advanced control over
    the final type, a custom ``parser`` can be passed instead.
    """

    __truthy__ = frozenset({"1", "true", "yes", "on"})
    __prefix__ = ""
    __item__ = None  # type: Optional[str]
    __item_separator__ = ","
    __value_separator__ = ":"

    def __init__(self, source=None, parent=None):
        # type: (Optional[Dict[str, str]], Optional[Env]) -> None
        self.source = source or os.environ
        self.parent = parent

        self._full_prefix = (
            parent._full_prefix if parent is not None else ""
        ) + _normalized(
            self.__prefix__
        )  # type: str
        if self._full_prefix and not self._full_prefix.endswith("_"):
            self._full_prefix += "_"

        self.spec = self.__class__
        derived = []
        for name, e in list(self.__class__.__dict__.items()):
            if isinstance(e, EnvVariable):
                setattr(self, name, e(self, self._full_prefix))
            elif isinstance(e, type) and issubclass(e, Env):
                if e.__item__ is not None and e.__item__ != name:
                    # Move the subclass to the __item__ attribute
                    setattr(self.spec, e.__item__, e)
                    delattr(self.spec, name)
                    name = e.__item__
                setattr(self, name, e(source, self))
            elif isinstance(e, DerivedVariable):
                derived.append((name, e))

        for n, d in derived:
            setattr(self, n, d(self))

    @classmethod
    def var(
        cls,
        type,  # type: Type[T]
        name,  # type: str
        parser=None,  # type: Optional[Callable[[str], T]]
        validator=None,  # type: Optional[Callable[[T], None]]
        map=None,  # type: Optional[MapType]
        default=NoDefault,  # type: Union[T, NoDefaultType]
        deprecations=None,  # type: Optional[List[DeprecationInfo]]
        help=None,  # type: Optional[str]
        help_type=None,  # type: Optional[str]
        help_default=None,  # type: Optional[str]
    ):
        # type: (...) -> EnvVariable[T]
        return EnvVariable(
            type,
            name,
            parser,
            validator,
            map,
            default,
            deprecations,
            help,
            help_type,
            help_default,
        )

    @classmethod
    def v(
        cls,
        type,  # type: Union[object, Type[T]]
        name,  # type: str
        parser=None,  # type: Optional[Callable[[str], T]]
        validator=None,  # type: Optional[Callable[[T], None]]
        map=None,  # type: Optional[MapType]
        default=NoDefault,  # type: Union[T, NoDefaultType]
        deprecations=None,  # type: Optional[List[DeprecationInfo]]
        help=None,  # type: Optional[str]
        help_type=None,  # type: Optional[str]
        help_default=None,  # type: Optional[str]
    ):
        # type: (...) -> EnvVariable[T]
        return EnvVariable(
            type,
            name,
            parser,
            validator,
            map,
            default,
            deprecations,
            help,
            help_type,
            help_default,
        )

    @classmethod
    def der(cls, type, derivation):
        # type: (Type[T], Callable[[Env], T]) -> DerivedVariable[T]
        return DerivedVariable(type, derivation)

    @classmethod
    def d(cls, type, derivation):
        # type: (Type[T], Callable[[Env], T]) -> DerivedVariable[T]
        return DerivedVariable(type, derivation)

    @classmethod
    def keys(cls):
        # type: () -> Iterator[str]
        """Return the names of all the items."""
        return (
            k
            for k, v in cls.__dict__.items()
            if isinstance(v, (EnvVariable, DerivedVariable))
            or isinstance(v, type)
            and issubclass(v, Env)
        )

    @classmethod
    def values(cls):
        # type: () -> Iterator[Union[EnvVariable, DerivedVariable, Type[Env]]]
        """Return the names of all the items."""
        return (
            v
            for v in cls.__dict__.values()
            if isinstance(v, (EnvVariable, DerivedVariable))
            or isinstance(v, type)
            and issubclass(v, Env)
        )

    @classmethod
    def include(cls, env_spec, namespace=None, overwrite=False):
        # type: (Type[Env], Optional[str], bool) -> None
        """Include variables from another Env subclass.

        The new items can be merged at the top level, or parented to a
        namespace. By default, the method raises a ``ValueError`` if the
        operation would result in some variables being overwritten. This can
        be disabled by setting the ``overwrite`` argument to ``True``.
        """
        if namespace is not None:
            if not overwrite and hasattr(cls, namespace):
                raise ValueError("Namespace already in use: {}".format(namespace))

            setattr(cls, namespace, env_spec)

            return None

        # Pick only the attributes that define variables.
        to_include = {
            k: v
            for k, v in env_spec.__dict__.items()
            if isinstance(v, (EnvVariable, DerivedVariable))
            or isinstance(v, type)
            and issubclass(v, Env)
        }

        if not overwrite:
            overlap = set(cls.__dict__.keys()) & set(to_include.keys())
            if overlap:
                raise ValueError("Configuration clashes detected: {}".format(overlap))

        for k, v in to_include.items():
            setattr(cls, k, v)

    @classmethod
    def help_info(cls, recursive=False):
        # type: (bool) -> List[HelpInfo]
        """Extract the help information from the class.

        Returns a list of all the environment variables declared by the class.
        The format of each entry is a tuple consisting of the variable name (in
        double backtics quotes), the type, the default value, and the help text.

        Set ``recursive`` to ``True`` to include variables from nested Env
        classes.
        """
        entries = []

        def add_entries(full_prefix, config):
            # type: (str, Type[Env]) -> None
            vars = sorted(
                (_ for _ in config.values() if isinstance(_, EnvVariable)),
                key=lambda v: v.name,
            )

            for v in vars:
                # Add a period at the end if necessary.
                help_message = v.help.strip() if v.help is not None else ""
                if help_message and not help_message.endswith("."):
                    help_message += "."

                entries.append(
                    (
                        "``" + full_prefix + _normalized(v.name) + "``",
                        v.help_type or "``%s``" % v.type.__name__,  # type: ignore[attr-defined]
                        v.help_default or str(v.default),
                        help_message,
                    )
                )

        configs = [("", cls)]

        while configs:
            full_prefix, config = configs.pop()
            new_prefix = full_prefix + _normalized(config.__prefix__)
            if not new_prefix.endswith("_"):
                new_prefix += "_"
            add_entries(new_prefix, config)

            if not recursive:
                break

            subconfigs = sorted(
                (
                    (new_prefix, v)
                    for k, v in config.__dict__.items()
                    if isinstance(v, type) and issubclass(v, Env) and k != "parent"
                ),
                key=lambda _: _[1].__prefix__,
            )

            configs[0:0] = subconfigs  # DFS

        return entries
