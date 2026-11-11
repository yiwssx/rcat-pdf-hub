#!/usr/bin/env bash
# Pinned, internally operated GNU LibreDWG 0.14 R2000 decoder for the
# isolated native-only image. GNU GPL-3.0-or-later: review obligations before
# distributing this binary/image outside the institution.
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
url='https://ftpmirror.gnu.org/libredwg/libredwg-0.14.tar.gz'
expected='cb6ee0b078c6d9e0f09d66f1feac33ba6342df88ae544e9f9335fab475218351'
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  ca-certificates curl build-essential autoconf automake libtool \
  pkg-config texinfo libxml2-dev zlib1g-dev libgmp-dev libpcre2-dev xz-utils
curl --fail --show-error --silent --location --retry 3 --max-time 180 \
  --proto '=https' --proto-redir '=https' "$url" -o /tmp/libredwg-0.14.tar.gz
printf '%s  %s\n' "$expected" /tmp/libredwg-0.14.tar.gz | sha256sum -c -
mkdir -p /tmp/libredwg-build
tar -xzf /tmp/libredwg-0.14.tar.gz -C /tmp/libredwg-build --strip-components=1
(
  cd /tmp/libredwg-build
  ./configure --prefix=/opt/pdfhub/cad --disable-python --disable-silent-rules
  make -j 2
  make install
)
printf '%s\n' /opt/pdfhub/cad/lib > /etc/ld.so.conf.d/pdfhub-cad.conf
ldconfig
/opt/pdfhub/cad/bin/dwgread --version
/opt/pdfhub/cad/bin/dwgwrite --version
# Production native image needs reader only; no ezdxf fixture package.
rm -rf /tmp/libredwg-build /tmp/libredwg-0.14.tar.gz /var/lib/apt/lists/*
