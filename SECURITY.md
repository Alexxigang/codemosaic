# Security Policy

## Supported Versions

当前重点维护 `0.1.x`。

## Reporting a Vulnerability

如果你发现 `codemosaic` 在以下方面存在问题，请私下报告，不要先公开提交 issue：

- 脱敏结果可逆泄露
- mapping 文件处理存在安全缺陷
- patch 回填可导致意外越权修改
- 风险扫描误导用户产生错误安全判断

## Security Notes

- 当前版本不提供 mapping 文件加密
- 当前 `scan` 只是风险线索扫描，不是完整 DLP
- 对高敏场景，请优先考虑自托管模型与企业审计体系
