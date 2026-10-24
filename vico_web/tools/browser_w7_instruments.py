"""W7 design integration: real six-bank Worklet, layout identity, and targeted housing checks.

Physical Tesla, human audition, GPS road, device IMU and acoustics remain NOT_RUN.
Use an SHA-bound, non-overwriting output directory and actual Chrome/Edge binaries.
"""
import argparse,json,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import instrument, choose, garage, start, stats, stop

VIEWPORTS=((1440,900),(1280,600),(1010,1270),(390,844))
AUTO=('mercedes','muscle','maranello','precision','technical','heritage')
REFINED={'mercedes','maranello','precision','technical','heritage'}
EXTRA=('bmw','audi','vw','honda')

def inspect(page,width,height,style):
 page.set_viewport_size({'width':width,'height':height})
 page.wait_for_timeout(80)
 return page.evaluate("""()=> {
  const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}};
  const svg=document.getElementById('r4-svg'),stage=rect(svg),housing=rect(svg.querySelector('.r5-housing'));
  const reads=[...svg.querySelectorAll('.r5-unit,.r5-meta,.r5-caption')]
    .filter(e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden')
    .map(e=>({kind:e.getAttribute('class'),value:e.textContent,...rect(e)}));
  const outside=(p,b)=>p.x<b.x-1||p.right>b.right+1||p.y<b.y-1||p.bottom>b.bottom+1;
  // Audit load/redline captions, units, numerals, and complete scale labels
  // together, including previous lower-margin failures.
  const overlap=(p,q)=>Math.min(p.right,q.right)-Math.max(p.x,q.x)>1&&Math.min(p.bottom,q.bottom)-Math.max(p.y,q.y)>1;
  const meta=[...svg.querySelectorAll('.r5-meta,.r5-unit,.r5-caption,.r5-value,.r5-scale')]
    .filter(e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden')
    .map(e=>({label:e.id||e.textContent,...rect(e)}));
  const metadataCollisions=meta.flatMap((m,i)=>meta.slice(i+1).filter(n=>overlap(m,n)).map(n=>[m.label,n.label]));
  const stop=document.getElementById('stop'),s=rect(stop);
  const hit=document.elementFromPoint(s.x+s.width/2,s.y+s.height/2);
  return {viewport:[innerWidth,innerHeight],scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],
   style:document.documentElement.dataset.instrument,theme:document.documentElement.dataset.appearance,
   stage,housing,readoutCount:reads.length,
   offstage:reads.filter(e=>outside(e,stage)),
   belowHood:reads.filter(e=>e.bottom>housing.bottom+1),
   metadataCollisions,
   stop:{height:s.height,width:s.width,inView:s.y>=0&&s.bottom<=innerHeight,hit:hit===stop||stop.contains(hit)},
   ids:['speed','rpm','gear','load','redline-rpm'].every(id=>document.querySelectorAll('#'+id).length===1),
   numeric:['speed','gear'].map(id=>({id,text:document.getElementById(id).textContent,rect:rect(document.getElementById(id))})),
   glyphs:['speed','gear'].map(id=>{const e=document.getElementById(id),cs=getComputedStyle(e),ctx=document.createElement('canvas').getContext('2d');ctx.font=cs.fontWeight+' '+cs.fontSize+' '+cs.fontFamily;const m=ctx.measureText(e.textContent),t=e.getScreenCTM();return {id,height:(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent)*Math.hypot(t.c,t.d)}})
  };
 }""")

def main():
 ap=argparse.ArgumentParser()
 for flag in ['url','out','expected-sha','executable']:ap.add_argument('--'+flag,required=True,type=Path if flag=='out' else str)
 a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 receipt={'sha':a.expected_sha,'scope':'ACTUAL_BROWSER_WORKLET_AND_LAYOUT_NOT_DEVICE_OR_ACOUSTICS',
          'url':a.url,'checks':[],'screenshots':[],'errors':[],'failure':None}
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path=a.executable)
  ctx=browser.new_context(viewport={'width':1440,'height':900})
  page=ctx.new_page();instrument(page)
  page.on('pageerror',lambda e:receipt['errors'].append(str(e)))
  page.on('console',lambda e:receipt['errors'].append('console '+e.text) if e.type=='error' else None)
  page.on('response',lambda r:receipt['errors'].append('HTTP '+str(r.status)+' '+r.url) if r.status>=400 else None)
  try:
   page.goto(a.url,wait_until='networkidle')
   catalog=page.evaluate("async()=>await(await fetch('catalog.json')).json()")
   assert catalog['webCommit']==a.expected_sha and catalog['testOnly'] is False
   assert len(catalog['vehicles'])==6
   for i,expected in enumerate(AUTO):
    choose(page,i)
    assert page.locator('html').get_attribute('data-instrument')==expected
    page.locator('[data-scenario="cruise"]').click()
    start(page)
    first=stats(page,catalog['vehicles'][i]['bankSha256'])
    before=page.evaluate("""()=>{const d=JSON.parse(document.getElementById('diagnostics').textContent);
      return {runId:d.runId,bank:d.stats.bankIdentity.bankSha256,
      contexts:testContexts.length,nodes:testNodes.length,volume:document.getElementById('volume').value,gps:geo.calls}}""")
    for theme in ('cyber','minimal'):
     page.locator(f'[data-appearance-choice="{theme}"]').click()
     for width,height in VIEWPORTS:
      z=inspect(page,width,height,expected)
      if z['style']!=expected or z['theme']!=theme:raise AssertionError(z)
      assert z['ids'] and z['stop']['hit'] and z['stop']['inView'],z
      assert z['stop']['height']>=56 and z['stop']['width']>=144,z
      assert z['scroll'][0]<=width+1,z
      if width>height:assert z['scroll'][1]<=height+1,z
      assert not z['offstage'] and not z['metadataCollisions'],z
      # The 400×400 compact SVG is still a physical binnacle: its load, unit
      # and redline text must remain inside the hood, on phones as well.
      assert not z['belowHood'],z
      if (width,height)==(1280,600):
       assert z['glyphs'][0]['height']>=64 and z['glyphs'][1]['height']>=44,z
      file=f'{i:02d}-{expected}-{theme}-{width}x{height}.png'
      page.screenshot(path=str(a.out/file),full_page=False)
      receipt['screenshots'].append({'file':file,'geometry':z})
    page.set_viewport_size({'width':1440,'height':900})
    second=stats(page,catalog['vehicles'][i]['bankSha256'])
    after=page.evaluate("""()=>{const d=JSON.parse(document.getElementById('diagnostics').textContent);
      return {runId:d.runId,bank:d.stats.bankIdentity.bankSha256,
      contexts:testContexts.length,nodes:testNodes.length,volume:document.getElementById('volume').value,gps:geo.calls}}""")
    assert second['frames']>first['frames'] and before==after and second['hardClips']==0 and second['nonfinite']==0
    receipt['checks'].append({'vehicle':catalog['vehicles'][i]['id'],'profile':expected,'pass':True,'frames':[first['frames'],second['frames']]})
    stop(page);garage(page)
   # Additional preset geometry without inventing extra sound vehicles.
   choose(page,0);page.locator('[data-scenario="cruise"]').click();start(page)
   previous=stats(page)
   prior=page.evaluate("JSON.parse(document.getElementById('diagnostics').textContent).runId")
   for preset in EXTRA:
    page.locator('#display-style').select_option(preset)
    for theme in ('cyber','minimal'):
     page.locator(f'[data-appearance-choice="{theme}"]').click()
     z=inspect(page,1280,600,preset)
     assert z['ids'] and z['stop']['hit'] and not z['offstage'] and not z['metadataCollisions'] and not z['belowHood']
     assert z['style']==preset and z['glyphs'][0]['height']>=64
     file=f'preset-{preset}-{theme}-1280x600.png'
     page.screenshot(path=str(a.out/file))
     receipt['screenshots'].append({'file':file,'geometry':z})
    page.set_viewport_size({'width':1440,'height':900})
    current=stats(page)
    assert current['frames']>previous['frames']
    assert page.evaluate("JSON.parse(document.getElementById('diagnostics').textContent).runId")==prior
    previous=current
    receipt['checks'].append({'preset':preset,'pass':True,'frames':current['frames']})
   stop(page)
   assert not receipt['errors'],receipt['errors']
  except Exception:
   receipt['failure']=traceback.format_exc()
   try:page.screenshot(path=str(a.out/'failure.png'),full_page=False)
   except Exception as e:receipt['errors'].append('screenshot failed: '+str(e))
  receipt['browser']=browser.version
  (a.out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
  ctx.close();browser.close()
 if receipt['failure'] or receipt['errors'] or not all(c.get('pass') for c in receipt['checks']):
  raise AssertionError('W7 instrument review failed; check receipt.json')
 print(f'W7 real Worklet {len(receipt["checks"])} cases, {len(receipt["screenshots"])} screenshots PASS. Tesla/Device/Human NOT_RUN')
if __name__=='__main__':main()
