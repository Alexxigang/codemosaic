# codemosaic

一个本地优先的开源代码脱敏工具，用来在把代码发送给外部 AI 编程工具前，先把敏感标识符、字符串和注释“打马赛克”，并在 AI 返回补丁后再映射回原始代码。

## 当前状态

- 已实现 `v0.1` CLI 原型
- 支持 `Python` 词法级脱敏
- 支持 `JS/TS/JSX/TSX` 专用词法脱敏，以及 `Java/Go/Rust` 轻量文本兜底
- 支持本地 `mapping vault`、可选口令加密与 `unified diff` 回填
- 支持 `scan` 风险扫描与 `bundle` 上下文导出
- 支持 `VS Code` 插件原型（含 recent runs 树视图）
- 支持本地 `VSIX` 打包与 GitHub Actions 打包工作流
- 默认只依赖 Python 3.11+ 标准库；VS Code 原型只依赖本机已有 Node / VS Code 运行环境

## 为什么做这个项目

很多团队希望利用外部 AI 提效，但又不希望把核心算法、业务术语、敏感常量和内部接口直接暴露给第三方模型。`codemosaic` 的目标不是“完美匿名化”，而是作为一个本地的 Code Privacy Gateway，显著降低源码明文泄露风险。

## MVP 设计

### 核心原则

- 本地优先：映射表只保存在本地工作机
- 结构保真：尽量保留函数、控制流和文件布局
- 确定性映射：同一轮运行中，相同原文得到相同占位符
- 可逆回填：AI 返回补丁后可翻译回原始代码
- 策略可配：通过 `policy.sample.yaml` 调整包含范围和脱敏行为

### 架构分层

- `Policy Loader`：加载 JSON 或简单 YAML 子集策略
- `Mask Engine`：对源码进行脱敏
- `Mapping Vault`：记录 `masked <-> original` 映射
- `Workspace Runner`：遍历目录、输出 masked workspace
- `JS/TS Masker`：处理模板字符串、注释和标识符等 JS/TS 语法片段
- `Scanner`：识别仓库中的高风险敏感内容线索
- `Bundle Builder`：导出给外部 AI 的 Markdown 上下文包
- `Patch Translator`：把 AI 生成的 patch 从 masked token 翻译回真实 token
- `VS Code Prototype`：把常用 CLI 流程包装进编辑器命令与 Runs 视图

## 快速开始

### 1. 先扫描风险

```bash
python -m codemosaic scan ./your-repo --policy policy.sample.yaml --output scan-report.json
```

### 2. 生成脱敏工作区

```bash
python -m codemosaic mask ./your-repo --policy policy.sample.yaml
```

如果你希望本地映射文件加密保存：

```bash
$env:CODEMOSAIC_PASSPHRASE="change-me"
python -m codemosaic mask ./your-repo --policy policy.sample.yaml --encrypt-mapping --passphrase-env CODEMOSAIC_PASSPHRASE
```

默认会：

- 输出脱敏后的目录到 `./your-repo.masked`
- 输出映射与报告到 `./your-repo/.codemosaic/runs/<run-id>/`

### Policy-Driven Mapping Encryption

This project is intentionally moving beyond plain secret scanning into semantic leakage control: not just ?did we redact secrets??, but also ?did business meaning still leak??.

You can require encrypted mappings for specific paths directly in `policy.sample.yaml` style rules:

```yaml
mapping:
  require_encryption: false
  encryption_provider: prototype-v1
  rules:
    src/secret/**:
      require_encryption: true
      encryption_provider: aesgcm-v1
```

If a run includes files under `src/secret/**`, `mask` now requires a passphrase and blocks plaintext mapping output.

### Leakage Budget Gate

`codemosaic` can now enforce a semantic leakage budget before you export code to external AI tools. This is the key differentiator: not just masking code, but deciding whether the masked result is still safe enough to leave your boundary.

```yaml
leakage:
  max_total_score: 20
  max_file_score: 8
  rules:
    src/secret/**:
      max_total_score: 4
      max_file_score: 0
```

Use `leakage-report --fail-on-threshold` for CI checks, or `bundle --fail-on-threshold` to block unsafe exports automatically.

### 3. 为外部 AI 导出上下文包

```bash
python -m codemosaic bundle ./your-repo.masked --output ai-bundle.md
```

### 4. 把 AI 返回的补丁翻译回原始代码

```bash
python -m codemosaic unmask-patch ./ai.patch \
  --mapping ./your-repo/.codemosaic/runs/<run-id>/mapping.json \
  --output ./translated.patch
```

如果 mapping 是加密的：

```bash
$env:CODEMOSAIC_PASSPHRASE="change-me"
python -m codemosaic unmask-patch ./ai.patch \
  --mapping ./your-repo/.codemosaic/runs/<run-id>/mapping.enc.json \
  --output ./translated.patch \
  --passphrase-env CODEMOSAIC_PASSPHRASE
```

### 5. 应用补丁

```bash
python -m codemosaic apply ./translated.patch --target ./your-repo
```

内部会调用 `git apply`，也支持 `--check` 和 `--3way`。

## 命令说明

### `scan`

```bash
python -m codemosaic scan <source> [--policy <file>] [--output <report.json>]
```

输出 URL、邮箱、手机号、疑似密钥、内网主机和注释提示词等风险线索统计。

### `leakage-report`

```bash
python -m codemosaic leakage-report <masked-source> [--policy <file>] [--output <report.json>] [--fail-on-threshold]
```

推荐对已经 masking 后的工作区执行，用来回答“代码虽然脱敏了，但还残留多少业务语义”。
推荐对已经 masking 后的工作区执行，用来回答“代码虽然脱敏了，但还残留多少业务语义”。
### `mask`

```bash
python -m codemosaic mask <source> [--policy <file>] [--output <dir>] [--run-id <id>] [--encrypt-mapping] [--encryption-provider <name>] [--passphrase-env <ENV>] [--passphrase-file <file>]
```

输出：

- `masked workspace`
- `mapping.json` 或 `mapping.enc.json`
- `report.json`

### `mask-segmented`

```bash
python -m codemosaic mask-segmented <source> [--policy <file>] [--output <dir>] [--run-id-prefix <prefix>] [--encrypt-mapping] [--encryption-provider <name>] [--passphrase-env <ENV>] [--passphrase-file <file>]
```

根据路径级 mapping 规则把一次处理拆成多个 segment，每个 segment 生成独立的 masked workspace、mapping 和 report。

### `plan-segments`

```bash
python -m codemosaic plan-segments <source> [--policy <file>] [--output <plan.json>]
```

预览当前策略会把仓库切成哪些 segment，适合在真正执行前检查 provider、加密要求和文件分布。

### `bundle`

```bash
python -m codemosaic bundle <source> [--policy <file>] [--output <file>] [--max-files 20] [--max-chars 12000] [--leakage-report <report.json>] [--fail-on-threshold]
```

推荐对 `masked workspace` 使用，只导出最小必要上下文。

### `unmask-patch`

```bash
python -m codemosaic unmask-patch <patch> --mapping <mapping.json|mapping.enc.json> [--output <file>] [--passphrase-env <ENV>] [--passphrase-file <file>]
```

### `rekey-mapping`

```bash
python -m codemosaic rekey-mapping <mapping.json|mapping.enc.json> [--output <file>] [--encryption-provider <name>] [--passphrase-env <ENV>] [--passphrase-file <file>] [--new-passphrase-env <ENV>] [--new-passphrase-file <file>]
```

用于对本地 mapping 做重新加密、口令轮换，或把加密 mapping 解包成明文 mapping；当前默认 provider 为 `prototype-v1`，接口已预留后续接入更成熟实现。

### `list-providers`

```bash
python -m codemosaic list-providers
```

用于查看当前环境中可用的 mapping 加密 provider；如果本机安装了额外加密库，列表会自动出现对应后端。

### `rekey-runs`

```bash
python -m codemosaic rekey-runs <workspace> [--limit <n>] [--encryption-provider <name>] [--passphrase-env <ENV>] [--passphrase-file <file>] [--new-passphrase-env <ENV>] [--new-passphrase-file <file>]
```

用于批量重包 `.codemosaic/runs/` 下的 mapping 文件；可按最近 run 数量限制范围，适合口令轮换和本地资产整理。

### `apply`

```bash
python -m codemosaic apply <patch> --target <repo> [--check] [--3way]
```

## VS Code 原型

- 扩展目录：`extensions/vscode/`
- 原型说明：`docs/vscode-extension.md`
- 扩展 README：`extensions/vscode/README.md`
- Explorer 中提供 `CodeMosaic Runs` 视图
- `unmask-patch` 会优先从最近 run 中选择 mapping

## 打包 VS Code 扩展

```bash
python scripts/package_vscode_extension.py --overwrite
```

生成的 `.vsix` 默认输出到 `dist/`，可在 VS Code 中通过 `Extensions: Install from VSIX...` 安装。

## 安全边界

- 它降低的是“源码明文泄露风险”，不是“零信息泄露”
- 控制流、文件结构和上下文仍可能让模型推断业务语义
- 如果 prompt 里补充了业务背景，仍可能发生侧信道泄露
- 当前 `scan` 只能发现一部分风险线索，不等于完整 DLP
- 当前 mapping 加密是标准库实现的口令保护封装，适合本地原型与开源首版，但仍建议后续接受独立安全审查
- 对高敏场景，建议结合 DLP、审计、最小上下文发送和自托管模型

## 已实现范围

### In scope

- Python 词法级脱敏
- JS/TS/JSX/TSX 专用词法脱敏
- 通用文本代码文件的轻量兜底脱敏
- 本地映射表与 patch 回填
- mapping 可选口令加密
- 风险扫描与 AI bundle 导出
- VS Code 插件原型与 recent runs 树视图
- VSIX 打包脚本、文档、样例策略、基础测试、CI 配置

### Out of scope

- TypeScript AST 级精确保真
- 代理模式 / 企业级策略平台
- 基于语义的机密发现与分类器
- 签名发布与扩展市场发布自动化

## 文档

- `docs/brainstorm.md`
- `docs/architecture.md`
- `docs/threat-model.md`
- `docs/vscode-extension.md`
- `docs/leakage-gate.md`
- `docs/ci-governance.md`
- `extensions/vscode/README.md`
- `scripts/package_vscode_extension.py`
- `scripts/bootstrap_repository.py`
- `scripts/run_demo_workflow.py`
- `docs/demo-walkthrough.md`
- `docs/release-playbook.md`
- `docs/landing-page.md`
- `docs/site/index.html`
- `examples/demo-repo/README.md`
- `scripts/generate_release_assets.py`
- `dist/release-assets/release-page.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `mydocs/specs/2026-03-08_00-19_codemosaic-mvp.md`

## 运行测试

```bash
python -m unittest discover -s tests -v
```

## 开源路线图

- `v0.1`：CLI 原型 + Python masking + JS/TS masking + mapping encryption + patch translator + scan/bundle + VS Code prototype + runs explorer
- `v0.2`：TypeScript AST 脱敏 + 更强策略系统 + 插件交互增强
- `v0.3`：企业级策略集成 + 审计日志 + 签名发布与更完整的 IDE 集成

## ????????

- ??????????? AI ???????
- ?????????????????????????????
- ??????????? AI ??????????????????

## Product Positioning

CodeMosaic is an **AI Code Privacy Gateway** for teams that want to use external AI coding tools without sending raw proprietary code.

### Why it stands out

- Reversible workflow: `mask -> AI -> patch -> unmask/apply`
- Policy-driven segmentation and mapping encryption
- Semantic leakage analysis after masking
- Leakage Budget Gate that blocks unsafe exports before they leave the workstation
- VS Code prototype and demo assets built around the same safe-export story

### Safe export example

```bash
python -m codemosaic bundle ./your-repo.masked --policy policy.sample.yaml --output ai-bundle.md --leakage-report leakage-report.json --fail-on-threshold
```

When the leakage budget is exceeded, the command exits with code `3` and does not generate the bundle.

## Policy Presets

- `presets/strict-ai-gateway.yaml`
- `presets/balanced-ai-gateway.yaml`
- `presets/public-sdk-ai-gateway.yaml`

## CI Governance

- GitHub Actions example: `examples/github-actions/leakage-gate.yml`
- Team rollout guide: `docs/ci-governance.md`
