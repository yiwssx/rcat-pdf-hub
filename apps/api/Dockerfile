FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv "$VIRTUAL_ENV"

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      qpdf ghostscript poppler-utils \
      tesseract-ocr tesseract-ocr-tha tesseract-ocr-eng \
      fonts-noto-core \
      unpaper pngquant jbig2dec curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && pip check
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app
COPY tests ./tests

RUN useradd --create-home --uid 10001 pdfhub && mkdir -p /data && chown -R pdfhub:pdfhub /data /app
USER pdfhub

EXPOSE 8000
CMD ["python", "-m", "app.entrypoint", "api"]
