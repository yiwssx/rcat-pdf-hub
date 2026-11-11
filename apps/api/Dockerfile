FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv "$VIRTUAL_ENV"

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends --only-upgrade perl-base && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      qpdf ghostscript poppler-utils \
      tesseract-ocr tesseract-ocr-tha tesseract-ocr-eng \
      fonts-noto-core \
      unpaper pngquant jbig2dec djvulibre-bin libchm1 wps2odt bubblewrap curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests

RUN useradd --create-home --uid 10001 pdfhub && mkdir -p /data && chown -R pdfhub:pdfhub /data /app
# The codec-only image must not contain even a writable-looking user-data
# directory. Its source bytes arrive over one authenticated request and exist
# only on private tmpfs. API/worker builds retain their original /data path.
ARG PDFHUB_NATIVE_ONLY=0
# Only the native sidecar may opt into building the patched decoder. The
# regular API image stays unchanged; this separately sourced runtime is
# pinned by upstream v1.23.7's exact full commit SHA in the installer.
ARG PDFHUB_HEIF_FROM_SOURCE=0
ARG PDFHUB_DWG_FROM_SOURCE=0
COPY build-pinned-cad.sh /tmp/build-pinned-cad.sh
COPY build-pinned-heif.sh /tmp/build-pinned-heif.sh
RUN if [ "$PDFHUB_NATIVE_ONLY" = "1" ]; then \
      rmdir /data; \
      if [ "$PDFHUB_HEIF_FROM_SOURCE" = "1" ]; then \
        bash /tmp/build-pinned-heif.sh; \
      fi; \
      if [ "$PDFHUB_DWG_FROM_SOURCE" = "1" ]; then \
        bash /tmp/build-pinned-cad.sh; \
      fi; \
    elif [ "$PDFHUB_HEIF_FROM_SOURCE" != "0" ] || [ "$PDFHUB_DWG_FROM_SOURCE" != "0" ]; then \
      echo "Only the dedicated native image may build the HEIF runtime" >&2; exit 1; \
    fi \
    && rm -f /tmp/build-pinned-heif.sh /tmp/build-pinned-cad.sh
USER pdfhub

EXPOSE 8000
CMD ["python", "-m", "app.entrypoint", "api"]
