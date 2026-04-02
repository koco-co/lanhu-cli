"""Playwright-based screenshot helper for Lanhu Axure pages."""

from __future__ import annotations

import base64
import json
import re
import time
import threading
import http.server
import socketserver
import random
from pathlib import Path
from typing import List

from lanhu_cli.config import VIEWPORT_WIDTH, VIEWPORT_HEIGHT


async def screenshot_page_internal(resource_dir: str, page_names: List[str],
                                   output_dir: str, return_base64: bool = True,
                                   version_id: str = None) -> List[dict]:
    """Screenshot Axure pages using Playwright with smart caching."""
    from playwright.async_api import async_playwright

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cache_meta_path = output_path / ".screenshot_cache.json"
    cache_meta = {}
    if cache_meta_path.exists():
        try:
            cache_meta = json.loads(cache_meta_path.read_text(encoding='utf-8'))
        except Exception:
            cache_meta = {}

    cached_version = cache_meta.get('version_id')
    pages_to_render = []
    cached_results = []

    for page_name in page_names:
        safe_name = re.sub(r'[^\w\s-]', '_', page_name)
        screenshot_file = output_path / f"{safe_name}.png"
        text_file = output_path / f"{safe_name}.txt"
        styles_file = output_path / f"{safe_name}_styles.json"

        if (version_id and cached_version == version_id and screenshot_file.exists()):
            page_text = ""
            if text_file.exists():
                try:
                    page_text = text_file.read_text(encoding='utf-8')
                except Exception:
                    page_text = "(Cached - text not available)"
            page_design_info = None
            if styles_file.exists():
                try:
                    page_design_info = json.loads(styles_file.read_text(encoding='utf-8'))
                except Exception:
                    pass
            cached_results.append({
                'page_name': page_name,
                'success': True,
                'screenshot_path': str(screenshot_file),
                'page_text': page_text or "(Cached result)",
                'page_design_info': page_design_info,
                'size': f"{screenshot_file.stat().st_size / 1024:.1f}KB",
                'from_cache': True,
            })
        else:
            pages_to_render.append(page_name)

    results = list(cached_results)

    if not pages_to_render:
        return results

    port = random.randint(8800, 8900)
    abs_dir = str(Path(resource_dir).resolve())
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=abs_dir, **kwargs
    )
    httpd = socketserver.TCPServer(("", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={'width': VIEWPORT_WIDTH, 'height': VIEWPORT_HEIGHT}
        )

        for page_name in pages_to_render:
            try:
                html_file = None
                for f in Path(resource_dir).glob("*.html"):
                    if f.stem == page_name:
                        html_file = f.name
                        break

                if not html_file:
                    results.append({
                        'page_name': page_name,
                        'success': False,
                        'error': f'Page {page_name} does not exist',
                    })
                    continue

                url = f"http://localhost:{port}/{html_file}"
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await page.wait_for_timeout(2000)

                page_text = await page.evaluate('''() => {
                    let sections = [];
                    const redTexts = Array.from(document.querySelectorAll('*')).filter(el => {
                        const style = window.getComputedStyle(el);
                        const color = style.color;
                        return color && (color.includes('rgb(255, 0, 0)') || color.includes('rgb(255,0,0)') || color === 'red');
                    });
                    if (redTexts.length > 0) {
                        const redContent = redTexts.map(el => el.textContent.trim())
                            .filter(t => t.length > 0 && t.length < 200)
                            .filter((v, i, a) => a.indexOf(v) === i);
                        if (redContent.length > 0) sections.push("[Important Tips/Warnings]\\n" + redContent.join("\\n"));
                    }
                    const axureShapes = document.querySelectorAll('[id^="u"], .ax_shape, .shape, [class*="shape"]');
                    const shapeTexts = [];
                    axureShapes.forEach(el => {
                        const text = el.textContent.trim();
                        if (text && text.length > 0 && text.length < 100) shapeTexts.push(text);
                    });
                    if (shapeTexts.length > 5) {
                        const uniqueShapes = [...new Set(shapeTexts)];
                        sections.push("[Flowchart/Component Text]\\n" + uniqueShapes.slice(0, 20).join(" | "));
                    }
                    const bodyText = document.body.innerText || '';
                    if (bodyText.trim()) sections.push("[Full Page Text]\\n" + bodyText.trim());
                    if (sections.length === 0) return "⚠️ Page text is empty or cannot be extracted";
                    return sections.join("\\n\\n");
                }''')

                page_design_info = await page.evaluate('''() => {
                    const allEls = document.querySelectorAll('*');
                    const textColors = {}, bgColors = {}, fontSpecs = {}, images = [];
                    allEls.forEach(el => {
                        const cs = window.getComputedStyle(el);
                        if (cs.display === 'none' || cs.visibility === 'hidden') return;
                        const rect = el.getBoundingClientRect();
                        if (rect.width < 1 || rect.height < 1) return;
                        const hasDirectText = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim().length > 0);
                        if (hasDirectText) {
                            const color = cs.color;
                            if (color) textColors[color] = (textColors[color] || 0) + 1;
                            const key = cs.fontSize + '|' + cs.fontWeight + '|' + color;
                            fontSpecs[key] = (fontSpecs[key] || 0) + 1;
                        }
                        const bg = cs.backgroundColor;
                        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') bgColors[bg] = (bgColors[bg] || 0) + 1;
                        const bgImg = cs.backgroundImage;
                        if (bgImg && bgImg !== 'none') {
                            const m = bgImg.match(/url\\("?([^"\\)]*)"?\\)/);
                            if (m && !m[1].startsWith('data:')) images.push({ src: m[1], type: 'bg', w: Math.round(rect.width), h: Math.round(rect.height) });
                        }
                    });
                    document.querySelectorAll('img').forEach(img => {
                        if (img.src && img.naturalWidth > 0 && !img.src.startsWith('data:')) images.push({ src: img.src, type: 'img', w: img.naturalWidth, h: img.naturalHeight });
                    });
                    const sortObj = o => Object.entries(o).sort((a, b) => b[1] - a[1]);
                    return { textColors: sortObj(textColors).slice(0, 15), bgColors: sortObj(bgColors).slice(0, 10), fontSpecs: sortObj(fontSpecs).slice(0, 15), images: images.slice(0, 30) };
                }''')

                safe_name = re.sub(r'[^\w\s-]', '_', page_name)
                screenshot_path = output_path / f"{safe_name}.png"
                text_path = output_path / f"{safe_name}.txt"
                styles_path = output_path / f"{safe_name}_styles.json"

                screenshot_bytes = await page.screenshot(full_page=True)
                screenshot_path.write_bytes(screenshot_bytes)
                try:
                    text_path.write_text(page_text, encoding='utf-8')
                except Exception:
                    pass
                try:
                    styles_path.write_text(
                        json.dumps(page_design_info, ensure_ascii=False), encoding='utf-8'
                    )
                except Exception:
                    pass

                result = {
                    'page_name': page_name,
                    'success': True,
                    'screenshot_path': str(screenshot_path),
                    'page_text': page_text,
                    'page_design_info': page_design_info,
                    'size': f"{len(screenshot_bytes) / 1024:.1f}KB",
                    'from_cache': False,
                }
                if return_base64:
                    result['base64'] = base64.b64encode(screenshot_bytes).decode('utf-8')
                    result['mime_type'] = 'image/png'
                results.append(result)
            except Exception as e:
                results.append({'page_name': page_name, 'success': False, 'error': str(e)})

        await browser.close()

    httpd.shutdown()
    httpd.server_close()

    if version_id:
        cache_meta['version_id'] = version_id
        cache_meta['cached_pages'] = page_names
        try:
            cache_meta_path.write_text(
                json.dumps(cache_meta, ensure_ascii=False, indent=2), encoding='utf-8'
            )
        except Exception:
            pass

    return results
