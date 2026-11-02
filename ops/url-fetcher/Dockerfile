# Opt-in low-trust HTTPS fetcher. NOT part of ordinary API/worker image.
FROM python:3.12.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONNOUSERSITE=1

WORKDIR /srv
COPY apps/api/app/services/url_fetch_core.py /srv/url_fetch_core.py
COPY ops/url-fetcher/server.py /srv/server.py
USER 65534:65534
EXPOSE 8099
CMD ["python", "/srv/server.py"]
