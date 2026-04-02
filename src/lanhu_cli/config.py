"""Configuration — loads .env and exports all shared constants."""

import os
from pathlib import Path
from datetime import timezone, timedelta

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)
except ImportError:
    pass

# ── Timezone ─────────────────────────────────────────────────
CHINA_TZ = timezone(timedelta(hours=8))

# ── Lanhu credentials ────────────────────────────────────────
COOKIE = os.getenv("LANHU_COOKIE", "")
DDS_COOKIE = os.getenv("DDS_COOKIE", COOKIE)

# ── API base URLs ─────────────────────────────────────────────
BASE_URL = "https://lanhuapp.com"
DDS_BASE_URL = "https://dds.lanhuapp.com"
CDN_URL = "https://axure-file.lanhuapp.com"

# ── Runtime settings ──────────────────────────────────────────
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "30"))
VIEWPORT_WIDTH = int(os.getenv("VIEWPORT_WIDTH", "1920"))
VIEWPORT_HEIGHT = int(os.getenv("VIEWPORT_HEIGHT", "1080"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ── Data storage ──────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", str(Path.home() / ".lanhu-cli" / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── In-memory metadata cache ─────────────────────────────────
_metadata_cache: dict = {}

# ── Role / mention config ─────────────────────────────────────
VALID_ROLES = ["后端", "前端", "客户端", "开发", "运维", "产品", "项目经理"]

MENTION_ROLES = [
    "张三", "李四", "王五", "赵六", "钱七", "孙八",
    "周九", "吴十", "郑十一", "冯十二", "陈十三", "褚十四",
    "卫十五", "蒋十六", "沈十七", "韩十八", "杨十九", "朱二十",
]

ROLE_MAPPING_RULES = [
    (["后端", "backend", "服务端", "server", "java", "php", "python", "go", "golang", "node", "nodejs", ".net", "c#"], "后端"),
    (["前端", "frontend", "h5", "web", "vue", "react", "angular", "javascript", "js", "ts", "typescript", "css"], "前端"),
    (["客户端", "client", "ios", "android", "安卓", "移动端", "mobile", "app", "flutter", "rn", "react native", "swift", "kotlin", "objective-c", "oc"], "客户端"),
    (["运维", "ops", "devops", "sre", "dba", "运营维护", "系统管理", "infra", "infrastructure"], "运维"),
    (["产品", "product", "pm", "产品经理", "需求"], "产品"),
    (["项目经理", "项目", "pmo", "project manager", "scrum", "敏捷"], "项目经理"),
    (["开发", "dev", "developer", "程序员", "coder", "engineer", "工程师"], "开发"),
]


def normalize_role(role: str) -> str:
    """Normalize a user role string to a standard role."""
    if not role:
        return "未知"
    if role in VALID_ROLES:
        return role
    role_lower = role.lower()
    for keywords, standard_role in ROLE_MAPPING_RULES:
        for keyword in keywords:
            if keyword.lower() in role_lower:
                return standard_role
    return role


def get_metadata_cache_key(project_id: str, doc_id: str = None) -> str:
    return f"{project_id}_{doc_id}" if doc_id else project_id


def get_cached_metadata(cache_key: str, version_id: str = None):
    if cache_key in _metadata_cache:
        entry = _metadata_cache[cache_key]
        if version_id:
            if entry.get("version_id") == version_id:
                return entry["data"]
            del _metadata_cache[cache_key]
            return None
        return entry["data"]
    return None


def set_cached_metadata(cache_key: str, metadata: dict, version_id: str = None):
    _metadata_cache[cache_key] = {"data": metadata.copy(), "version_id": version_id}
