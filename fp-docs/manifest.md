# FeaturePilot Manifest

Schema: fp-manifest/v2
Generated: 2026-10-28T04:50:23Z
Project root: `D:\01-code\guangzhuang`
FP docs root: `fp-docs/`
Git SHA: 09e57a204bef92b829e4e7838d55c0888399ff0b
Working tree: dirty

## Precedence

For current-state facts, current code and command output win over settings and intel.
For target-state requirements, user instructions and approved active change artifacts win.

## Settings Files

| File | Role | Authoritative For | When To Read | Status |
| --- | --- | --- | --- | --- |
| `settings/agent.md` | Lean FeaturePilot policy adapter | workflow, constraints, external-doc pointers | workflow/policy questions only | present |
| `settings/frontend.md` | Frontend/UI/visual settings | UI implementation and visual acceptance | UI/page/prototype work only | present; Vue preset registered for `frontend/` |
| `settings/backend.md` | Backend/API/data/security settings | backend implementation and backend acceptance | backend/API/data/security/permission work only | present; project rules registered for `backend/` |
| `settings/code-standards.md` | Approved project code rules | appRoot-scoped project conventions | technical work with a registered Project rule sources reference only | present; registered by frontend/backend settings |
| `settings/prototype-style.md` | Prototype visual style reference | prototype generation consistency | prototype generation only | present |

## Code Map

| Provider | Status | Version | Index Path | Last Checked | Use As |
| --- | --- | --- | --- | --- | --- |
| CodeGraph | ready | 1.6.2 | `.codegraph/` | 2026-10-28T07:03:10Z | navigation-hint-only |

## Prototype Bases

| App | App Root | Mode | Manifest | When To Read |
| --- | --- | --- | --- | --- |
| frontend | `frontend/` | `static-modular` | `prototype-bases/frontend/manifest.json` | only no-build static prototype work for this app; verify source/owned-file fingerprints live |

## Intel Artifacts

| File | Purpose | When To Read | Freshness | Sources |
| --- | --- | --- | --- | --- |
| `intel/project-facts.md` | Optional generated facts cache | validation or non-obvious boundary lookup only | missing | approved discovery only |
| `intel/.freshness.json` | metadata-only freshness inputs for project facts | live refresh calculation only | missing | created with project facts only |
| `intel/unknowns.md` | Project-level unknowns | only when manifest lists relevant actual content | missing | human-owned, lazy, explicit approval |
| `intel/decisions.md` | Project-level decisions | only when manifest lists relevant actual content | missing | human-owned, lazy, explicit approval |

## External Project Docs

| File | Priority | Notes |
| --- | --- | --- |

## Critical Unknowns

- 腾讯云 SSH 主机指纹尚未通过控制台带外确认；目标 Linux、真实来源、HTTPS 与生产 E2E 保持阻塞。

## Consumption Rules

- Read this manifest first as an index, not as permission to read everything.
- Do **not** bulk-read all settings or intel files.
- Use `When To Read` to pull only the smallest relevant settings/intel set for the current phase and question.
- Treat generated intel as navigation and stale-prone hints, not proof of current behavior.
- Treat the Code Map row as discovery metadata only; live CodeGraph detection and current source win over its recorded state.
- Current code and command output win for current-state facts.
- Approved change artifacts win for target-state requirements.
- Re-open referenced source files before editing.
- Re-run commands before claiming validation.
- Missing referenced paths make dependent sections stale.
- Compute stale/conflict live from `.freshness.json`, current sources, and current generated body; never trust a stored verdict.
- UI-related phases must read `settings/frontend.md` when present.
- Prototype generation should read `settings/prototype-style.md` when present.
- Backend-related phases must read `settings/backend.md` when present.
