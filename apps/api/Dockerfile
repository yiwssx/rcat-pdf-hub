FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv "$VIRTUAL_ENV"

RUN apt-get update && apt-get install -y --no-install-recommends \
      qpdf ghostscript poppler-utils \
      tesseract-ocr tesseract-ocr-tha tesseract-ocr-eng \
      fonts-noto-core \
      unpaper pngquant jbig2dec curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY tests ./tests

RUN useradd --create-home --uid 10001 pdfhub && mkdir -p /data && chown -R pdfhub:pdfhub /data /app
USER pdfhub

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
