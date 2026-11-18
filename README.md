# QQ 收藏本地备份

适合 **QQ 收藏了很多内容，希望备份到本地，再整理成笔记** 的用户。

在本机登录 **NT 版 QQ**，打开过收藏夹后，运行本工具即可提取本地已缓存的收藏，保留你在 QQ 中设置的分组，整理为可检索网页、Markdown、Excel 与本机已有附件。网页可修改标题、正文并保存到对应 Markdown，也可用 Obsidian 打开笔记文件夹。

**本项目仅整理用户授权的本机收藏缓存，不额外采集好友、聊天或个人资料，不连接 QQ 服务器，不上传收藏、密钥或其他内容。** 公开仓库与发行包不包含作者的收藏、账号、密钥或图片。

## 使用条件

- Windows 10/11 64 位，已安装 NT 版 QQ。
- 本机登录要备份的账号，并打开过收藏夹，让 QQ 生成本地缓存。
- 桌面界面需要 Microsoft Edge WebView2 Runtime；EXE 无需安装 Python。
- 只处理本机已有的缓存。未缓存的正文、图片或视频不会从网络补齐，也不承诺能完整恢复云端收藏。

加密库需要匹配的密钥：默认模式会只读扫描 QQ 进程内存，仅保留能验证**所选收藏库**的密钥候选，不保存内存转储或密钥。不会注入、挂钩、修改 QQ 或关闭系统保护。你也可使用本地密钥文件或明文库，详见[纯文件模式](docs/USAGE.md#纯文件模式)。

## 一键备份

1. 从 [Releases](https://github.com/GXinnnnnn/qq-collection-backup/releases) 下载并完整解压 Windows 便携包。
2. 登录 NT 版 QQ，打开收藏夹，运行 `QQ收藏备份工具.exe`。
3. 检查自动识别的账号和保存位置，点击 **一键备份收藏**。
4. 完成后自动打开本地编辑网页，按 QQ 原分组检索、阅读和编辑。

软件使用 Windows `SHGetKnownFolderPath(Documents)` 以及系统文档位置设置，支持“我的文档”迁移到其他磁盘，不把文档目录写死为 C 盘。多个账号可选择，也可手动选择 `collection.db` 或账号文件夹。成功后只在本机记住路径偏好。

## 导出与更新

| 输出 | 用途 |
| --- | --- |
| 可编辑网页 | QQ 原分组筛选、搜索、分页和正文编辑 |
| 每条 Markdown | 按 QQ 原分组建文件夹，可用 Obsidian 或其他笔记软件打开 |
| Excel | 分组及收藏索引，属于导出时的快照 |
| 原样附件 | 仅复制本机缓存中被收藏引用的文件；缺失项列入清单 |
| 原始字段与变化记录 | 本地核对增删改，不代表云端删除证明 |

再次选择同一账号、同一保存目录即可更新，旧版保存在 `历史版本`。网页保存的文字与修改历史会继承；QQ 原文同时变化时提示合并。**更新前关闭本地编辑服务**。Excel 不随每次网页保存即时更新，下一次导出时重新生成。

自定义 Markdown 排版、在其他笔记软件里的改动，以及网页之外的副本并非通用双向同步：请阅读[使用说明](docs/USAGE.md)。原始数据库只取副本，包含 WAL 时一起取得稳定快照，不对源库执行写入或 checkpoint。

## 开发

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[build]"
python -m unittest discover -s tests -v
python -m qq_collection_backup
```

源码运行编辑器：

```powershell
python -m qq_collection_backup.editor_main --folder "你的导出目录\collection\可编辑收藏"
```

构建两个独立 EXE 与便携 ZIP：

```powershell
python scripts/build_release.py
```

产物位于 `dist/`。详见[项目结构与构建](docs/DEVELOPMENT.md)。测试和[可选 CI 配置](docs/ci-workflow.example.yml)只使用人工构造数据，**不需要 QQ 账号或个人数据库**。如需启用 GitHub Actions，可将示例复制到 `.github/workflows/checks.yml`。

## 适用范围与限制

- 只支持收藏库 `collection.db`；不提供好友、聊天、群信息导出或通用账号取密钥功能。
- QQ 数据结构和加密方式可能变化。已验证版本范围与局限见 [COMPATIBILITY](docs/COMPATIBILITY.md)。
- 不保证得到全部正文或附件，不保证兼容所有 QQ 版本，也不承诺不存在账号、数据或平台规则方面的风险。
- 不得用来处理无授权的数据、绕过权限保护、监控他人或传播第三方隐私。

使用前请阅读[免责声明](DISCLAIMER.md)、[隐私与本地处理说明](PRIVACY.md)及 [MIT 许可证](LICENSE)。本项目非腾讯官方产品，QQ 相关名称及商标归其权利人所有。
