"""MessageStore and CRUD helpers for the Lanhu team message board."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from lanhu_cli.config import (
    CHINA_TZ, DATA_DIR, MENTION_ROLES,
    normalize_role, get_metadata_cache_key,
    get_cached_metadata, set_cached_metadata,
)
from lanhu_cli.utils.url import parse_lanhu_url


# ── Helpers ───────────────────────────────────────────────────

def _get_project_id_from_url(url: str) -> Optional[str]:
    if not url or url.lower() == "all":
        return None
    try:
        return parse_lanhu_url(url).get("project_id")
    except Exception:
        return None


def _clean_message_dict(msg: dict, current_user_name: str = None) -> dict:
    """Strip None values and add convenience flags."""
    cleaned = {k: v for k, v in msg.items() if v is not None}
    cleaned["is_edited"] = bool(cleaned.get("updated_at"))
    if current_user_name:
        cleaned["is_mine"] = cleaned.get("author_name") == current_user_name
    return cleaned


# ── MessageStore ──────────────────────────────────────────────

class MessageStore:
    """Local JSON-backed message board for a single Lanhu project."""

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id
        self.storage_dir = DATA_DIR / "messages"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        if project_id:
            self.file_path = self.storage_dir / f"{project_id}.json"
            self._data = self._load()
        else:
            self.file_path = None
            self._data = None

    def _load(self) -> dict:
        if self.file_path and self.file_path.exists():
            try:
                return json.loads(self.file_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "project_id": self.project_id,
            "next_id": 1,
            "messages": [],
            "collaborators": [],
        }

    def _save(self):
        self.file_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _now(self) -> str:
        return datetime.now(CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")

    def _check_mentions_me(self, mentions: List[str], user_role: str) -> bool:
        if not mentions:
            return False
        if "所有人" in mentions:
            return True
        normalized = normalize_role(user_role)
        return user_role in mentions or normalized in mentions

    # ── Collaborators ─────────────────────────────────────────

    def record_collaborator(self, name: str, role: str):
        if not name or not role:
            return
        now = self._now()
        for c in self._data.get("collaborators", []):
            if c["name"] == name and c["role"] == role:
                c["last_seen"] = now
                self._save()
                return
        self._data.setdefault("collaborators", []).append(
            {"name": name, "role": role, "first_seen": now, "last_seen": now}
        )
        self._save()

    def get_collaborators(self) -> List[dict]:
        return self._data.get("collaborators", [])

    # ── CRUD ──────────────────────────────────────────────────

    def save_message(self, summary: str, content: str, author_name: str,
                     author_role: str, mentions: List[str] = None,
                     message_type: str = "normal", **meta) -> dict:
        msg_id = self._data["next_id"]
        self._data["next_id"] += 1
        message = {
            "id": msg_id,
            "summary": summary,
            "content": content,
            "mentions": mentions or [],
            "message_type": message_type,
            "author_name": author_name,
            "author_role": author_role,
            "created_at": self._now(),
            "updated_at": None,
            "updated_by_name": None,
            "updated_by_role": None,
            "project_id": self.project_id,
            **meta,
        }
        self._data["messages"].append(message)
        self._save()
        return message

    def get_messages(self, user_role: str = None) -> List[dict]:
        msgs = []
        for m in self._data.get("messages", []):
            copy = {k: v for k, v in m.items() if k != "content"}
            if user_role:
                copy["mentions_me"] = self._check_mentions_me(m.get("mentions", []), user_role)
            msgs.append(copy)
        msgs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return msgs

    def get_message_by_id(self, msg_id: int, user_role: str = None) -> Optional[dict]:
        for m in self._data.get("messages", []):
            if m["id"] == msg_id:
                copy = m.copy()
                if user_role:
                    copy["mentions_me"] = self._check_mentions_me(m.get("mentions", []), user_role)
                return copy
        return None

    def update_message(self, msg_id: int, editor_name: str, editor_role: str,
                       summary: str = None, content: str = None,
                       mentions: List[str] = None) -> Optional[dict]:
        for m in self._data.get("messages", []):
            if m["id"] == msg_id:
                if summary is not None:
                    m["summary"] = summary
                if content is not None:
                    m["content"] = content
                if mentions is not None:
                    m["mentions"] = mentions
                m["updated_at"] = self._now()
                m["updated_by_name"] = editor_name
                m["updated_by_role"] = editor_role
                self._save()
                return m
        return None

    def delete_message(self, msg_id: int) -> bool:
        msgs = self._data.get("messages", [])
        for i, m in enumerate(msgs):
            if m["id"] == msg_id:
                msgs.pop(i)
                self._save()
                return True
        return False

    # ── Global queries ────────────────────────────────────────

    def get_all_messages(self, user_role: str = None) -> List[dict]:
        all_msgs: list = []
        for json_file in self.storage_dir.glob("*.json"):
            try:
                store = MessageStore(json_file.stem)
                all_msgs.extend(store.get_messages(user_role=user_role))
            except Exception:
                continue
        all_msgs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return all_msgs

    def get_all_messages_grouped(self, user_role: str = None, user_name: str = None) -> List[dict]:
        all_msgs = self.get_all_messages(user_role)
        groups_dict: dict = defaultdict(list)
        for m in all_msgs:
            groups_dict[f"{m.get('project_id', 'unknown')}_{m.get('doc_id', 'no_doc')}"].append(m)

        meta_fields = {
            "project_id", "project_name", "folder_name",
            "doc_id", "doc_name", "doc_type", "doc_version", "doc_updated_at", "doc_url",
        }
        groups: list = []
        for msgs in groups_dict.values():
            if not msgs:
                continue
            first = msgs[0]
            group = {
                **{k: first.get(k) for k in meta_fields},
                "message_count": len(msgs),
                "mentions_me_count": sum(1 for m in msgs if m.get("mentions_me")),
                "messages": [
                    _clean_message_dict({k: v for k, v in m.items() if k not in meta_fields}, user_name)
                    for m in msgs
                ],
            }
            groups.append(group)

        groups.sort(
            key=lambda g: max((m.get("created_at", "") for m in g["messages"]), default=""),
            reverse=True,
        )
        return groups


# ── High-level API functions ──────────────────────────────────

async def _fetch_metadata(url: str) -> dict:
    """Fetch document metadata from Lanhu API (with in-process cache)."""
    from lanhu_cli.api.extractor import LanhuExtractor

    metadata = {
        "project_id": None, "project_name": None, "folder_name": None,
        "doc_id": None, "doc_name": None, "doc_type": None,
        "doc_version": None, "doc_updated_at": None, "doc_url": None,
    }

    async with LanhuExtractor() as ex:
        try:
            params = ex.parse_url(url)
            project_id = params.get("project_id")
            doc_id = params.get("doc_id")
            team_id = params.get("team_id")
            metadata["project_id"] = project_id
            metadata["doc_id"] = doc_id
            if not project_id:
                return metadata

            cache_key = get_metadata_cache_key(project_id, doc_id)
            version_id = None

            if doc_id:
                doc_info = await ex.get_document_info(project_id, doc_id)
                versions = doc_info.get("versions", [])
                if versions:
                    version_id = versions[0].get("id")
                    metadata["doc_version"] = versions[0].get("version_info")
                cached = get_cached_metadata(cache_key, version_id)
                if cached:
                    return cached
                metadata["doc_name"] = doc_info.get("name")
                metadata["doc_type"] = doc_info.get("type", "axure")
                from lanhu_cli.config import CHINA_TZ
                from datetime import datetime
                ut = doc_info.get("update_time")
                if ut:
                    try:
                        dt = datetime.fromisoformat(ut.replace("Z", "+00:00"))
                        metadata["doc_updated_at"] = dt.astimezone(CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        metadata["doc_updated_at"] = ut
                if team_id and project_id and doc_id:
                    metadata["doc_url"] = (
                        f"https://lanhuapp.com/web/#/item/project/product"
                        f"?tid={team_id}&pid={project_id}&docId={doc_id}"
                    )

            if project_id and team_id:
                from lanhu_cli.config import BASE_URL
                r = await ex.client.get(f"{BASE_URL}/api/project/multi_info",
                                        params={"project_id": project_id, "team_id": team_id, "doc_info": 1})
                if r.status_code == 200:
                    d = r.json()
                    if d.get("code") == "00000":
                        pi = d.get("result", {})
                        metadata["project_name"] = pi.get("name")
                        metadata["folder_name"] = pi.get("folder_name")

            set_cached_metadata(cache_key, metadata, version_id)
        except Exception:
            pass
    return metadata


async def say(url: str, summary: str, content: str,
              mentions: Optional[List[str]] = None,
              message_type: str = "normal",
              author_name: str = "cli-user",
              author_role: str = "开发") -> dict:
    project_id = _get_project_id_from_url(url)
    if not project_id:
        return {"status": "error", "message": "无法从URL解析project_id"}

    valid_types = ["normal", "task", "question", "urgent", "knowledge"]
    if message_type not in valid_types:
        return {"status": "error", "message": f"无效类型: {message_type}", "valid_types": valid_types}

    if mentions:
        bad = [n for n in mentions if n not in MENTION_ROLES]
        if bad:
            return {"status": "error", "message": f"无效人名: {bad}", "valid_names": MENTION_ROLES}

    metadata = await _fetch_metadata(url)
    store = MessageStore(project_id)
    store.record_collaborator(author_name, author_role)

    msg = store.save_message(
        summary=summary, content=content,
        author_name=author_name, author_role=author_role,
        mentions=mentions or [], message_type=message_type,
        project_name=metadata.get("project_name"),
        folder_name=metadata.get("folder_name"),
        doc_id=metadata.get("doc_id"),
        doc_name=metadata.get("doc_name"),
        doc_type=metadata.get("doc_type"),
        doc_version=metadata.get("doc_version"),
        doc_updated_at=metadata.get("doc_updated_at"),
        doc_url=metadata.get("doc_url"),
    )
    return {"status": "success", "message": "留言发布成功", "data": {
        "id": msg["id"], "summary": msg["summary"],
        "message_type": msg["message_type"], "mentions": msg["mentions"],
        "author_name": msg["author_name"], "created_at": msg["created_at"],
        "project_id": project_id,
    }}


async def say_list(url: Optional[str] = None, filter_type: Optional[str] = None,
                   search_regex: Optional[str] = None, limit: Optional[int] = None,
                   user_name: str = "cli-user", user_role: str = "开发") -> dict:
    regex_pattern = None
    if search_regex:
        try:
            regex_pattern = re.compile(search_regex, re.IGNORECASE)
        except re.error as e:
            return {"status": "error", "message": f"无效正则: {search_regex}", "error": str(e)}

    def apply_filters(msgs: list) -> list:
        result = []
        for m in msgs:
            if filter_type and m.get("message_type") != filter_type:
                continue
            if regex_pattern:
                text = f"{m.get('summary', '')} {m.get('content', '')}"
                if not regex_pattern.search(text):
                    continue
            result.append(m)
        return result[:limit] if limit else result

    if not url or url.lower() == "all":
        store = MessageStore(project_id=None)
        groups = store.get_all_messages_grouped(user_role=user_role, user_name=user_name)
        filtered_groups = []
        for g in groups:
            fm = apply_filters(g["messages"])
            if fm:
                gc = g.copy()
                gc["messages"] = fm
                gc["message_count"] = len(fm)
                gc["mentions_me_count"] = sum(1 for m in fm if m.get("mentions_me"))
                filtered_groups.append(gc)
        return {
            "status": "success", "mode": "global",
            "total_messages": sum(g["message_count"] for g in filtered_groups),
            "total_groups": len(filtered_groups),
            "groups": filtered_groups,
        }

    project_id = _get_project_id_from_url(url)
    if not project_id:
        return {"status": "error", "message": "无法从URL解析project_id"}

    store = MessageStore(project_id)
    store.record_collaborator(user_name, user_role)
    msgs = apply_filters(store.get_messages(user_role=user_role))

    meta_fields = {"project_id", "project_name", "folder_name", "doc_id", "doc_name",
                   "doc_type", "doc_version", "doc_updated_at", "doc_url"}
    groups_dict: dict = defaultdict(list)
    for m in msgs:
        groups_dict[m.get("doc_id", "no_doc")].append(m)

    groups = []
    for doc_msgs in groups_dict.values():
        first = doc_msgs[0]
        groups.append({
            **{k: first.get(k) for k in ("doc_id", "doc_name", "doc_type", "doc_version", "doc_updated_at", "doc_url")},
            "message_count": len(doc_msgs),
            "mentions_me_count": sum(1 for m in doc_msgs if m.get("mentions_me")),
            "messages": [_clean_message_dict({k: v for k, v in m.items() if k not in meta_fields}, user_name) for m in doc_msgs],
        })
    groups.sort(key=lambda g: max((m.get("created_at", "") for m in g["messages"]), default=""), reverse=True)

    return {
        "status": "success", "mode": "single_project",
        "project_id": project_id,
        "total_messages": len(msgs), "total_groups": len(groups),
        "mentions_me_count": sum(1 for m in msgs if m.get("mentions_me")),
        "groups": groups,
    }


async def say_detail(message_ids, url: Optional[str] = None,
                     project_id: Optional[str] = None,
                     user_role: str = "开发") -> dict:
    if isinstance(message_ids, (int, float)):
        message_ids = [int(message_ids)]
    elif isinstance(message_ids, list):
        message_ids = [int(mid) for mid in message_ids]
    else:
        return {"status": "error", "message": "message_ids 必须是整数或数组"}

    pid = _get_project_id_from_url(url) if url and url.lower() != "all" else project_id
    if not pid:
        return {"status": "error", "message": "请提供url或project_id"}

    store = MessageStore(pid)
    msgs, not_found = [], []
    for mid in message_ids:
        m = store.get_message_by_id(mid, user_role=user_role)
        (msgs if m else not_found).append(m if m else mid)
    return {"status": "success", "total": len(msgs), "messages": msgs, "not_found": not_found}


async def say_edit(url: str, message_id: int,
                   summary: str = None, content: str = None,
                   mentions: Optional[List[str]] = None,
                   editor_name: str = "cli-user",
                   editor_role: str = "开发") -> dict:
    project_id = _get_project_id_from_url(url)
    if not project_id:
        return {"status": "error", "message": "无法从URL解析project_id"}

    if mentions:
        bad = [n for n in mentions if n not in MENTION_ROLES]
        if bad:
            return {"status": "error", "message": f"无效人名: {bad}"}

    if summary is None and content is None and mentions is None:
        return {"status": "error", "message": "请至少提供一个要更新的字段"}

    store = MessageStore(project_id)
    store.record_collaborator(editor_name, editor_role)
    updated = store.update_message(int(message_id), editor_name, editor_role,
                                   summary=summary, content=content, mentions=mentions)
    if not updated:
        return {"status": "error", "message": "消息不存在", "message_id": message_id}
    return {"status": "success", "message": "消息更新成功", "data": updated}


async def say_delete(url: str, message_id: int,
                     editor_name: str = "cli-user",
                     editor_role: str = "开发") -> dict:
    project_id = _get_project_id_from_url(url)
    if not project_id:
        return {"status": "error", "message": "无法从URL解析project_id"}
    store = MessageStore(project_id)
    store.record_collaborator(editor_name, editor_role)
    success = store.delete_message(int(message_id))
    if not success:
        return {"status": "error", "message": "消息不存在", "message_id": message_id}
    return {"status": "success", "message": "消息删除成功", "deleted_id": message_id}


async def get_members(url: str, user_name: str = "cli-user", user_role: str = "开发") -> dict:
    project_id = _get_project_id_from_url(url)
    if not project_id:
        return {"status": "error", "message": "无法从URL解析project_id"}
    store = MessageStore(project_id)
    store.record_collaborator(user_name, user_role)
    return {
        "status": "success",
        "project_id": project_id,
        "total": len(store.get_collaborators()),
        "collaborators": store.get_collaborators(),
    }
