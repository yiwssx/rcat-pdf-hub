#!/usr/bin/env bash
# This command runs only on RCAT Ubuntu Docker HOST as root (sudo).
# Does NOT deploy containers, change DNS/SSO or process user documents.
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "${EUID}" -eq 0 ]] || { echo 'Use sudo for Production provisioning' >&2; exit 2; }
[[ "${GITHUB_ACTIONS:-false}" != true ]] || { echo 'No CI Production provisioning' >&2; exit 2; }
test -f .env || { echo 'Existing institutional .env required' >&2; exit 2; }
command -v systemctl >/dev/null || { echo 'systemd required' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker host required' >&2; exit 2; }

python3 scripts/provision-t90-runtime-secrets.py
# Reserve a free, Host-specific /28; never touch existing Docker networks.
python3 scripts/provision-t90-url-egress-network.py
# Retain the immutable reviewed scripts outside the Git checkout for boot.
install -d -m 0755 /usr/local/libexec/pdfhub
install -m 0755 ops/url-fetcher/install-host-egress-firewall.sh \
  /usr/local/libexec/pdfhub/install-host-egress-firewall.sh
install -m 0755 ops/url-fetcher/verify-host-egress-firewall.sh \
  /usr/local/libexec/pdfhub/verify-host-egress-firewall.sh
install -m 0755 ops/url-fetcher/ensure-host-egress-firewall.sh \
  /usr/local/libexec/pdfhub/ensure-host-egress-firewall.sh
install -m 0644 ops/url-fetcher/systemd/pdfhub-url-firewall-boot.service \
  /etc/systemd/system/pdfhub-url-firewall-boot.service
install -m 0644 ops/url-fetcher/systemd/pdfhub-url-firewall-guard.service \
  /etc/systemd/system/pdfhub-url-firewall-guard.service
install -m 0644 ops/url-fetcher/systemd/pdfhub-url-firewall-guard.timer \
  /etc/systemd/system/pdfhub-url-firewall-guard.timer
systemctl daemon-reload
# Initial boot unit enforces exact iptables/FORWARD/INPUT chain. An unknown
# existing policy fails closed rather than replacing any firewall rules.
systemctl enable pdfhub-url-firewall-boot.service >/dev/null
systemctl start pdfhub-url-firewall-boot.service
systemctl enable --now pdfhub-url-firewall-guard.timer >/dev/null
systemctl start pdfhub-url-firewall-guard.service
bash /usr/local/libexec/pdfhub/verify-host-egress-firewall.sh
systemctl is-active --quiet pdfhub-url-firewall-guard.timer
echo 'T90 Production local secrets and host firewall lease: PROVISIONED'
echo 'No container has been deployed or feature flag enabled by this command.'
