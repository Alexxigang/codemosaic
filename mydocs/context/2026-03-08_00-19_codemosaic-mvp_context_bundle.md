# Context Bundle: codemosaic MVP

## Requirement Snapshot

- 用户要做一个开源项目
- 核心想法是“给代码打马赛克”，降低外部 AI 使用时的源码泄露风险
- 需要先头脑风暴设计，再按照设计直接做第一版实现

## Product Thesis

- 这个项目本质上是一个 `Code Privacy Gateway`
- 不是替代 AI，而是给外部 AI 使用场景增加一道本地脱敏层
- 核心竞争力在于“结构保真 + 本地映射 + patch 回填”

## Technical Constraints

- 当前仓库几乎为空
- 需要快速做出可运行原型
- 不宜依赖复杂基础设施
- 用户已经休息，本轮要尽量自主推进到可交付状态

## MVP Boundary

- 支持 Python 作为主语言
- 支持多语言文本兜底
- 支持本地 mapping 与 patch 翻译
- 文档中明确威胁模型和剩余风险

## Open Questions

- 后续是优先做 TypeScript AST，还是优先做 VS Code 插件
- mapping vault 是否需要默认加密
- 与具体 AI 平台的集成方式采用 CLI、代理还是插件
