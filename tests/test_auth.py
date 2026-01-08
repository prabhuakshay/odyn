"""Tests for the odyn.auth module."""

import base64

import httpx
import pytest

from odyn.auth import BasicAuth


class TestBasicAuth:
    """Tests for BasicAuth class."""

    def test_init_stores_credentials(self):
        """BasicAuth stores username and password."""
        auth = BasicAuth("user", "password123")
        assert auth.username == "user"
        assert auth.password == "password123"

    def test_auth_header_format(self):
        """auth_header returns properly formatted Basic auth string."""
        auth = BasicAuth("user", "password123")
        header = auth.auth_header

        assert header.startswith("Basic ")
        encoded_part = header[6:]  # Remove "Basic " prefix

        # Decode and verify
        decoded = base64.b64decode(encoded_part).decode()
        assert decoded == "user:password123"

    def test_auth_header_with_domain_username(self):
        """auth_header handles domain\\username format."""
        auth = BasicAuth("DOMAIN\\user", "password")
        header = auth.auth_header

        encoded_part = header[6:]
        decoded = base64.b64decode(encoded_part).decode()
        assert decoded == "DOMAIN\\user:password"

    def test_auth_header_with_special_characters(self):
        """auth_header handles special characters in password."""
        auth = BasicAuth("user", "p@ss:word!#$%")
        header = auth.auth_header

        encoded_part = header[6:]
        decoded = base64.b64decode(encoded_part).decode()
        assert decoded == "user:p@ss:word!#$%"

    def test_auth_header_is_deterministic(self):
        """auth_header returns the same value on multiple calls."""
        auth = BasicAuth("user", "password")
        assert auth.auth_header == auth.auth_header

    def test_repr_hides_password(self):
        """__repr__ does not expose the password."""
        auth = BasicAuth("user", "secretpassword")
        repr_str = repr(auth)

        assert "user" in repr_str
        assert "secretpassword" not in repr_str
        assert "***" in repr_str

    def test_frozen_dataclass(self):
        """BasicAuth is immutable."""
        auth = BasicAuth("user", "password")

        with pytest.raises(AttributeError):
            auth.username = "new_user"

        with pytest.raises(AttributeError):
            auth.password = "new_password"

    def test_empty_username(self):
        """BasicAuth accepts empty username."""
        auth = BasicAuth("", "password")
        assert auth.username == ""

    def test_empty_password(self):
        """BasicAuth accepts empty password."""
        auth = BasicAuth("user", "")
        assert auth.password == ""

    def test_apply_adds_header(self):
        """apply method adds Authorization header to httpx Request."""
        auth = BasicAuth("user", "password123")
        request = httpx.Request("GET", "https://example.com")

        assert "Authorization" not in request.headers

        updated_request = auth.apply(request)

        assert updated_request is request
        assert "Authorization" in request.headers
        assert request.headers["Authorization"].startswith("Basic ")
