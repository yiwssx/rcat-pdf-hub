#!/usr/bin/env bash
# Build a pinned decoder-only patched libheif in the OPTIONAL native sidecar.
# Never run in the normal API/RQ image. Requires build-container internet.
set -euo pipefail

EXPECTED_COMMIT=12a259a5882dd99d45ec5fc77e296a3b620d1e2e
TARGET=/opt/pdfhub/heif
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates git cmake ninja-build pkg-config g++ \
  libde265-dev libaom-dev libjpeg-dev libpng-dev
# Preserve runtime libraries when removing compilers; the native image
# carries only decoder binaries and the libraries required at runtime.
apt-mark manual libde265-0 libaom3 libjpeg62-turbo libpng16-16

mkdir -p /tmp/pdfhub-native-build
git clone --quiet --filter=blob:none --depth=1 --branch v1.23.7 \
  https://github.com/strukturag/libheif.git /tmp/pdfhub-native-build/libheif
actual=$(git -C /tmp/pdfhub-native-build/libheif rev-parse HEAD)
if [[ "$actual" != "$EXPECTED_COMMIT" ]]; then
  echo "Pinned libheif source commit mismatch: refusing build" >&2
  exit 1
fi

cmake -S /tmp/pdfhub-native-build/libheif \
  -B /tmp/pdfhub-native-build/build \
  -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$TARGET" \
  -DENABLE_PLUGIN_LOADING=OFF \
  -DWITH_LIBDE265=ON \
  -DWITH_AOM_DECODER=ON \
  -DWITH_UNCOMPRESSED_CODEC=ON \
  -DWITH_EXAMPLES=ON \
  -DWITH_GDK_PIXBUF=OFF \
  -DWITH_X265=OFF \
  -DWITH_AOM_ENCODER=OFF \
  -DBUILD_TESTING=OFF

cmake --build /tmp/pdfhub-native-build/build --parallel 2
cmake --install /tmp/pdfhub-native-build/build
test -f "$TARGET/lib/libheif.so.1"
test -x "$TARGET/bin/heif-dec"
LD_LIBRARY_PATH="$TARGET/lib" "$TARGET/bin/heif-dec" --version

# Never leave build toolchain, git metadata or source documents in the
# production decoder image. This is for decode-only / no HEVC encoder.
apt-get purge -y --auto-remove git g++ cmake ninja-build pkg-config libde265-dev libaom-dev libjpeg-dev libpng-dev
rm -rf /tmp/pdfhub-native-build /var/lib/apt/lists/*
