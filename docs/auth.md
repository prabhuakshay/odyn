# Authentication

Odyn supports two authentication strategies: `BasicAuth` for username/password credentials and `APIKeyAuth` for API key-based access. Both implement the same interface (`auth_header` property + `apply()` method) and can be passed to `BCWebServiceClient.create()`.

The type alias `AuthStrategy = BasicAuth | APIKeyAuth` is used throughout the library.

## BasicAuth

HTTP Basic Authentication. The standard method for on-premises Business Central deployments.

```python
from odyn import BasicAuth
```

### Constructor

```python
BasicAuth(username: str, password: str)
```

Both fields are required. The dataclass is frozen (immutable) and uses `__slots__`.

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `username` | `str` | Username. Supports `DOMAIN\user` format for Windows domain auth. |
| `password` | `str` | Password. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `auth_header` | `str` | The full `Authorization` header value (e.g., `Basic dXNlcjpwYXNz`) |

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `apply()` | `(request: httpx.Request) -> httpx.Request` | Adds the `Authorization` header to the request. |

### Examples

```python
# Standard credentials
auth = BasicAuth("myuser", "mypassword")

# Windows domain auth
auth = BasicAuth("MYDOMAIN\\svc_account", "password")

# The auth_header property
print(auth.auth_header)
# 'Basic bXl1c2VyOm15cGFzc3dvcmQ='

# Safe repr (password hidden)
print(auth)
# BasicAuth(username='myuser', password='***')
```

### How It Works

1. Concatenates `username:password`
2. Base64-encodes the result
3. Prepends `Basic ` to form the header value
4. Sets the `Authorization` header on every request

## APIKeyAuth

API Key Authentication. Sends the key via a configurable HTTP header with a configurable prefix.

```python
from odyn import APIKeyAuth
```

### Constructor

```python
APIKeyAuth(
    api_key: str,
    header_name: str = "Authorization",
    prefix: str = "Bearer",
)
```

The dataclass is frozen (immutable) and uses `__slots__`.

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | — | The API key value. Required. |
| `header_name` | `str` | `"Authorization"` | HTTP header name to use. |
| `prefix` | `str` | `"Bearer"` | Prefix before the key value. Set to `""` for no prefix. |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `auth_header` | `str` | The formatted header value (e.g., `Bearer my-key` or just `my-key` if prefix is empty) |

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `apply()` | `(request: httpx.Request) -> httpx.Request` | Adds the auth header to the request. |

### Examples

```python
# Default: Bearer token in Authorization header
auth = APIKeyAuth("my-secret-key")
# Header: Authorization: Bearer my-secret-key

# Custom header name, no prefix
auth = APIKeyAuth("my-secret-key", header_name="X-API-Key", prefix="")
# Header: X-API-Key: my-secret-key

# Custom prefix
auth = APIKeyAuth("my-secret-key", prefix="ApiKey")
# Header: Authorization: ApiKey my-secret-key

# Safe repr (key hidden)
print(auth)
# APIKeyAuth(api_key='***', header_name='Authorization')
```

## Using Auth with the Client

Both auth types are passed to the `auth` parameter of `BCWebServiceClient.create()` or `BCWebServiceClientSync.create()`:

```python
from odyn import BCWebServiceClient, BasicAuth, APIKeyAuth

# Basic auth
async with BCWebServiceClient.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=BasicAuth("user", "password"),
) as client:
    df = await client.get("customers")

# API key auth
async with BCWebServiceClient.create(
    server="https://bc-server:7048",
    instance="BC210",
    auth=APIKeyAuth("my-api-key"),
) as client:
    df = await client.get("customers")
```

## AuthStrategy Type Alias

```python
from odyn import AuthStrategy

# AuthStrategy = BasicAuth | APIKeyAuth
```

Use this type when writing functions that accept either auth type:

```python
from odyn import AuthStrategy

def create_client(auth: AuthStrategy):
    return BCWebServiceClient.create(
        server="https://bc-server:7048",
        instance="BC210",
        auth=auth,
    )
```

## Security Notes

- Both classes hide secrets in `__repr__` output — safe for logging
- Both are frozen dataclasses — credentials cannot be mutated after creation
- Credentials are sent on every request via HTTP headers — always use HTTPS in production
