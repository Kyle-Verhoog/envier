<h1 align="center">Envier</h1>
<h2 align="center">Python application configuration from the environment</h2>

## Synopsis

Envier is a Python library for extracting configuration from environment
variables in a declarative and (eventually) 12-factor-app-compliant way.


## Usage

The following example shows how to declare the configuration for an application
that uses the `MYAPP_DEBUG`, `MYAPP_SERVICE_HOST` and `MYAPP_SERVICE_PORT`
variables from the environment.

~~~ python
>>> from envier import Env
>>> 
>>> class GlobalConfig(Env):
>>>     __prefix__ = "myapp"
>>>     
>>>     debug_mode = Env.var(bool, "debug", default=False)
>>> 
>>>     service_host = Env.var(str, "service.host", default="localhost")
>>>     service_port = Env.var(int, "service.port", default=3000)
>>> 
>>>     _is_default_port = Env.der(bool, lambda c: c.service_port == c.spec.service_port.default)
>>> 
>>> config = GlobalConfig()
>>> config.service_port
3000
>>> config._is_default_port
True
~~~

Configurations can also be nested to create namespaces:

~~~ python
>>> from envier import Env
>>> 
>>> class ServiceConfig(Env):
>>>     __prefix__ = "service"
>>> 
>>>     host = Env.var(str, "host", default="localhost")
>>>     port = Env.var(int, "port", default=3000)
>>> 
>>> class GlobalConfig(Env):
>>>     __prefix__ = "myapp"
>>>     
>>>     debug_mode = Env.var(bool, "debug", default=False)
>>> 
>>>     service = ServiceConfig
>>> 
>>> config = GlobalConfig()
>>> config.service.port
3000
~~~

The same configuration can be obtained with implicit nesting by declaring the
`ServiceConfig` subclass inside `GlobalConfig`, and setting the class attribute
`__item__` to the name of the item the sub-configuration should be assigned to,
viz.

~~~ python
>>> from envier import Env
>>> 
>>> class GlobalConfig(Env):
>>>     __prefix__ = "myapp"
>>>     
>>>     debug_mode = Env.var(bool, "debug", default=False)
>>> 
>>>     class ServiceConfig(Env):
>>>         __item__ = __prefix__ = "service"
>>>         
>>>         host = Env.var(str, "host", default="localhost")
>>>         port = Env.var(int, "port", default=3000)
>>> 
>>> config = GlobalConfig()
>>> config.service.port
3000
~~~


## Type Checking

The library ships with a `mypy` plugin to allow for type checking. If you want
to use it, either install the library with the `mypy` extra or ensure that
`mypy` is installed, and then add `envier.mypy` to the list of extra plugins in
the `mypy` configuration.


## Sphinx Plugin

The library comes with a Sphinx plugin at `envier.sphinx` to allow generating
documentation from the configuration spec class directly. It exposes the
``envier`` directive that takes a mandatory argument, the configuration spec
class in the form `module:class`; additionally, the options `heading` and
`recursive` can be used to control whether to add heading and whether to
recursively get help information from nested configuration spec classes
respectively. By default, the plugin will display the table heading and will not
recurse over nested configuration spec classes.

Here is an example for a configuration class `GlobalConfig` located in the
`myapp.config` module. We omit the table header and recurse over nested
configuration.

~~~ rst
.. envier:: myapp.config:GlobalConfig
   :heading: false
   :recursive: true
~~~

## Roadmap

- Add support for environment files.
- Rely on type hints as support for older versions of Python is dropped.
- Derivations might require an evaluation order.
