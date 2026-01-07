# Authentication Guide

Odyn currently focuses on on-premises deployments of Business Central, which typically use Basic Authentication.

## Basic Authentication

The `BasicAuth` class handles the encoding of credentials into the standard HTTP `Authorization` header.

```python
from odyn import BasicAuth

auth = BasicAuth("DOMAIN\\user", "password")
```

### Windows/NetBIOS Authentication

For on-premises installations using Windows Authentication, you frequently need to provide the domain as a prefix to the username.

```python
# Use a double backslash to escape the character in Python strings
auth = BasicAuth("MYDOMAIN\\JohnDoe", "p@ssword123")
```

## Security Best Practices

1. **Environment Variables**: Never hardcode credentials in your source code. Use environment variables or a secret manager.
2. **HTTPS**: Always connect to Business Central over HTTPS. Basic Authentication transmits credentials in a reversible Base64 format; without TLS/SSL, they are effectively visible in plain text.
3. **Restricted Accounts**: Use a dedicated service account with the minimum permissions required for the specific integration task.
4. **SSL Verification**: While `verify_ssl=False` is available for development against self-signed certificates, always use proper certificates and `verify_ssl=True` in production.
