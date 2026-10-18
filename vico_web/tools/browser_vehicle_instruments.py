"""Six vehicle instrument identities and real Worklets; not device/acoustic acceptance."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import instrument, choose, garage, start, stats, stop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--executable', required=True)
    ap.add_argument('--expected-sha', required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    report = {'expectedSha': a.expected_sha, 'url': a.url, 'scope': 'REAL_BROWSER_VIRTUAL_DATA',
              'failure': None, 'checks': [], 'pageErrors': [], 'consoleErrors': [], 'httpErrors': [],
              'physicalTesla': 'NOT_RUN', 'humanAudition': 'NOT_EVALUATED'}
    profiles = ['classic', 'muscle', 'maranello', 'precision', 'technical', 'heritage']
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path=a.executable)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        instrument(page)
        page.on('pageerror', lambda e: report['pageErrors'].append(str(e)))
        page.on('console', lambda e: report['consoleErrors'].append(e.text) if e.type == 'error' else None)
        page.on('response', lambda r: report['httpErrors'].append({'url': r.url, 'status': r.status}) if r.status >= 400 else None)
        try:
            page.goto(a.url, wait_until='networkidle')
            catalog = page.evaluate("async()=>await(await fetch('catalog.json')).json()")
            assert catalog['webCommit'] == a.expected_sha and catalog['testOnly'] is False
            for i, profile in enumerate(profiles):
                choose(page, i)
                assert page.locator('html').get_attribute('data-instrument') == profile
                page.locator('[data-cluster-choice="touring"]').click()
                page.locator('[data-scenario="cruise"]').click()
                start(page)
                page.wait_for_function("()=>{try{return JSON.parse(document.getElementById('diagnostics').textContent).stats.speedKmh>10}catch{return false}}", timeout=15000)
                initial = stats(page)
                owner = page.evaluate("JSON.parse(document.getElementById('diagnostics').textContent).runId")
                counts = page.evaluate('[testContexts.length,testNodes.length]')
                volume = page.locator('#volume').input_value()
                screenshots = []
                for theme in ('cyber', 'minimal'):
                    page.locator(f'[data-appearance-choice="{theme}"]').click()
                    for width, height in ((1440, 900), (1280, 720), (1024, 600), (390, 844)):
                        page.set_viewport_size({'width': width, 'height': height})
                        page.wait_for_timeout(80)
                        layout = page.evaluate("""()=>{const panel=document.querySelector('.instrument').getBoundingClientRect();const b=document.getElementById('stop'),r=b.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight,panel:{height:panel.height,width:panel.width},stopVisible:r.y>=0&&r.bottom<=innerHeight&&r.width>=144&&r.height>=56&&(hit===b||b.contains(hit)),dials:[...document.querySelectorAll('.dial')].map(d=>{const r=d.getBoundingClientRect();return {width:r.width,height:r.height}})}}""")
                        assert layout['scrollWidth'] <= width + 1, layout
                        assert layout['stopVisible'], layout
                        if width > height:
                            assert layout['scrollHeight'] <= height + 1, layout
                        assert all(d['height'] > 40 for d in layout['dials']), layout
                        name = f'{profile}-{theme}-{width}x{height}.png'
                        page.screenshot(path=str(a.out / name))
                        screenshots.append({'file': name, 'layout': layout})
                page.set_viewport_size({'width': 1440, 'height': 900})
                page.locator('[data-cluster-choice="digital"]').click()
                page.locator('[data-cluster-choice="touring"]').click()
                final = stats(page)
                assert final['frames'] > initial['frames']
                assert final['bankIdentity'] == initial['bankIdentity']
                assert page.evaluate('[testContexts.length,testNodes.length]') == counts
                assert page.locator('#volume').input_value() == volume
                assert page.evaluate("JSON.parse(document.getElementById('diagnostics').textContent).runId") == owner
                assert final['nonfinite'] == 0 and final['hardClips'] == 0
                assert 0 < final['preClipPeak'] <= 0.8413951416451951
                report['checks'].append({'vehicle': catalog['vehicles'][i]['id'], 'profile': profile,
                                         'pass': True, 'initial': initial, 'final': final, 'screenshots': screenshots})
                stop(page)
                garage(page)
            assert not report['pageErrors'] and not report['consoleErrors'] and not report['httpErrors']
        except Exception as error:
            report['failure'] = f'{type(error).__name__}: {error}'
            page.screenshot(path=str(a.out / 'failure.png'))
        report['browser'] = browser.version
        (a.out / 'receipt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        context.close()
        browser.close()
    if report['failure']:
        raise AssertionError(report['failure'])
    print('6 vehicles x 2 themes x 4 viewports; real Worklet continuity PASS')


if __name__ == '__main__':
    main()
