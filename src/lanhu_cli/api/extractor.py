"""LanhuExtractor — direct HTTP client for the Lanhu API."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from lanhu_cli.config import (
    BASE_URL, CDN_URL, DDS_BASE_URL, COOKIE, DDS_COOKIE,
    HTTP_TIMEOUT, CHINA_TZ,
    get_metadata_cache_key, get_cached_metadata, set_cached_metadata,
)
from lanhu_cli.utils.url import parse_lanhu_url


class LanhuExtractor:
    """Direct HTTP client for the Lanhu API."""

    CACHE_META_FILE = ".lanhu_cache.json"

    def __init__(self, cookie: str = None):
        used_cookie = cookie or COOKIE
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://lanhuapp.com/web/",
            "Accept": "application/json, text/plain, */*",
            "Cookie": used_cookie,
            "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "request-from": "web",
            "real-path": "/item/project/product",
        }
        self.client = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT, headers=headers, follow_redirects=True
        )

    def parse_url(self, url: str) -> dict:
        return parse_lanhu_url(url)

    async def get_document_info(self, project_id: str, doc_id: str) -> dict:
        """Fetch document metadata from /api/project/image."""
        api_url = f"{BASE_URL}/api/project/image"
        params = {"pid": project_id, "image_id": doc_id}
        response = await self.client.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        code = data.get("code")
        if code not in (0, "0", "00000"):
            raise Exception(f"API Error: {data.get('msg')} (code={code})")
        return data.get("data") or data.get("result", {})

    # ── Cache helpers ─────────────────────────────────────────

    def _get_cache_meta_path(self, output_dir: Path) -> Path:
        return output_dir / self.CACHE_META_FILE

    def _load_cache_meta(self, output_dir: Path) -> dict:
        p = self._get_cache_meta_path(output_dir)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_cache_meta(self, output_dir: Path, meta: dict):
        output_dir.mkdir(parents=True, exist_ok=True)
        self._get_cache_meta_path(output_dir).write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _should_update_cache(self, output_dir: Path, version_id: str, mapping: dict):
        meta = self._load_cache_meta(output_dir)
        if meta.get("version_id") != version_id:
            return (True, "version_changed", [])
        pages = mapping.get("pages", {})
        missing = [fn for fn in pages if not (output_dir / fn).exists()]
        if missing:
            return (True, "files_missing", missing)
        return (False, "up_to_date", [])

    # ── Page list ─────────────────────────────────────────────

    async def get_pages_list(self, url: str) -> dict:
        """Return structured page list for a Lanhu Axure document."""
        params = self.parse_url(url)
        doc_info = await self.get_document_info(params["project_id"], params["doc_id"])

        project_info = None
        try:
            r = await self.client.get(
                f"{BASE_URL}/api/project/multi_info",
                params={
                    "project_id": params["project_id"],
                    "team_id": params["team_id"],
                    "doc_info": 1,
                },
            )
            r.raise_for_status()
            d = r.json()
            if d.get("code") == "00000":
                project_info = d.get("result", {})
        except Exception:
            pass

        versions = doc_info.get("versions", [])
        if not versions:
            raise Exception("Document version info not found")

        latest_version = versions[0]
        json_url = latest_version.get("json_url")
        if not json_url:
            raise Exception("Mapping JSON URL not found")

        r = await self.client.get(json_url)
        r.raise_for_status()
        project_mapping = r.json()

        sitemap = project_mapping.get("sitemap", {})
        root_nodes = sitemap.get("rootNodes", [])

        def extract_pages(nodes, pages_list, parent_path="", level=0, parent_folder=None):
            for node in nodes:
                page_name = node.get("pageName", "")
                node_url = node.get("url", "")
                node_type = node.get("type", "Wireframe")
                node_id = node.get("id", "")
                current_path = f"{parent_path}/{page_name}" if parent_path else page_name
                is_pure_folder = node_type == "Folder" and not node_url
                if page_name and node_url:
                    pages_list.append({
                        "index": len(pages_list) + 1,
                        "name": page_name,
                        "filename": node_url,
                        "id": node_id,
                        "type": node_type,
                        "level": level,
                        "folder": parent_folder or "根目录",
                        "path": current_path,
                        "has_children": bool(node.get("children")),
                    })
                children = node.get("children", [])
                if children:
                    next_folder = page_name if is_pure_folder else parent_folder
                    extract_pages(children, pages_list, current_path, level + 1, next_folder)

        pages_list: list = []
        extract_pages(root_nodes, pages_list)

        def fmt_time(ts):
            if not ts:
                return None
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.astimezone(CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return ts

        folder_stats: dict = defaultdict(int)
        max_level = 0
        pages_with_children = 0
        for p in pages_list:
            folder_stats[p.get("folder", "根目录")] += 1
            max_level = max(max_level, p.get("level", 0))
            if p.get("has_children"):
                pages_with_children += 1

        result = {
            "document_id": params["doc_id"],
            "document_name": doc_info.get("name", "Unknown"),
            "document_type": doc_info.get("type", "axure"),
            "total_pages": len(pages_list),
            "max_level": max_level,
            "pages_with_children": pages_with_children,
            "folder_statistics": dict(folder_stats),
            "pages": pages_list,
        }
        if doc_info.get("create_time"):
            result["create_time"] = fmt_time(doc_info["create_time"])
        if doc_info.get("update_time"):
            result["update_time"] = fmt_time(doc_info["update_time"])
        result["total_versions"] = len(versions)
        if latest_version.get("version_info"):
            result["latest_version"] = latest_version["version_info"]
        if project_info:
            for key in ("creator_name", "folder_name", "save_path", "member_cnt"):
                if project_info.get(key):
                    out_key = "project_path" if key == "save_path" else ("member_count" if key == "member_cnt" else key)
                    result[out_key] = project_info[key]
        return result

    # ── Resource download ─────────────────────────────────────

    async def download_resources(self, url: str, output_dir: str, force_update: bool = False) -> dict:
        """Download all Axure resources for a document (with caching)."""
        params = self.parse_url(url)
        doc_info = await self.get_document_info(params["project_id"], params["doc_id"])
        versions = doc_info.get("versions", [])
        ver_info = versions[0]
        version_id = ver_info.get("id", "")
        json_url = ver_info.get("json_url")

        r = await self.client.get(json_url)
        r.raise_for_status()
        project_mapping = r.json()
        output_path = Path(output_dir)

        if not force_update and output_path.exists():
            need, reason, _ = self._should_update_cache(output_path, version_id, project_mapping)
            if not need:
                return {"status": "cached", "version_id": version_id, "output_dir": output_dir}

        output_path.mkdir(parents=True, exist_ok=True)
        pages = project_mapping.get("pages", {})
        is_first_page = True
        downloaded: list = []

        for html_filename, page_info in pages.items():
            html_file_with_md5 = page_info.get("html", {}).get("sign_md5", "")
            page_mapping_md5 = page_info.get("mapping_md5", "")
            if not html_file_with_md5:
                continue
            r = await self.client.get(f"{CDN_URL}/{html_file_with_md5}")
            r.raise_for_status()
            html_content = r.text
            if page_mapping_md5:
                mr = await self.client.get(f"{CDN_URL}/{page_mapping_md5}")
                mr.raise_for_status()
                page_mapping = mr.json()
                await self._download_page_resources(page_mapping, output_path, skip_document_js=not is_first_page)
                is_first_page = False
            (output_path / html_filename).write_text(html_content, encoding="utf-8")
            downloaded.append(html_filename)

        self._save_cache_meta(output_path, {
            "version_id": version_id,
            "document_id": params["doc_id"],
            "document_name": doc_info.get("name", "Unknown"),
            "pages": list(pages.keys()),
            "total_files": len(downloaded),
        })
        return {"status": "downloaded", "version_id": version_id, "output_dir": output_dir}

    async def _download_page_resources(self, page_mapping: dict, output_dir: Path, skip_document_js: bool = False):
        tasks = []
        for section in ("styles", "scripts", "images"):
            for local_path, info in page_mapping.get(section, {}).items():
                if skip_document_js and local_path == "data/document.js":
                    continue
                md5 = info.get("sign_md5", "")
                if md5:
                    file_url = md5 if md5.startswith("http") else f"{CDN_URL}/{md5}"
                    tasks.append(self._download_file(file_url, output_dir / local_path))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _download_file(self, url: str, local_path: Path):
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            r = await self.client.get(url)
            r.raise_for_status()
            local_path.write_bytes(r.content)
        except Exception:
            pass

    # ── Design slices ─────────────────────────────────────────

    async def get_design_slices_info(self, image_id: str, team_id: str, project_id: str,
                                     include_metadata: bool = True) -> dict:
        """Return all slice metadata for a design file."""
        r = await self.client.get(f"{BASE_URL}/api/project/image", params={
            "dds_status": 1, "image_id": image_id,
            "team_id": team_id, "project_id": project_id,
        })
        data = r.json()
        if data["code"] != "00000":
            raise Exception(f"Failed to get design: {data['msg']}")
        result = data["result"]
        latest_version = result["versions"][0]
        sketch_data = (await self.client.get(latest_version["json_url"])).json()

        slices: list = []

        def find_slices(obj, parent_name="", layer_path=""):
            if not obj or not isinstance(obj, dict):
                return
            current_name = obj.get("name", "")
            current_path = f"{layer_path}/{current_name}" if layer_path else current_name

            # New structure
            if obj.get("image") and (obj["image"].get("imageUrl") or obj["image"].get("svgUrl")):
                img = obj["image"]
                frame = obj.get("frame") or obj.get("bounds") or {}
                w, h = frame.get("width", 0), frame.get("height", 0)
                sl: dict = {
                    "id": obj.get("id"),
                    "name": current_name,
                    "type": obj.get("type") or obj.get("layerType") or "bitmap",
                    "download_url": img.get("imageUrl") or img.get("svgUrl"),
                    "size": f"{int(w)}x{int(h)}" if w and h else "unknown",
                    "format": "png" if img.get("imageUrl") else "svg",
                    "layer_path": current_path,
                }
                x = frame.get("x") or frame.get("left", 0)
                y = frame.get("y") or frame.get("top", 0)
                if x is not None or y is not None:
                    sl["position"] = {"x": int(x), "y": int(y)}
                if parent_name:
                    sl["parent_name"] = parent_name
                if include_metadata:
                    meta: dict = {}
                    for k in ("fills", "borders", "opacity", "rotation", "textStyle", "shadows"):
                        if obj.get(k):
                            meta[k] = obj[k]
                    if obj.get("radius") or obj.get("cornerRadius"):
                        meta["border_radius"] = obj.get("radius") or obj.get("cornerRadius")
                    if meta:
                        sl["metadata"] = meta
                slices.append(sl)
            # Old structure
            elif obj.get("ddsImage") and obj["ddsImage"].get("imageUrl"):
                sl = {
                    "id": obj.get("id"),
                    "name": current_name,
                    "type": obj.get("type") or obj.get("ddsType"),
                    "download_url": obj["ddsImage"]["imageUrl"],
                    "size": obj["ddsImage"].get("size", "unknown"),
                    "format": "png",
                    "layer_path": current_path,
                }
                if "left" in obj and "top" in obj:
                    sl["position"] = {"x": int(obj.get("left", 0)), "y": int(obj.get("top", 0))}
                if parent_name:
                    sl["parent_name"] = parent_name
                slices.append(sl)

            for layer in obj.get("layers", []):
                find_slices(layer, current_name, current_path)
            for v in obj.values():
                if isinstance(v, dict) and v is not obj:
                    find_slices(v, parent_name, layer_path)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            find_slices(item, parent_name, layer_path)

        if sketch_data.get("artboard") and sketch_data["artboard"].get("layers"):
            for layer in sketch_data["artboard"]["layers"]:
                find_slices(layer)
        elif sketch_data.get("info"):
            for item in sketch_data["info"]:
                find_slices(item)

        return {
            "design_id": image_id,
            "design_name": result["name"],
            "version": latest_version["version_info"],
            "canvas_size": {"width": result.get("width"), "height": result.get("height")},
            "total_slices": len(slices),
            "slices": slices,
        }

    # ── DDS schema (for design HTML conversion) ───────────────

    async def _get_version_id_by_image_id(self, project_id: str, team_id: str, image_id: str) -> str:
        r = await self.client.get(f"{BASE_URL}/api/project/multi_info", params={
            "project_id": project_id, "team_id": team_id,
            "img_limit": 500, "detach": 1,
        })
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "00000":
            raise Exception(f"multi_info failed: {data.get('msg')}")
        for img in (data.get("result") or {}).get("images") or []:
            if img.get("id") == image_id:
                vid = img.get("latest_version")
                if vid:
                    return vid
                raise Exception("Design has no latest_version")
        raise Exception(f"image_id={image_id} not found")

    async def _fetch_dds_schema(self, version_id: str) -> dict:
        dds_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://dds.lanhuapp.com/",
            "Cookie": DDS_COOKIE,
            "Authorization": "Basic dW5kZWZpbmVkOg==",
        }
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=dds_headers, follow_redirects=True) as c:
            rev = await c.get(f"{DDS_BASE_URL}/api/dds/image/store_schema_revise",
                              params={"version_id": version_id})
            rev.raise_for_status()
            rev_data = rev.json()
            if rev_data.get("code") != "00000":
                raise Exception(f"store_schema_revise failed: {rev_data.get('msg')}")
            schema_url = (rev_data.get("data") or {}).get("data_resource_url")
            if not schema_url:
                raise Exception("store_schema_revise returned no data_resource_url")
            return (await c.get(schema_url)).json()

    async def get_design_schema_json(self, image_id: str, team_id: str, project_id: str) -> dict:
        version_id = await self._get_version_id_by_image_id(project_id, team_id, image_id)
        return await self._fetch_dds_schema(version_id)

    async def get_sketch_json(self, image_id: str, team_id: str, project_id: str) -> dict:
        r = await self.client.get(f"{BASE_URL}/api/project/image", params={
            "dds_status": 1, "image_id": image_id,
            "team_id": team_id, "project_id": project_id,
        })
        data = r.json()
        if data["code"] != "00000":
            raise Exception(f"Failed to get design: {data['msg']}")
        result = data["result"]
        return (await self.client.get(result["versions"][0]["json_url"])).json()

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()
