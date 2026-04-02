# lanhu-cli

> 蓝湖设计平台的独立命令行工具，无需 MCP 协议，直接通过 CLI 获取原型文档、UI 设计图、消息留言等数据。

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 功能特性

| 功能模块 | 说明 |
|---|---|
| **原型文档（pages）** | 列出 Axure 原型页面、截图 + 文本提取，支持开发/测试/探索三种分析视角 |
| **UI 设计图（designs）** | 列出设计图清单、从 Schema 生成 HTML+CSS 代码、获取切图资源列表 |
| **留言板（messages）** | 发布/查看/编辑/删除留言，支持 @成员、知识库类型、正则筛选 |
| **协作者（members）** | 查看曾访问项目的协作者列表及时间记录 |
| **链接解析（resolve）** | 将蓝湖邀请/分享链接解析为含 tid/pid/docId 的完整 URL |

---

## 安装

> 请参考 [INSTALL.md](INSTALL.md) 了解环境要求、Cookie 配置及完整启动步骤。

---

## 快速使用

```bash
# 列出原型文档的所有页面
lanhu pages list "https://lanhuapp.com/web/#/item/project/product?tid=...&pid=...&docId=..."

# 全局文本扫描（快速）
lanhu pages analyze <URL> --mode text_only

# 深度分析指定页面（开发视角）
lanhu pages analyze <URL> --page-names "登录页,首页" --analysis-mode developer

# 列出 UI 设计图
lanhu designs list "https://lanhuapp.com/web/#/item/project/stage?tid=...&pid=..."

# 生成指定设计图的 HTML+CSS
lanhu designs analyze <URL> --design-names "首页"

# 获取设计图切图资源
lanhu designs slices <URL> "首页设计"

# 查看所有项目留言
lanhu messages list all

# 发布一条问题留言并 @成员
lanhu messages post <URL> "接口确认" "登录字段格式待确认" --type question --mentions 张三

# 查看项目协作者
lanhu members list <URL>

# 解析邀请链接
lanhu resolve "https://lanhuapp.com/link/#/invite?sid=xxx"
```

---

## 命令参考

### `lanhu pages`

```
lanhu pages list <URL>
lanhu pages analyze <URL>
    --page-names TEXT     页面名称，"all" 或逗号分隔  [默认: all]
    --mode                full | text_only            [默认: full]
    --analysis-mode       developer | tester | explorer  [默认: developer]
```

**分析模式说明：**

| 模式 | 适用场景 | 输出内容 |
|---|---|---|
| `developer` | 开发人员看需求、准备写代码 | 字段规则表、业务规则清单、全局流程图 |
| `tester` | 测试人员写测试用例 | 正向/异常场景、字段校验表、状态变化表 |
| `explorer` | 需求评审会议、快速了解 | 模块核心功能、依赖关系图、评审讨论点 |

---

### `lanhu designs`

```
lanhu designs list <URL>
lanhu designs analyze <URL>
    --design-names TEXT   名称或序号，"all" 或逗号分隔  [默认: all]
lanhu designs slices <URL> <DESIGN_NAME>
    --no-metadata         跳过颜色/阴影元数据
```

---

### `lanhu messages`

```
lanhu messages post <URL> <SUMMARY> <CONTENT>
    --type     normal | task | question | urgent | knowledge  [默认: normal]
    --mentions 逗号分隔的 @成员姓名

lanhu messages list [URL|all]
    --filter-type  按类型过滤
    --search TEXT  正则表达式搜索
    --limit INT    最多返回条数

lanhu messages detail <MESSAGE_IDS> [URL]
lanhu messages edit   <URL> <ID> [--summary TEXT] [--content TEXT] [--mentions TEXT]
lanhu messages delete <URL> <ID>
```

---

### `lanhu members`

```
lanhu members list <URL>
```

---

### `lanhu resolve`

```
lanhu resolve <INVITE_URL>
```

---

## 全局选项

所有命令均支持以下选项：

| 选项 | 默认值 | 说明 |
|---|---|---|
| `--user-name` | `cli-user` | 协作者记录中显示的用户名 |
| `--user-role` | `开发` | AI 提示词视角选择（前端/后端/测试等） |
| `--help` | — | 显示帮助信息 |

---

## 数据存储

所有本地数据（截图缓存、留言数据库、设计图下载）存储于：

```
~/.lanhu-cli/data/
├── messages/     # 留言板 SQLite 数据库（按项目 ID 分目录）
├── lanhu_designs/  # 设计图 HTML/CSS 及图片
└── axure_extract_*/  # Axure 原型资源及截图缓存
```

---

## 注意事项

- Cookie 有效期有限，失效后需重新从浏览器复制并更新 `.env` 文件
- 截图功能依赖 Playwright Chromium，首次使用需执行 `playwright install chromium`
- 部分 API（`pages analyze`、`designs analyze`）受蓝湖账号权限限制，无权限时返回 418 错误
- `.env` 文件**不会**被提交到 Git（已加入 `.gitignore`）

---

## 开发

```bash
git clone https://github.com/koco-co/lanhu-cli.git
cd lanhu-cli
uv venv .venv && uv pip install -e .
cp .env.example .env   # 填入真实 Cookie
```

---

## License

MIT
