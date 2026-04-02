"""Designs API — get UI design list, analyze, and get slices."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from lanhu_cli.config import DATA_DIR
from lanhu_cli.utils.html import convert_lanhu_to_html, minify_html, _localize_image_urls, _extract_design_tokens


async def _get_designs_internal(extractor, url: str) -> dict:
    params = extractor.parse_url(url)
    api_url = (
        f"https://lanhuapp.com/api/project/images"
        f"?project_id={params['project_id']}"
        f"&team_id={params['team_id']}"
        f"&dds_status=1&position=1&show_cb_src=1&comment=1"
    )
    response = await extractor.client.get(api_url)
    response.raise_for_status()
    data = response.json()

    if data.get('code') != '00000':
        return {'status': 'error', 'message': data.get('msg', 'Unknown error')}

    project_data = data.get('data', {})
    images = project_data.get('images', [])
    design_list = []
    for idx, img in enumerate(images, 1):
        design_list.append({
            'index': idx,
            'id': img.get('id'),
            'name': img.get('name'),
            'width': img.get('width'),
            'height': img.get('height'),
            'url': img.get('url'),
            'has_comment': img.get('has_comment', False),
            'update_time': img.get('update_time'),
        })
    return {
        'status': 'success',
        'project_name': project_data.get('name'),
        'total_designs': len(design_list),
        'designs': design_list,
    }


async def get_designs(url: str, user_name: str = "cli-user",
                      user_role: str = "开发") -> dict:
    """Get UI design image list for a Lanhu project."""
    from lanhu_cli.api.extractor import LanhuExtractor
    from lanhu_cli.api.messages import MessageStore
    from lanhu_cli.utils.url import parse_lanhu_url

    async with LanhuExtractor() as ex:
        project_id = parse_lanhu_url(url).get("project_id")
        if project_id:
            MessageStore(project_id).record_collaborator(user_name, user_role)
        result = await _get_designs_internal(ex, url)
        if result['status'] == 'success':
            total = result.get('total_designs', 0)
            if total > 8:
                result['ai_suggestion'] = {
                    'notice': f'Project contains {total} design images',
                    'user_prompt': f'该项目包含 {total} 个设计图。请选择下载范围：全部 or 指定设计图。',
                }
        return result


async def analyze_designs(url: str,
                          design_names: Union[str, List[str]] = "all",
                          user_name: str = "cli-user",
                          user_role: str = "开发") -> dict:
    """Download designs and generate HTML+CSS code from schema."""
    from lanhu_cli.api.extractor import LanhuExtractor
    from lanhu_cli.api.messages import MessageStore
    from lanhu_cli.utils.url import parse_lanhu_url

    async with LanhuExtractor() as ex:
        project_id_parsed = parse_lanhu_url(url).get("project_id")
        if project_id_parsed:
            MessageStore(project_id_parsed).record_collaborator(user_name, user_role)

        params = ex.parse_url(url)
        designs_data = await _get_designs_internal(ex, url)
        if designs_data['status'] != 'success':
            return {'status': 'error', 'message': designs_data.get('message')}

        designs = designs_data['designs']

        if isinstance(design_names, str) and design_names.lower() == 'all':
            target_designs = designs
        else:
            if isinstance(design_names, (str, int, float)):
                design_names = [design_names]
            seen_ids = set()
            target_designs = []
            image_id_from_url = params.get('doc_id')

            for name in (design_names or []):
                name_str = str(name).strip()
                if name_str.isdigit():
                    n = int(name_str)
                    for d in designs:
                        if d.get('index') == n and d['id'] not in seen_ids:
                            target_designs.append(d)
                            seen_ids.add(d['id'])
                            break
                else:
                    for d in designs:
                        if d['name'] == name_str and d['id'] not in seen_ids:
                            target_designs.append(d)
                            seen_ids.add(d['id'])
                            break

            if not target_designs and image_id_from_url:
                for d in designs:
                    if d.get('id') == image_id_from_url:
                        target_designs.append(d)
                        break

        if not target_designs:
            available = [d['name'] for d in designs]
            return {'status': 'error', 'message': 'No matching design found',
                    'available_designs': available}

        output_dir = DATA_DIR / 'lanhu_designs' / params['project_id']
        output_dir.mkdir(parents=True, exist_ok=True)

        results_out = []

        for design in target_designs:
            entry: dict = {'design_name': design['name'], 'design_id': design['id']}

            # 1. Download image
            try:
                img_url = design['url'].split('?')[0]
                response = await ex.client.get(img_url)
                response.raise_for_status()
                img_filepath = output_dir / f"{design['name']}.png"
                img_filepath.write_bytes(response.content)
                entry['image_path'] = str(img_filepath)
            except Exception as e:
                entry['image_error'] = str(e)

            # 2. Get schema HTML
            try:
                schema_json = await ex.get_design_schema_json(
                    design['id'], params['team_id'], params['project_id']
                )
                html_code = minify_html(convert_lanhu_to_html(schema_json))
                html_code, image_url_mapping = _localize_image_urls(html_code, design['name'])
                html_filepath = output_dir / f"{design['name']}.html"
                html_filepath.write_text(html_code, encoding='utf-8')
                entry['html_path'] = str(html_filepath)
                entry['html_code'] = html_code
                entry['image_url_mapping'] = image_url_mapping
                entry['html_success'] = True
            except Exception as e:
                entry['html_error'] = str(e)
                entry['html_success'] = False

            # 3. Get Sketch JSON / design tokens
            try:
                sketch_json = await ex.get_sketch_json(
                    design['id'], params['team_id'], params['project_id']
                )
                design_tokens = _extract_design_tokens(sketch_json)
                if design_tokens:
                    entry['design_tokens'] = design_tokens

                if not entry.get('html_success'):
                    from lanhu_cli.utils.html import convert_sketch_to_html
                    device_str = sketch_json.get('device', '')
                    scale = 3.0 if '@3x' in device_str else (1.0 if '@1x' in device_str else 2.0)
                    img_url = design['url'].split('?')[0]
                    fallback_html, fallback_mapping, _ = convert_sketch_to_html(
                        sketch_json, scale, img_url
                    )
                    fallback_mapping['./assets/designs/design.png'] = img_url
                    fallback_html = minify_html(fallback_html)
                    entry['fallback_html'] = fallback_html
                    entry['image_url_mapping'] = fallback_mapping
            except Exception:
                pass

            results_out.append(entry)

        return {
            'status': 'success',
            'project_name': designs_data['project_name'],
            'total': len(results_out),
            'designs': results_out,
        }


async def get_design_slices(url: str, design_name: str,
                            include_metadata: bool = True,
                            user_name: str = "cli-user",
                            user_role: str = "开发") -> dict:
    """Get slice/asset info from a specific Lanhu design."""
    from lanhu_cli.api.extractor import LanhuExtractor
    from lanhu_cli.api.messages import MessageStore
    from lanhu_cli.utils.url import parse_lanhu_url

    async with LanhuExtractor() as ex:
        project_id_parsed = parse_lanhu_url(url).get("project_id")
        if project_id_parsed:
            MessageStore(project_id_parsed).record_collaborator(user_name, user_role)

        designs_data = await _get_designs_internal(ex, url)
        if designs_data['status'] != 'success':
            return {'status': 'error', 'message': designs_data.get('message')}

        params = ex.parse_url(url)
        image_id_from_url = params.get('doc_id')

        target_design = None
        for d in designs_data['designs']:
            if d['name'] == design_name:
                target_design = d
                break
        if not target_design and image_id_from_url:
            for d in designs_data['designs']:
                if d.get('id') == image_id_from_url:
                    target_design = d
                    break

        if not target_design:
            available = [d['name'] for d in designs_data['designs']]
            return {'status': 'error',
                    'message': f"Design '{design_name}' not found",
                    'available_designs': available}

        slices_data = await ex.get_design_slices_info(
            image_id=target_design['id'],
            team_id=params['team_id'],
            project_id=params['project_id'],
            include_metadata=include_metadata,
        )
        return {'status': 'success', **slices_data}
