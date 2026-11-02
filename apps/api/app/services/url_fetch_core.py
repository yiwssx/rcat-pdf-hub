"""T90-2 URL -> PDF: bounded, DNS-pinned, text-first public HTTPS importer.

This module executes ONLY inside the separately isolated URL-fetcher service. It fetches one public HTTPS document,
never sends Chromium to a remote URL, and returns a sanitized, attribute-free HTML transcript without executing page scripts.

Network protection requirements:
- no userinfo, non-443 ports, fragments, queries, literal IPs or special names
- resolve all advertised A/AAAA addresses and reject the entire answer if
  ANY address is private, reserved, mapped-private or otherwise non-global
- connect DIRECTLY to a numerical, previously validated address and preserve
  the original hostname for TLS SNI, certificate and Host verification
- no ambient proxy, cookies, redirects, auth, JS, images or external resources
- strict response type, status, Content-Length and streaming byte limits
- a separate network egress policy is still required before public release
"""
from __future__ import annotations

from html import escape
from html.parser import HTMLParser
import http.client
import ipaddress
import re
import socket
import ssl
from urllib.parse import urlsplit


URL_MAX_LENGTH = 1800
MAX_HTML_BYTES = 1_500_000
MAX_HTML_TAGS = 20_000
MAX_TEXT_CHARS = 240_000
MAX_DNS_RESULTS = 16
CONNECT_TIMEOUT = 7
READ_TIMEOUT = 14
SAFE_OUTPUT_TAGS = frozenset({
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "section",
    "article", "span", "strong", "em", "b", "i", "u", "pre", "code",
    "blockquote", "ul", "ol", "li", "table", "thead", "tbody",
    "tr", "td", "th", "br", "hr",
})
EMPTY_TAGS = frozenset({"br", "hr"})
HIDDEN_TAGS = frozenset({
    "script", "style", "head", "noscript", "template", "iframe",
    "object", "embed", "svg", "math", "video", "audio", "canvas",
    "form", "select", "textarea", "button", "picture", "meta",
    "link", "base", "source",
})
# These are void elements in HTML5: their absence of a closing tag must
# not leave the sanitizer permanently suppressing printable content.
VOID_HIDDEN_TAGS = frozenset({"meta", "link", "base", "source", "input"})
BLOCKED_SUFFIXES = (
    ".local", ".localhost", ".internal", ".test", ".invalid", ".example",
    ".home.arpa", ".onion",
)


def validate_public_https_url(raw: str) -> tuple[str, str]:
    """Validate without networking. Return (canonical ASCII hostname, path).

    An unqualified host, literal IP or query-bearing URL is not a public
    webpage source for this narrow first version of the feature.
    """
    if (not isinstance(raw, str) or not 10 <= len(raw) <= URL_MAX_LENGTH
            or any(ord(c) < 33 or ord(c) == 127 for c in raw)
            or "\\" in raw):
        raise ValueError("URL must be a bounded, unambiguous HTTPS address")
    try:
        url = urlsplit(raw)
        port = url.port
        hostname = url.hostname
    except ValueError as exc:
        raise ValueError("Malformed URL authority") from exc
    if (url.scheme != "https" or not hostname or url.username is not None
            or url.password is not None or url.query or url.fragment
            or port not in (None, 443)):
        raise ValueError("Only public HTTPS URLs without credentials, query or fragment are accepted")
    if url.netloc.endswith(".") or hostname.endswith("."):
        raise ValueError("Unqualified or trailing-dot domain is unsupported")
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        raise ValueError("Literal IP address URLs are not permitted")
    if "%" in raw or "[" in url.netloc or "]" in url.netloc:
        raise ValueError("Encoded or bracketed hosts are unsupported")
    try:
        canonical_host = hostname.encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError) as exc:
        raise ValueError("URL hostname is not a valid IDN") from exc
    if (len(canonical_host) > 253 or "." not in canonical_host
            or canonical_host == "localhost"
            or canonical_host.endswith(BLOCKED_SUFFIXES)):
        raise ValueError("URL hostname is not a public fully qualified name")
    for label in canonical_host.split("."):
        if (not 1 <= len(label) <= 63
                or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)):
            raise ValueError("URL hostname contains an invalid DNS label")
    # Do not collapse // path segments or decode URL percent escapes: the
    # server must see the exact user-supplied path, without local file access.
    path = url.path or "/"
    if not path.startswith("/") or any(c in path for c in ("\r", "\n", "\0")):
        raise ValueError("URL path contains unsafe characters")
    # HTTP request path remains ASCII, percent-encoding non-ASCII path UTF-8.
    from urllib.parse import quote
    return canonical_host, quote(path, safe="/%:@!$&'()*+,;=-._~")


def _public_addresses(hostname: str) -> tuple[str, ...]:
    try:
        answers = socket.getaddrinfo(
            hostname, 443, family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP,
        )
    except OSError as exc:
        raise ValueError("Public URL hostname could not be resolved") from exc
    addresses = []
    for family, kind, protocol, cname, sockaddr in answers:
        if family not in (socket.AF_INET, socket.AF_INET6):
            raise ValueError("URL DNS returned an unsupported address family")
        address = ipaddress.ip_address(sockaddr[0])
        mapped = getattr(address, "ipv4_mapped", None)
        if mapped is not None:
            address = mapped
        if not address.is_global:
            raise ValueError("URL DNS contains private, non-global or prohibited addresses")
        if str(address) not in addresses:
            addresses.append(str(address))
    if not 1 <= len(addresses) <= MAX_DNS_RESULTS:
        raise ValueError("URL DNS answer count exceeds limits")
    # The dedicated egress network has IPv6 explicitly disabled. Reject mixed
    # private A/AAAA answers above, then select only an independently checked
    # public IPv4 address for the pinned TCP connection.
    public_ipv4 = tuple(
        value for value in addresses
        if ipaddress.ip_address(value).version == 4
    )
    if not public_ipv4:
        raise ValueError("URL requires a globally routable IPv4 A record")
    return public_ipv4


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname: str, numeric_address: str):
        self._numeric_address = numeric_address
        super().__init__(
            host=hostname, port=443, timeout=CONNECT_TIMEOUT,
            context=ssl.create_default_context(),
        )

    def connect(self) -> None:
        # Connect to numeric IP and *never* let the HTTP client re-resolve the
        # original hostname or honor proxy environment variables.
        unwrapped = socket.create_connection((self._numeric_address, 443), timeout=self.timeout)
        try:
            unwrapped.settimeout(READ_TIMEOUT)
            self.sock = self._context.wrap_socket(unwrapped, server_hostname=self.host)
        except BaseException:
            unwrapped.close()
            raise


def fetch_bounded_public_html(url: str) -> str:
    hostname, path = validate_public_https_url(url)
    addresses = _public_addresses(hostname)
    # Picking the first public address keeps the entire transaction pinned.
    # Never retry through a private alternate or perform a second DNS lookup.
    client = _PinnedHTTPS(hostname, addresses[0])
    try:
        client.request(
            "GET", path,
            headers={
                "Host": hostname,
                "User-Agent": "RCAT-PDF-HUB-URL-Importer/0.1",
                "Accept": "text/html,text/plain;q=0.9",
                "Accept-Encoding": "identity",
                "Accept-Language": "th,en;q=0.8",
                "Connection": "close",
            },
        )
        response = client.getresponse()
        if response.status != 200:
            # HTTP 3xx is NOT followed; a redirect requires revalidating
            # its destination and is not yet supported by this feature.
            raise ValueError("Public URL did not return HTTP 200")
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("Compressed URL responses are unsupported")
        content_type = response.getheader("Content-Type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type not in ("text/html", "text/plain", "application/xhtml+xml"):
            raise ValueError("URL response is not an HTML or plain-text document")
        declared_length = response.getheader("Content-Length")
        if declared_length is not None:
            try:
                length = int(declared_length)
            except ValueError as exc:
                raise ValueError("URL content length is invalid") from exc
            if not 0 < length <= MAX_HTML_BYTES:
                raise ValueError("URL response length exceeds limits")
        body = response.read(MAX_HTML_BYTES + 1)
        if not 0 < len(body) <= MAX_HTML_BYTES:
            raise ValueError("URL response is empty or oversized")
        if declared_length is not None and len(body) != length:
            # Don't turn a prematurely closed/truncated upstream response
            # into a plausible-looking, incomplete PDF.
            raise ValueError("URL document was truncated or length mismatched")
        header = re.search(r"charset\s*=\s*([a-zA-Z0-9_-]+)", content_type)
        encoding = header.group(1).lower() if header else "utf-8"
        aliases = {
            "utf-8": "utf-8-sig", "utf8": "utf-8-sig",
            "iso-8859-1": "latin1", "windows-1252": "cp1252",
            "windows-874": "cp874", "tis-620": "cp874",
        }
        if encoding not in aliases:
            raise ValueError("URL document declares unsupported encoding")
        try:
            text = body.decode(aliases[encoding], errors="strict")
        except UnicodeError as exc:
            raise ValueError("URL document encoding does not match its contents") from exc
        if media_type == "text/plain":
            if len(text) > MAX_TEXT_CHARS:
                raise ValueError("Plain text URL page exceeds printable character cap")
            return "<pre>" + escape(text) + "</pre>"
        return sanitize_fetched_html(text)
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        raise ValueError("Public HTTPS fetch was rejected or failed") from exc
    finally:
        client.close()


class _SanitizedDocument(HTMLParser):
    """Explicit output markup only, no attributes, CSS, scripts or remote links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.visible: list[str] = []
        self.hidden: list[str] = []
        self.tags = 0
        self.chars = 0

    def handle_starttag(self, tag, attrs):
        self.tags += 1
        if self.tags > MAX_HTML_TAGS:
            raise ValueError("URL HTML tag count exceeds bounds")
        if tag in HIDDEN_TAGS:
            if tag not in VOID_HIDDEN_TAGS:
                self.hidden.append(tag)
            return
        if self.hidden:
            return
        if tag in SAFE_OUTPUT_TAGS:
            self.parts.append("<" + tag + ">")
            if tag not in EMPTY_TAGS:
                self.visible.append(tag)
                if len(self.visible) > 128:
                    raise ValueError("URL HTML nesting exceeds supported bounds")

    def handle_startendtag(self, tag, attrs):
        # Reject XML-style self-closed active nodes except void HTML5
        # elements, which are routine and must never suppress the body.
        if tag in HIDDEN_TAGS and tag not in VOID_HIDDEN_TAGS:
            raise ValueError("Ambiguous self-closing active HTML")
        self.handle_starttag(tag, attrs)
        if tag in SAFE_OUTPUT_TAGS and tag not in EMPTY_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in HIDDEN_TAGS:
            if tag in VOID_HIDDEN_TAGS:
                return
            if not self.hidden or self.hidden[-1] != tag:
                raise ValueError("URL HTML filtered element is unbalanced")
            self.hidden.pop()
            return
        if self.hidden or tag not in SAFE_OUTPUT_TAGS or tag in EMPTY_TAGS:
            return
        if tag in self.visible:
            # A malformed close cannot pop unrelated tags unless the matching
            # tag actually exists in the open-tag stack.
            while self.visible:
                last = self.visible.pop()
                self.parts.append("</" + last + ">")
                if last == tag:
                    break

    def handle_data(self, data):
        if self.hidden or not data:
            return
        self.chars += len(data)
        if self.chars > MAX_TEXT_CHARS:
            raise ValueError("URL HTML printable content exceeds limits")
        self.parts.append(escape(data))

    def finish(self) -> str:
        self.close()
        if self.hidden:
            raise ValueError("URL HTML contains an unclosed active element")
        while self.visible:
            self.parts.append("</" + self.visible.pop() + ">")
        body = "".join(self.parts)
        if not re.search(r"[^\s<>]", re.sub(r"<[^>]+>", "", body)):
            raise ValueError("URL HTML does not contain printable text")
        return body


def sanitize_fetched_html(source: str) -> str:
    purifier = _SanitizedDocument()
    purifier.feed(source)
    return purifier.finish()


