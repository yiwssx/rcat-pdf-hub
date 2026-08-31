# RCAT PDF Hub — UI/UX Design System

This document is the visual and interaction contract for RCAT PDF Hub 0.5.x and later. The goal is a **Colorful Workspace**: energetic and easy to scan, while remaining suitable for institutional use.

## 1. Product principles

1. **Color communicates function.** Color is used to separate tool families and states, never as decoration alone.
2. **One visual language.** Header, login, workspace, tools, advanced settings, jobs, admin and mobile navigation must use the same tokens, radii, shadows and icon treatment.
3. **Icons must explain the action.** Use vector icons with distinct silhouettes. Do not use emoji or Unicode characters as primary UI icons.
4. **Human login is not API authentication.** Local development uses the local admin form. Production uses organizational identity. Service API Keys belong to Admin/integration workflows only.
5. **Mobile is first-class.** All primary actions must remain usable at 390 px width without horizontal scrolling.
6. **Accessibility is a release requirement.** Keyboard focus, contrast, reduced motion and 44 px touch targets are part of the design system, not optional polish.

## 2. Color architecture

The canonical tokens live in `apps/web/app/design-system.css` and must be used instead of introducing arbitrary component-local colors.

### Brand

- Brand A: `#6d4aff` — violet
- Brand B: `#4b68ff` — blue
- Brand C: `#ff4f9a` — pink
- Brand D: `#ff8a3d` — orange

The product brand may use multi-stop gradients. Large brand surfaces should not fall back to plain white with a small colored icon.

### Tool families

- **Manage — violet → pink**: OCR, merge, organize, split, compress
- **Convert — cyan → blue**: PDF/image conversion, PDF/A, Office conversion
- **Decorate — orange → pink**: watermark, page numbers, stamping
- **Deliver — green → teal**: secure links and document archive

Individual tools may have their own accent colors, but they must remain visually compatible with their family.

### Semantic states

- Success: green
- Warning/queued: amber
- Error/danger: red
- Information/running: blue

Status must always include text or a shape in addition to color.

## 3. Surface hierarchy

Use three visual levels:

1. **Page background** — low-contrast multi-color ambient gradient.
2. **Section surface** — tinted family/semantic gradient that identifies context.
3. **Interactive card** — strongest local accent, clear icon, concise title and action affordance.

Avoid stacking several plain white cards without semantic separation.

## 4. Component rules

### Header

- Sticky and compact.
- Brand mark uses the core brand gradient.
- Active navigation uses a filled brand gradient, not a gray underline.

### Login

- Local development: username/password form only when local auth is enabled.
- Production: organization login only when OIDC is enabled.
- Service API Key must never be the default human login UI.
- Authentication icon uses the same vector/icon system as the rest of the app.

### Workspace

- Upload surface is a high-visibility action area.
- File target surface must be visually distinct from upload.
- File selection, preview and signed-link controls remain grouped around the selected file.

### Tool cards

Every tool card must have:

- a unique vector icon silhouette;
- a unique accent pair (`--tone` + `--tone2`);
- a short title;
- one-sentence description;
- a visible disabled state;
- hover/focus feedback that does not move layout.

Do not use the same generic document icon for unrelated tools.

### Advanced settings

Advanced controls should look like the detailed configuration state of the corresponding tool, not like a separate back-office application. Use a colored side accent and the same icon family.

### Jobs

- Queued = amber
- Running = blue
- Completed = green
- Failed = red

Keep operation name and progress visible before technical IDs.

### Admin

Admin is part of the same product, not a gray utility screen. Use the admin violet/blue family, while destructive actions retain semantic red.

Service API Keys are explicitly machine-to-machine credentials. Their placement in Admin is intentional.

### Mobile navigation

- Maximum five primary destinations.
- Center upload action is visually dominant.
- Use vector icons only.
- Minimum touch target 44 × 44 px.

## 5. Typography

Use the existing Thai-capable system stack:

`Noto Sans Thai`, `Leelawadee UI`, Tahoma, Arial, sans-serif.

Hierarchy:

- Hero: 40–74 px responsive
- Section title: 26–32 px
- Card title: 14–18 px
- Body: 12–16 px
- Metadata: 9–12 px

Avoid all-caps English labels as the only explanation of a section; Thai title must carry the primary meaning.

## 6. Spacing and shape

Canonical radii are defined as `--ds-radius-*` in `design-system.css`.

- Small controls: 10–14 px
- Cards: 18–24 px
- Major surfaces: 24–32 px

Use generous section gaps rather than borders everywhere. Shadows should communicate elevation, not decoration.

## 7. Accessibility requirements

Required for release:

- visible `:focus-visible` state;
- primary interactive targets at least 44 px high;
- disabled controls are visibly disabled and non-interactive;
- information is not encoded by color alone;
- `prefers-reduced-motion` disables nonessential animation/transition;
- no horizontal page scroll at 390 px;
- form labels remain visible; placeholder text is not a substitute for labels.

## 8. CSS authority and maintenance

Import order in `apps/web/app/layout.tsx` is intentional:

1. `globals.css` — baseline/shared structure
2. `app-v2.css` — current application layout
3. `ui-refresh.css` — 0.5.1 structural/auth/icon compatibility layer
4. `design-system.css` — **final visual authority**

New color, elevation and component-state work belongs in `design-system.css`. Do not add competing visual rules to the earlier layers.

When legacy structure is eventually consolidated, visual behavior must remain equivalent to the final design-system layer.

## 9. Release guardrail

Run:

```bash
make validate-ui
```

The UI gate verifies the authority import order, mandatory tokens and accessibility contracts. It is also included in `make validate-free` and `make validate-frontend`.

## 10. Change review checklist

Before merging UI changes, confirm:

- Does the change use an existing semantic token/family?
- Is the icon distinct and understandable without reading the title?
- Is the state obvious without relying only on color?
- Does it work at desktop and 390 px mobile widths?
- Can it be used by keyboard?
- Does it preserve local-vs-production authentication boundaries?
- Does it avoid exposing Service API Keys as user-login credentials?
- Does `make validate-ui` pass?
