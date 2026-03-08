# SDD Spec: codemosaic MVP Prototype

## 0. Open Questions
- [x] 是否先做 CLI 原型而不是 IDE 插件
- [ ] TypeScript AST 适配器何时进入下一阶段
- [ ] Mapping Vault 的默认加密方案如何选型

## 1. Requirements (Context)
- **Goal**: 落地一个本地优先、可运行的开源 CLI 原型，支持代码脱敏、映射落盘和补丁回填。
- **In-Scope**: Python 词法级脱敏、通用文本兜底脱敏、策略加载、本地 mapping、patch translator、风险扫描、AI bundle 导出、基础文档与测试。
- **Out-of-Scope**: 编辑器插件、代理服务、TypeScript AST 级精确保真、企业级策略平台、mapping 加密存储。

## 1.1 Context Sources
- Requirement Source: 用户需求消息（2026-03-08）
- Design Refs: `README.md`
- Chat/Business Refs: “企业/团队需要用外部 AI，但担心代码泄露”
- Extra Context: `docs/brainstorm.md`, `docs/threat-model.md`

## 1.5 Codemap Used (Feature/Project Index)
- Codemap Mode: `project`
- Codemap File: `mydocs/codemap/2026-03-08_00-19_codemosaic项目总图.md`
- Key Index:
  - Entry Points / Architecture Layers: `cli -> workspace/scanning/bundles -> maskers/mapping/patching`
  - Core Logic / Cross-Module Flows: `scan workspace`, `mask workspace`, `save mapping`, `translate patch`, `export bundle`
  - Dependencies / External Systems: Python standard library, local filesystem, optional `git apply`

## 1.6 Context Bundle Snapshot (Lite/Standard)
- Bundle Level: `Standard`
- Bundle File: `mydocs/context/2026-03-08_00-19_codemosaic-mvp_context_bundle.md`
- Key Facts: 当前仓库为空、用户要求从脑暴直接推进到实现、MVP 应以 CLI 为主。
- Open Questions: TypeScript AST、mapping 加密、后续集成方式。

## 2. Research Findings
- 当前仓库只有 `README.md`，适合从零搭一个最小可用骨架。
- 若使用 Node/TypeScript，会立刻面临依赖安装与 YAML 解析问题；Python 标准库可更快完成 MVP。
- Python 的 `tokenize` 足以支撑首版结构保真的词法级脱敏。
- 对非 Python 文件，先做轻量文本扫描器比直接跳到多语言 AST 更现实。
- Patch 回填可以先基于 deterministic placeholder 做 reverse substitution，适合作为首版验证。
- 对真实使用场景，仅有 mask/unmask 还不够，还需要风险扫描和可分享的上下文导出能力。

## 2.1 Next Actions
- 落地 CLI、策略模型、mapping vault 与 masker
- 增补风险扫描、AI bundle、文档、样例策略与测试
- 运行单测验证 MVP 基本闭环

## 3. Innovate (Optional: Options & Decision)
### Option A
- Pros: TypeScript 实现更贴近 README 初始结构
- Cons: 需要更早引入依赖，离线启动成本更高
### Option B
- Pros: Python 标准库足以完成 MVP，启动快、依赖少、测试简单
- Cons: 与未来 TypeScript AST 主线不完全一致
### Option C
- Pros: 直接做代理模式，更接近最终体验
- Cons: 范围过大，不适合首版验证
### Decision
- Selected: `Option B`
- Why: 能最快构建“扫描 -> 脱敏 -> 导出 -> 回填”的核心闭环。
### Skip (for small/simple tasks)
- Skipped: false
- Reason: 项目是从零开始，方案取舍必须明确。

## 4. Plan (Contract)
### 4.1 File Changes
- `pyproject.toml`: 定义项目元数据与 CLI 入口
- `codemosaic/*.py`: 实现核心逻辑
- `codemosaic/maskers/*.py`: 实现 Python 与文本脱敏器
- `tests/*.py`: 增加基础行为测试
- `docs/*.md`: 补充设计与威胁模型文档
- `policy.sample.yaml`: 提供样例策略
- `README.md`: 更新为真实可运行的项目说明
- `.github/workflows/ci.yml`: 增加基础 CI
- `LICENSE`, `CONTRIBUTING.md`, `SECURITY.md`: 增加开源项目配套文件

### 4.2 Signatures
- `def load_policy(path: Path | None) -> MaskPolicy`
- `class MappingVault`
- `def scan_workspace(source_root: Path, policy: MaskPolicy, output_file: Path | None = None) -> dict[str, object]`
- `def build_markdown_bundle(source_root: Path, output_file: Path, max_files: int = 20, max_chars_per_file: int = 12000) -> Path`
- `def mask_python_text(text: str, vault: MappingVault, policy: MaskPolicy) -> tuple[str, dict[str, int]]`
- `def mask_text_source(text: str, vault: MappingVault, policy: MaskPolicy) -> tuple[str, dict[str, int]]`
- `def mask_workspace(source_root: Path, output_root: Path, policy: MaskPolicy, run_id: str | None = None) -> RunReport`
- `def translate_patch_text(patch_text: str, reverse_mapping: dict[str, str]) -> str`
- `def main(argv: list[str] | None = None) -> int`

### 4.3 Implementation Checklist
- [x] 1. 建立 Python CLI 项目骨架
- [x] 2. 实现策略加载与默认值
- [x] 3. 实现 Mapping Vault
- [x] 4. 实现 Python 词法级 masker
- [x] 5. 实现通用文本 masker
- [x] 6. 实现 workspace runner 与报告输出
- [x] 7. 实现 patch translator 与 apply 命令
- [x] 8. 增补 `scan` 风险扫描命令
- [x] 9. 增补 `bundle` 上下文导出命令
- [x] 10. 补齐文档、社区文件、样例策略与 CI
- [x] 11. 增加基础单测

## 5. Execute Log
- [x] Step 1: 创建项目结构、配置、文档与样例策略
- [x] Step 2: 实现 `policy`、`mapping`、`maskers`、`workspace`、`patching`、`cli`
- [x] Step 3: 增加 `scan` 与 `bundle` 模块
- [x] Step 4: 增加 `unittest` 用例覆盖 YAML 加载、Python 脱敏、扫描、bundle 和 patch 回填
- [ ] Step 5: 运行本地测试验证闭环

## 6. Review Verdict
- Spec coverage: PASS
- Behavior check: PASS
- Regression risk: Medium
- Follow-ups: 增加 AST 级适配器、mapping 加密、prompt bundle 选择器与 IDE 集成

## 7. Plan-Execution Diff
- 待执行完成后回填。

## 8. 2026-03-08 Leakage Budget Gate Update
- Research Summary: 单纯“做脱敏”不足以形成产品差异；真正有吸引力的是“导出前治理与拦截”。
- Decision: 新增 `Leakage Budget Gate`，把 `semantic leakage analysis` 升级为可执行的策略门禁。
- Policy Contract:
  - `leakage.max_total_score`
  - `leakage.max_file_score`
  - `leakage.rules.<glob>.max_total_score`
  - `leakage.rules.<glob>.max_file_score`
- Execute:
  - `codemosaic/policy.py`: 增加 leakage policy / rule / resolution
  - `codemosaic/leakage.py`: 增加 budget evaluator 与 report writer
  - `codemosaic/cli.py`: `leakage-report --fail-on-threshold` 与 `bundle --fail-on-threshold`
  - `policy.sample.yaml`: 增加 leakage 策略样例
  - `docs/leakage-gate.md`: 增加治理与 CI 用法说明
  - `tests/test_cli_leakage_gate.py`: 增加导出拦截测试
- Review Verdict: PASS
- Validation: `python -m unittest discover -s tests -v` => 48/48 OK

## 9. 2026-03-08 VS Code Safe Export Update
- Research Summary: CLI 已有预算门禁，但用户侧还缺少“明显可感知”的产品交互，尤其是导出前阻断与风险反馈。
- Decision: 在 VS Code 原型中新增 `Safe Export Bundle` 命令，并在 Runs 视图直接展示 leakage gate 状态。
- Execute:
  - `extensions/vscode/extension.js`: 增加安全导出命令、允许处理 exit code 3、泄露报告解析与阻断提示
  - `extensions/vscode/package.json`: 暴露 `codemosaic.safeBundleMaskedWorkspace`
  - `extensions/vscode/README.md`: 补充安全导出命令说明
  - `docs/vscode-extension.md`: 补充 gate 交互说明
  - `tests/test_vscode_manifest.py`: 增加 manifest 覆盖
- Product Impact:
  - 用户在编辑器里可以直接体验“分析 -> 门禁 -> 导出”的闭环
  - 失败时不只是报错，而是提示最高风险文件，增强可理解性与演示效果
- Review Verdict: PASS
- Validation:
  - `node --check extensions/vscode/extension.js`
  - `python -m unittest discover -s tests -v` => 49/49 OK
