# API reference

Everything below is importable from the top-level `aiomoto` package.

```python
from aiomoto import (
    AutoEndpointMode,
    mock_aws,
    mock_aws_decorator,
    __version__,
)
```

## `mock_aws`

```python
mock_aws(
    func=None,
    *,
    reset=True,
    remove_data=True,
    config=None,
    server_mode=False,
    server_port=None,
    auto_endpoint=None,
)
```

A drop-in replacement for Moto's `mock_aws`. Use it as a context manager
(`with` / `async with`) or as a decorator over a sync or async callable. When
called with keyword arguments and no function, it returns a reusable
context/decorator object.

| Parameter       | Type                    | Default | Description                                                                             |
| --------------- | ----------------------- | ------- | --------------------------------------------------------------------------------------- |
| `func`          | callable \| `None`      | `None`  | The function being decorated when used as `@mock_aws` without parentheses.              |
| `reset`         | `bool`                  | `True`  | Reset Moto's backends when the context starts.                                          |
| `remove_data`   | `bool`                  | `True`  | Remove backend data when the context exits.                                             |
| `config`        | `Config \| None`        | `None`  | Optional Moto config override (in-process mode only).                                   |
| `server_mode`   | `bool`                  | `False` | Start a local Moto server instead of patching in process.                               |
| `server_port`   | `int \| None`           | `None`  | Attach to a server already listening on this port (requires `server_mode=True`).        |
| `auto_endpoint` | `AutoEndpointMode \| None` | `None` | Endpoint-injection strategy in server mode (defaults to `FORCE` when `server_mode`).    |

### Context attributes

When used as a context manager in server mode, the returned object exposes:

| Attribute              | Type          | Description                                  |
| ---------------------- | ------------- | -------------------------------------------- |
| `server_endpoint`      | `str \| None` | Base URL of the running server.              |
| `server_host`          | `str \| None` | Host the server bound to.                    |
| `server_port`          | `int \| None` | Port the server bound to.                    |
| `server_registry_path` | `str \| None` | Path to the registry file aiomoto wrote.     |

## `mock_aws_decorator`

```python
mock_aws_decorator(
    func=None,
    *,
    reset=True,
    remove_data=True,
    config=None,
    server_mode=False,
    server_port=None,
    auto_endpoint=None,
)
```

A decorator factory mirroring Moto's `mock_aws` wrapper, exported for teams that
prefer an explicitly decorator-only name. Parentheses are optional:
`@mock_aws_decorator` uses the defaults, while `@mock_aws_decorator(reset=False)`
preconfigures behaviour. Accepts the same keyword arguments as `mock_aws`.

## `AutoEndpointMode`

A `StrEnum` selecting how endpoints are injected in [server mode](../guides/server-mode.md):

| Member       | Value          | Behaviour                                                       |
| ------------ | -------------- | -------------------------------------------------------------- |
| `FORCE`      | `"force"`      | Always inject the server endpoint (default in server mode).    |
| `IF_MISSING` | `"if_missing"` | Inject only when the client has no explicit `endpoint_url`.    |
| `DISABLED`   | `"disabled"`   | Never inject; clients target the server themselves.            |

## Exceptions

All exception types subclass the built-in `Exception` and are importable from
`aiomoto`:

| Exception                       | Raised when                                              |
| ------------------------------- | -------------------------------------------------------- |
| `RealHTTPRequestBlockedError`   | A real HTTP request is attempted while mocking.          |
| `AutoEndpointError`             | Server-mode auto-endpoint configuration is invalid.      |
| `InProcessModeError`            | In-process mode state is invalid or unavailable.         |
| `ModeConflictError`             | In-process and server-mode settings conflict.            |
| `ProxyModeError`                | Moto proxy mode is requested (unsupported).              |
| `ServerModeConfigurationError`  | Server-mode configuration is invalid.                    |
| `ServerModeDependencyError`     | Server-mode dependencies are missing.                    |
| `ServerModeEndpointError`       | Server-mode endpoint discovery fails.                    |
| `ServerModeHealthcheckError`    | A server-mode healthcheck fails.                         |
| `ServerModePortError`           | An invalid or conflicting server port is supplied.       |
| `ServerModeRequiredError`       | Server mode is required but not enabled.                 |

## `__version__`

The installed package version as a string.
