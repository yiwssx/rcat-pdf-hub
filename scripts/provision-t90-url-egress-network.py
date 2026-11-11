#!/usr/bin/env python3
"""Choose a free /28 for the isolated URL egress bridge on the real Docker host.

No container/network/firewall modifications. Only two non-secret fields in
the existing institutional .env are added/reconciled with the host topology.
Fail closed for ambiguous Docker/routing evidence, malformed settings, or
a live URL egress network whose original address would be changed.
"""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
SUBNET_KEY = "PDFHUB_URL_EGRESS_SUBNET"
IP_KEY = "PDFHUB_URL_EGRESS_IPV4"
BRIDGE = "br-pdfhub-url"
DEFAULT = ipaddress.IPv4Network("172.30.243.0/28")
PRIVATE = (
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
)
KV = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def execute(*command: str) -> str:
    p = subprocess.run(command, check=False, capture_output=True, text=True, timeout=45)
    if p.returncode:
        raise ValueError("required local Docker/network discovery failed: " + command[0])
    return p.stdout


def parse_subnet(value: str) -> ipaddress.IPv4Network:
    network = ipaddress.ip_network(value, strict=True)
    if (not isinstance(network, ipaddress.IPv4Network) or network.prefixlen != 28
            or not any(network.subnet_of(parent) for parent in PRIVATE)):
        raise ValueError("URL egress subnet must be a private IPv4 /28")
    return network


def egress_ip(network: ipaddress.IPv4Network) -> ipaddress.IPv4Address:
    return network.network_address + 2


def candidates():
    yield DEFAULT
    # Docker often allocates entire 172.x /16 ranges. Check, do not guess.
    for second in range(31, 19, -1):
        for third in (243, 244, 245, 246, 247, 248, 249, 250, 251, 252):
            yield ipaddress.IPv4Network(f"172.{second}.{third}.0/28")
    for second in range(254, 239, -1):
        for third in (240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250):
            yield ipaddress.IPv4Network(f"10.{second}.{third}.0/28")
    for third in range(240, 255):
        yield ipaddress.IPv4Network(f"192.168.{third}.0/28")


def docker_subnets():
    ids = execute("docker", "network", "ls", "-q").split()
    if not ids:
        raise ValueError("Docker network discovery unexpectedly returned nothing")
    info = json.loads(execute("docker", "network", "inspect", *ids))
    occupied = []
    own = []
    for item in info:
        labels = item.get("Labels") or {}
        options = item.get("Options") or {}
        is_ours = (labels.get("com.docker.compose.network") == "url_fetch_egress"
                   and options.get("com.docker.network.bridge.name") == BRIDGE)
        for record in (item.get("IPAM") or {}).get("Config") or []:
            cidr = record.get("Subnet")
            if not cidr:
                continue
            net = ipaddress.ip_network(cidr, strict=False)
            if not isinstance(net, ipaddress.IPv4Network):
                continue
            (own if is_ours else occupied).append(net)
    return occupied, own


def host_subnets():
    occupied = []
    routes = json.loads(execute("ip", "-j", "-4", "route", "show", "table", "all"))
    addresses = json.loads(execute("ip", "-j", "-4", "address", "show"))
    for item in routes:
        dst = item.get("dst")
        if not dst or dst == "default":
            continue
        occupied.append(ipaddress.ip_network(dst, strict=False))
    for interface in addresses:
        for addr in interface.get("addr_info", []):
            if addr.get("family") == "inet":
                occupied.append(ipaddress.ip_network(
                    f"{addr['local']}/{addr['prefixlen']}", strict=False))
    return [net for net in occupied if isinstance(net, ipaddress.IPv4Network)]


def pick(existing: ipaddress.IPv4Network | None,
         occupied: list[ipaddress.IPv4Network],
         own: list[ipaddress.IPv4Network]) -> ipaddress.IPv4Network:
    if len(own) > 1:
        raise ValueError("multiple existing URL egress networks; refuse readdress")
    if own:
        current = own[0]
        if existing is not None and existing != current:
            raise ValueError("existing URL egress Docker network differs from host configuration")
        if current.overlaps(next((n for n in occupied if current.overlaps(n)), current)) and any(
            current.overlaps(n) for n in occupied
        ):
            raise ValueError("existing URL egress network conflicts with another host subnet")
        # Keep the running network stable; never readdress an active deployment.
        return parse_subnet(str(current))
    if existing is not None and not any(existing.overlaps(n) for n in occupied):
        return existing
    for candidate in candidates():
        if not any(candidate.overlaps(n) for n in occupied):
            return candidate
    raise ValueError("no collision-free private URL egress /28 on this host")


def provision() -> tuple[str, str]:
    if os.geteuid() != 0 or os.environ.get("GITHUB_ACTIONS") == "true":
        raise ValueError("authorized root Ubuntu Host required (not CI)")
    st = ENV.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise ValueError("Production .env must be a regular non-linked file")
    before = ENV.read_bytes()
    lines = before.decode("utf-8").splitlines(keepends=True)
    found: dict[str, tuple[int, str]] = {}
    for index, raw in enumerate(lines):
        if raw.lstrip().startswith("#"):
            continue
        m = KV.match(raw.strip())
        if not m or m.group(1) not in (SUBNET_KEY, IP_KEY):
            continue
        key, value = m.groups()
        if key in found:
            raise ValueError("duplicate URL egress setting: " + key)
        found[key] = (index, value.strip().strip("'").strip('"'))
    if bool(SUBNET_KEY in found) != bool(IP_KEY in found):
        raise ValueError("partial URL egress configuration: require subnet AND address")
    existing = parse_subnet(found[SUBNET_KEY][1]) if SUBNET_KEY in found else None
    if existing is not None and found[IP_KEY][1] != str(egress_ip(existing)):
        raise ValueError("configured URL egress address must be subnet network + 2")
    docker, own = docker_subnets()
    occupied = docker + host_subnets()
    chosen = pick(existing, occupied, own)
    for key, value in ((SUBNET_KEY, str(chosen)), (IP_KEY, str(egress_ip(chosen)))):
        if key in found:
            index, _ = found[key]
            ending = "\r\n" if lines[index].endswith("\r\n") else "\n"
            lines[index] = key + "=" + value + ending
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(key + "=" + value + "\n")
    after = "".join(lines).encode("utf-8")
    if after == before:
        return str(chosen), "REUSED"
    fd, name = tempfile.mkstemp(dir=ROOT, prefix=".env-url-egress-")
    try:
        os.fchmod(fd, 0o600)
        os.fchown(fd, st.st_uid, st.st_gid)
        with os.fdopen(fd, "wb") as out:
            out.write(after)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, ENV)
        directory = os.open(ROOT, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return str(chosen), "UPDATED"


if __name__ == "__main__":
    try:
        subnet, status = provision()
        print(f"T90 URL egress subnet: {status} {subnet}; host bridge {BRIDGE} unchanged")
        print("No Docker network, Firewall policy, credentials or containers modified")
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as error:
        # No unexpected raw subprocess output, .env or secrets are ever logged.
        raise SystemExit("T90 URL egress subnet: BLOCKED — " + str(error))
