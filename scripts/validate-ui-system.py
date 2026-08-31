#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "apps/web/app/layout.tsx"
DESIGN = ROOT / "apps/web/app/design-system.css"
REFRESH = ROOT / "apps/web/app/ui-refresh.css"
APP = ROOT / "apps/web/app/components/pdf-hub-app.tsx"
GUIDE = ROOT / "UI_UX.md"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ui design system: FAIL — {message}")


def main() -> int:
    for path in (LAYOUT, DESIGN, REFRESH, APP, GUIDE):
        require(path.is_file() and path.stat().st_size > 0, f"missing {path.relative_to(ROOT)}")

    layout = LAYOUT.read_text(encoding="utf-8")
    design = DESIGN.read_text(encoding="utf-8")
    refresh = REFRESH.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    guide = GUIDE.read_text(encoding="utf-8")

    imports = [
        'import "./globals.css";',
        'import "./app-v2.css";',
        'import "./ui-refresh.css";',
        'import "./design-system.css";',
    ]
    positions = [layout.find(item) for item in imports]
    require(all(pos >= 0 for pos in positions), "stylesheet authority imports are incomplete")
    require(positions == sorted(positions), "design-system.css must be imported after legacy structural layers")
    require(layout.strip().startswith(imports[0]), "globals.css must remain the baseline stylesheet")

    required_tokens = [
        "--ds-brand-a", "--ds-brand-b", "--ds-brand-c", "--ds-brand-d",
        "--ds-manage-a", "--ds-convert-a", "--ds-decorate-a", "--ds-deliver-a",
        "--ds-success", "--ds-warning", "--ds-danger", "--ds-info",
        "--ds-radius-lg", "--ds-shadow-2", "--ds-focus",
    ]
    for token in required_tokens:
        require(token in design, f"missing semantic token {token}")

    for selector in (
        ".group-manage", ".group-convert", ".group-decorate", ".group-deliver",
        ".welcomeHero", ".authCard", ".platformStrip", ".workspaceGrid",
        ".advancedSection", ".jobsSection", ".adminPage", ".mobileNav",
    ):
        require(selector in design, f"design system does not own {selector}")

    require(":focus-visible" in design, "keyboard focus-visible contract is missing")
    require("min-height: 44px" in design, "44px minimum touch target contract is missing")
    require("prefers-reduced-motion" in design, "reduced-motion accessibility contract is missing")

    tool_icons = (
        "scan", "merge", "organize", "split", "compress", "image", "imagePdf",
        "watermark", "numbers", "archive", "office", "stamp", "link", "pdfa",
    )
    require("function ToolIcon" in app, "shared vector ToolIcon component is missing")
    for icon in tool_icons:
        require(f'name === "{icon}"' in app, f"distinct vector icon is missing: {icon}")
    require("Service API Key • pdfh_" not in app, "machine API key leaked back into the human login UI")
    require("localLogin" in app and "เข้าสู่ระบบ PDF Hub" in app, "local human login UI is missing")

    # Some legacy JSX spans still carry fallback Unicode text for older browsers.
    # The compatibility layer must mask those carriers with the canonical vector system.
    require("-webkit-mask: var(--app-symbol)" in refresh, "legacy symbol carriers are not normalized to vector masks")
    require("mobileNav button:not(.navScan)" in refresh, "mobile navigation vector normalization is missing")

    guide_requirements = (
        "Colorful Workspace",
        "Service API Key must never be the default human login UI",
        "Minimum touch target 44 × 44 px",
        "design-system.css",
        "make validate-ui",
    )
    for text in guide_requirements:
        require(text in guide, f"UI_UX.md is missing policy: {text}")

    print("ui design system: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
