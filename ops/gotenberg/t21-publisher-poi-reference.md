# T21 disposable Gotenberg Publisher source-to-output reference

This development-only evidence case is executed in `scripts/test-t90-2-publisher-gotenberg.sh` using the existing disposable native Gotenberg lane. It does not touch Production or change Gotenberg runtime packages.

- Upstream: Apache POI `test-data/publisher/Sample.pub` at immutable commit `cdcdcf1833beb8483229be5989db1ee3b98232c2`, Git blob `b870168319048c9e8631c2338eb937e6f8f62b5b`.
- Independent source-text companion: Apache POI `test-data/publisher/Sample.txt`, same commit; page 1 includes `This is some text on the first page`; page 2 includes `This is the second page` and `This text is on page two`.
- Real output acceptance checks both pages' PDF text extraction and nonblank Poppler image rendering, exact two-page count, strict v3 CFB structural validation and unchanged SHA-256 source.
- The other pinned LibreOffice `fdo59355-1.pub` sample remains a known ambiguous blank-page sample, not evidence of successful second-page conversion. Successful Apache POI sample establishes a *narrow supported subset*, not universal Microsoft Publisher/Thai layout fidelity, independent RCAT QA or release approval.

This reference document also routes this change through the repository's existing native Gotenberg source-scoped CI job so the real conversion must actually execute before development status is promoted.
