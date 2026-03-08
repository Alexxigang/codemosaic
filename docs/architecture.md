# Architecture

## Pipeline

1. `Policy Loader` 读取策略
2. `Workspace Runner` 遍历源目录并选择合适的 masker
3. `Mask Engine` 将源码转换为 masked code
4. `Mapping Vault` 记录占位符与原文映射
5. 输出 `masked workspace`、`mapping.json`、`report.json`
6. `Patch Translator` 将 AI 返回补丁中的占位符替换回真实 token
7. `Apply` 阶段调用 `git apply` 回填到真实仓库

## 模块划分

- `codemosaic/policy.py`
- `codemosaic/mapping.py`
- `codemosaic/maskers/python_masker.py`
- `codemosaic/maskers/jsts_masker.py`
- `codemosaic/maskers/text_masker.py`
- `codemosaic/workspace.py`
- `codemosaic/patching.py`
- `codemosaic/cli.py`

## 当前实现策略

### Python

使用 `tokenize` 做词法级处理：

- `NAME` -> 标识符占位符
- `STRING` -> 字符串占位符
- `COMMENT` -> 注释占位符或移除

优点：

- 不需要第三方依赖
- 比简单正则更稳
- 保留了较多结构信息

限制：

- 不是 AST 级语义分析
- 不区分业务标识符与第三方依赖名

### 其他语言

当前提供一个轻量文本扫描器作为兜底，支持：

- 行注释
- 块注释
- 常见字符串字面量
- 代码段中的标识符替换

它的目标是“先覆盖常见场景”，不是追求完整语法精确性。

## Mapping Vault

占位符采用确定性命名：

- 标识符：`ID_0001`
- 字符串：`STR_<CATEGORY>_0001`
- 注释：`COMMENT_0001`

同一轮运行中，相同原文会复用同一个 masked token。

## Patch Translation

Patch 回填的核心假设是：AI 对脱敏 token 做的是局部编辑，而不是大规模重写。这时只需要用 mapping 反向替换 patch 中的占位符，就可以翻译回原始补丁。

## 下一步增强点

- 增加 TypeScript AST 适配器
- 给 Mapping Vault 增加加密与完整性校验
- 输出更适合喂给 AI 的 prompt bundle
- 引入敏感信息分类器与策略模板
