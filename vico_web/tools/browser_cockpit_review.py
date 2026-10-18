"""Focused actual-browser R2 acceptance; never substitutes a DOM mock for audio.
Run against a SHA-bound locally built release or the published HTTPS origin.
Uses the already-installed Playwright/browser; never installs or weakens policy.
"""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import choose, instrument, start, stats, stop, mode


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--expected-sha', required=True)
    p.add_argument('--executable')
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    report = {'scope': 'ACTUAL_BROWSER_NOT_DEVICE_OR_ACOUSTIC', 'expectedSha': a.expected_sha,
              'url': a.url, 'checks': [], 'failure': None, 'screenshots': [], 'physical': 'NOT_RUN'}
    errors = []
    with sync_playwright() as pw:
        opts = {'headless': True}
        if a.executable:
            opts['executable_path'] = a.executable
        browser = pw.chromium.launch(**opts)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        instrument(page)
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(a.url, wait_until='networkidle')
            catalog = page.evaluate("async()=>await(await fetch('catalog.json')).json()")
            assert catalog['webCommit'] == a.expected_sha and catalog['testOnly'] is False
            assert page.evaluate('testContexts.length===0&&geo.calls===0')
            choose(page)
            page.locator('[data-scenario="cruise"]').click()
            start(page)
            baseline = stats(page)
            identity = page.evaluate("()=>({run:JSON.parse(document.getElementById('diagnostics').textContent).runId,contexts:testContexts.length,nodes:testNodes.length,volume:document.getElementById('volume').value})")
            for theme in ('cyber', 'minimal'):
                page.locator(f'[data-appearance-choice="{theme}"]').click()
                for layout in ('touring', 'digital'):
                    page.locator(f'[data-cluster-choice="{layout}"]').click()
                    fresh = stats(page)
                    now = page.evaluate("()=>({run:JSON.parse(document.getElementById('diagnostics').textContent).runId,contexts:testContexts.length,nodes:testNodes.length,volume:document.getElementById('volume').value})")
                    assert now == identity and fresh['frames'] > baseline['frames']
                    assert fresh['bankIdentity'] == baseline['bankIdentity']
                    baseline = fresh
                    for width, height in ((1440, 900), (1280, 600), (1024, 600), (390, 844)):
                        page.set_viewport_size({'width': width, 'height': height})
                        page.wait_for_timeout(120)
                        rect = page.evaluate("""()=>{const e=document.getElementById('stop'),r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {width:innerWidth,height:innerHeight,scrollW:document.documentElement.scrollWidth,scrollH:document.documentElement.scrollHeight,stopVisible:r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight,stopHit:e===hit||e.contains(hit),stopW:r.width,stopH:r.height,appearance:document.documentElement.dataset.appearance,cluster:document.documentElement.dataset.cluster}}""")
                        assert rect['scrollW'] <= width + 1 and (height > width or rect['scrollH'] <= height + 1)
                        assert rect['stopVisible'] and rect['stopHit'] and rect['stopW'] >= 144 and rect['stopH'] >= 56
                        assert rect['appearance'] == theme and rect['cluster'] == layout
                        image = f'{theme}-{layout}-{width}x{height}.png'
                        page.screenshot(path=str(a.out / image), full_page=False)
                        report['screenshots'].append({'file': image, **rect})
                    page.set_viewport_size({'width': 1440, 'height': 900})
            report['checks'].append({'case': '2 themes x 2 layouts x 4 viewports; unchanged live owner', 'pass': True})
            page.evaluate("document.documentElement.requestFullscreen=()=>Promise.reject(new DOMException('Test rejection','NotAllowedError'))")
            if page.locator('#fullscreen').is_visible():
                page.locator('#fullscreen').click()
                page.wait_for_function("()=>document.getElementById('message').textContent.includes('不允许全屏')")
                assert stats(page)['frames'] > baseline['frames']
                report['checks'].append({'case': 'injected fullscreen rejection is contained', 'pass': True})
            else:
                report['checks'].append({'case': 'fullscreen', 'status': 'NOT_SUPPORTED', 'pass': False})
            page.locator('#pedal').focus()
            page.keyboard.down('Space')
            assert page.locator('#pedal').get_attribute('aria-pressed') == 'true'
            page.locator('#settings-toggle').focus()
            page.keyboard.up('Space')
            assert page.locator('#pedal').get_attribute('aria-pressed') == 'false'
            assert 'active' in page.locator('[data-scenario="decel"]').get_attribute('class')
            report['checks'].append({'case': 'actual keyboard focus loss releases pedal', 'pass': True})
            stop(page)
            mode(page, 'gps')
            assert page.evaluate('geo.calls===0')
            page.locator('#gps').click()
            page.evaluate('geo.fail({code:1})')
            start(page)
            assert stats(page)['inputUsable'] is False
            for id_ in ('speed', 'rpm', 'gear', 'load'):
                assert page.locator('#' + id_).text_content() == '—'
            assert page.locator('#speed-arc').get_attribute('stroke-dashoffset') == '100'
            report['checks'].append({'case': 'injected GPS invalidates all current instruments', 'pass': True})
            stop(page)
            assert page.evaluate("testContexts.every(c=>c.state==='closed')")
            assert not errors
        except Exception as e:
            report['failure'] = f'{type(e).__name__}: {e}'
            page.screenshot(path=str(a.out / 'failure.png'))
        report['browser'] = browser.version
        report['pageErrors'] = errors
        (a.out / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf8')
        context.close()
        browser.close()
    if report['failure']:
        raise AssertionError(report['failure'])
    print('Cockpit browser acceptance completed; inspect unsupported checks; physical listening NOT_RUN')


if __name__ == '__main__':
    main()
