"""Tests for Home Assistant WebSocket client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from app.core.ha_client import HomeAssistantClient, HomeAssistantClientError


class TestHomeAssistantClient:
    """Tests for HomeAssistantClient class."""

    def test_client_initialization(self):
        """Test client initializes with correct URL and token."""
        client = HomeAssistantClient(
            url="http://homeassistant.local:8123",
            token="test-token",
        )
        
        assert client.url == "http://homeassistant.local:8123"
        assert client.token == "test-token"
        assert client.ws_url == "ws://homeassistant.local:8123/api/websocket"

    def test_client_initialization_strips_trailing_slash(self):
        """Test client strips trailing slash from URL."""
        client = HomeAssistantClient(
            url="http://homeassistant.local:8123/",
            token="test-token",
        )
        
        assert client.url == "http://homeassistant.local:8123"

    def test_client_https_to_wss(self):
        """Test client converts https to wss for WebSocket URL."""
        client = HomeAssistantClient(
            url="https://homeassistant.local:8123",
            token="test-token",
        )
        
        assert client.ws_url == "wss://homeassistant.local:8123/api/websocket"

    def test_is_connected_property(self):
        """Test is_connected property returns connection state."""
        client = HomeAssistantClient(
            url="http://homeassistant.local:8123",
            token="test-token",
        )
        
        assert client.is_connected is False


class TestSecurityUtils:
    """Tests for security utility functions."""

    def test_generate_passphrase_default_length(self):
        """Test passphrase generation with default length."""
        from app.core.security import generate_passphrase
        
        passphrase = generate_passphrase()
        assert len(passphrase) == 12

    def test_generate_passphrase_custom_length(self):
        """Test passphrase generation with custom length."""
        from app.core.security import generate_passphrase
        
        passphrase = generate_passphrase(16)
        assert len(passphrase) == 16

    def test_generate_passphrase_minimum_length(self):
        """Test passphrase enforces minimum length."""
        from app.core.security import generate_passphrase
        
        passphrase = generate_passphrase(4)  # Below minimum
        assert len(passphrase) == 8  # Should be clamped to 8

    def test_generate_passphrase_maximum_length(self):
        """Test passphrase enforces maximum length."""
        from app.core.security import generate_passphrase
        
        passphrase = generate_passphrase(64)  # Above maximum
        assert len(passphrase) == 32  # Should be clamped to 32

    def test_generate_passphrase_contains_required_chars(self):
        """Test passphrase contains uppercase, lowercase, and digit."""
        from app.core.security import generate_passphrase
        
        # Run multiple times to ensure randomness doesn't break requirements
        for _ in range(10):
            passphrase = generate_passphrase()
            has_upper = any(c.isupper() for c in passphrase)
            has_lower = any(c.islower() for c in passphrase)
            has_digit = any(c.isdigit() for c in passphrase)
            
            assert has_upper, f"Passphrase {passphrase} missing uppercase"
            assert has_lower, f"Passphrase {passphrase} missing lowercase"
            assert has_digit, f"Passphrase {passphrase} missing digit"

    def test_generate_invite_code(self):
        """Test invite code generation."""
        from app.core.security import generate_invite_code
        
        code = generate_invite_code()
        assert len(code) == 8
        assert code.isupper()
        assert code.isalnum()

    def test_generate_verification_code(self):
        """Test verification code generation."""
        from app.core.security import generate_verification_code
        
        code = generate_verification_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_password_hashing(self):
        """Test password hashing and verification."""
        from app.core.security import hash_password, verify_password
        
        password = "test-password-123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong-password", hashed) is False

    def test_jwt_token_creation_and_verification(self):
        """Test JWT token creation and verification."""
        from app.core.security import create_access_token, verify_token
        
        data = {"sub": "test-user", "email": "test@example.com"}
        token = create_access_token(data)
        
        assert token is not None
        
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "test-user"
        assert payload["email"] == "test@example.com"

    def test_invalid_token_verification(self):
        """Test that invalid tokens are rejected."""
        from app.core.security import verify_token
        
        result = verify_token("invalid-token")
        assert result is None
