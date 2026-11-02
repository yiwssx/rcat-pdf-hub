#!/usr/bin/env bash
# Manual/periodic host-side T33 firewall verifier and short-lived attestation.
# Run only as root on the Docker HOST, never inside the URL fetcher.
# Refuses unexpected rules, rule order or missing Docker iptables hook.
set -euo pipefail

CHAIN=PDFHUB_T90_URL_EGRESS
BRIDGE_IF=br-pdfhub-url
ATTESTATION=/etc/pdfhub/url-egress.attested
VERSION=RCAT-T90-2-URL-FETCH-EGRESS-V2

deny_prefixes=(
  0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8
  169.254.0.0/16 172.16.0.0/12 192.0.0.0/24
  192.0.2.0/24 192.168.0.0/16 198.18.0.0/15
  198.51.100.0/24 203.0.113.0/24 224.0.0.0/4
  240.0.0.0/4
)

invalidate() {
  # In-place overwrite preserves the inode bind-mounted read-only into the
  # container. Atomic rename leaves the container reading the old inode.
  if [[ -f "$ATTESTATION" ]]; then
    printf 'DISABLED\n' > "$ATTESTATION" || true
  fi
}
fail() {
  invalidate
  echo "T33 URL firewall verification failed; attestation invalidated." >&2
  exit 1
}
trap fail ERR

[[ "$EUID" -eq 0 ]] || fail
command -v iptables >/dev/null || fail
command -v date >/dev/null || fail
[[ -r /proc/sys/kernel/random/boot_id ]] || fail
BOOT_ID=$(cat /proc/sys/kernel/random/boot_id)
[[ -n "$BOOT_ID" ]] || fail

# The Docker-iptables backend must run DOCKER-USER before any FORWARD ACCEPT.
# This does not apply to Docker's native nftables backend: fail closed.
forward_rules=$(iptables -w -S FORWARD) || fail
user_rules=$(iptables -w -S DOCKER-USER) || fail
input_rules=$(iptables -w -S INPUT) || fail
chain_rules=$(iptables -w -S "$CHAIN") || fail

[[ "$(printf '%s\n' "$forward_rules" | sed -n '2p')" == "-A FORWARD -j DOCKER-USER" ]] || fail
[[ "$(printf '%s\n' "$user_rules" | sed -n '2p')" == "-A DOCKER-USER -i $BRIDGE_IF -j $CHAIN" ]] || fail
[[ "$(printf '%s\n' "$input_rules" | sed -n '2p')" == "-A INPUT -i $BRIDGE_IF -j DROP" ]] || fail

readarray -t observed <<< "$chain_rules"
expected=("-N $CHAIN")
for prefix in ${deny_prefixes[@]}; do
  expected+=("-A $CHAIN -d $prefix -j REJECT --reject-with icmp-port-unreachable")
done
expected+=("-A $CHAIN -p tcp -m tcp --dport 443 -j RETURN")
expected+=("-A $CHAIN -j REJECT --reject-with icmp-port-unreachable")

[[ "${#observed[@]}" -eq "${#expected[@]}" ]] || fail
for i in "${!expected[@]}"; do
  [[ "${observed[$i]}" == "${expected[$i]}" ]] || fail
done

# This is a lease, not an eternal boot marker. The fetcher checks every request.
# Host-side systemd timer must refresh it.
mkdir -p /etc/pdfhub
[[ -f "$ATTESTATION" && ! -L "$ATTESTATION" ]] || fail
printf '%s\n%s\n%s\n' "$VERSION" "$BOOT_ID" "$(date +%s)" > "$ATTESTATION"
chmod 0444 "$ATTESTATION"
echo "T33 firewall rules match expected order; time-limited lease refreshed."
