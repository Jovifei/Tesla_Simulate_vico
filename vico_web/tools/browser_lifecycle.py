"""Browser lifecycle integration tests. Instrumentation never replaces the worklet/core."""
import argparse,json,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import instrument,choose,garage,mode

p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--executable',required=True);a=p.parse_args();a.out.mkdir(exist_ok=False)
results=[]
with sync_playwright() as pw:
 b=pw.chromium.launch(executable_path=a.executable,headless=True)
 for rate in [44100,48000,96000]:
  c=b.new_context();page=c.new_page();errors=[];requests=[]
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append({'url':r.url,'method':r.method,'body':r.post_data}))
  instrument(page,rate)
  page.goto(a.url);page.locator('.vehicle-card').first.wait_for()
  def status(value):page.wait_for_function('(value)=>document.getElementById("play-status").textContent===value',arg=value,timeout=30000)
  def stats():
   page.wait_for_timeout(600)
   return json.loads(page.locator('#diagnostics').text_content())
  def start():page.locator('#start').click();status('正在播放')
  def stop():page.locator('#stop').click();status('尚未启动')
  try:
   choose(page);assert page.evaluate('testContexts.length===0&&geo.calls===0')
   page.locator('[data-scenario="launch"]').click();start();s=stats();assert s['contextSampleRate']==rate and s['frames']>0 and s['nonfinite']==0
   results.append({'rate':rate,'test':'actual worklet requested output rate','status':'PASS','stats':s})
   garage(page);choose(page,4);assert page.evaluate("testContexts.every(c=>c.state==='closed')&&geo.calls===0");garage(page);choose(page)
   start();page.evaluate('testContexts.at(-1).suspend()');status('已停止 / 异常');assert page.evaluate("testContexts.every(c=>c.state==='closed')")
   start();page.evaluate("window.dispatchEvent(new Event('pagehide'))");status('尚未启动')
   start();page.evaluate("Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))");status('尚未启动');page.evaluate("delete document.hidden;document.dispatchEvent(new Event('visibilitychange'))");page.wait_for_timeout(300);status('尚未启动');assert page.evaluate("testContexts.every(c=>c.state==='closed')")
   results.append({'rate':rate,'test':'context suspend pagehide and hidden stop','status':'PASS','note':'pagehide and hidden events injected; physical OS visibility transition NOT_RUN'})
   # A late pedal release must not mutate the new input mode.
   page.locator('#pedal').dispatch_event('keydown',{'code':'Space'});mode(page,'manual');page.locator('#pedal').dispatch_event('keyup',{'code':'Space'});page.locator('#target').fill('80');page.locator('#target').dispatch_event('input');start();assert stats()['source']=='MANUAL';stop()
   mode(page,'demo');r=page.locator('#pedal').bounding_box();page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);page.mouse.down();page.locator('#mode-gps').dispatch_event('click');status('尚未启动');page.mouse.up();page.locator('#pedal').dispatch_event('pointerup',{'pointerId':1});assert page.locator('#mode-gps').get_attribute('aria-pressed')=='true'
   assert page.evaluate('geo.calls===0');page.locator('#gps').click();page.evaluate('geo.fail({code:1})');invalid_speed=page.locator('#speed').text_content();results.append({'rate':rate,'test':'GPS invalid before start clears speed','status':'PASS' if invalid_speed=='—' else 'FAIL','speed':invalid_speed});start();assert stats()['inputUsable']==False
   page.evaluate('geo.ok({coords:{speed:null,latitude:12.345,longitude:67.891},timestamp:Date.now()})');assert stats()['inputUsable']==False
   page.evaluate('geo.ok({coords:{speed:20,latitude:12.345,longitude:67.891},timestamp:Date.now()-5000})');assert stats()['inputUsable']==False
   page.evaluate('geo.ok({coords:{speed:20,latitude:12.345,longitude:67.891},timestamp:Date.now()})');assert stats()['inputUsable']==True
   page.wait_for_timeout(2500);assert stats()['inputUsable']==False;assert page.locator('#speed').text_content()=='—';stop()
   results.append({'rate':rate,'test':'GPS reject null stale valid freshness expiry','status':'PASS','note':'injected geolocation callbacks; no real permission/device claim'})
   delayed=[]
   def hold(route):delayed.append(route)
   mode(page,'manual');page.route('**/bank.json',hold);page.locator('#start').click();status('资源校验中');page.locator('#target').fill('80');page.locator('#target').dispatch_event('input')
   page.wait_for_timeout(200)
   for r in delayed:r.continue_()
   page.unroute('**/bank.json',hold);status('正在播放');s=stats();assert s['inputUsable'] and s['source']=='MANUAL' and s['speedKmh']>0;stop()
   delayed.clear();page.route('**/bank.json',hold);page.locator('#start').click();page.wait_for_timeout(100);page.locator('#stop').click();status('尚未启动')
   for r in delayed:r.abort()
   page.unroute('**/bank.json',hold);page.wait_for_timeout(600);status('尚未启动')
   results.append({'rate':rate,'test':'loading manual update and rapid cancel','status':'PASS','stats':s})
   delayed.clear();page.route('**/bank.json',hold);page.locator('#start').click();status('资源校验中');page.wait_for_timeout(100);page.go_back();page.locator('#garage').wait_for(state='visible');choose(page,4)
   for r in delayed:r.continue_()
   page.unroute('**/bank.json',hold);page.wait_for_timeout(600);status('尚未启动');assert page.evaluate("testContexts.every(c=>c.state==='closed')")
   start();page.locator('#settings-toggle').click();page.locator('#stop').click();status('尚未启动');page.locator('#settings-toggle').click()
   results.append({'rate':rate,'test':'loading browser back other car and settings emergency stop','status':'PASS'})
   def corrupt(route):route.fulfill(status=200,content_type='application/json',body='{}')
   page.route('**/bank.json',corrupt);page.locator('#start').click();status('已停止 / 异常');assert 'SHA-256' in page.locator('#message').text_content()
   page.unroute('**/bank.json',corrupt);start();assert stats()['frames']>0;stop()
   results.append({'rate':rate,'test':'invalid hash refuses audio and clean response recovers','status':'PASS','scope':'isolated browser response substitution; original dist unchanged'})
   assert not errors,errors
   assert all(r['method']=='GET' and r['body'] is None and '12.345' not in r['url'] and '67.891' not in r['url'] for r in requests)
  except Exception as e:results.append({'rate':rate,'status':'FAIL','error':traceback.format_exc()});print(rate,traceback.format_exc(),flush=True)
  (a.out/f'rate-{rate}-network.json').write_text(json.dumps({'browser':b.version,'url':a.url,'route':page.evaluate('location.hash'),'build':page.locator('#build-id').text_content(),'viewport':page.evaluate('({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})'),'requests':requests,'errors':errors},indent=2),encoding='utf8');c.close()
 b.close()
(a.out/'receipt.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
raise SystemExit(1 if any(r['status']=='FAIL' for r in results) else 0)
