import base64
import hashlib
import hmac
import json
import secrets
import time
from functools import lru_cache
from urllib.parse import urlencode, urlparse

import httpx
import jwt
from jwt import PyJWKClient
from ldap3 import Connection, Server, SUBTREE
from ldap3.utils.conv import escape_filter_chars
from redis import Redis

from app.config import get_settings

settings = get_settings()
OIDC_STATE_PREFIX = "pdfhub:oidc:state:"
SAFE_OIDC_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"]


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _claim_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [item for item in value.replace(",", " ").split() if item]
    return [str(value)]


def identity_from_claims(claims: dict, source: str) -> dict:
    subject = str(claims.get("sub") or claims.get("uid") or claims.get("username") or "unknown")
    display = str(
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("name")
        or claims.get("uid")
        or subject
    )
    groups = _claim_list(claims.get(settings.oidc_group_claim) or claims.get("groups"))
    is_admin = bool(set(groups) & settings.admin_group_set)
    scopes = {"*"} if is_admin else set(settings.human_scope_set)
    return {
        "name": f"identity:{source}",
        "subject": subject,
        "display_name": display,
        "groups": groups,
        "scopes": sorted(scopes),
        "source": source,
        "issuer": str(claims.get("iss") or ""),
        "is_identity_admin": is_admin,
    }


def authenticate_local(username: str, password: str) -> dict:
    if not settings.local_auth_enabled:
        raise ValueError("Local authentication is disabled")
    candidate_user = username.strip()
    user_ok = hmac.compare_digest(candidate_user, settings.local_admin_username)
    password_ok = hmac.compare_digest(password, settings.local_admin_password)
    if not (user_ok and password_ok):
        raise ValueError("Invalid local credentials")
    return {
        "name": "local-admin",
        "subject": candidate_user,
        "display_name": "Local Admin",
        "groups": ["local-admin"],
        "scopes": ["*"],
        "source": "local",
        "is_identity_admin": True,
    }


def create_session_token(identity: dict) -> str:
    now = int(time.time())
    payload = {
        "iss": "pdfhub",
        "aud": "pdfhub-web",
        "iat": now,
        "exp": now + settings.session_ttl_minutes * 60,
        "sub": identity["subject"],
        "pdfhub_name": identity["name"],
        "pdfhub_display_name": identity.get("display_name", identity["name"]),
        "pdfhub_groups": identity.get("groups", []),
        "pdfhub_scopes": identity.get("scopes", []),
        "pdfhub_source": identity.get("source", "session"),
        "pdfhub_issuer": identity.get("issuer", ""),
        "pdfhub_identity_admin": bool(identity.get("is_identity_admin", False)),
    }
    return jwt.encode(payload, settings.auth_token_secret, algorithm="HS256")


def decode_session_token(token: str) -> dict:
    claims = jwt.decode(
        token,
        settings.auth_token_secret,
        algorithms=["HS256"],
        issuer="pdfhub",
        audience="pdfhub-web",
        options={"require": ["exp", "iat", "sub"]},
    )
    return {
        "name": str(claims.get("pdfhub_name") or f"user:{claims['sub']}")[:120],
        "subject": str(claims["sub"]),
        "display_name": str(claims.get("pdfhub_display_name") or claims["sub"]),
        "groups": _claim_list(claims.get("pdfhub_groups")),
        "scopes": _claim_list(claims.get("pdfhub_scopes")),
        "source": str(claims.get("pdfhub_source") or "session"),
        "issuer": str(claims.get("pdfhub_issuer") or ""),
        "is_identity_admin": bool(claims.get("pdfhub_identity_admin", False)),
    }


@lru_cache(maxsize=4)
def _discovery(url: str) -> dict:
    response = httpx.get(url, timeout=10.0, follow_redirects=False)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("OIDC discovery returned invalid JSON")
    return payload


def oidc_discovery() -> dict:
    if not settings.oidc_enabled:
        raise RuntimeError("OIDC is disabled")
    url = settings.oidc_discovery_url or settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
    payload = _discovery(url)
    issuer = str(payload.get("issuer") or "")
    if issuer.rstrip("/") != settings.oidc_issuer.rstrip("/"):
        raise RuntimeError("OIDC discovery issuer mismatch")
    for key in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        if not payload.get(key):
            raise RuntimeError(f"OIDC discovery missing {key}")
    return payload


@lru_cache(maxsize=4)
def _jwk_client(jwks_uri: str) -> PyJWKClient:
    return PyJWKClient(jwks_uri, cache_keys=True, lifespan=300)


def validate_oidc_token(token: str, audience: str | None = None) -> dict:
    discovery = oidc_discovery()
    header = jwt.get_unverified_header(token)
    algorithm = str(header.get("alg") or "")
    if algorithm not in SAFE_OIDC_ALGORITHMS:
        raise jwt.InvalidAlgorithmError("OIDC token uses a disallowed signing algorithm")
    signing_key = _jwk_client(str(discovery["jwks_uri"])).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=[algorithm],
        issuer=settings.oidc_issuer,
        audience=audience or settings.oidc_audience or settings.oidc_client_id,
        options={"require": ["exp", "iat", "sub"]},
    )


def build_oidc_authorization_url(return_to: str = "/") -> str:
    discovery = oidc_discovery()
    if not return_to.startswith("/") or return_to.startswith("//"):
        return_to = "/"
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    payload = json.dumps({"nonce": nonce, "verifier": verifier, "return_to": return_to})
    Redis.from_url(settings.redis_url).setex(OIDC_STATE_PREFIX + state, settings.oidc_state_ttl_seconds, payload)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": settings.oidc_redirect_uri,
            "scope": settings.oidc_scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return str(discovery["authorization_endpoint"]) + "?" + query


def complete_oidc_callback(code: str, state: str) -> tuple[dict, str]:
    redis = Redis.from_url(settings.redis_url)
    key = OIDC_STATE_PREFIX + state
    raw = redis.get(key)
    if not raw:
        raise ValueError("OIDC state is missing or expired")
    redis.delete(key)
    saved = json.loads(raw)
    discovery = oidc_discovery()
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.oidc_redirect_uri,
        "client_id": settings.oidc_client_id,
        "code_verifier": saved["verifier"],
    }
    if settings.oidc_client_secret:
        form["client_secret"] = settings.oidc_client_secret
    response = httpx.post(str(discovery["token_endpoint"]), data=form, timeout=15.0, follow_redirects=False)
    response.raise_for_status()
    token_payload = response.json()
    id_token = token_payload.get("id_token")
    if not id_token:
        raise ValueError("OIDC token endpoint did not return id_token")
    claims = validate_oidc_token(str(id_token), audience=settings.oidc_client_id)
    if claims.get("nonce") != saved.get("nonce"):
        raise ValueError("OIDC nonce mismatch")
    return identity_from_claims(claims, "oidc"), str(saved.get("return_to") or "/")


def _ldap_server() -> Server:
    parsed = urlparse(settings.ldap_url)
    if parsed.scheme not in {"ldap", "ldaps"} or not parsed.hostname:
        raise ValueError("LDAP_URL must use ldap:// or ldaps://")
    return Server(
        parsed.hostname,
        port=parsed.port or (636 if parsed.scheme == "ldaps" else 389),
        use_ssl=parsed.scheme == "ldaps",
        connect_timeout=settings.ldap_connect_timeout_seconds,
    )


def _ldap_service_connection(server: Server) -> Connection:
    if settings.ldap_bind_dn:
        return Connection(server, settings.ldap_bind_dn, settings.ldap_bind_password, auto_bind=True, raise_exceptions=True)
    return Connection(server, auto_bind=True, raise_exceptions=True)


def authenticate_ldap(username: str, password: str) -> dict:
    if not settings.ldap_enabled:
        raise ValueError("LDAP is disabled")
    if not username or not password:
        raise ValueError("LDAP username and password are required")

    server = _ldap_server()
    attributes: dict[str, object] = {"uid": username}
    if settings.ldap_user_dn_template:
        user_dn = settings.ldap_user_dn_template.format(username=username)
    else:
        service = _ldap_service_connection(server)
        try:
            search_filter = settings.ldap_user_filter.format(username=escape_filter_chars(username))
            ok = service.search(
                settings.ldap_base_dn,
                search_filter,
                search_scope=SUBTREE,
                attributes=["uid", "cn", "mail", "displayName"],
                size_limit=2,
            )
            if not ok or len(service.entries) != 1:
                raise ValueError("LDAP user not found or not unique")
            entry = service.entries[0]
            user_dn = entry.entry_dn
            for key in ("uid", "cn", "mail", "displayName"):
                if key in entry.entry_attributes and entry[key].value is not None:
                    attributes[key] = entry[key].value
        finally:
            service.unbind()

    user = Connection(server, user_dn, password, auto_bind=True, raise_exceptions=True)
    user.unbind()

    groups: list[str] = []
    if settings.ldap_group_base_dn:
        service = _ldap_service_connection(server)
        try:
            group_filter = settings.ldap_group_filter.format(user_dn=escape_filter_chars(user_dn))
            service.search(
                settings.ldap_group_base_dn,
                group_filter,
                search_scope=SUBTREE,
                attributes=[settings.ldap_group_attribute],
            )
            for entry in service.entries:
                if settings.ldap_group_attribute in entry.entry_attributes:
                    values = entry[settings.ldap_group_attribute].values
                    groups.extend(str(value) for value in values)
        finally:
            service.unbind()

    claims = {
        "sub": user_dn,
        "uid": str(attributes.get("uid") or username),
        "preferred_username": str(attributes.get("uid") or username),
        "email": str(attributes.get("mail") or ""),
        "name": str(attributes.get("displayName") or attributes.get("cn") or username),
        "groups": sorted(set(groups)),
    }
    return identity_from_claims(claims, "ldap")


def public_auth_config() -> dict:
    return {
        "session_cookie": settings.session_cookie_name,
        "local": {"enabled": settings.local_auth_enabled},
        "oidc": {
            "enabled": settings.oidc_enabled,
            "issuer": settings.oidc_issuer if settings.oidc_enabled else None,
            "login_url": "/api/v1/auth/oidc/login" if settings.oidc_enabled else None,
        },
        "ldap": {"enabled": settings.ldap_enabled},
        "api_key": {"enabled": True},
    }
