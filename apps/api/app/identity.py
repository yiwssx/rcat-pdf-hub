import base64
import hashlib
import json
import re
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
from app.rbac import ROLE_ADMIN, ROLE_OPERATOR, is_admin_role, normalize_roles, role_for_groups, scopes_for_roles

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


def _verified_rcat_email(email: object, verified: object) -> str:
    """Accept only OIDC-provider-attested institutional mail, never a UI field.

    The supplied email must be a conventional single-address ASCII mailbox;
    subdomains, lookalikes, whitespace, Unicode homographs and unverified
    email values are rejected rather than silently normalized.
    """
    if verified is not True or not isinstance(email, str):
        raise ValueError("A verified institutional email is required")
    if (len(email) > 254 or not email.isascii()
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._%+\-]*@rcat\.ac\.th",
                                email, flags=re.IGNORECASE)):
        raise ValueError("Only verified @rcat.ac.th identities may sign in")
    return email.lower()


def _require_google_workspace(hosted_domain: object) -> None:
    """Require signed membership in RCAT Google Workspace, not just mail."""
    if settings.oidc_issuer.rstrip("/") not in {
        "https://accounts.google.com", "accounts.google.com"
    }:
        return
    if not isinstance(hosted_domain, str) or hosted_domain.lower() != "rcat.ac.th":
        raise ValueError("Google Workspace hosted domain must be rcat.ac.th")


def _require_rcat_identity(identity: dict) -> None:
    """Re-evaluate the restriction when creating/decoding any session."""
    if not settings.rcat_institutional_only:
        return
    if identity.get("source") not in {"oidc", "oidc-bearer"}:
        raise ValueError("Institutional access requires trusted OIDC")
    _verified_rcat_email(identity.get("email"), identity.get("email_verified"))
    _require_google_workspace(identity.get("hosted_domain"))


def _institutional_role(groups: list[str], verified_email: str) -> str:
    """Grant all verified school mailboxes basic conversion access.

    Google ID tokens normally omit Workspace groups. Explicit role mappings
    still narrow a user to viewer or elevate an IdP-asserted admin group;
    an operator fallback applies only after verified school-email checks.
    """
    if verified_email in settings.rcat_admin_email_set:
        return ROLE_ADMIN
    try:
        return role_for_groups(groups, settings.human_role_group_map)
    except ValueError:
        return ROLE_OPERATOR


def _institutional_owner_name(subject: str) -> str:
    """Stable issuer-scoped owner; avoids mutable-email reassignment."""
    if not subject or subject == "unknown":
        raise ValueError("Institutional OIDC subject is required")
    material = (settings.oidc_issuer.rstrip("/") + "\x00" + subject).encode("utf-8")
    return "user:oidc:" + hashlib.sha256(material).hexdigest()


def _safe_return_to(value: str) -> str:
    """Only origin-relative paths; browsers treat backslashes as slashes."""
    if (not value.startswith("/") or value.startswith("//")
            or "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        return "/"
    return value


def identity_from_claims(claims: dict, source: str) -> dict:
    if settings.rcat_institutional_only:
        if source not in {"oidc", "oidc-bearer"}:
            raise ValueError("Institutional access requires OIDC")
        validated_email = _verified_rcat_email(
            claims.get("email"), claims.get("email_verified"))
        _require_google_workspace(claims.get("hd"))
    else:
        validated_email = str(claims.get("email") or "")[:254]
    subject = str(claims.get("sub") or claims.get("uid") or claims.get("username") or "unknown")
    display = str(
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("name")
        or claims.get("uid")
        or subject
    )
    groups = _claim_list(claims.get(settings.oidc_group_claim) or claims.get("groups"))
    roles = (
        (_institutional_role(groups, validated_email),)
        if settings.rcat_institutional_only
        else (role_for_groups(groups, settings.human_role_group_map),)
    )
    scopes = scopes_for_roles(roles, settings.human_scope_set)
    safe_display = display[:110]
    # The signed sub claim is stable when email is renamed or reassigned;
    # verified email remains a display/authorization attribute, not owner key.
    owner_name = (
        _institutional_owner_name(subject)
        if settings.rcat_institutional_only
        else f"user:{safe_display}"[:120]
    )
    return {
        "name": owner_name,
        "subject": subject,
        "email": validated_email,
        "email_verified": claims.get("email_verified") is True if source.startswith("oidc") else False,
        "hosted_domain": str(claims.get("hd") or ""),
        "display_name": display,
        "groups": groups,
        "roles": list(roles),
        "scopes": sorted(scopes),
        "source": source,
        "is_identity_admin": is_admin_role(roles),
    }


def create_web_console_identity() -> dict:
    workspace_id = settings.web_console_workspace_id.strip() or "default"
    subject = f"workspace:{workspace_id}"[:120]
    return {
        "name": f"web-console:{workspace_id}"[:120],
        "subject": subject,
        "display_name": "Web Console",
        "groups": ["web-console"],
        "roles": [ROLE_OPERATOR],
        "scopes": sorted(scopes_for_roles((ROLE_OPERATOR,), settings.human_scope_set)),
        "source": "web-console",
        "is_identity_admin": False,
    }


def create_local_admin_identity(username: str) -> dict:
    safe_username = username.strip()[:80]
    return {
        "name": f"local-admin:{safe_username}"[:120],
        "subject": f"local-admin:{safe_username}"[:120],
        "display_name": safe_username,
        "groups": ["pdfhub-admins", "local-admin"],
        "roles": [ROLE_ADMIN],
        "scopes": ["*"],
        "source": "local-admin",
        "is_identity_admin": True,
    }


def create_session_token(identity: dict) -> str:
    _require_rcat_identity(identity)
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
        "pdfhub_roles": identity.get("roles", []),
        "pdfhub_scopes": identity.get("scopes", []),
        "pdfhub_source": identity.get("source", "session"),
        "pdfhub_email": identity.get("email", ""),
        "pdfhub_email_verified": identity.get("email_verified") is True,
        "pdfhub_hosted_domain": identity.get("hosted_domain", ""),
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
    source = str(claims.get("pdfhub_source") or "session")
    if settings.rcat_institutional_only:
        if source != "oidc":
            raise jwt.InvalidTokenError("Institutional access requires OIDC")
        try:
            _verified_rcat_email(
                claims.get("pdfhub_email"), claims.get("pdfhub_email_verified"))
            _require_google_workspace(claims.get("pdfhub_hosted_domain"))
        except ValueError as exc:
            raise jwt.InvalidTokenError("Institutional email is not verified") from exc
    if source == "web-console":
        if not settings.web_console_auto_login_enabled:
            raise jwt.InvalidTokenError("Web Console sessions are disabled while institutional authentication is active")
        return create_web_console_identity()
    groups = _claim_list(claims.get("pdfhub_groups"))
    roles_claim = _claim_list(claims.get("pdfhub_roles"))
    if source in {"oidc", "ldap"}:
        # Re-evaluate institutional groups on every session decode so a mapping
        # change or group removal cannot leave stale privileges in a cookie.
        roles = (
            (_institutional_role(groups, _verified_rcat_email(
                claims.get("pdfhub_email"), claims.get("pdfhub_email_verified")
            )),)
            if settings.rcat_institutional_only
            else (role_for_groups(groups, settings.human_role_group_map),)
        )
        scopes = scopes_for_roles(roles, settings.human_scope_set)
    elif roles_claim:
        roles = normalize_roles(roles_claim)
        scopes = scopes_for_roles(roles, settings.human_scope_set)
    elif source == "local-admin":
        roles = (ROLE_ADMIN,)
        scopes = scopes_for_roles(roles, settings.human_scope_set)
    else:
        # Backward compatibility for legacy/custom signed sessions that predate
        # human RBAC. Preserve their signed scopes instead of broadening them
        # into the operator role.
        roles = ()
        scopes = set(_claim_list(claims.get("pdfhub_scopes")))
    return {
        "name": (
            _institutional_owner_name(str(claims["sub"]))
            if settings.rcat_institutional_only
            else str(claims.get("pdfhub_name") or f"user:{claims['sub']}")[:120]
        ),
        "subject": str(claims["sub"]),
        "email": str(claims.get("pdfhub_email") or ""),
        "email_verified": claims.get("pdfhub_email_verified") is True,
        "hosted_domain": str(claims.get("pdfhub_hosted_domain") or ""),
        "display_name": str(claims.get("pdfhub_display_name") or claims["sub"]),
        "groups": groups,
        "roles": list(roles),
        "scopes": sorted(scopes),
        "source": source,
        "is_identity_admin": is_admin_role(roles),
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
    return_to = _safe_return_to(return_to)
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    payload = json.dumps({"nonce": nonce, "verifier": verifier, "return_to": return_to})
    Redis.from_url(settings.redis_url).setex(OIDC_STATE_PREFIX + state, settings.oidc_state_ttl_seconds, payload)
    query_params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": settings.oidc_scope,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if settings.oidc_issuer.rstrip("/") in {
        "https://accounts.google.com", "accounts.google.com",
    }:
        # Always offer a new account choice; never force a remembered Gmail account.
        query_params["prompt"] = "select_account"
        if settings.rcat_institutional_only:
            # Google UX hint only. Signed email/hd claims remain enforced below.
            query_params["hd"] = "rcat.ac.th"
    query = urlencode(query_params)
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
    return identity_from_claims(claims, "oidc"), _safe_return_to(str(saved.get("return_to") or "/"))


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
        "oidc": {
            "enabled": settings.oidc_enabled,
            "issuer": settings.oidc_issuer if settings.oidc_enabled else None,
            "login_url": "/api/v1/auth/oidc/login" if settings.oidc_enabled else None,
        },
        "ldap": {"enabled": settings.ldap_enabled},
        "web_console": {"auto_login": settings.web_console_auto_login_enabled},
        "local_admin": {"enabled": settings.local_admin_enabled},
        "institutional": {
            "rcat_only": settings.rcat_institutional_only,
            "email_domain": "rcat.ac.th" if settings.rcat_institutional_only else None,
        },
    }
