"""Pages API — get page list and analyze pages."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Union

from lanhu_cli.config import DATA_DIR
from lanhu_cli.utils.html import _format_page_design_info


def _get_analysis_mode_options_by_role(user_role: str) -> str:
    from lanhu_cli.config import normalize_role
    normalized_role = normalize_role(user_role)
    developer_option = """1️⃣ 【开发视角】- 详细技术文档
   适合：开发人员看需求，准备写代码
   输出：详细字段规则表、业务规则清单、全局流程图、接口依赖说明"""
    tester_option = """2️⃣ 【测试视角】- 测试用例和验证点
   适合：测试人员写测试用例
   输出：正向/异常测试场景、字段校验规则表、状态变化表、联调测试清单"""
    explorer_option = """3️⃣ 【快速探索】- 全局评审视角
   适合：需求评审会议、快速了解需求
   输出：模块核心功能概览、依赖关系图、开发顺序建议"""

    if normalized_role in ["后端", "前端", "客户端", "开发"]:
        return f"\n{developer_option}\n\n{tester_option}\n\n{explorer_option}\n"
    elif "测试" in user_role or "test" in user_role.lower() or "qa" in user_role.lower():
        return f"\n{tester_option.replace('2️⃣', '1️⃣')}\n\n{developer_option.replace('1️⃣', '2️⃣')}\n\n{explorer_option}\n"
    else:
        return f"\n{explorer_option.replace('3️⃣', '1️⃣')}\n\n{developer_option.replace('1️⃣', '2️⃣')}\n\n{tester_option.replace('2️⃣', '3️⃣')}\n"


def _get_stage2_prompt_developer() -> str:
    return """
🧠 元认知验证（开发视角）

**🔍 变更类型识别**：🆕新增 / 🔄修改 / ❓未明确
**📊 功能清单表**：| 功能点 | 描述 | 输入 | 输出 | 业务规则 | 异常处理 |
**📋 字段规则表**（如有表单）：| 字段名 | 必填 | 类型 | 长度/格式 | 校验规则 | 错误提示 |
**🔗 与全局关联**：数据依赖、数据输出、交互跳转、状态同步
**⚠️ 遗漏/矛盾检查**：不清晰的地方、潜在矛盾、UI与文字冲突
"""


def _get_stage2_prompt_tester() -> str:
    return """
🧠 元认知验证（测试视角）

**🔍 变更类型识别**：🆕新增→全量测试 / 🔄修改→回归+增量测试
**✅ 正向场景（P0）**：前置条件→步骤→期望结果
**⚠️ 异常场景（P1）**：触发条件→期望结果
**📋 字段校验规则表**：| 字段名 | 必填 | 长度/格式 | 校验规则 | 错误提示 | 测试边界值 |
**🔄 状态变化表**：| 操作 | 操作前 | 操作后 | 界面变化 |
**🔗 联调测试点**：依赖模块、影响模块
"""


def _get_stage2_prompt_explorer() -> str:
    return """
🧠 元认知验证（快速探索视角）

**🔍 变更类型识别**：🆕新增 / 🔄修改 / ❓未明确
**📦 模块核心功能**（3-5个）：一句话描述
**🔗 依赖关系识别**：依赖输入、输出影响、依赖强度
**💡 关键特征**：外部接口、支付、审批、文件上传
**🎯 评审讨论点**：给产品/给开发/给测试
"""


def _get_analysis_mode_prompt(analysis_mode: str) -> dict:
    if analysis_mode == "tester":
        return {"mode_name": "测试视角", "mode_desc": "提取测试场景、校验规则、异常清单",
                "stage2_prompt": _get_stage2_prompt_tester(),
                "stage4_prompt": "【STAGE 4 - 测试视角】：测试计划文档（模块数、场景数、测试用例清单、回归建议）"}
    elif analysis_mode == "explorer":
        return {"mode_name": "快速探索", "mode_desc": "提取核心功能、依赖关系、评审要点",
                "stage2_prompt": _get_stage2_prompt_explorer(),
                "stage4_prompt": "【STAGE 4 - 快速探索】：评审文档（模块清单表、数据流向图、开发顺序建议）"}
    else:
        return {"mode_name": "开发视角", "mode_desc": "提取所有细节、字段规则、完整流程",
                "stage2_prompt": _get_stage2_prompt_developer(),
                "stage4_prompt": "【STAGE 4 - 开发视角】：需求文档总结（概览+全局流程图+模块详情+待确认事项）"}


def fix_html_files(directory: str):
    from bs4 import BeautifulSoup
    for html_path in Path(directory).glob("*.html"):
        try:
            content = html_path.read_text(encoding='utf-8')
            soup = BeautifulSoup(content, 'html.parser')
            for tag in soup.find_all(['img', 'script']):
                if tag.has_attr('data-src'):
                    tag['src'] = tag['data-src']
                    del tag['data-src']
            for tag in soup.find_all('link'):
                if tag.has_attr('data-src'):
                    tag['href'] = tag['data-src']
                    del tag['data-src']
            body = soup.find('body')
            if body and body.has_attr('style'):
                style = body['style']
                style = re.sub(r'display\s*:\s*none\s*;?', '', style)
                style = re.sub(r'opacity\s*:\s*0\s*;?', '', style)
                style = style.strip()
                if style:
                    body['style'] = style
                else:
                    del body['style']
            for script in soup.find_all('script'):
                if script.string and 'alistatic.lanhuapp.com' in script.string:
                    script.decompose()
            head = soup.find('head')
            if head:
                mapping_script = soup.new_tag('script')
                mapping_script.string = 'function lanhu_Axure_Mapping_Data(data){return data;}'
                first_script = head.find('script')
                if first_script:
                    first_script.insert_before(mapping_script)
                else:
                    head.append(mapping_script)
            html_path.write_text(str(soup), encoding='utf-8')
        except Exception:
            pass


async def get_pages(url: str, user_name: str = "cli-user",
                   user_role: str = "开发") -> dict:
    """Get page list for a Lanhu Axure prototype document."""
    from lanhu_cli.api.extractor import LanhuExtractor
    from lanhu_cli.api.messages import MessageStore
    from lanhu_cli.utils.url import parse_lanhu_url

    async with LanhuExtractor() as ex:
        project_id = parse_lanhu_url(url).get("project_id")
        if project_id:
            MessageStore(project_id).record_collaborator(user_name, user_role)

        result = await ex.get_pages_list(url)
        total_pages = result.get('total_pages', 0)
        mode_options = _get_analysis_mode_options_by_role(user_role)

        result['ai_suggestion'] = {
            'notice': f'Document has {total_pages} pages',
            'next_action': 'Call analyze_pages(page_names="all", mode="text_only") for STAGE 1 global scan',
            'workflow': 'STAGE 1 (text scan) → choose mode → STAGE 2 (detail) → STAGE 3 (validate) → STAGE 4 (doc)',
            'mode_options': mode_options,
        }
        return result


async def analyze_pages(url: str, page_names: Union[str, List[str]] = "all",
                        mode: str = "full", analysis_mode: str = "developer",
                        user_name: str = "cli-user", user_role: str = "开发") -> dict:
    """Analyze Axure prototype pages — screenshot + text extraction."""
    from lanhu_cli.api.extractor import LanhuExtractor
    from lanhu_cli.api.messages import MessageStore
    from lanhu_cli.utils.url import parse_lanhu_url
    from lanhu_cli.utils.screenshot import screenshot_page_internal

    async with LanhuExtractor() as ex:
        project_id = parse_lanhu_url(url).get("project_id")
        if project_id:
            MessageStore(project_id).record_collaborator(user_name, user_role)

        params = ex.parse_url(url)
        doc_id = params['doc_id']

        resource_dir = str(DATA_DIR / f"axure_extract_{doc_id[:8]}")
        output_dir = str(DATA_DIR / f"axure_extract_{doc_id[:8]}_screenshots")

        download_result = await ex.download_resources(url, resource_dir)
        if download_result['status'] in ('downloaded', 'updated'):
            fix_html_files(resource_dir)

        pages_info = await ex.get_pages_list(url)
        all_pages = pages_info['pages']
        page_map = {p['name']: p['filename'].replace('.html', '') for p in all_pages}

        if isinstance(page_names, str):
            if page_names.lower() == 'all':
                target_pages = [p['filename'].replace('.html', '') for p in all_pages]
                target_page_names = [p['name'] for p in all_pages]
            else:
                if page_names in page_map:
                    target_pages = [page_map[page_names]]
                    target_page_names = [page_names]
                else:
                    target_pages = [page_names]
                    target_page_names = [page_names]
        else:
            target_pages, target_page_names = [], []
            for pn in page_names:
                if pn in page_map:
                    target_pages.append(page_map[pn])
                    target_page_names.append(pn)
                else:
                    target_pages.append(pn)
                    target_page_names.append(pn)

        version_id = download_result.get('version_id', '')
        is_text_only = (mode == "text_only")

        results = await screenshot_page_internal(
            resource_dir, target_pages, output_dir,
            return_base64=False, version_id=version_id
        )

        filename_to_display = {p['filename'].replace('.html', ''): p['name'] for p in all_pages}
        success_results = [r for r in results if r['success']]
        failed_results = [r for r in results if not r['success']]

        mode_prompts = _get_analysis_mode_prompt(analysis_mode)

        pages_out = []
        for idx, r in enumerate(success_results, 1):
            display_name = filename_to_display.get(r['page_name'], r['page_name'])
            page_data = {
                'index': idx,
                'page_name': display_name,
                'screenshot_path': r.get('screenshot_path'),
                'text': r.get('page_text', ''),
                'from_cache': r.get('from_cache', False),
            }
            if not is_text_only and r.get('page_design_info'):
                style_text = _format_page_design_info(r['page_design_info'], resource_dir)
                if style_text:
                    page_data['design_info'] = style_text
            pages_out.append(page_data)

        return {
            'status': 'success',
            'mode': mode,
            'analysis_mode': analysis_mode,
            'mode_name': mode_prompts['mode_name'],
            'version_id': version_id,
            'total': len(success_results),
            'failed': len(failed_results),
            'pages': pages_out,
            'failed_pages': [{'page': r['page_name'], 'error': r.get('error')} for r in failed_results],
            'stage2_prompt': mode_prompts['stage2_prompt'] if not is_text_only else None,
            'stage4_prompt': mode_prompts['stage4_prompt'] if not is_text_only else None,
        }
