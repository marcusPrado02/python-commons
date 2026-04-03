from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any


def _require_pyjwt() -> Any:
    try:
        import jwt as pyjwt  # type: ignore[import-untyped]

        return pyjwt
    except ImportError as exc:
        raise ImportError("Install 'PyJWT' to use the JWT security module") from exc


__all__ = [
    "JwtClaims",
    "JwtDecoder",
    "JwtIssuer",
    "JwtValidationError",
]


class JwtValidationError(Exception):
    """Raised when a JWT cannot be decoded or fails validation."""


@dataclass
class JwtClaims:
    sub: str
    iss: str = ""
    aud: str | list[str] = ""
    exp: datetime = field(default_factory=lambda: datetime.now(UTC))
    iat: datetime = field(default_factory=lambda: datetime.now(UTC))
    jti: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.exp

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> JwtClaims:
        def _dt(v: Any) -> datetime:
            if isinstance(v, datetime):
                return v.replace(tzinfo=UTC) if v.tzinfo is None else v
            return datetime.fromtimestamp(int(v), tz=UTC)

        known = {"sub", "iss", "aud", "exp", "iat", "jti"}
        extra = {k: v for k, v in payload.items() if k not in known}
        return cls(
            sub=payload.get("sub", ""),
            iss=payload.get("iss", ""),
            aud=payload.get("aud", ""),
            exp=_dt(payload["exp"]) if "exp" in payload else datetime.now(UTC),
            iat=_dt(payload["iat"]) if "iat" in payload else datetime.now(UTC),
            jti=payload.get("jti", ""),
            extra=extra,
        )


class JwtDecoder:
    """Decodes and validates JWTs using PyJWT."""

    def decode(
        self,
        token: str,
        secret_or_key: str | bytes,
        algorithms: list[str] | None = None,
        audience: str | list[str] | None = None,
    ) -> JwtClaims:
        algs = algorithms or ["HS256"]
        options: dict[str, Any] = {}
        if audience is None:
            options["verify_aud"] = False
        _pyjwt = _require_pyjwt()
        try:
            payload = _pyjwt.decode(
                token,
                secret_or_key,
                algorithms=algs,
                audience=audience,
                options=options,
            )
        except _pyjwt.ExpiredSignatureError as exc:
            raise JwtValidationError("Token has expired") from exc
        except _pyjwt.InvalidAudienceError as exc:
            raise JwtValidationError("Invalid audience") from exc
        except _pyjwt.PyJWTError as exc:
            raise JwtValidationError(str(exc)) from exc
        return JwtClaims.from_payload(payload)


class JwtIssuer:
    """Issues (signs) JWTs using PyJWT."""

    def __init__(self, issuer: str = "") -> None:
        self._issuer = issuer

    def issue(
        self,
        claims: dict[str, Any],
        secret_or_key: str | bytes,
        algorithm: str = "HS256",
        expires_in: timedelta | None = None,
    ) -> str:
        payload = dict(claims)
        now = datetime.now(UTC)
        payload.setdefault("iat", now)
        if self._issuer:
            payload.setdefault("iss", self._issuer)
        if expires_in is not None:
            payload["exp"] = now + expires_in
        return _require_pyjwt().encode(payload, secret_or_key, algorithm=algorithm)
