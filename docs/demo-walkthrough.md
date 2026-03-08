# Demo Walkthrough

## What this demonstrates

- Scan a workspace before sending anything to an external AI tool
- Generate a masked workspace and encrypted mapping file
- Measure semantic leakage after masking
- Show that a normal masked bundle can exist while a policy-gated export is still blocked
- Use the VS Code prototype to inspect recent runs, leakage state, and safe export decisions

## Suggested demo script

如需一键准备演示产物，可先运行：

```bash
python scripts/run_demo_workflow.py --encrypt-mapping --clean
```

然后按下面的顺序演示：

1. Run `CodeMosaic: Quick Workflow`
2. Choose `Scan workspace`
3. Choose `Mask workspace` and enable encrypted mapping
4. Open the `CodeMosaic Runs` view and click the latest mapping and report
5. Choose `Analyze semantic leakage`
6. Explain the leakage score and highest-risk files
7. Choose `Build AI Bundle` and show the generated `ai-bundle.md`
8. Choose `Safe Export Bundle` and show that the leakage gate blocks the export
9. Open `leakage-report.json` and highlight the gate reasons
10. Explain how `unmask-patch` can restore changes using the selected mapping

## Demo assets

- `assets/demo/workflow-overview.svg`
- `assets/demo/vscode-runs-view.svg`
- `dist/demo-output/demo-summary.md`

## Speaker notes

- Emphasize that mapping files stay local
- Explain that masking alone is not enough; the real question is whether business meaning still leaks
- Show that the safe export gate answers “can we send this to external AI right now?”
- Call out that mapping encryption is optional but recommended for local persistence
- Show that the VS Code prototype reduces the friction of the CLI workflow
