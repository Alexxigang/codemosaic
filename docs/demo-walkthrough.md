# Demo Walkthrough

## What this demonstrates

- Scan a workspace before sending anything to an external AI tool
- Generate a masked workspace and encrypted mapping file
- Export an AI bundle from masked files
- Use the VS Code prototype to inspect recent runs and artifacts

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
5. Choose `Build AI Bundle`
6. Show the generated `ai-bundle.md`
7. Explain how `unmask-patch` can restore changes using the selected mapping

## Demo assets

- `assets/demo/workflow-overview.svg`
- `assets/demo/vscode-runs-view.svg`

## Speaker notes

- Emphasize that mapping files stay local
- Explain that masked code still preserves enough structure for external AI help
- Call out that mapping encryption is optional but recommended for local persistence
- Show that the VS Code prototype reduces the friction of the CLI workflow
