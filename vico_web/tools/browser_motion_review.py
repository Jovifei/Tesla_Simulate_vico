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
 // Native Chromium may emit real, empty motion packets concurrently with the
 // injected packet. Only injected packets reach the production listener in this
 // test; the production listener and its removal/ownership remain unchanged.
 const motionWrappers=new Map();
 window.addEventListener=(type,cb,...args)=>{
   if(type!=='devicemotion')return add(type,cb,...args);
   if(motionWrappers.has(cb))return;
   const proxy=event=>{if(event.__vicoInjectedMotion===true)cb.call(window,event)};
   motionWrappers.set(cb,proxy);motionProbe.subscriptions++;
   return add(type,proxy,...args);
 };
 window.removeEventListener=(type,cb,...args)=>{
   if(type!=='devicemotion')return remove(type,cb,...args);
   const proxy=motionWrappers.get(cb);if(!proxy)return;
   motionWrappers.delete(cb);motionProbe.subscriptions--;
   return remove(type,proxy,...args);
 };
 window.motionProbe.emit=(accel,includingGravity=null)=>{
   const e=new Event('devicemotion');
   Object.defineProperty(e,'__vicoInjectedMotion',{value:true});
   Object.defineProperty(e,'acceleration',{value:accel});
   Object.defineProperty(e,'accelerationIncludingGravity',{value:includingGravity});
   window.dispatchEvent(e);
 };
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
   for width,height in ((1280,600),(390,844)):
    page.set_viewport_size({'width':width,'height':height})
    bounds=page.evaluate("""()=>{const s=document.getElementById('settings').getBoundingClientRect(),a=document.getElementById('motion-start').getBoundingClientRect(),b=document.getElementById('motion-stop').getBoundingClientRect(),stop=document.getElementById('stop'),r=stop.getBoundingClientRect();return {startFullyVisible:a.y>=s.y-1&&a.bottom<=s.bottom+1&&a.x>=s.x-1&&a.right<=s.right+1,stopFullyVisible:b.y>=s.y-1&&b.bottom<=s.bottom+1,stopAccessible:r.y>=0&&r.bottom<=innerHeight&&r.width>=144&&r.height>=56&&(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===stop)}}""")
    assert all(bounds.values()),(width,height,bounds)
   page.set_viewport_size({'width':1280,'height':600})
   report['checks'].append({'case':'motion consent controls visible at landscape and portrait; emergency stop uncovered','pass':True})
   page.locator('#motion-start').click()
   page.wait_for_function('motionProbe.subscriptions===1')
   assert page.evaluate('motionProbe.consents===1&&geo.calls===0&&testContexts.length===0')
   page.evaluate('motionProbe.emit({x:-1.25,y:2.5,z:0})')
   assert page.locator('#motion-x').text_content()=='-1.25'
   assert page.locator('#motion-y').text_content()=='2.50'
   # A deliberately invalid sample MUST blank the reading; a subsequent fresh
   # injected packet must restore it before any asynchronous Worklet assertions.
   page.evaluate('motionProbe.emit({x:null,y:null,z:null})')
   assert page.locator('#motion-x').text_content()=='—'
   page.evaluate('motionProbe.emit({x:-1.25,y:2.5,z:0})')
   assert page.locator('#motion-x').text_content()=='-1.25'
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
   # Real Escape keyboard path closes the drawer from app.mjs rather than by
   # clicking settings-toggle. It must also release the motion observer.
   page.locator('#settings-toggle').click()
   page.locator('#motion-start').click()
   page.wait_for_function('motionProbe.subscriptions===1')
   page.keyboard.press('Escape')
   assert page.locator('#settings').is_hidden()
   assert page.evaluate('motionProbe.subscriptions===0')
   assert page.locator('#motion-x').text_content()=='—'
   report['checks'].append({'case':'Escape drawer close releases injected motion listener','pass':True})
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
