# AxonHub 社区插件

AxonHub 从 [registry.json](registry.json) 读取市场列表。所有条目都是社区插件。市场包按索引中的 SHA-256 校验，启用时由 AxonHub Owner 授权。

| 插件 | 维护位置 |
| --- | --- |
| 每日用量卡 | [plugins/community/day-card](https://github.com/looplj/axonhub/tree/unstable/plugins/community/day-card) |
| Jev 请求审查 | [plugins/community/jev-guard](https://github.com/looplj/axonhub/tree/unstable/plugins/community/jev-guard) |
| 实时请求 | [plugins/community/request-live](https://github.com/looplj/axonhub/tree/unstable/plugins/community/request-live) |
| 重置监控 | [plugins/community/reset-watch](https://github.com/looplj/axonhub/tree/unstable/plugins/community/reset-watch) |
| 载荷存储切桶 | [axonhub-bucket-rotate](https://github.com/jin-yu-liu/axonhub-bucket-rotate) |

## AxonHub 维护的插件

在 AxonHub 的 `plugins/community/<目录名>/` 修改源码，并在 `manifest.json` 中递增插件版本（SemVer）。保留已发布插件的 manifest ID 和目录名。插件开发方式见 [AxonHub 插件开发指南](https://github.com/looplj/axonhub/blob/unstable/docs/zh/development/plugins.md)。

源码合并到 AxonHub 的 `unstable` 后，AxonHub 向本仓库发送 `community-plugins` 事件，payload 是该提交的完整 SHA。Release workflow 检出这个提交，为新版本生成 `<目录名>-<版本>.axplugin`，发布到 `<目录名>/v<版本>`，再更新索引。Release 说明链接到对应的 AxonHub 源码。已发布版本的包保持固定。要补齐一次发布，手动运行 workflow 并填入同一个 SHA。

AxonHub 仓库的 secret `AXONHUB_PLUGINS_TOKEN` 用来创建这个事件，需要对 `looplj/axonhub-plugins` 有 Contents 写权限。本仓库的 `GITHUB_TOKEN` 不能跨仓库触发 workflow。

本地检查需要 Go、Node.js 和 Python 3.10 以上。在本仓库执行以下命令，路径指向本地的 AxonHub 工作区。

```sh
go install github.com/looplj/axonhub/cmd/pack-plugin@c2826aa422821d88c717502a72c87395dcdb3cb3
python3 scripts/plugins.py check --source-root /path/to/axonhub
```

## 外部维护的插件

在 [external-plugins.json](external-plugins.json) 登记原仓库的 HTTPS 下载地址、包的 SHA-256、插件 ID、版本和 AxonHub 兼容范围。后续版本也在这里通过 PR 提交。合并到 `main` 后，workflow 把这些条目和本仓库已发布的 Release 写成 `registry.json`。包仍在原仓库，这里不打包。
