"""Headless playback-readiness check of the published static review pages."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[2]
package = Path('E:/Tesla_speed/review_packages/s12-stage-y-hellcat-layers-v1')
out = root / 'tasks/reports/runtime/s12-stage-y/y6_audition'
started = datetime.now(timezone.utc).isoformat()
results = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    try:
        for name in ('timbre_review.html', 'dynamic_review.html'):
            page = browser.new_page()
            page.goto((package / name).as_uri(), wait_until='load')
            page.wait_for_function("""() => { const a=[...document.querySelectorAll('audio')]; return a.length===77 && a.every(x=>x.readyState>=1 && Number.isFinite(x.duration) && x.duration>0 && !x.error); }""", timeout=90000)
            durations = page.locator('audio').evaluate_all('(nodes)=>nodes.map(x=>x.duration)')
            playback = page.evaluate("""async () => {
              const nodes=[...document.querySelectorAll('audio')];
              const result=[];
              for (const index of [0,5,6]) {
                const a=nodes[index]; a.muted=true; await a.play();
                await new Promise((resolve,reject)=>{
                  const timer=setTimeout(()=>reject(new Error('playback timeout')),5000);
                  a.addEventListener('timeupdate',()=>{clearTimeout(timer);resolve();},{once:true});
                });
                result.push({index,time:a.currentTime,error:a.error?.code ?? null}); a.pause();
              }
              return result;
            }""")
            assert all(row['time'] > 0 and row['error'] is None for row in playback)
            results.append({'page':name,'audio_count':len(durations),'min_duration':min(durations),'max_duration':max(durations),'playback':playback})
            page.close()
    finally:
        browser.close()
record = {'status':'PASS','command':'python .superpowers/sdd/check_y6_browser.py','started_at':started,'ended_at':datetime.now(timezone.utc).isoformat(),'package_manifest_sha256':hashlib.sha256((package/'package_manifest.json').read_bytes()).hexdigest(),'pages':results,'scope':'browser decoding/playback only; no human auditory acceptance'}
out.mkdir(parents=True, exist_ok=True)
(out/'browser_playback_receipt.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
