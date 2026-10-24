"""Device-axis sensor UI with an actual Worklet; sensor packets are deliberately injected.
No physical Tesla/IMU, GPS, acoustics or human listening claim is made here.
"""
import argparse, json, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import instrument, choose, start, stats, stop

INIT = """(()=>{
 const add=window.addEventListener.bind(window),remove=window.removeEventListener.bind(window);
 window.motionProbe={consents:0,subscriptions:0,grant:'granted'};
 class FakeMotion {}
 FakeMotion.requestPermission=()=>{motionProbe.consents++;return Promise.resolve(motionProbe.grant)};
 Object.defineProperty(window,'DeviceMotionEvent',{value:FakeMotion,configurable:true});
 window.addEventListener=(type,cb,...args)=>{if(type==='devicemotion')motionProbe.subscriptions++;return add(type,cb,...args)};
 window.removeEventListener=(type,cb,...args)=>{if(type==='devicemotion')motionProbe.subscriptions--;return remove(type,cb,...args)};
 window.motionProbe.emit=(accel,includingGravity=null)=>{const e=new Event('devicemotion');Object.defineProperty(e,'acceleration',{value:accel});Object.defineProperty(e,'accelerationIncludingGravity',{value:includingGravity});window.dispatchEvent(e)};
})();"""

def main():
 ap=argparse.ArgumentParser()
 ap.add_argument('--url',required=True)
 ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--expected-sha',required=True)
 ap.add_argument('--executable',required=True)
 a=ap.parse_args()
 a.out.mkdir(parents=True,exist_ok=False)
 report={'scope':'INJECTED_DEVICE_MOTION_WITH_REAL_BROWSER_WORKLET','url':a.url,'sha':a.expected_sha,'checks':[],'errors':[],'failure':None,'physicalDevice':'NOT_RUN'}
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path=a.executable,headless=True)
  page=browser.new_page(viewport={'width':1280,'height':600})
  instrument(page)
  page.add_init_script(INIT)
  page.on('pageerror',lambda error:report['errors'].append(str(error)))
  page.on('console',lambda msg:report['errors'].append(msg.text) if msg.type=='error' else None)
  try:
   page.goto(a.url,wait_until='networkidle')
   catalog=page.evaluate("async()=>await(await fetch('catalog.json')).json()")
   assert catalog['webCommit']==a.expected_sha and not catalog['testOnly']
   choose(page)
   assert page.evaluate('testContexts.length===0&&geo.calls===0&&motionProbe.consents===0&&motionProbe.subscriptions===0')
   page.locator('#settings-toggle').click()
   page.locator('#motion-start').click()
   page.wait_for_function('motionProbe.subscriptions===1')
   assert page.evaluate('motionProbe.consents===1&&geo.calls===0&&testContexts.length===0')
   page.evaluate('motionProbe.emit({x:-1.25,y:2.5,z:0})')
   assert page.locator('#motion-x').text_content()=='-1.25'
   assert page.locator('#motion-y').text_content()=='2.50'
   report['checks'].append({'case':'explicit consent, three axes and no audio/GPS side effects','pass':True})
   # Settings drawer overlays toolbar: dispatch ordinary element events while the drawer is open.
   page.evaluate("""()=>{
     document.querySelector('[data-appearance-choice="minimal"]').click();
     document.querySelector('[data-cluster-choice="digital"]').click();
     const s=document.getElementById('display-style');s.value='bmw';s.dispatchEvent(new Event('change',{bubbles:true}));
   }""")
   page.wait_for_timeout(100)
   assert page.evaluate('motionProbe.subscriptions===1&&motionProbe.consents===1')
   report['checks'].append({'case':'theme, layout, display style preserve sensor ownership','pass':True})
   page.locator('#settings-toggle').click()
   assert page.evaluate('motionProbe.subscriptions===0')
   assert page.locator('#motion-x').text_content()=='—'
   report['checks'].append({'case':'closing settings clears readings and removes listener','pass':True})
   page.locator('[data-scenario="cruise"]').click()
   start(page)
   first=stats(page)
   page.locator('#settings-toggle').click()
   page.locator('#motion-start').click()
   page.wait_for_function('motionProbe.subscriptions===1')
   page.evaluate('motionProbe.emit({x:0.25,y:0,z:-3})')
   assert page.locator('#motion-z').text_content()=='-3.00'
   later=stats(page)
   assert later['frames']>first['frames'] and later['bankIdentity']==first['bankIdentity']
   assert page.evaluate('testContexts.length===1&&testNodes.length===1&&geo.calls===0')
   report['checks'].append({'case':'actual Worklet frames continue while monitoring motion','pass':True,'frames':[first['frames'],later['frames']]})
   rect=page.evaluate("""()=>{const b=document.getElementById('stop'),r=b.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {w:r.width,h:r.height,visible:r.y>=0&&r.bottom<=innerHeight,hit:hit===b||b.contains(hit)}}""")
   assert rect['w']>=144 and rect['h']>=56 and rect['visible'] and rect['hit']
   page.screenshot(path=str(a.out/'motion-settings-1280x600.png'),full_page=False)
   stop(page)
   assert page.evaluate("motionProbe.subscriptions===0&&testContexts.every(c=>c.state==='closed')")
   report['checks'].append({'case':'immediate stop remains clickable and cancels sensor listener','pass':True})
   assert not report['errors']
  except Exception:
   report['failure']=traceback.format_exc()
   try: page.screenshot(path=str(a.out/'failure.png'),full_page=False)
   except Exception as e: report['errors'].append('Failed to capture failure screenshot: '+str(e))
  report['browser']=browser.version
  (a.out/'receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
  browser.close()
 if report['failure'] or report['errors'] or any(c.get('pass') is not True for c in report['checks']):
  raise AssertionError('Device-motion browser test failed; see receipt.json')
 print('Device-axis UI with real browser Worklet PASS (injected sensor data; physical NOT_RUN)')
if __name__=='__main__':main()
