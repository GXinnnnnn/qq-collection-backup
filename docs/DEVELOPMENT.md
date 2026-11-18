# 项目结构与构建

```text
src/qq_collection_backup/
  cli.py, __main__.py       收藏专用入口
  app_common.py, modern_gui.py  桌面界面和命令行桥接
  qqsource.py               文档发现、只读快照、目标库密钥匹配和解密
  collection_models.py      收藏及 QQ 原分组解析
  collection_export.py      Markdown、Excel 和附件导出
  sync_engine.py            原子替换、旧版保留和增删改
  editable_export.py        生成可编辑网页和笔记库
  editor_main.py, editor_core.py  本地 HTTP 服务与文件保存
  local_edits.py, note_render.py  独立编辑层和 Markdown 渲染
  export_common.py, pb.py   公共导出与 protobuf 字段解析
  assets/                  界面模板、样式和编辑脚本
tests/                     人工构造的数据与回归测试
scripts/                   PyInstaller 入口和发行打包
docs/                      使用、结构与兼容性说明
```

只保留收藏所需模块，没有好友、聊天或通用数据库导出模块。依赖从 `pyproject.toml` 安装，不依赖作者电脑的目录、缓存或已有 EXE。

## 构建

Windows x64、Python 3.12。安装 `python -m pip install -e ".[build]"` 后执行 `python scripts/build_release.py`。先从本仓库源码构建独立编辑器，再将其作为资源打入收藏备份程序，最后生成便携 ZIP 和 SHA256SUMS。无个人文件参与构建。

源码运行不要求先构建 EXE；此时导出不复制编辑器二进制，可通过 Python 模块启动本地编辑服务。

## 验证边界

测试使用人工构造的 SQLite、笔记和 HTTP 请求，覆盖分组、WAL、纯文件模式、编辑持久化、并发冲突和失败回滚。CI 不登录 QQ、不接触个人缓存。测试通过不等于所有 QQ 版本、所有机器或真实视觉交互均已验证。
