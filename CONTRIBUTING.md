# Contributing

欢迎贡献 `codemosaic`。

## 本地开发

```bash
python -m unittest discover -s tests -v
python -m codemosaic --help
```

## 提交建议

- 保持改动聚焦
- 先补测试，再补实现
- 对安全能力的变更请同步更新 `docs/threat-model.md`
- 对 CLI 行为的变更请同步更新 `README.md`

## 优先贡献方向

- TypeScript / JavaScript AST 脱敏
- Mapping Vault 加密与完整性校验
- 更智能的 AI bundle 选择器
- VS Code 扩展原型
