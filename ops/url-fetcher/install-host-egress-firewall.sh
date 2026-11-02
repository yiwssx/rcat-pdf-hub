#!/usr/bin/env bash
# T90-2 — MANUAL host-side firewall installer for the optional URL sidecar.
# Never invoked by Docker build/Compose/CI. Must be reviewed and run by root.
# Targets the fixed source IP 172.30.243.2/32 of the egress bridge only.
# Refuses to create an attestation unless all rules are installed.
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Run as root on the Docker HOST, not inside any container." >&2
  exit 1
fi
for program in iptables install mkdir; do
  command -v "$program" >/dev/null || { echo "Missing $program" >&2; exit 1; }
done

# Match the host-side Docker bridge interface, not only a container source
# address, which an attacker could alter by explicitly binding another IP.
BRIDGE_IF=br-pdfhub-url
CHAIN=PDFHUB_T90_URL_EGRESS
ATTESTATION=/etc/pdfhub/url-egress.attested
# DOCKER-USER is a Docker iptables backend hook. Do NOT silently downgrade
# to an unfiltered Docker nftables backend or make firewall exemptions.
iptables -w -S DOCKER-USER >/dev/null || {
  echo "Docker DOCKER-USER chain unavailable: use a reviewed equivalent nftables policy." >&2
  exit 1
}
iptables -w -C FORWARD -j DOCKER-USER >/dev/null || {
  echo "DOCKER-USER is not reached from FORWARD: refusing nftables/iptables bypass." >&2
  exit 1
}
if iptables -w -S "$CHAIN" >/dev/null 2>&1; then
  echo "Existing URL fetcher firewall chain: review manually; not overwriting." >&2
  exit 1
fi

iptables -w -N "$CHAIN"

# Block reserved/internal destinations before any public HTTPS allowance.
# The public URL fetcher additionally validates every DNS A/AAAA response
# and connects only to a pinned, globally routable IPv4 address.
for prefix in \
  0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 \
  169.254.0.0/16 172.16.0.0/12 192.0.0.0/24 \
  192.0.2.0/24 192.168.0.0/16 198.18.0.0/15 \
  198.51.100.0/24 203.0.113.0/24 224.0.0.0/4 \
  240.0.0.0/4
do
  iptables -w -A "$CHAIN" -d "$prefix" -j REJECT --reject-with icmp-port-unreachable
done

# Only public TCP/443 may leave. No arbitrary TCP, UDP, SMTP, metadata APIs,
# internal DNS or HTTP destinations are allowed from the external interface.
iptables -w -A "$CHAIN" -p tcp --dport 443 -j RETURN
iptables -w -A "$CHAIN" -j REJECT --reject-with icmp-port-unreachable

# FORWARD controls containers' routed traffic. INPUT separately denies
# container-to-host traffic that may bypass DOCKER-USER (the host is local).
iptables -w -I DOCKER-USER 1 -i "$BRIDGE_IF" -j "$CHAIN"
iptables -w -I INPUT 1 -i "$BRIDGE_IF" -j DROP

iptables -w -C DOCKER-USER -i "$BRIDGE_IF" -j "$CHAIN"
iptables -w -C INPUT -i "$BRIDGE_IF" -j DROP
iptables -w -C "$CHAIN" -p tcp --dport 443 -j RETURN
iptables -w -C "$CHAIN" -j REJECT --reject-with icmp-port-unreachable

# Do NOT attest by simply writing a boot-id marker. The standalone host
# verifier must inspect the exact firewall rule chain/order and only then
# refresh a short-lived lease. A host systemd timer must keep it renewed.
mkdir -p /etc/pdfhub
if [[ ! -e "$ATTESTATION" ]]; then
  : > "$ATTESTATION"
fi
chmod 0444 "$ATTESTATION"
VERIFY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/verify-host-egress-firewall.sh"
bash "$VERIFY"
echo "Initial URL egress firewall verified. Install the separate host guard timer."
echo "Rules expire at reboot unless a reviewed host firewall restoration policy exists."
