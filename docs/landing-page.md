# CodeMosaic Landing Page Draft

## Hero

**CodeMosaic** is an **AI Code Privacy Gateway** for teams that want external AI coding help without sending raw proprietary source code outside the workstation boundary.

### Core promise

- Mask source code before it leaves the machine
- Keep reversible mappings local
- Measure semantic leakage after masking
- Block exports that still reveal too much business meaning

## The problem

Most teams are stuck between two bad options:

1. **Don’t use external AI tools** and lose engineering leverage
2. **Paste private code into AI tools** and accept unclear privacy risk

The real problem is not just “secret scanning.”
The real problem is: **after masking, is this code still safe enough to send?**

## The CodeMosaic approach

### 1. Prepare
- Run `scan` to detect obvious sensitive markers
- Run `mask` to generate a masked workspace and local mapping vault

### 2. Evaluate
- Run `leakage-report` to estimate how much business meaning still leaks after masking
- Apply policy-based thresholds with `Leakage Budget Gate`

### 3. Export safely
- Build a normal AI bundle for inspection
- Use `bundle --fail-on-threshold` or `CodeMosaic: Safe Export Bundle` to block unsafe exports

## Why it stands out

### Not just redaction
Most tools stop at “secrets hidden.”
CodeMosaic continues with **semantic leakage evaluation** and **export governance**.

### Reversible closed loop
CodeMosaic supports:

`mask -> AI -> patch -> unmask/apply`

That means the developer workflow stays practical, not just theoretically safer.

### Policy-driven governance
Teams can define different rules for different paths:

- stricter thresholds for sensitive modules
- looser thresholds for public SDK code
- path-based mapping encryption requirements
- segmented masking workflows by policy group

### Productized workflow
The same story works across:

- CLI
- VS Code prototype
- demo repo
- release assets
- documentation and launch material

## Ideal users

- Startups and teams using external AI coding assistants with private repositories
- Mid-sized engineering orgs that need a local-first AI governance starting point
- Security-conscious teams that want something lighter than a full enterprise DLP stack

## What to demo in 3 minutes

1. Show a repository with obvious internal URLs, tokens, and business terms
2. Run `Scan Workspace`
3. Run `Mask Workspace`
4. Open `Analyze Semantic Leakage`
5. Show that `Build AI Bundle` can succeed
6. Show that `Safe Export Bundle` can still be blocked
7. Open the leakage report and highlight the top-risk file
8. Open the Runs view and point at `Leakage gate: BLOCKED`

## Suggested visuals

- `assets/demo/workflow-overview.svg`
- `assets/demo/vscode-runs-view.svg`
- `assets/demo/safe-export-gate.svg`

## Open source direction

### Now
- local-first masking
- encrypted mapping vaults
- semantic leakage analysis
- export gating
- VS Code prototype

### Next
- stronger AST-based masking
- richer policy model
- better review UX for leakage findings
- CI/GitHub Actions governance recipes

## One-line pitch

**CodeMosaic helps teams use external AI coding tools without giving up control over what their code reveals.**
