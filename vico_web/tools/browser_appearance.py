"""Native browser check that a live audio run survives appearance changes."""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_smoke import choose, instrument, start, stats, stop


def snapshot(page):
    return page.evaluate("""() => {
      const receipt = JSON.parse(document.getElementById('diagnostics').textContent);
      const node = testNodes.at(-1);
      return {
        appearance: document.documentElement.dataset.appearance,
        storedAppearance: localStorage.getItem('vico-web-appearance-v1'),
        route: location.hash,
        runId: receipt.runId,
        vehicle: receipt.vehicle,
        algorithm: receipt.algorithm,
        bankSha256: receipt.stats.bankIdentity.bankSha256,
        volume: document.getElementById('volume').value,
        contextCount: testContexts.length,
        contextState: testContexts.at(-1).state,
        workletCount: testNodes.length,
        frameCount: node.stats.frames,
        gpsRequests: geo.calls,
        playStatus: document.getElementById('play-status').textContent
      };
    }""")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--executable', required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    errors = []
    receipt = {'url': args.url, 'scope': 'HEADLESS_NATIVE_AUDIOWORKLET_NOT_PHYSICAL_OUTPUT', 'steps': [], 'failure': None}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=args.executable)
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()
        instrument(page)
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(args.url, wait_until='networkidle')
            choose(page)
            assert page.evaluate('testContexts.length===0&&geo.calls===0')
            start(page)
            stats(page)
            before = snapshot(page)
            assert before['appearance'] == 'cyber' and before['frameCount'] > 0
            receipt['steps'].append({'stage': 'before', **before})
            for appearance in ('minimal', 'cyber', 'minimal'):
                page.locator(f'[data-appearance-choice="{appearance}"]').click()
                page.wait_for_function('frames => testNodes.at(-1).stats.frames > frames', arg=before['frameCount'])
                after = snapshot(page)
                for field in ('route', 'runId', 'vehicle', 'algorithm', 'bankSha256', 'volume', 'contextCount', 'workletCount', 'gpsRequests'):
                    assert after[field] == before[field], (field, before[field], after[field])
                assert after['appearance'] == after['storedAppearance'] == appearance
                assert after['contextState'] == 'running' and after['playStatus'] == '正在播放'
                assert after['frameCount'] > before['frameCount']
                receipt['steps'].append({'stage': 'live-switch', **after})
                before = after
            stop(page)
            assert page.evaluate('testContexts.every(c=>c.state==="closed")')
            page.locator('#back-garage').click()
            page.locator('#garage').wait_for(state='visible')
            assert page.evaluate('document.documentElement.dataset.appearance==="minimal"')
            page.reload(wait_until='networkidle')
            assert page.evaluate('document.documentElement.dataset.appearance==="minimal"&&localStorage.getItem("vico-web-appearance-v1")==="minimal"')
            receipt['steps'].append({'stage': 'route-and-reload', 'appearance': 'minimal', 'route': page.evaluate('location.hash')})
            page.evaluate('localStorage.setItem("vico-web-appearance-v1", "invalid")')
            page.reload(wait_until='networkidle')
            assert page.evaluate('document.documentElement.dataset.appearance==="cyber"')
            receipt['steps'].append({'stage': 'invalid-storage', 'appearance': 'cyber'})
            assert not errors, errors
        except Exception as error:
            receipt['failure'] = f'{type(error).__name__}: {error}'
        receipt['browser'] = browser.version
        receipt['pageErrors'] = errors
        (args.out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
        context.close()
        browser.close()
    if receipt['failure']:
        raise AssertionError(receipt['failure'])
    print('Live appearance AudioWorklet continuity PASS')


if __name__ == '__main__':
    main()
