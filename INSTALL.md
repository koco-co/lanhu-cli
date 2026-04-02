# 安装与配置指南

本文档说明如何在本地环境中配置并启动 **lanhu-cli**。

---

## 环境要求

| 依赖 | 最低版本 | 说明 |
|---|---|---|
| Python | 3.10+ | 推荐 3.11 或 3.12 |
| [uv](https://docs.astral.sh/uv/) | 最新版 | Python 环境与包管理工具 |
| Git | — | 用于克隆仓库 |

---

## 第一步：克隆仓库

```bash
git clone https://github.com/koco-co/lanhu-cli.git
cd lanhu-cli
```

---

## 第二步：创建虚拟环境并安装依赖

```bash
# 创建 .venv 虚拟环境（自动选择系统中合适的 Python 版本）
uv venv .venv

# 安装项目及所有依赖
uv pip install -e .
```

安装完成后，`lanhu` 命令会注册到 `.venv/bin/lanhu`。

> **提示：** 激活虚拟环境后可直接使用 `lanhu` 命令：
> ```bash
> source .venv/bin/activate
> lanhu --help
> ```
> 或不激活，直接使用完整路径：
> ```bash
> .venv/bin/lanhu --help
> ```

---

## 第三步：安装 Playwright 浏览器（截图功能必须）

`pages analyze` 和 `resolve` 命令依赖 Playwright 驱动 Chromium 进行截图和链接跳转。

```bash
.venv/bin/playwright install chromium
```

> 如果只使用 `pages list`、`messages`、`members` 等无截图命令，可跳过此步骤。

---

## 第四步：配置蓝湖 Cookie

lanhu-cli 通过 Cookie 鉴权访问蓝湖 API。

### 4.1 复制 `.env` 模板

```bash
cp .env.example .env
```

### 4.2 从浏览器获取 Cookie

1. 在浏览器中打开 [lanhuapp.com](https://lanhuapp.com) 并登录
2. 按 `F12` 打开开发者工具 → 切换到 **Network（网络）** 标签
3. 刷新页面，点击任意一个 `api/` 请求
4. 在 **Request Headers** 中找到 `Cookie:` 字段，复制完整 Cookie 字符串

### 4.3 写入 `.env` 文件

打开 `.env`，填入以下内容：

```dotenv
# 必填：从浏览器 DevTools 复制的完整 Cookie 字符串
LANHU_COOKIE="acw_tc=...; PASSPORT=...; session=...; user_token=..."

# 可选：留言板本地服务配置（通常不需要修改）
SERVER_HOST="127.0.0.1"
SERVER_PORT=8000
```

> ⚠️ **安全提示：**
> - `.env` 文件已被加入 `.gitignore`，**不会**被提交到 Git
> - 请勿将 Cookie 分享给他人或提交到任何代码仓库
> - Cookie 有时效性，失效后重新复制即可

---

## 第五步：验证安装

```bash
# 查看版本和帮助
.venv/bin/lanhu --version
.venv/bin/lanhu --help

# 测试基础功能（无需截图）
.venv/bin/lanhu messages list all
.venv/bin/lanhu pages list "https://lanhuapp.com/web/#/item/project/product?tid=...&pid=...&docId=..."
```

如果返回 JSON 数据则说明安装成功。

---

## 常见问题

### Q: 执行命令时报 `401` 或 `403` 错误

Cookie 已过期或无效。重新从浏览器复制 Cookie 并更新 `.env` 文件。

### Q: 执行 `pages analyze` 时报错 `playwright` 找不到

未安装 Playwright 浏览器。执行：

```bash
.venv/bin/playwright install chromium
```

### Q: 返回 `418 You don't have the permission`

当前蓝湖账号对该项目无访问权限。请联系项目管理员将你的账号加入项目。

### Q: `uv` 命令找不到

参考 [uv 官方安装文档](https://docs.astral.sh/uv/getting-started/installation/)：

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或通过 pip
pip install uv
```

### Q: Python 版本不满足要求

uv 可以自动下载并管理指定版本的 Python：

```bash
uv venv .venv --python 3.12
```

---

## 目录结构参考

```
lanhu-cli/
├── .env                  # 本地配置（不提交 Git）
├── .env.example          # 配置模板
├── pyproject.toml        # 项目元数据与依赖
├── src/
│   └── lanhu_cli/
│       ├── cli.py        # CLI 入口
│       ├── config.py     # 配置加载
│       ├── api/          # 各功能模块
│       └── utils/        # 工具函数
└── README.md
```

---

## 卸载

```bash
# 删除虚拟环境
rm -rf .venv

# 删除本地数据缓存（可选）
rm -rf ~/.lanhu-cli
```
