# AxonHub 社区插件

AxonHub 从 [registry.json](registry.json) 读取市场列表。所有条目都是社区插件。市场包按索引中的 SHA-256 校验，启用时由 AxonHub Owner 授权。

| 插件 | 维护位置 |
| --- | --- |
| 每日用量卡 | [plugins/day-card](plugins/day-card) |
| Jev 请求审查 | [plugins/jev-guard](plugins/jev-guard) |
| 实时请求 | [plugins/request-live](plugins/request-live) |
| 重置监控 | [plugins/reset-watch](plugins/reset-watch) |
| 载荷存储切桶 | [axonhub-bucket-rotate](https://github.com/jin-yu-liu/axonhub-bucket-rotate) |

## 本仓库维护的插件

每个插件放在 `plugins/<目录名>/`，包含自己的 `manifest.json` 和运行所需源码。保留已发布插件的 manifest ID 和目录名。插件开发方式见 [AxonHub 插件开发指南](https://github.com/looplj/axonhub/blob/unstable/docs/zh/development/plugins.md)。

本地检查需要 Go、Node.js 和 Python 3.10 以上：

```sh
go install github.com/looplj/axonhub/cmd/pack-plugin@c2826aa422821d88c717502a72c87395dcdb3cb3
python3 scripts/plugins.py check
```

发布时在 PR 中递增插件 `manifest.json` 的版本（SemVer）。合并到 `main` 后，Release workflow 为新版本生成 `<目录名>-<版本>.axplugin`，发布到 `<目录名>/v<版本>`，再更新索引。已发布版本的包保持固定。workflow 可以手动重跑，补齐未完成的发布。

## 外部维护的插件

在 [external-plugins.json](external-plugins.json) 登记原仓库的 HTTPS 下载地址、包的 SHA-256、插件 ID、版本和 AxonHub 兼容范围。后续版本也在这里通过 PR 提交。workflow 将这些条目和本仓库的 Release 合并为市场索引。
