"""HTML conversion helpers migrated from lanhu-mcp."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


# ── CSS utilities ──────────────────────────────────────────────

_UNITLESS_PROPERTIES = {'zIndex', 'fontWeight', 'opacity', 'flex', 'flexGrow', 'flexShrink', 'order'}

COMMON_CSS_FOR_DESIGN = """
body * {
  box-sizing: border-box;
  flex-shrink: 0;
}
body {
  font-family: PingFangSC-Regular, Roboto, Helvetica Neue, Helvetica, Tahoma,
    Arial, PingFang SC-Light, Microsoft YaHei;
}
input {
  background-color: transparent;
  border: 0;
}
button {
  margin: 0;
  padding: 0;
  border: 1px solid transparent;
  outline: none;
  background-color: transparent;
}
button:active {
  opacity: 0.6;
}
.flex-col {
  display: flex;
  flex-direction: column;
}
.flex-row {
  display: flex;
  flex-direction: row;
}
.justify-start {
  display: flex;
  justify-content: flex-start;
}
.justify-center {
  display: flex;
  justify-content: center;
}
.justify-end {
  display: flex;
  justify-content: flex-end;
}
.justify-evenly {
  display: flex;
  justify-content: space-evenly;
}
.justify-around {
  display: flex;
  justify-content: space-around;
}
.justify-between {
  display: flex;
  justify-content: space-between;
}
.align-start {
  display: flex;
  align-items: flex-start;
}
.align-center {
  display: flex;
  align-items: center;
}
.align-end {
  display: flex;
  align-items: flex-end;
}
"""


def _camel_to_kebab(s: str) -> str:
    return re.sub(r'([A-Z])', lambda m: f'-{m.group(1).lower()}', s)


def _format_css_value(key: str, value) -> str:
    if value is None:
        return ''
    if isinstance(value, (int, float)):
        if value == 0:
            return '0'
        return str(value) if key in _UNITLESS_PROPERTIES else f'{value}px'
    if isinstance(value, str):
        if 'rgba(' in value:
            def replace_rgba(match):
                r, g, b, a = match.groups()
                alpha = float(a) if '.' in a else int(a)
                return f'rgba({r}, {g}, {b}, {alpha})'
            return re.sub(r'rgba\(([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)\)', replace_rgba, value)
        if re.match(r'^\d+$', value) and key not in _UNITLESS_PROPERTIES:
            return '0' if value == '0' else f'{value}px'
    return str(value)


def _merge_padding(styles: dict) -> None:
    pt = styles.get('paddingTop')
    pr = styles.get('paddingRight')
    pb = styles.get('paddingBottom')
    pl = styles.get('paddingLeft')
    if pt is not None and pr is not None and pb is not None and pl is not None:
        pt_v, pr_v, pb_v, pl_v = pt or 0, pr or 0, pb or 0, pl or 0
        if pt_v == pb_v and pl_v == pr_v:
            styles['padding'] = f'{pt_v}px' if pt_v == pl_v else f'{pt_v}px {pr_v}px'
        else:
            styles['padding'] = f'{pt_v}px {pr_v}px {pb_v}px {pl_v}px'
        for k in ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft']:
            styles.pop(k, None)


def _merge_margin(styles: dict) -> None:
    mt = styles.get('marginTop')
    mr = styles.get('marginRight')
    mb = styles.get('marginBottom')
    ml = styles.get('marginLeft')
    if mt is not None or mr is not None or mb is not None or ml is not None:
        mt_v, mr_v, mb_v, ml_v = mt or 0, mr or 0, mb or 0, ml or 0
        if not any([mt_v, mr_v, mb_v, ml_v]):
            pass
        elif mt_v == mb_v and ml_v == mr_v:
            styles['margin'] = f'{mt_v}px' if mt_v == ml_v else f'{mt_v}px {mr_v}px'
        else:
            styles['margin'] = f'{mt_v}px {mr_v}px {mb_v}px {ml_v}px'
        for k in ['marginTop', 'marginRight', 'marginBottom', 'marginLeft']:
            styles.pop(k, None)


def _should_use_flex(node: dict) -> bool:
    if not node:
        return False
    style = {**node.get('style', {}), **node.get('props', {}).get('style', {})}
    return style.get('display') == 'flex' or style.get('flexDirection') is not None


def _get_flex_classes(node: dict) -> list:
    classes = []
    if not _should_use_flex(node):
        return classes
    style = {**node.get('style', {}), **node.get('props', {}).get('style', {})}
    class_name = node.get('props', {}).get('className', '')
    flex_direction = style.get('flexDirection')
    if flex_direction == 'column' or 'flex-col' in class_name:
        classes.append('flex-col')
    elif flex_direction == 'row' or 'flex-row' in class_name:
        classes.append('flex-row')
    justify = node.get('alignJustify', {}).get('justifyContent') or style.get('justifyContent')
    justify_map = {'space-between': 'justify-between', 'center': 'justify-center',
                   'flex-end': 'justify-end', 'flex-start': 'justify-start',
                   'space-around': 'justify-around', 'space-evenly': 'justify-evenly'}
    if justify in justify_map:
        classes.append(justify_map[justify])
    align = node.get('alignJustify', {}).get('alignItems') or style.get('alignItems')
    align_map = {'flex-start': 'align-start', 'center': 'align-center', 'flex-end': 'align-end'}
    if align in align_map:
        classes.append(align_map[align])
    return classes


def _clean_styles(node: dict, flex_classes: list) -> dict:
    props_style = node.get('props', {}).get('style', {})
    styles = {}
    standard_justify = {'flex-start', 'center', 'flex-end', 'space-between', 'space-around', 'space-evenly'}
    standard_align = {'flex-start', 'center', 'flex-end'}
    for key, value in props_style.items():
        if key in ('display', 'flexDirection') and flex_classes:
            continue
        if key == 'justifyContent' and flex_classes and value in standard_justify:
            continue
        if key == 'alignItems' and flex_classes and value in standard_align:
            continue
        if key == 'position' and value == 'static':
            continue
        if key == 'overflow' and value == 'visible':
            continue
        styles[key] = value
    if any(k in styles for k in ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft']):
        _merge_padding(styles)
    if any(k in styles for k in ['marginTop', 'marginRight', 'marginBottom', 'marginLeft']):
        _merge_margin(styles)
    return styles


def _get_loop_arr(node: dict) -> list:
    if not node:
        return []
    arr = node.get('loop') or node.get('loopData')
    return arr if isinstance(arr, list) else []


def _generate_css(node: dict, css_rules: dict, loop_suffixes: list | None = None) -> None:
    if not node:
        return
    loop_arr = _get_loop_arr(node) if node.get('loopType') else []
    if loop_arr and not loop_suffixes:
        loop_suffixes = [str(i) for i in range(len(loop_arr))]
    node_props = node.get('props', {})
    class_name = node_props.get('className')
    if class_name:
        flex_classes = _get_flex_classes(node)
        styles = _clean_styles(node, flex_classes)
        style_entries = list(styles.items())
        if style_entries or node.get('type') == 'lanhutext':
            css_props = [
                f'  {_camel_to_kebab(k)}: {_format_css_value(k, v)};'
                for k, v in style_entries if _format_css_value(k, v)
            ]
            content = '\n'.join(css_props) if css_props else ''
        else:
            content = ''
        if loop_suffixes:
            for suf in loop_suffixes:
                css_rules[f'{class_name}-{suf}'] = content
        else:
            css_rules[class_name] = content
    for child in node.get('children', []):
        _generate_css(child, css_rules, loop_suffixes)


def _resolve_loop_placeholder(value: str, loop_item: dict) -> str:
    if not value or not isinstance(loop_item, dict):
        return value or ''
    s = str(value).strip()
    m = re.match(r'^this\.item\.(\w+)$', s)
    return loop_item.get(m.group(1), '') if m else value


def _generate_html(node: dict, indent: int = 2,
                   loop_context: tuple[list, int] | None = None) -> str:
    if not node:
        return ''
    loop_item = loop_context[0][loop_context[1]] if loop_context else None
    loop_index = loop_context[1] if loop_context else None
    spaces = ' ' * indent
    flex_classes = _get_flex_classes(node)
    node_props = node.get('props', {})
    class_name = node_props.get('className', '')
    if loop_index is not None and class_name:
        class_name = f'{class_name}-{loop_index}'
    all_classes = ' '.join([c for c in [class_name] + flex_classes if c])
    node_type = node.get('type')

    if node_type == 'lanhutext':
        text = node.get('data', {}).get('value') or node_props.get('text') or ''
        if loop_item is not None and text and re.match(r'^this\.item\.\w+$', str(text).strip()):
            text = _resolve_loop_placeholder(text, loop_item)
        elif text and re.match(r'^this\.item\.\w+$', str(text).strip()):
            text = ''
        return f'{spaces}<span class="{all_classes}">{text}</span>'

    if node_type == 'lanhuimage':
        src = node.get('data', {}).get('value') or node_props.get('src') or ''
        if loop_item is not None and src and re.match(r'^this\.item\.\w+$', str(src).strip()):
            src = _resolve_loop_placeholder(src, loop_item)
        elif src and re.match(r'^this\.item\.\w+$', str(src).strip()):
            src = ''
        return (f'{spaces}<img\n{spaces}  class="{all_classes}"\n'
                f'{spaces}  referrerpolicy="no-referrer"\n'
                f'{spaces}  src="{src}"\n{spaces}/>')

    if node_type == 'lanhubutton':
        children_html = '\n'.join([_generate_html(c, indent + 2, loop_context) for c in node.get('children', [])])
        return f'{spaces}<button class="{all_classes}">\n{children_html}\n{spaces}</button>'

    children = node.get('children', [])
    loop_arr = _get_loop_arr(node) if node.get('loopType') else []

    if loop_arr and loop_context is None:
        parts = []
        for i in range(len(loop_arr)):
            ctx = (loop_arr, i)
            for child in children:
                parts.append(_generate_html(child, indent + 2, ctx))
        return f'{spaces}<div class="{all_classes}">\n' + '\n'.join(parts) + f'\n{spaces}</div>'

    if children:
        children_html = '\n'.join([_generate_html(c, indent + 2, loop_context) for c in children])
        return f'{spaces}<div class="{all_classes}">\n{children_html}\n{spaces}</div>'
    return f'{spaces}<div class="{all_classes}"></div>'


def convert_lanhu_to_html(json_data: dict) -> str:
    css_rules = {}
    _generate_css(json_data, css_rules)
    css_parts = []
    for class_name, props in css_rules.items():
        if props:
            css_parts.append(f'.{class_name} {{\n{props}\n}}')
        else:
            css_parts.append(f'.{class_name} {{\n}}')
    css_string = '\n\n'.join(css_parts) + COMMON_CSS_FOR_DESIGN
    body_html = _generate_html(json_data, 4)
    return f'''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Document</title>
    <style>
{css_string}
    </style>
  </head>
  <body>
{body_html}
  </body>
</html>'''


def minify_html(html: str) -> str:
    try:
        import htmlmin
    except ImportError:
        return html
    def replace_style(match):
        inner = _minify_css(match.group(1))
        return f'<style>\n{inner}\n</style>'
    html = re.sub(r'<style[^>]*>([\s\S]*?)</style>', replace_style, html, count=0)
    return htmlmin.minify(html, remove_comments=True, remove_empty_space=True)


def _minify_css(css: str) -> str:
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    css = re.sub(r'\s+', ' ', css)
    css = re.sub(r'\s*([{};:,>~+])\s*', r'\1', css)
    return css.strip()


def _localize_image_urls(html_code: str, design_name: str) -> tuple[str, dict]:
    url_mapping = {}
    counter = [0]

    def _make_local_name(remote_url: str) -> str:
        parsed = urlparse(remote_url)
        path = parsed.path
        ext = '.png'
        if '.' in path.split('/')[-1]:
            ext = '.' + path.split('/')[-1].rsplit('.', 1)[-1]
            if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'):
                ext = '.png'
        counter[0] += 1
        return f"img_{counter[0]}{ext}"

    def _replace_img_src(match):
        url = match.group(1)
        if not url or not url.startswith('http'):
            return match.group(0)
        local_name = _make_local_name(url)
        local_path = f"./assets/slices/{local_name}"
        url_mapping[local_path] = url
        return f'src="{local_path}"'

    def _replace_css_url(match):
        url = match.group(1).strip('\'"')
        if not url or not url.startswith('http'):
            return match.group(0)
        local_name = _make_local_name(url)
        local_path = f"./assets/slices/{local_name}"
        url_mapping[local_path] = url
        return f"url('{local_path}')"

    result = re.sub(r'src="(https?://[^"]*)"', _replace_img_src, html_code)
    result = re.sub(r"src='(https?://[^']*)'", _replace_img_src, result)
    result = re.sub(r'src=(https?://[^\s>\'\"]+)', _replace_img_src, result)
    result = re.sub(r'url\(([\'"]*https?://[^\)]*)\)', _replace_css_url, result)
    return result, url_mapping


def _format_page_design_info(design_info: dict, resource_dir: str = "") -> str:
    if not design_info:
        return ""
    lines = ["[设计样式参考 - 用于生成代码时匹配原型视觉效果]"]
    text_colors = design_info.get('textColors', [])
    if text_colors:
        lines.append("  文字颜色 (按使用频率):")
        for color_val, count in text_colors:
            lines.append(f"    {color_val} (x{count})")
    bg_colors = design_info.get('bgColors', [])
    if bg_colors:
        lines.append("  背景颜色:")
        for color_val, count in bg_colors:
            lines.append(f"    {color_val} (x{count})")
    font_specs = design_info.get('fontSpecs', [])
    if font_specs:
        lines.append("  字体规格 (字号/字重/颜色):")
        for spec_key, count in font_specs:
            parts = spec_key.split('|')
            if len(parts) == 3:
                lines.append(f"    {parts[0]} / {parts[1]} / {parts[2]} (x{count})")
            else:
                lines.append(f"    {spec_key} (x{count})")
    images = design_info.get('images', [])
    if images:
        lines.append("  页面图片资源 (切图):")
        seen = set()
        for img in images:
            src = img.get('src', '')
            if not src or src in seen:
                continue
            seen.add(src)
            if 'localhost' in src or '127.0.0.1' in src:
                parsed = urlparse(src)
                src = parsed.path.lstrip('/')
            w = img.get('w', '?')
            h = img.get('h', '?')
            img_type = img.get('type', 'img')
            label = "背景图" if img_type == 'bg' else "图片"
            local_note = ""
            if resource_dir:
                local_file = Path(resource_dir) / src
                if local_file.exists():
                    local_note = f" [本地: {local_file}]"
            lines.append(f"    [{label}] {src} ({w}x{h}){local_note}")
    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def _extract_design_tokens(sketch_data: dict) -> str:
    """Extract high-risk element design tokens from Sketch JSON for AI validation."""
    import math

    NOISE_TYPES = {'color', 'gradient', 'colorStop', 'colorControl'}

    def _get_dimensions(obj):
        frame = obj.get('ddsOriginFrame') or obj.get('layerOriginFrame') or {}
        x = frame.get('x', obj.get('left', 0)) or 0
        y = frame.get('y', obj.get('top', 0)) or 0
        w = frame.get('width', obj.get('width', 0)) or 0
        h = frame.get('height', obj.get('height', 0)) or 0
        return x, y, w, h

    def _simplify_fill(fill):
        if not fill.get('isEnabled', True):
            return None
        fill_type = fill.get('fillType', 0)
        if fill_type == 0:
            color = fill.get('color', {})
            return f"solid({color.get('value', 'unknown')})"
        if fill_type == 1:
            gradient = fill.get('gradient', {})
            stops = gradient.get('colorStops', [])
            from_pt = gradient.get('from', {})
            to_pt = gradient.get('to', {})
            dx = to_pt.get('x', 0.5) - from_pt.get('x', 0.5)
            dy = to_pt.get('y', 0) - from_pt.get('y', 0)
            angle = round(math.degrees(math.atan2(dx, dy))) % 360
            parts = []
            for s in stops:
                c = s.get('color', {}).get('value', 'unknown')
                p = s.get('position', 0)
                parts.append(f"{c} {round(p * 100)}%")
            return f"linear-gradient({angle}deg, {', '.join(parts)})"
        return None

    def _simplify_border(border):
        if not border.get('isEnabled', True):
            return None
        color = border.get('color', {}).get('value', 'unknown')
        thickness = border.get('thickness', 1)
        pos_map = {'内边框': 'inside', '外边框': 'outside', '中心边框': 'center'}
        pos = pos_map.get(border.get('position', ''), border.get('position', 'center'))
        return f"{thickness}px {pos} {color}"

    def _simplify_shadow(shadow):
        if not shadow.get('isEnabled', True):
            return None
        color = shadow.get('color', {}).get('value', 'unknown')
        x = shadow.get('offsetX', 0)
        y = shadow.get('offsetY', 0)
        blur = shadow.get('blurRadius', 0)
        spread = shadow.get('spread', 0)
        return f"{color} {x}px {y}px {blur}px {spread}px"

    def _has_only_transparent_solid(fills):
        for f in fills:
            if not f.get('isEnabled', True):
                continue
            if f.get('fillType', 0) == 0:
                color = f.get('color', {})
                val = color.get('value', '')
                if 'rgba' in val and ',0)' in val.replace(' ', ''):
                    continue
                alpha = color.get('alpha', color.get('a', 1))
                if alpha == 0:
                    continue
            return False
        return True

    def _is_high_risk(obj):
        obj_type = (obj.get('type') or obj.get('ddsType') or '').lower()
        if obj_type in NOISE_TYPES:
            return False
        _, _, w, h = _get_dimensions(obj)
        if w < 2 and h < 2:
            return False
        fills = obj.get('fills', [])
        if any(f.get('isEnabled', True) and f.get('fillType') == 1 for f in fills):
            return True
        if any(b.get('isEnabled', True) for b in obj.get('borders', [])):
            return True
        radius = obj.get('radius')
        if isinstance(radius, list) and len(set(radius)) > 1:
            return True
        opacity = obj.get('opacity')
        if opacity is not None and opacity < 100:
            if _has_only_transparent_solid(fills) and not obj.get('borders') and not obj.get('shadows'):
                return False
            return True
        if any(s.get('isEnabled', True) for s in obj.get('shadows', [])):
            return True
        return False

    tokens = []

    def _walk(obj, parent_path=""):
        if not obj or not isinstance(obj, dict):
            return
        if not obj.get('isVisible', True):
            return
        name = obj.get('name', '')
        current_path = f"{parent_path}/{name}" if parent_path else name
        if _is_high_risk(obj):
            obj_type = obj.get('type') or obj.get('ddsType') or 'unknown'
            x, y, w, h = _get_dimensions(obj)
            lines = [f'[{obj_type}] "{name}" @({int(x)},{int(y)}) {int(w)}x{int(h)}']
            if parent_path:
                lines[0] += f'  path: {current_path}'
            radius = obj.get('radius')
            if radius:
                if isinstance(radius, list):
                    lines.append(f'  radius: {radius[0]}' if len(set(radius)) == 1 else f'  radius: {radius}')
                else:
                    lines.append(f'  radius: {radius}')
            for f in obj.get('fills', []):
                s = _simplify_fill(f)
                if s:
                    lines.append(f'  fill: {s}')
            for b in obj.get('borders', []):
                s = _simplify_border(b)
                if s:
                    lines.append(f'  border: {s}')
            opacity = obj.get('opacity')
            if opacity is not None and opacity < 100:
                lines.append(f'  opacity: {opacity}%')
            for sh in obj.get('shadows', []):
                s = _simplify_shadow(sh)
                if s:
                    lines.append(f'  shadow: {s}')
            tokens.append('\n'.join(lines))
        for child in obj.get('layers', []):
            _walk(child, current_path)

    if sketch_data.get('artboard') and sketch_data['artboard'].get('layers'):
        for layer in sketch_data['artboard']['layers']:
            _walk(layer)
    elif sketch_data.get('info'):
        for item in sketch_data['info']:
            _walk(item)
            for value in item.values():
                if isinstance(value, dict):
                    _walk(value)
                elif isinstance(value, list):
                    for v in value:
                        if isinstance(v, dict):
                            _walk(v)

    if not tokens:
        return ""
    return '\n\n'.join(tokens)


def _oc_to_css(oc_code: str) -> str:
    """Convert Lanhu OC annotation panel code to CSS properties."""
    css = []
    m = re.search(r'CGRectMake\(([\d.]+),([\d.]+),([\d.]+),([\d.]+)\)', oc_code)
    if m:
        css.append(f"left:{m.group(1)}px;top:{m.group(2)}px;width:{m.group(3)}px;height:{m.group(4)}px")
    for pat in re.finditer(r'backgroundColor = \[UIColor colorWithRed:([\d]+)/255\.0 green:([\d]+)/255\.0 blue:([\d]+)/255\.0 alpha:([\d.]+)\]', oc_code):
        r, g, b, a = pat.group(1), pat.group(2), pat.group(3), pat.group(4)
        css.append(f"background-color:rgba({r},{g},{b},{a})")
    m = re.search(r'cornerRadius = ([\d.]+)', oc_code)
    if m:
        css.append(f"border-radius:{m.group(1)}px")
    shadow_color = re.search(r'shadowColor = \[UIColor colorWithRed:([\d]+)/255\.0 green:([\d]+)/255\.0 blue:([\d]+)/255\.0 alpha:([\d.]+)\]', oc_code)
    shadow_offset = re.search(r'shadowOffset = CGSizeMake\(([\d.-]+),([\d.-]+)\)', oc_code)
    shadow_radius = re.search(r'shadowRadius = ([\d.]+)', oc_code)
    if shadow_color and shadow_offset:
        sr, sg, sb, sa = shadow_color.group(1), shadow_color.group(2), shadow_color.group(3), shadow_color.group(4)
        sx, sy = shadow_offset.group(1), shadow_offset.group(2)
        blur = shadow_radius.group(1) if shadow_radius else '0'
        css.append(f"box-shadow:{sx}px {sy}px {blur}px rgba({sr},{sg},{sb},{sa})")
    border_w = re.search(r'borderWidth = ([\d.]+)', oc_code)
    border_c = re.search(r'borderColor = \[UIColor colorWithRed:([\d]+)/255\.0 green:([\d]+)/255\.0 blue:([\d]+)/255\.0 alpha:([\d.]+)\]', oc_code)
    if border_w and border_c:
        bw = border_w.group(1)
        br, bg, bb, ba = border_c.group(1), border_c.group(2), border_c.group(3), border_c.group(4)
        css.append(f"border:{bw}px solid rgba({br},{bg},{bb},{ba})")
    if 'fontWithName:@"' in oc_code:
        fm = re.search(r'fontWithName:@"([^"]+)" size: ([\d.]+)', oc_code)
        if fm:
            css.append(f"font-family:\"{fm.group(1)}\",sans-serif;font-size:{fm.group(2)}px")
    fc = re.search(r'ForegroundColorAttributeName: \[UIColor colorWithRed:([\d]+)/255\.0 green:([\d]+)/255\.0 blue:([\d]+)/255\.0 alpha:([\d.]+)\]', oc_code)
    if fc:
        css.append(f"color:rgba({fc.group(1)},{fc.group(2)},{fc.group(3)},{fc.group(4)})")
    return ';'.join(css)


def convert_sketch_to_html(sketch_data: dict, design_scale: float = 2.0,
                            design_img_url: str = "") -> tuple:
    """Convert Sketch/PSD JSON to HTML+CSS.
    Returns (html_string, image_url_mapping, layer_annotations).
    """
    import math as _math

    scale = design_scale or 2.0

    def px(v):
        if v is None:
            return 0
        return round(float(v) / scale * 10) / 10

    def color_css(c, opacity=100):
        if not c or not isinstance(c, dict):
            return None
        if 'value' in c:
            return c['value']
        r = round(c.get('red', c.get('r', 0)))
        g = round(c.get('green', c.get('g', 0)))
        b = round(c.get('blue', c.get('b', 0)))
        a = round(opacity / 100, 2) if opacity < 100 else 1
        return f"rgba({r},{g},{b},{a})" if a < 1 else f"rgb({r},{g},{b})"

    def get_opacity(layer):
        bo = layer.get('blendOptions') or {}
        if 'opacity' in bo:
            op = bo['opacity']
            return op.get('value', 100) if isinstance(op, dict) else op
        return 100

    def extract_border_radius(layer):
        path = layer.get('path') or {}
        comps = path.get('pathComponents') or []
        if not comps:
            return None
        origin = comps[0].get('origin') or {}
        radii = origin.get('radii')
        if not radii:
            return None
        r = [px(v) for v in radii]
        if len(set(r)) == 1 and r[0] > 0:
            return f"{r[0]}px"
        if any(v > 0 for v in r):
            return f"{r[0]}px {r[1]}px {r[2]}px {r[3]}px"
        return None

    def extract_shadow(effects):
        shadows = []
        for key in ('dropShadow', 'innerShadow'):
            fx = effects.get(key)
            if not fx or not fx.get('enabled'):
                continue
            c = fx.get('color') or {}
            color = color_css(c)
            if not color:
                continue
            op_obj = fx.get('opacity') or {}
            op_val = op_obj.get('value', 100) if isinstance(op_obj, dict) else 100
            if op_val < 100:
                r2 = round(c.get('red', c.get('r', 0)))
                g2 = round(c.get('green', c.get('g', 0)))
                b2 = round(c.get('blue', c.get('b', 0)))
                color = f"rgba({r2},{g2},{b2},{round(op_val/100, 2)})"
            angle_obj = fx.get('localLightingAngle') or {}
            angle_deg = angle_obj.get('value', 90) if isinstance(angle_obj, dict) else 90
            angle_rad = _math.radians(angle_deg)
            dist = px(fx.get('distance', 0))
            blur = px(fx.get('blur', 0))
            spread = px(fx.get('chokeMatte', 0))
            ox = round(-dist * _math.cos(angle_rad) * 10) / 10
            oy = round(dist * _math.sin(angle_rad) * 10) / 10
            inset = "inset " if key == 'innerShadow' else ""
            spread_str = f" {spread}px" if spread else ""
            shadows.append(f"{inset}{ox}px {oy}px {blur}px{spread_str} {color}")
        return ','.join(shadows) if shadows else None

    def extract_border(effects):
        stroke = effects.get('frameFX') or effects.get('solidFill')
        if not stroke or not stroke.get('enabled'):
            return None
        size = px(stroke.get('size', 1))
        c = stroke.get('color') or {}
        color = color_css(c)
        if color:
            return f"{size}px solid {color}"
        return None

    def parse_font_weight(style_name):
        if not style_name:
            return None
        m = re.search(r'(\d+)', style_name)
        return int(m.group(1)) if m else None

    layers_list = []
    board_w = 375
    board_h = 667

    if 'board' in sketch_data:
        board = sketch_data['board']
        board_w = px(board.get('width', 750))
        board_h = px(board.get('height', 1334))
        raw_layers = board.get('layers', [])

        def _flatten(layer):
            if not layer or not isinstance(layer, dict):
                return
            if layer.get('visible') is False:
                return
            w = layer.get('width', 0) or 0
            h = layer.get('height', 0) or 0
            if w == 0 and h == 0:
                for child in reversed(layer.get('layers', [])):
                    _flatten(child)
                return
            ltype = layer.get('type', '')
            if ltype == 'layerSection':
                images = layer.get('images') or {}
                if images.get('png_xxxhd') or images.get('svg'):
                    layers_list.append(layer)
                else:
                    for child in reversed(layer.get('layers', [])):
                        _flatten(child)
                return
            layers_list.append(layer)

        for l in reversed(raw_layers):
            _flatten(l)

    css_rules = []
    html_parts = []
    image_url_mapping = {}
    layer_annotations = []

    for idx, L in enumerate(layers_list):
        cls = f"el{idx + 1}"
        ltype = L.get('type', '')
        name = L.get('name', '')
        left = px(L.get('left', 0))
        top = px(L.get('top', 0))
        w = px(L.get('width', 0))
        h = px(L.get('height', 0))
        opacity = get_opacity(L)
        effects = L.get('layerEffects') or {}

        annot = {
            'name': name, 'type': ltype,
            'css': {'position': 'absolute', 'left': f'{left}px', 'top': f'{top}px',
                    'width': f'{w}px', 'height': f'{h}px'},
        }

        props = ["position:absolute", f"left:{left}px", f"top:{top}px",
                 f"width:{w}px", f"height:{h}px"]

        if opacity < 100:
            op_css = round(opacity / 100, 2)
            props.append(f"opacity:{op_css}")
            annot['css']['opacity'] = str(op_css)

        br = extract_border_radius(L)
        if br:
            props.extend([f"border-radius:{br}", "overflow:hidden"])
            annot['css']['border-radius'] = br

        shadow = extract_shadow(effects)
        if shadow:
            annot['css']['box-shadow'] = shadow

        border = extract_border(effects)
        if border:
            annot['css']['border'] = border

        text_content = ""
        is_slice = False
        slice_url = ""

        images = L.get('images') or {}
        if images.get('png_xxxhd') or images.get('svg'):
            is_slice = True
            slice_url = images.get('png_xxxhd') or images.get('svg')
            local_name = f"{name.replace('/', '_').replace(' ', '_')}.png"
            local_path = f"./assets/slices/{local_name}"
            image_url_mapping[local_path] = slice_url
            annot['slice_url'] = slice_url

        if ltype == 'textLayer' and L.get('textInfo'):
            ti = L['textInfo']
            text_content = ti.get('text', '')
            annot['text'] = text_content
            props.append('z-index:10')
            text_color = color_css(ti.get('color'), opacity)
            if text_color:
                props.append(f"color:{text_color}")
                annot['css']['color'] = text_color
            font_size = px(ti.get('size', 0))
            if font_size:
                props.append(f"font-size:{font_size}px")
                annot['css']['font-size'] = f'{font_size}px'
            font_name = ti.get('fontPostScriptName') or ti.get('fontName', '')
            if font_name:
                props.append(f'font-family:"{font_name}","PingFang SC","Microsoft YaHei","Hiragino Sans GB",sans-serif')
                annot['css']['font-family'] = font_name
            font_style_name = ti.get('fontStyleName', '')
            fw = parse_font_weight(font_style_name)
            if fw:
                props.append(f"font-weight:{fw}")
                annot['css']['font-weight'] = str(fw)
            elif font_style_name:
                annot['css']['font-weight'] = font_style_name
            if ti.get('bold') and not fw:
                props.append("font-weight:bold")
            if ti.get('italic'):
                props.append("font-style:italic")
            just = ti.get('justification', 'left')
            if just != 'left':
                props.append(f"text-align:{just}")
                annot['css']['text-align'] = just
            lines_list = [ln for ln in text_content.split('\r') if ln]
            line_count = max(len(lines_list), 1)
            if line_count > 1 and h > 0 and font_size > 0:
                lh = round(h / line_count * 10) / 10
                props.append(f"line-height:{lh}px")
            else:
                props.append("line-height:1")
            props.extend(["white-space:pre-wrap", "overflow:hidden", "word-break:break-all"])
        elif is_slice:
            props.append('z-index:5')
        else:
            fill = L.get('fill') or {}
            fill_color = color_css(fill.get('color'), opacity)
            if fill_color:
                annot['css']['background-color'] = fill_color

        css_rules.append(f".{cls}{{{';'.join(props)}}}")

        safe_name = (name or "").replace('"', '&quot;')
        css_data = '; '.join(f'{k}: {v}' for k, v in annot['css'].items())
        safe_css = css_data.replace('"', '&quot;')
        if text_content:
            safe_text = text_content.replace('<', '&lt;').replace('>', '&gt;').replace('\r', '\n')
            html_parts.append(f'<div class="{cls}" title="{safe_name}" data-css="{safe_css}">{safe_text}</div>')
        elif is_slice:
            html_parts.append(f'<img class="{cls}" title="{safe_name}" data-css="{safe_css}" src="{slice_url}" referrerpolicy="no-referrer" />')
        else:
            html_parts.append(f'<div class="{cls}" title="{safe_name}" data-css="{safe_css}"></div>')

        layer_annotations.append(annot)

    bg_style = (f';background:url({design_img_url}) no-repeat;background-size:{board_w}px {board_h}px'
                if design_img_url else '')
    html = (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">'
        f'<meta name="referrer" content="no-referrer">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1.0">'
        f'<title>Design</title><style>'
        f'*{{margin:0;padding:0;box-sizing:border-box}}img{{display:block}}'
        f'.design{{position:relative;width:{board_w}px;height:{board_h}px;overflow:hidden;margin:0 auto{bg_style}}}\n'
        + '\n'.join(css_rules)
        + '</style></head><body><div class="design">\n'
        + '\n'.join(html_parts)
        + '\n</div></body></html>'
    )

    return html, image_url_mapping, layer_annotations
