# CodeMosaic

Language: [English](README.md) | **简体中文**

CodeMosaic 是一个 **local-first 的 AI 代码隐私网关**，专门给想使用外部 AI 编程工具，但不想把原始商业代码发出机器边界之外的团队。

它不只是“秘密字符串替换”或“脱敏脚本”，而是一条可逆、可治理、可审计的完整闭环：

`scan -> mask -> leakage-report -> safe export -> AI patch -> unmask/apply`

## 这个项目的差异化

市面上很多工具只解决其中一个点：

- 扫描 secrets
- 单向脱敏
- 把 prompt 打包给 AI

CodeMosaic 想做的是再走一步，而且是从“企业真实可用”的角度设计：

1. **可逆工作流**
   - 在代码离开本地之前先 `mask`
   - mapping 始终保留在本地
   - 把 AI 生成的 patch 翻译回原仓库

2. **语义泄漏控制**
   - 不只看“是否脱敏”，还评估“还剩下多少业务意义泄漏”
   - 对文件和路径进行 leakage score
   - 当风险超阈值时阻断导出

3. **基于 policy 的密钥与治理能力**
   - 对敏感路径强制 mapping 加密
   - 从 `env` / `file` / registry 解析密钥材料
   - 记录 `key_id`，支持轮换、审计、密钥生命周期管理
   - 对 mapping 做防篡改签名与验签
   - 对历史 run 做加密 / 签名 / 验签状态审计

这个产品角度的差异点在于：**不只是“有没有把 secret 挡住”，而是“这份给 AI 的代码现在是否真的还可以安全发送”。**

## 当前已有功能

### 核心 CLI

- `scan`：扫描疑似敏感内容
- `mask`：生成脱敏工作区
- `mask-segmented`：按 policy 分段生成多份脱敏输出
- `plan-segments`：预览分段规则
- `leakage-report`：评估语义泄漏风险
- `bundle`：构建发给外部 AI 的 Markdown 上下文包
- `unmask-patch`：把 mask 后 patch 翻译回原始符号
- `verify-mapping`：验证 mapping 签名是否有效
- `audit-runs`：审计历史 run 的加密与签名状态
- `apply`：使用 `git apply` 应用翻译后的 patch
- `rekey-mapping` / `rekey-runs`：mapping 重包装和密钥轮换
- `generate-key`：生成高熵 mapping 密钥
- `register-key-source` / `list-key-sources` / `set-key-source-status`：管理工作区 key registry
- `list-providers`：查看可用加密 provider

### 隐私与治理能力

- 本地 mapping vault，位于 `.codemosaic/runs/...`
- 支持口令式 mapping 加密
- 支持 `managed-v1` 托管密钥模式
- 支持 `active` / `decrypt-only` / `retired` 三种密钥状态
- 支持 mapping 防篡改签名与验签
- 支持 run 级审计与 governance 摘要
- 支持 `key_id` / `signature key_id` 记录
- 支持 total / file 级 leakage budget
- 支持 segment-aware masking 规则

## 快速开始

### 环境要求

- Python `3.11+`
- 本地可用 Git
- 如果要试 VS Code 原型，可选 Node.js + VS Code

### 0) 初始化一份策略预设

```bash
python -m codemosaic list-policy-presets
python -m codemosaic init-policy --preset balanced-ai-gateway --output policy.codemosaic.yaml
```

大多数仓库先用 `balanced-ai-gateway`，核心内部代码用 `strict-ai-gateway`，SDK 或示例仓库用 `public-sdk-ai-gateway`。
下面所有命令里的 `policy.sample.yaml` 都可以替换成你刚生成的 `policy.codemosaic.yaml`。

### 1) 扫描仓库

```bash
python -m codemosaic scan ./your-repo --policy policy.sample.yaml --output scan-report.json
```

### 2) 生成 mapping 密钥

```bash
python -m codemosaic generate-key --output ./.codemosaic/keys/team-dev.key
```

PowerShell:

```powershell
$env:CODEMOSAIC_MAPPING_KEY = Get-Content ./.codemosaic/keys/team-dev.key
```

### 3) 注册工作区密钥来源

```bash
python -m codemosaic register-key-source ./your-repo --key-id team-dev-2026q1 --source env --reference CODEMOSAIC_MAPPING_KEY
```

### 4) 生成脱敏工作区

```bash
python -m codemosaic mask ./your-repo --policy policy.sample.yaml
```

默认会生成：

- `./your-repo.masked`
- `./your-repo/.codemosaic/runs/<run-id>/`

### 5) 评估 leakage

```bash
python -m codemosaic leakage-report ./your-repo.masked --policy policy.sample.yaml --output leakage-report.json
```

### 6) 安全导出 AI bundle

```bash
python -m codemosaic bundle ./your-repo.masked --policy policy.sample.yaml --output ai-bundle.md --max-files 20 --max-chars 12000
```

### 7) 翻译 AI patch

```bash
python -m codemosaic unmask-patch ./masked-response.patch --mapping ./your-repo/.codemosaic/runs/<run-id>/mapping.enc.json --key-env CODEMOSAIC_MAPPING_KEY --output translated.patch
python -m codemosaic apply translated.patch --target ./your-repo --check
python -m codemosaic apply translated.patch --target ./your-repo
```

## 更像正式产品的密钥与签名管理

### managed mapping key

`managed-v1` 是内置 provider，面向 `generate-key` 生成的高熵密钥材料。

### 工作区 key registry

```bash
python -m codemosaic register-key-source ./your-repo --key-id team-dev-2026q1 --source env --reference CODEMOSAIC_MAPPING_KEY
python -m codemosaic list-key-sources ./your-repo
python -m codemosaic set-key-source-status ./your-repo --key-id team-dev-2026q1 --status decrypt-only
```

状态说明：

- `active`：可用于新加密和解密
- `decrypt-only`：不再用于新加密，但仍可解密与 rekey
- `retired`：不再参与 registry 自动解析

### 密钥轮换

```powershell
$env:OLD_CODEMOSAIC_KEY = Get-Content ./.codemosaic/keys/team-dev.key
$env:NEW_CODEMOSAIC_KEY = Get-Content ./.codemosaic/keys/team-dev-v2.key
python -m codemosaic rekey-runs ./your-repo --key-env OLD_CODEMOSAIC_KEY --new-key-env NEW_CODEMOSAIC_KEY --new-key-id team-dev-2026q2 --encryption-provider managed-v1
python -m codemosaic set-key-source-status ./your-repo --key-id team-dev-2026q1 --status decrypt-only
python -m codemosaic set-key-source-status ./your-repo --key-id team-dev-2025q4 --status retired
```

推荐节奏：

1. 新密钥保持 `active`
2. 上一代密钥切到 `decrypt-only`
3. 更早的密钥在 mapping 完成 rewrap 或过期后切到 `retired`

### 签名验真

```bash
python -m codemosaic verify-mapping ./.codemosaic/runs/<run-id>/mapping.enc.json --signing-key-env CODEMOSAIC_AUDIT_KEY --require-signature
```

对于加密 mapping，签名覆盖的是 envelope 元数据和密文，无需先解密。

### run 审计

```bash
python -m codemosaic audit-runs ./your-repo --signing-key-env CODEMOSAIC_AUDIT_KEY --output run-audit.json
```

它会输出一份治理友好的摘要，明确告诉你哪些 run 已加密、哪些 run 已签名、哪些 run 已验签通过。

### unmask 强制验签 gate

现在 `unmask-patch` 可以加载 policy，并在翻译 patch 前强制要求 mapping 已签名且验签通过。

```yaml
mapping:
  require_signature_for_unmask: true
  signature_management:
    source: env
    reference: CODEMOSAIC_AUDIT_KEY
    key_id: audit-2026q1
```

```bash
python -m codemosaic unmask-patch ./masked-response.patch   --mapping ./.codemosaic/runs/<run-id>/mapping.enc.json   --policy policy.sample.yaml   --key-env CODEMOSAIC_MAPPING_KEY   --output translated.patch
```

## policy 方向

### 按路径强制 mapping 加密

```yaml
mapping:
  require_encryption: false
  encryption_provider: managed-v1
  key_management:
    source: env
    reference: CODEMOSAIC_MAPPING_KEY
    key_id: team-dev-2026q1
  rules:
    src/secret/**:
      require_encryption: true
      encryption_provider: managed-v1
```

### leakage budget gate

```yaml
leakage:
  max_total_score: 20
  max_file_score: 8
  rules:
    src/secret/**:
      max_total_score: 4
      max_file_score: 0
```

### 分段规划

```bash
python -m codemosaic plan-segments ./your-repo --policy policy.sample.yaml --output segment-plan.json
python -m codemosaic mask-segmented ./your-repo --policy policy.sample.yaml --output ./segmented-output
```

## VS Code 原型

仓库内包含 `extensions/vscode` 原型扩展，可以进入编辑器中直接调用本地工作流。

它现在支持 `CodeMosaic: Initialize Policy Preset`，可以在编辑器里一键生成工作区 policy，并自动把扩展配置指向这个文件。

```bash
python scripts/package_vscode_extension.py --overwrite
```

## 文档索引

- `docs/key-management.md`：托管密钥、签名、轮换和 registry
- `docs/leakage-gate.md`：leakage score 和 gate 行为
- `docs/ci-governance.md`：CI / governance 示例
- `docs/demo-walkthrough.md`：demo 演示流程
- `docs/landing-page.md`：官网 / 落地页文案
- `docs/release-playbook.md`：本地发版流程
- `docs/site/index.html`：静态站点源文件

## 安全边界

CodeMosaic 能显著降低对外发送 AI 代码上下文的风险，但它不是魔法。

- masking 不等于零泄漏
- prompt 文本自身仍可能泄露业务背景
- leakage 分析目前是启发式，不是完整 DLP
- `managed-v1` 和签名能力让它更接近正式产品，但仍不等同于经过正式审计的企业 KMS / DLP 体系
- 对高敏场景，仍建议叠加 DLP、audit log、最小化上下文和 self-hosted AI

## 一句话

**CodeMosaic 帮助团队使用外部 AI 编程工具，同时不失去对代码泄漏边界的控制。**
