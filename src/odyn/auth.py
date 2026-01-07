"""Authentication handlers for Business Central Web Services.

This module provides authentication strategies for connecting to
Business Central on-premises web services.

Example:
    >>> from odyn.auth import BasicAuth
    >>> auth = BasicAuth("username", "password")
    >>> client = BCWebServiceClient(base_url=..., auth=auth)
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

__all__ = [
    "BasicAuth",
]


@dataclass(frozen=True, slots=True)
class BasicAuth:
    r"""HTTP Basic Authentication for on-premises Business Central.

    Encodes credentials as Base64 and adds the Authorization header
    to outgoing requests.

    Attributes:
        username: The username for authentication.
        password: The password for authentication.

    Example:
        >>> auth = BasicAuth("DOMAIN\\username", "password123")
        >>> auth.auth_header
        'Basic RE9NQUlOXHVzZXJuYW1lOnBhc3N3b3JkMTIz'
    """

    username: str
    password: str

    @property
    def auth_header(self) -> str:
        """Generate the Authorization header value.

        Returns:
            The base64-encoded Basic auth string.
        """
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def apply(self, request: httpx.Request) -> httpx.Request:
        """Apply authentication to a request.

        Args:
            request: The httpx request to authenticate.

        Returns:
            The request with Authorization header added.
        """
        request.headers["Authorization"] = self.auth_header
        return request

    def __repr__(self) -> str:
        """Return a string representation hiding the password."""
        return f"BasicAuth(username={self.username!r}, password='***')"
