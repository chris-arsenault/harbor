import asyncio
import inspect
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import Request, WebSocket, status
from jwt import InvalidTokenError
from starlette.responses import JSONResponse, Response

from harbor_bot.settings import Settings

JWKS_CACHE_TTL_SECONDS = 15 * 60
WEBSOCKET_POLICY_VIOLATION = status.WS_1008_POLICY_VIOLATION

JwksFetcher = Callable[[], dict[str, Any] | Awaitable[dict[str, Any]]]


class AuthError(Exception):
    """Raised when a bearer token cannot authenticate the request."""


@dataclass(frozen=True)
class AuthConfig:
    issuer_url: str
    client_id: str


@dataclass(frozen=True)
class AuthenticatedUser:
    sub: str
    username: str | None
    email: str | None
    token_use: str


class AuthState:
    def __init__(
        self,
        config: AuthConfig,
        *,
        jwks_fetcher: JwksFetcher | None = None,
    ) -> None:
        self._config = AuthConfig(
            issuer_url=config.issuer_url.rstrip("/"),
            client_id=config.client_id,
        )
        self._jwks_fetcher = jwks_fetcher
        self._jwks_cache: dict[str, Any] = {}
        self._jwks_loaded_at = 0.0
        self._jwks_lock = asyncio.Lock()

    @property
    def issuer_url(self) -> str:
        return self._config.issuer_url

    @property
    def client_id(self) -> str:
        return self._config.client_id

    async def validate_bearer(self, token: str) -> AuthenticatedUser:
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise AuthError("invalid jwt header") from exc
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise AuthError("jwt missing kid")

        try:
            key = await self._find_key(kid)
        except Exception as exc:
            raise AuthError("jwks request failed") from exc
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=["RS256"],
                issuer=self._config.issuer_url,
                options={"verify_aud": False},
            )
        except InvalidTokenError as exc:
            raise AuthError("jwt validation failed") from exc

        self._validate_client(claims)
        sub = _required_string(claims, "sub")
        return AuthenticatedUser(
            sub=sub,
            username=_optional_string(claims, "username")
            or _optional_string(claims, "cognito:username"),
            email=_optional_string(claims, "email"),
            token_use=_required_string(claims, "token_use"),
        )

    def _validate_client(self, claims: dict[str, Any]) -> None:
        token_use = claims.get("token_use")
        if token_use == "access":
            if claims.get("client_id") != self._config.client_id:
                raise AuthError("jwt client mismatch")
            return
        if token_use == "id":
            if claims.get("aud") != self._config.client_id:
                raise AuthError("jwt audience mismatch")
            return
        raise AuthError("unsupported token_use")

    async def _find_key(self, kid: str) -> Any:
        cached = self._cached_key(kid)
        if cached is not None:
            return cached
        async with self._jwks_lock:
            cached = self._cached_key(kid)
            if cached is not None:
                return cached
            self._jwks_cache = await self._load_jwks()
            self._jwks_loaded_at = time.monotonic()
        cached = self._cached_key(kid)
        if cached is None:
            raise AuthError("jwks missing key id")
        return cached

    def _cached_key(self, kid: str) -> Any | None:
        if time.monotonic() - self._jwks_loaded_at > JWKS_CACHE_TTL_SECONDS:
            return None
        return self._jwks_cache.get(kid)

    async def _load_jwks(self) -> dict[str, Any]:
        jwks = await self._fetch_jwks()
        keys: dict[str, Any] = {}
        for item in jwks.get("keys", []):
            if not isinstance(item, dict):
                continue
            kid = item.get("kid")
            if item.get("kty") != "RSA" or not isinstance(kid, str):
                continue
            keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(item))
        return keys

    async def _fetch_jwks(self) -> dict[str, Any]:
        if self._jwks_fetcher is not None:
            value = self._jwks_fetcher()
            if inspect.isawaitable(value):
                value = await value
            return value
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{self._config.issuer_url}/.well-known/jwks.json")
            response.raise_for_status()
            return response.json()


def auth_state_from_settings(settings: Settings) -> AuthState | None:
    if not settings.auth_enabled:
        return None
    return AuthState(
        AuthConfig(
            issuer_url=str(settings.harbor_auth_issuer_url),
            client_id=str(settings.harbor_auth_client_id),
        )
    )


async def require_http_auth(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    auth_state = getattr(request.app.state, "auth_state", None)
    if auth_state is None:
        return await call_next(request)

    token = _bearer_token(
        authorization=request.headers.get("authorization"),
        query_token=request.query_params.get("access_token"),
    )
    if token is None:
        return _unauthorized()
    try:
        request.state.authenticated_user = await auth_state.validate_bearer(token)
    except AuthError:
        return _unauthorized()
    return await call_next(request)


async def require_websocket_auth(websocket: WebSocket) -> bool:
    auth_state = getattr(websocket.app.state, "auth_state", None)
    if auth_state is None:
        return True

    token = _bearer_token(
        authorization=websocket.headers.get("authorization"),
        query_token=websocket.query_params.get("access_token"),
    )
    if token is None:
        await websocket.close(code=WEBSOCKET_POLICY_VIOLATION)
        return False
    try:
        websocket.state.authenticated_user = await auth_state.validate_bearer(token)
    except AuthError:
        await websocket.close(code=WEBSOCKET_POLICY_VIOLATION)
        return False
    return True


def _bearer_token(*, authorization: str | None, query_token: str | None) -> str | None:
    if authorization is not None and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token:
            return token
    if query_token is not None and query_token.strip():
        return query_token.strip()
    return None


def _unauthorized() -> JSONResponse:
    return JSONResponse({"detail": "unauthorized"}, status_code=status.HTTP_401_UNAUTHORIZED)


def _required_string(claims: dict[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value:
        raise AuthError(f"jwt missing {name}")
    return value


def _optional_string(claims: dict[str, Any], name: str) -> str | None:
    value = claims.get(name)
    return value if isinstance(value, str) and value else None
