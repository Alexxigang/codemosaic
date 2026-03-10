# CodeMosaic

语言： [English](README.en.md) | **简体中文**

CodeMosaic 是一个本地优先的 AI 代码隐私网关，目标是帮助团队在使用外部 AI 编程工具时，不必把原始的专有代码直接暴露到工作站边界之外。

它不是一个“简单打码脚本”。这个项目想做的是一条可落地、可逆、可治理的闭环流程：

`scan -> mask -> leakage-report -> safe export -> AI patch -> unmask/apply`

## 核心差异化

很多工具只做到下面某一步：

- 扫描 secret
- 单向脱敏
- 打包 prompt

CodeMosaic 想继续往前走三步：

1. **可逆工作流**
   - 代码发出去之前先做 mask
   - 映射表只保留在本地
   - AI 生成的补丁还能翻译回原始仓库

2. **语义泄漏控制**
   - 不只看 secret 有没有藏住
   - 还评估 mask 之后还剩多少业务语义泄漏
   - 在真正导出前给出风险评分和阻断结果

3. **策略化的密钥与导出治理**
   - 对敏感路径强制加密 mapping
   - 从环境变量或文件解析托管密钥
   - 记录 `key_id`，让轮换和审计更像正式产品

核心卖点是：**不只是“有没有藏住秘密”，而是“这份 mask 后的代码现在到底能不能安全发给外部 AI”。**

## 当前已经有的能力

### 核心 CLI

- `scan`：扫描疑似敏感内容
- `mask`：生成脱敏工作区
- `mask-segmented`：按策略分段生成多个脱敏工作区
- `plan-segments`：预览按策略切分出来的 masking 分段
- `leakage-report`：评估语义泄漏分数与阈值结果
- `bundle`：构建给外部 AI 使用的 Markdown 上下文包
- `unmask-patch`：把 mask 后补丁翻译回原始符号
- `verify-mapping`??? mapping ?????
- `apply`：调用 `git apply` 应用翻译后的补丁
- `rekey-mapping` 与 `rekey-runs`：重包裹 mapping，支持轮换密钥
- `generate-key`：生成高熵 mapping 密钥
- `register-key-source` / `list-key-sources` / `set-key-source-status`：管理工作区级别的 key registry 生命周期
- `list-providers`：查看当前可用的加密 provider

### 隐私与治理能力

- 本地 mapping vault，位于 `.codemosaic/runs/...`
- 支持传统口令式 mapping 加密
- 支持 `managed-v1` 托管密钥流程
- 支持从 `env` / `file` 解析密钥来源
- 支持 `active` / `decrypt-only` / `retired` 三种密钥状态
- ????? mapping ??????????
- 支持记录 `key_id`，便于轮换和审计
- 支持总分与单文件级别的泄漏预算阈值
- 支持按路径分段的 masking 策略

## 快速开始

### 1）先扫描仓库

```bash
python -m codemosaic scan ./your-repo --policy policy.sample.yaml --output scan-report.json
```

### 2）先生成一把托管密钥

```bash
python -m codemosaic generate-key --output ./.codemosaic/keys/team-dev.key
```

PowerShell：

```powershell
$env:CODEMOSAIC_MAPPING_KEY = Get-Content ./.codemosaic/keys/team-dev.key
```

### 3）先把密钥来源注册到工作区

```bash
python -m codemosaic register-key-source ./your-repo --key-id team-dev-2026q1 --source env --reference CODEMOSAIC_MAPPING_KEY
```

### 4）生成脱敏工作区

```bash
python -m codemosaic mask ./your-repo --policy policy.sample.yaml
```

默认会生成：

- 脱敏后的代码目录：`./your-repo.masked`
- 运行产物目录：`./your-repo/.codemosaic/runs/<run-id>/`

### 5）计算语义泄漏

```bash
python -m codemosaic leakage-report ./your-repo.masked --policy policy.sample.yaml --output leakage-report.json
```

### 6）阻断不安全导出

```bash
python -m codemosaic bundle ./your-repo.masked --policy policy.sample.yaml --output ai-bundle.md --leakage-report leakage-report.json --fail-on-threshold
```

### 7）把 AI 补丁翻译回原仓库

```bash
python -m codemosaic unmask-patch ./masked-response.patch --mapping ./your-repo/.codemosaic/runs/<run-id>/mapping.enc.json --key-env CODEMOSAIC_MAPPING_KEY --output translated.patch
python -m codemosaic apply translated.patch --target ./your-repo --check
python -m codemosaic apply translated.patch --target ./your-repo
```

## 更像正式产品的密钥管理模型

CodeMosaic 现在支持一种更“产品化”的密钥工作流，而不只是临时口令。现在还支持通过本地工作区 key registry 用 `key_id` 解析实际密钥来源。

### `managed-v1`

`managed-v1` 是内置 provider，面向 `generate-key` 生成的高熵密钥材料。

推荐方式：

- 先生成随机密钥
- 把它放进本地 secret store、环境变量或受保护文件
- 在 policy 里只写“引用关系”
- 用 `key_id` 标记当前生效密钥版本

### 策略驱动的密钥解析

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

当前支持的密钥来源：

- `env`
- `file`

### 工作区 key registry

团队可以在每个工作区内注册可复用的密钥来源引用：

```bash
python -m codemosaic register-key-source ./your-repo --key-id team-dev-2026q1 --source env --reference CODEMOSAIC_MAPPING_KEY
python -m codemosaic list-key-sources ./your-repo
python -m codemosaic set-key-source-status ./your-repo --key-id team-dev-2026q1 --status decrypt-only
```

registry 里的条目支持三种生命周期状态：

- `active`：可用于新加密，也可用于解密
- `decrypt-only`：不能再用于新加密，但仍可用于解密和 rekey
- `retired`：不再参与 registry 的自动解析

之后 policy 里只需要写 `key_id`，`mask` 会自动从 `.codemosaic/key-registry.json` 解析对应来源。

### 密钥轮换

```powershell
$env:OLD_CODEMOSAIC_KEY = Get-Content ./.codemosaic/keys/team-dev.key
$env:NEW_CODEMOSAIC_KEY = Get-Content ./.codemosaic/keys/team-dev-v2.key
python -m codemosaic rekey-runs ./your-repo --key-env OLD_CODEMOSAIC_KEY --new-key-env NEW_CODEMOSAIC_KEY --new-key-id team-dev-2026q2 --encryption-provider managed-v1
python -m codemosaic set-key-source-status ./your-repo --key-id team-dev-2026q1 --status decrypt-only
python -m codemosaic set-key-source-status ./your-repo --key-id team-dev-2025q4 --status retired
```

推荐的轮换节奏：

1. 新密钥保持 `active`。
2. 上一把密钥切到 `decrypt-only`，保证历史 run 还能继续翻译补丁。
3. 更老的密钥在相关 mapping 完成 rewrap 或过期后再切到 `retired`。

### ????

CodeMosaic ????????????? mapping ?????????? unmask AI ????????? mapping envelope ??????

```bash
python -m codemosaic verify-mapping ./.codemosaic/runs/<run-id>/mapping.enc.json --signing-key-env CODEMOSAIC_AUDIT_KEY --require-signature
```

??????????? mapping ??? mapping????? mapping??????? envelope ???????????????????

### 元数据与可审计性

现在加密后的 mapping envelope 会保留一小部分安全头信息，例如：

- `run_id`
- `generated_at`
- `encryption_provider`
- `key_management.key_id`
- `key_management.source`

这样即使不解开完整 mapping，也能更方便地做运维检查和轮换管理。

## 文档索引

- `docs/key-management.md`：托管密钥工作流、策略引用与轮换说明
- `docs/leakage-gate.md`：语义泄漏评分与 gate 行为
- `docs/ci-governance.md`：CI 中的策略治理样例
- `docs/demo-walkthrough.md`：演示流程
- `docs/landing-page.md`：落地页文案草稿
- `docs/release-playbook.md`：本地发版步骤与素材

## 安全边界

CodeMosaic 能显著降低暴露风险，但它不是魔法。

- Masking 不能保证零语义泄漏
- Prompt 文本本身仍可能泄漏业务背景
- 当前 leakage 分析仍是启发式，不是完整 DLP
- `managed-v1` 让密钥处理流程更像正式产品，但它仍是开源原型，不等同于经过正式审计的企业级 KMS
- 对高敏环境，仍建议叠加 DLP、审计、最小上下文发送和自托管 AI

## 一句话介绍

**CodeMosaic 帮助团队使用外部 AI 编程工具，同时不失去对代码泄漏边界的控制。**




