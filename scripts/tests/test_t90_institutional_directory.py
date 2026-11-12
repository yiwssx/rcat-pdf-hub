"""T90 institutional directory: 90 exact named links, no duplicate engines or gates.

Read-only structural contract tests. The catalog is navigational, not an
independent claim of real-format functional or institutional user QA.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "apps/web/app/components/t90-directory-catalog.ts"
CANONICAL = ROOT / "contracts/pdf-tools.v1.json"
APP = ROOT / "apps/web/app"

MANAGE_ROUTES = {
    "M01": "/staged/edit-text",
    "M02": "/tools/compress",
    "M03": "/staged/document-assist?tool=summary",
    "M04": "/tools/merge-pdf",
    "M05": "/staged/translate",
    "M06": "/staged/document-assist?tool=evidence",
    "M07": "/staged/split-zip",
    "M08": "/staged/pdf-access?tool=unlock-pdf",
    "M09": "/staged/pdf-access?tool=protect-pdf",
    "M10": "/tools/split-rotate",
    "M11": "/staged/geometry?tool=M11",
    "M12": "/staged/signature",
    "M13": "/staged/document-data?tool=M13",
    "M14": "/staged/manage?tool=M14",
    "M15": "/staged/manage?tool=M15",
    "M16": "/staged/manage?tool=M16",
    "M17": "/staged/document-data?tool=M17",
    "M18": "/staged/manage?tool=M18",
    "M19": "/tools/page-numbers",
    "M20": "/staged/viewer",
    "M21": "/tools/watermark",
    "M22": "/staged/manage?tool=M22",
    "M23": "/staged/image-overlay",
    "M24": "/staged/flatten",
    "M25": "/staged/markup?tool=M25",
    "M26": "/staged/markup?tool=M26",
    "M27": "/staged/document-data?tool=M27",
    "M28": "/staged/geometry?tool=M28",
    "M29": "/staged/markup?tool=M29",
    "M30": "/staged/manage?tool=M30",
    "M31": "/staged/manage?tool=M31",
    "M32": "/staged/repair",
    "M33": "/staged/manage?tool=M33",
}


def catalog():
    source = CATALOG.read_text(encoding="utf-8")
    records = re.findall(r'(?m)^  (\{"id":".*?"\}),$', source)
    return [json.loads(row) for row in records]


class T90DirectoryTests(unittest.TestCase):
    def test_exact_90_canonical_ids_names_categories(self):
        reference = json.loads(CANONICAL.read_text(encoding="utf-8"))
        records = catalog()
        self.assertEqual(len(records), 90)
        self.assertEqual(len({item["id"] for item in records}), 90)
        self.assertEqual(
            {x["id"]: (x["title"], x["category"]) for x in records},
            {x["id"]: (x["title"], x["category"]) for x in reference["tools"]},
        )
        for family, count in (("manage", 33), ("to_pdf", 40), ("from_pdf", 17)):
            self.assertEqual(sum(x["category"] == family for x in records), count)

    def test_every_named_tool_links_to_a_real_existing_flow(self):
        records = catalog()
        self.assertEqual(set(MANAGE_ROUTES), {x["id"] for x in records if x["category"] == "manage"})
        for tool in records:
            id_ = tool["id"]
            href = tool["href"]
            if id_[0] == "M":
                self.assertEqual(href, MANAGE_ROUTES[id_])
            else:
                expected = "/staged/converters" if id_[0] == "T" else "/staged/exports"
                self.assertEqual(href, expected + "?tool=" + id_)
            url = urlsplit(href)
            self.assertTrue(url.path.startswith(("/staged/", "/tools/")))
            if url.path.startswith("/staged/"):
                self.assertTrue((APP / url.path.lstrip("/") / "page.tsx").is_file(), href)
            else:
                self.assertTrue((APP / "tools/[slug]/page.tsx").is_file(), href)
            tool_query = parse_qs(url.query).get("tool", [])
            if tool_query:
                self.assertEqual(len(tool_query), 1)
                self.assertLessEqual(len(tool_query[0]), 40)

    def test_private_t90_rollout_gate_is_server_side(self):
        page = (APP / "page.tsx").read_text(encoding="utf-8")
        component = (APP / "components/pdf-hub-app.tsx").read_text(encoding="utf-8")
        home = (APP / "components/v3-ui.tsx").read_text(encoding="utf-8")
        self.assertIn('export const dynamic = "force-dynamic"', page)
        self.assertIn('process.env.PDFHUB_T90_CODE_ROLLOUT_ENABLED === "true"', page)
        self.assertIn('process.env.PDFHUB_T90_PRIVATE_PILOT_ENABLED === "true"', page)
        self.assertIn("t90CatalogEnabled && institutionalPilot", component)
        self.assertIn("t90CatalogVisible ? (", home)
        self.assertIn("InstitutionalT90Directory", home)
        self.assertNotIn("NEXT_PUBLIC_PDFHUB_T90", page)
        overlay = (ROOT / "compose.t90-code-first.yaml").read_text(encoding="utf-8")
        web_block = overlay.split("  web:\n    environment:\n", 1)[1]
        self.assertIn('PDFHUB_T90_CODE_ROLLOUT_ENABLED: "true"', web_block)
        self.assertIn('PDFHUB_T90_PRIVATE_PILOT_ENABLED: "true"', web_block)
        preflight = (ROOT / "scripts/release1-host-preflight.py").read_text(encoding="utf-8")
        self.assertIn("T90_MARKER", preflight)


    def test_shared_workflows_open_requested_mode(self):
        geometry = (APP / "staged/geometry/staged-geometry-client.tsx").read_text(encoding="utf-8")
        metadata = (APP / "staged/document-data/staged-document-data-client.tsx").read_text(encoding="utf-8")
        self.assertIn('requestedToolId === "M28" ? "resize-pdf" : "crop-pdf"', geometry)
        for code in ('requestedToolId === "M13"', 'requestedToolId === "M27"'):
            self.assertIn(code, metadata)
        self.assertIn('requestedToolId', (APP / "staged/geometry/page.tsx").read_text(encoding="utf-8"))
        self.assertIn('requestedToolId', (APP / "staged/document-data/page.tsx").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
