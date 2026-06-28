import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from harbor_bot.api import create_app
from harbor_bot.auth import AuthConfig, AuthError, AuthState
from harbor_bot.settings import Settings


@pytest.mark.asyncio
async def test_auth_state_validates_cognito_access_token() -> None:
    fixture = JwtFixture()
    auth = AuthState(
        AuthConfig(issuer_url=fixture.issuer, client_id=fixture.client_id),
        jwks_fetcher=lambda: fixture.jwks,
    )

    user = await auth.validate_bearer(fixture.token())

    assert user.sub == "user-123"
    assert user.username == "chris"
    assert user.email == "chris@example.com"
    assert user.token_use == "access"


@pytest.mark.asyncio
async def test_auth_state_rejects_wrong_client() -> None:
    fixture = JwtFixture()
    auth = AuthState(
        AuthConfig(issuer_url=fixture.issuer, client_id="expected-client"),
        jwks_fetcher=lambda: fixture.jwks,
    )

    with pytest.raises(AuthError, match="client mismatch"):
        await auth.validate_bearer(fixture.token(client_id="wrong-client"))


def test_api_routes_require_bearer_when_auth_is_enabled() -> None:
    app = create_app(
        observability_service=FakeObservabilityService(),
        settings=_auth_required_settings(),
        auth_state=FakeAuthState(),
    )
    client = TestClient(app)

    missing = client.get("/api/status")
    present = client.get("/api/status", headers={"Authorization": "Bearer good-token"})
    health = client.get("/health")

    assert missing.status_code == 401
    assert present.status_code == 200
    assert present.json()["bot_state"] == "WAIT_SWEEP"
    assert health.status_code == 200


def test_websocket_requires_access_token_when_auth_is_enabled() -> None:
    app = create_app(
        observability_service=FakeObservabilityService(),
        settings=_auth_required_settings(),
        auth_state=FakeAuthState(),
    )
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect("/ws"):
        pass

    assert exc.value.code == 1008
    with client.websocket_connect("/ws?access_token=good-token") as websocket:
        assert websocket.receive_json()["type"] == "status"


class JwtFixture:
    issuer = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_example"
    client_id = "harbor-client"

    def __init__(self) -> None:
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_numbers = self._key.public_key().public_numbers()
        self.jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "test-key",
                    "use": "sig",
                    "alg": "RS256",
                    "n": _base64url_uint(public_numbers.n),
                    "e": _base64url_uint(public_numbers.e),
                }
            ]
        }

    def token(self, *, client_id: str | None = None) -> str:
        now = datetime.now(tz=UTC)
        return jwt.encode(
            {
                "iss": self.issuer,
                "sub": "user-123",
                "client_id": client_id or self.client_id,
                "token_use": "access",
                "username": "chris",
                "email": "chris@example.com",
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(minutes=10)).timestamp()),
            },
            self._key,
            algorithm="RS256",
            headers={"kid": "test-key"},
        )


class FakeAuthState:
    async def validate_bearer(self, token: str) -> dict[str, str]:
        if token != "good-token":
            raise AuthError("bad token")
        return {"sub": "user-123"}


class FakeObservabilityService:
    async def get_status(self) -> dict[str, Any]:
        return {
            "bot_state": "WAIT_SWEEP",
            "mode": "practice",
            "trading_enabled": False,
        }


def _auth_required_settings() -> Settings:
    return Settings(
        HARBOR_AUTH_REQUIRED=True,
        HARBOR_AUTH_ISSUER_URL="https://issuer.test",
        HARBOR_AUTH_CLIENT_ID="harbor-client",
    )


def _base64url_uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    raw = value.to_bytes(length, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
