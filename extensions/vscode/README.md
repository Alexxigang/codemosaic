# CodeMosaic VS Code Prototype

这个目录提供一个轻量的 VS Code 插件原型，用来把仓库里的 CodeMosaic CLI 工作流包装进命令面板、状态栏和 Explorer 视图。

## 已有命令

- `CodeMosaic: Quick Workflow`
- `CodeMosaic: Scan Workspace`
- `CodeMosaic: Mask Workspace`
- `CodeMosaic: Plan Segments`
- `CodeMosaic: Mask Segmented Workspace`
- `CodeMosaic: Build AI Bundle`
- `CodeMosaic: Unmask Patch`
- `CodeMosaic: Rekey Mapping`
- `CodeMosaic: Rekey Recent Runs`
- `CodeMosaic: Show Encryption Providers`
- `CodeMosaic: Apply Patch`
- `CodeMosaic: Refresh Runs`

## 状态栏入口

左下角会显示 `CodeMosaic` 状态栏按钮，点击后会打开一个 quick workflow 菜单，常用动作包括：

- 扫描当前工作区
- 生成 masked workspace
- 导出 AI bundle
- 反脱敏 patch
- 应用 patch
- 打开最近一次 run 的 mapping / report / masked workspace
- 打开最近的 scan report / AI bundle

可通过设置 `codemosaic.statusBar.enabled` 关闭。

## Runs 视图

Explorer 中会出现 `CodeMosaic Runs` 视图，用来展示：

- 最新 `scan-report.json`
- 最新 `ai-bundle.md`
- `.codemosaic/runs/` 下最近的 run
- 每个 run 的 `mapping.json` / `mapping.enc.json`
- 每个 run 的 `report.json`
- run 对应的 masked workspace 根目录

## 使用方式

1. 在 VS Code 中打开 `extensions/vscode`
2. 按 `F5` 启动 Extension Development Host
3. 在新窗口中打开一个真实代码仓库
4. 点击状态栏 `CodeMosaic`，或从命令面板执行 `CodeMosaic:*`
5. 在 Explorer 的 `CodeMosaic Runs` 视图中查看最近产物

## 依赖前提

- 目标工作区机器上可运行 `python -m codemosaic`
- 如果不是当前单仓开发方式，可在设置里调整：
  - `codemosaic.cliCommand`
  - `codemosaic.cliArgs`
  - `codemosaic.policyPath`
  - `codemosaic.defaultPassphraseEnv`
  - `codemosaic.encryptionProvider`

## 打包与安装

### 本地打包

```bash
python scripts/package_vscode_extension.py --overwrite
```

默认会输出到仓库根目录的 `dist/`。

### 本地安装

在 VS Code 中执行：

- `Extensions: Install from VSIX...`
- 选择 `dist/` 下生成的 `.vsix` 文件

## 当前限制

- 这是原型扩展，还没有 Webview 和后台任务管理
- 多根工作区目前只取第一个 folder
- 视图当前主要依赖 `.codemosaic/runs/` 与 `report.json`
- 还没有签名发布流程
