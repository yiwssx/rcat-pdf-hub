import hashlib

from app.config import get_settings

settings = get_settings()


def principal_name_for_identity(identity: dict) -> str:
    """Return a stable, non-display tenant key for a human identity.

    OIDC ownership is keyed from the issuer + subject pair. LDAP ownership is keyed
    from the authenticated directory subject DN. Display names, usernames and email
    addresses are deliberately excluded so renames or duplicate presentation claims
    cannot collapse two tenants into the same file/job owner.
    """
    source = str(identity.get("source") or "identity")
    subject = str(identity.get("subject") or "").strip()
    if not subject:
        raise ValueError("Identity subject is required")

    if source.startswith("oidc"):
        namespace = "oidc"
        issuer = str(identity.get("issuer") or settings.oidc_issuer or "").strip().rstrip("/")
        if not issuer:
            raise ValueError("OIDC issuer is required for stable identity ownership")
        material = f"{issuer}\0{subject}"
    elif source.startswith("ldap"):
        namespace = "ldap"
        material = subject
    else:
        namespace = "identity"
        material = f"{source}\0{subject}"

    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"
