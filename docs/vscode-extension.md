# VS Code Extension Prototype

## 目标

把 `codemosaic` CLI 的关键流程包装成 VS Code 命令，降低首次使用门槛。

## 当前命令

- `CodeMosaic: Quick Workflow`
- `CodeMosaic: Scan Workspace`
- `CodeMosaic: Analyze Semantic Leakage`
- `CodeMosaic: Mask Workspace`
- `CodeMosaic: Plan Segments`
- `CodeMosaic: Mask Segmented Workspace`
- `CodeMosaic: Safe Export Bundle`
- `CodeMosaic: Build AI Bundle`
- `CodeMosaic: Unmask Patch`
- `CodeMosaic: Rekey Mapping`
- `CodeMosaic: Rekey Recent Runs`
- `CodeMosaic: Show Encryption Providers`
- `CodeMosaic: Apply Patch`
- `CodeMosaic: Refresh Runs`

## 设计要点

- 不重写核心能力，直接调用已有 CLI
- 使用 VS Code `OutputChannel` 展示执行日志
- 提供状态栏入口，降低命令面板使用门槛
- 提供 `CodeMosaic Runs` 树视图，展示最近 run 和产物
- `unmask-patch` 默认优先让用户从最近 run 的 mapping 中选择
- 加密 mapping 时，使用密码输入框临时注入环境变量
- 保持配置项最少，优先围绕现有单仓工作流

## 打包发布

- 本地打包：`python scripts/package_vscode_extension.py --overwrite`
- GitHub Actions：`.github/workflows/package-vscode-extension.yml` 会生成 VSIX artifact
- 当前方案不依赖 `vsce`，便于在纯 Python/Node 环境下快速验证

## 后续增强

- 状态栏文案根据最近 run 动态变化
- 右键菜单与更多上下文动作
- 直接从视图里触发更多工作流动作
- Webview 风险报告与 bundle 预览
- 签名发布与扩展市场发布流程
