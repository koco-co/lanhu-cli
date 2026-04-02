"""Members API — resolve invite links and get project members."""

from __future__ import annotations


async def resolve_invite_link(invite_url: str) -> dict:
    """Resolve a Lanhu invite/share link to actual project URL using Playwright."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {'status': 'error', 'message': 'playwright not installed. Run: playwright install chromium'}

    import asyncio
    from lanhu_cli.config import COOKIE

    resolved_url = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        for cookie_item in _parse_cookies(COOKIE):
            await context.add_cookies([{
                'name': cookie_item['name'],
                'value': cookie_item['value'],
                'domain': '.lanhuapp.com',
                'path': '/',
            }])

        page = await context.new_page()

        async def capture(response):
            nonlocal resolved_url
            if 'lanhuapp.com/web/#/item/project' in response.url:
                resolved_url = response.url

        page.on('response', lambda r: asyncio.ensure_future(capture(r)))

        try:
            await page.goto(invite_url, wait_until='networkidle', timeout=15000)
            await page.wait_for_timeout(2000)
            resolved_url = resolved_url or page.url
        except Exception as e:
            pass
        finally:
            await browser.close()

    if not resolved_url or 'invite' in resolved_url:
        resolved_url = page.url if resolved_url is None else resolved_url

    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(resolved_url.replace('#', '?', 1) if '#/item' in resolved_url else resolved_url)
    qs = parse_qs(parsed.query)

    result = {
        'status': 'success',
        'resolved_url': resolved_url,
        'tid': qs.get('tid', [None])[0],
        'pid': qs.get('pid', [None])[0],
        'doc_id': qs.get('docId', [None])[0],
    }
    return result


def _parse_cookies(cookie_str: str) -> list:
    cookies = []
    for part in cookie_str.split(';'):
        part = part.strip()
        if '=' in part:
            name, _, value = part.partition('=')
            cookies.append({'name': name.strip(), 'value': value.strip()})
    return cookies
