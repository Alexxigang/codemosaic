# Leakage Budget Gate

`CodeMosaic` 不只是在导出前做脱敏，还可以在导出前做一层“语义泄露预算”门禁。

## 核心思路

- `scan` 负责发现显性风险线索，比如 URL、邮箱、手机号、疑似密钥。
- `leakage-report` 负责评估 mask 后还残留多少业务语义，例如路径语义、未脱敏标识符、字符串和注释。
- `bundle --fail-on-threshold` 负责在真正把上下文导出给外部 AI 前做最后一道拦截。

这让产品从“脱敏工具”变成“AI 导出治理网关”。

## 策略示例

```yaml
leakage:
  max_total_score: 20
  max_file_score: 8
  rules:
    src/secret/**:
      max_total_score: 4
      max_file_score: 0
    src/public-sdk/**:
      max_file_score: 16
```

含义：

- 整个导出源的总泄露分不能超过 `20`
- 任意单文件不能超过 `8`
- `src/secret/**` 目录更严格，基本要求“零语义泄露”
- `src/public-sdk/**` 可以相对放宽

## CLI 用法

先做报告：

```bash
python -m codemosaic leakage-report ./repo.masked --policy policy.sample.yaml --output leakage-report.json
```

在 CI 里卡阈值：

```bash
python -m codemosaic leakage-report ./repo.masked --policy policy.sample.yaml --fail-on-threshold
```

直接阻断导出：

```bash
python -m codemosaic bundle ./repo.masked --policy policy.sample.yaml --output ai-bundle.md --leakage-report leakage-report.json --fail-on-threshold
```

当预算超标时，`bundle` 返回退出码 `3`，且不会生成导出文件。

## GitHub Actions 示例

```yaml
- name: Build masked bundle safely
  run: |
    python -m codemosaic bundle ./repo.masked \
      --policy policy.sample.yaml \
      --output ai-bundle.md \
      --leakage-report leakage-report.json \
      --fail-on-threshold
```

## 为什么这是差异化点

很多工具只能“做脱敏”，但没有回答一个更关键的问题：

> “脱敏之后，这份代码现在到底能不能安全发给外部 AI？”

`Leakage Budget Gate` 回答的正是这个问题。
