"""کلاینت OIDC برای ورود یکگانه (SSO) با پرتال مرکزی (مثل پرتال ورود یکپارچه :8086).

جریان: ریدایرکت به authorization_endpoint → callback با code → تبادل توکن در
token_endpoint (client_secret_post) → اعتبارسنجی id_token با RS256/JWKS →
provision کاربر → صدور «بلیت یک‌بارمصرف» برای تبادل امن با فرانت‌اند.
"""
import base64
import hashlib
import secrets
import time
import uuid as uuid_mod

import httpx
import jwt  # PyJWT
from jwt import PyJWKClient

DISCOVERY_PATH = "/.well-known/openid-configuration"
_DISCOVERY_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600

# بلیت‌های یک‌بارمصرف تبادل با فرانت‌اند: ticket → (user_id, expires_at)
_TICKETS: dict[str, tuple[uuid_mod.UUID, float]] = {}
TICKET_TTL = 30


def sso_enabled() -> bool:
    from app.core.config import get_settings
    s = get_settings()
    return bool(s.sso_client_id)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def pkce_pair() -> tuple[str, str]:
    """(verifier, challenge) با روش S256."""
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def get_discovery(base_url: str) -> dict:
    """دریافت و کش discovery سرویس SSO."""
    base = base_url.rstrip("/")
    now = time.time()
    cached = _DISCOVERY_CACHE.get(base)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]
    with httpx.Client(base_url=base, timeout=10.0) as client:
        resp = client.get(DISCOVERY_PATH)
        resp.raise_for_status()
        doc = resp.json()
    _DISCOVERY_CACHE[base] = (now, doc)
    return doc


def build_authorize_url(discovery: dict, client_id: str, redirect_uri: str,
                        scope: str, state: str, challenge: str,
                        nonce: str | None = None) -> str:
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if nonce:  # nonce ضد تکرار پاسخ (بازخورد ۳.۱)
        params["nonce"] = nonce
    return f"{discovery['authorization_endpoint']}?{urlencode(params)}"


def exchange_code(discovery: dict, client_id: str, client_secret: str,
                  redirect_uri: str, code: str, verifier: str) -> dict:
    """تبادل code با token_endpoint (client_secret_post)."""
    token_ep = discovery["token_endpoint"]
    with httpx.Client(timeout=12.0) as client:
        resp = client.post(token_ep, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": verifier,
        })
        if resp.status_code != 200:
            raise RuntimeError(f"SSO token endpoint پاسخ {resp.status_code} داد")
        return resp.json()


def verify_id_token(id_token: str, jwks_uri: str, issuer: str, audience: str,
                    expected_nonce: str | None = None) -> dict:
    """اعتبارسنجی امضای RS256 id_token با JWKS و برگرداندن claims؛
    در صورت ارائه nonce، مطابقت claim بررسی می‌شود."""
    key = PyJWKClient(jwks_uri).get_signing_key_from_jwt(id_token)
    claims = jwt.decode(id_token, key.key, algorithms=["RS256"],
                        audience=audience, issuer=issuer)
    if expected_nonce and claims.get("nonce") != expected_nonce:
        raise RuntimeError("nonce id_token مطابقت ندارد")
    return claims


def fetch_userinfo(discovery: dict, access_token: str) -> dict:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(discovery["userinfo_endpoint"],
                          headers={"Authorization": f"Bearer {access_token}"})
        if resp.status_code != 200:
            return {}
        return resp.json()


# ---------- بلیت یک‌بارمصرف ----------

def issue_ticket(user_id: uuid_mod.UUID) -> str:
    ticket = secrets.token_urlsafe(24)
    _TICKETS[ticket] = (user_id, time.time() + TICKET_TTL)
    # پاک‌سازی بلیت‌های منقضی
    now = time.time()
    for t in [k for k, v in _TICKETS.items() if v[1] < now]:
        _TICKETS.pop(t, None)
    return ticket


def pop_ticket(ticket: str) -> uuid_mod.UUID | None:
    item = _TICKETS.pop(ticket, None)
    if item is None or item[1] < time.time():
        return None
    return item[0]


# ---------- state ضد CSRF + nonce ضد تکرار ----------

_STATES: dict[str, tuple[str, float, str | None]] = {}
STATE_TTL = 600


def store_state(state: str, verifier: str, nonce: str | None = None) -> None:
    _STATES[state] = (verifier, time.time() + STATE_TTL, nonce)


def pop_state(state: str) -> str | None:
    item = _STATES.pop(state, None)
    if item is None or item[1] < time.time():
        return None
    return item[0]


def pop_state_full(state: str) -> tuple[str, str | None] | None:
    """(verifier, nonce) — با مصرف یک‌باره state."""
    item = _STATES.pop(state, None)
    if item is None or item[1] < time.time():
        return None
    return item[0], item[2]
