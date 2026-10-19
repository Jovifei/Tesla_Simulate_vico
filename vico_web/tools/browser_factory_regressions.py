"""R4 negative-path/geometry regression. Injected display values are NOT audio evidence."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import instrument,choose,mode


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--url',required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--expected-sha',required=True);ap.add_argument('--executable',required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 report={'sha':a.expected_sha,'scope':'DISPLAY_GEOMETRY_INJECTION_AND_GPS_NO_AUTH_NOT_AUDIO','checks':[],'errors':[]}
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True,executable_path=a.executable);p=b.new_page(viewport={'width':1440,'height':900});instrument(p);p.on('pageerror',lambda e:report['errors'].append(str(e)))
  p.goto(a.url,wait_until='networkidle');catalog=p.evaluate("async()=>await(await fetch('catalog.json')).json()");assert catalog['webCommit']==a.expected_sha and catalog['testOnly'] is False
  choose(p,0);mode(p,'gps');assert p.locator('#speed').text_content()=='—';p.select_option('#display-style','honda')
  actual=p.locator('#speed').text_content();ok=actual=='—' and p.evaluate('geo.calls===0&&testContexts.length===0')
  report['checks'].append({'case':'never-authorized GPS unknown speed survives style change','pass':ok,'actual':actual});p.screenshot(path=str(a.out/'gps-style.png'))
  p.locator('[data-cluster-choice="digital"]').click();actual=p.locator('#speed').text_content();report['checks'].append({'case':'never-authorized GPS unknown survives layout change','pass':actual=='—','actual':actual})
  p.reload(wait_until='networkidle');p.locator('#drive').wait_for(state='visible');p.locator('[data-cluster-choice="touring"]').click()
  ids=catalog['vehicles'];cases=[(i,'auto') for i in range(6)]+[(0,s) for s in ('mercedes','bmw','audi','vw','honda')]
  for i,style in cases:
   p.goto(a.url+'#/drive/'+ids[i]['id'],wait_until='networkidle');p.locator('#drive').wait_for(state='visible');p.select_option('#display-style',style)
   for theme in ('cyber','minimal'):
    p.locator(f'[data-appearance-choice="{theme}"]').click()
    for layout in ('touring','digital'):
     p.locator(f'[data-cluster-choice="{layout}"]').click()
     for w,h in ((1440,900),(1280,600),(1010,1270)):
      p.set_viewport_size({'width':w,'height':h})
      p.evaluate("()=>window.VicoFactory.update(Object.freeze({inputUsable:true,source:'DEMO',speedKmh:144,rpm:7200,gear:8,load:1}),true)")
      result=p.evaluate("""()=>{const rect=e=>{let r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom}}, overlap=(a,b)=>Math.min(a.right,b.right)-Math.max(a.x,b.x)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>1,visible=e=>getComputedStyle(e).display!=='none'&&getComputedStyle(e).visibility!=='hidden',fields=[...document.querySelectorAll('.r4-field .r4-number')].map(e=>({id:e.id,...rect(e)})),captions=[...document.querySelectorAll('.r4-field .r4-micro')].filter(visible).map(e=>({text:e.textContent,...rect(e)})),ticks=[...document.querySelectorAll('.r4-tick-label')].filter(visible).map(e=>({text:e.textContent,...rect(e)})),plates=[...document.querySelectorAll('.r4-value-plate')].filter(visible).map(rect),hubs=[...document.querySelectorAll('.r4-hub')].filter(visible).map(rect);return {captionOverlap:captions.flatMap(c=>fields.filter(f=>overlap(c,f)).map(f=>({caption:c.text,value:f.id}))),tickOverlap:ticks.filter(t=>[...fields,...captions,...plates].some(f=>overlap(t,f))).map(t=>t.text),coveredHubs:hubs.filter(h=>fields.some(f=>overlap(h,f))).length}}""")
      ok=not result['captionOverlap'] and not result['tickOverlap'] and not result['coveredHubs']
      report['checks'].append({'case':'readouts do not obscure scale, subtitles or mechanical hubs','vehicle':ids[i]['id'],'style':style,'theme':theme,'layout':layout,'viewport':[w,h],'pass':ok,'result':result})
      if not ok:p.screenshot(path=str(a.out/f'overlap-{i}-{style}-{theme}-{layout}-{w}x{h}.png'))
  assert p.evaluate('geo.calls===0&&testContexts.length===0')
  report['browser']=b.version;b.close()
 (a.out/'receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 failed=sum(not c['pass'] for c in report['checks']);print(json.dumps({'checks':len(report['checks']),'failed':failed,'errors':report['errors']}));raise SystemExit(1 if failed or report['errors'] else 0)
if __name__=='__main__':main()
