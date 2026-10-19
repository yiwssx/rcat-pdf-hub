# Match the frozen upstream Gotenberg version in docker-compose.yml.
# LibreOffice's page layout depends on fonts available INSIDE this container.
FROM gotenberg/gotenberg:8.34.0

USER root

# Thai fallback fonts; these are not replacements for a document's exact font.
RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends fonts-thai-tlwg \
    && rm -rf /var/lib/apt/lists/*

# Institution-supplied, appropriately licensed font files are intentionally not
# committed to Git. Copy them to ops/gotenberg/fonts/ before building.
COPY fonts/ /usr/local/share/fonts/rcat/
RUN fc-cache -f

USER gotenberg
