"""Real native browser/worklet and viewport matrix; no dependency installation."""
import argparse,json
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

def status(p,v,timeout=30000):p.wait_for_function('(v)=>document.getElementById("play-status").textContent===v',arg=v,timeout=timeout)
def stats(p,expected=None):
 if expected is None:
  expected=p.evaluate("async()=>{const c=await(await fetch('catalog.json')).json();return c.vehicles.find(v=>location.hash.endsWith('/'+v.id)).bankSha256}")
 baseline=p.evaluate('testNodes.at(-1)?.seen||0')
 p.wait_for_function("""({expected,baseline})=>{const n=testNodes.at(-1);if(!n||n.ctx!==testContexts.at(-1)||n.ctx.state!=='running'||n.seen<=baseline)return false;try{const d=JSON.parse(document.getElementById('diagnostics').textContent),s=d.stats||d;return ((window.testAllowLegacyDiagnostics&&!d.stats)||(d.scope==='CURRENT_RUN'&&d.runId===window.testExpectedRunId&&d.runId!=null&&location.hash.endsWith('/'+d.vehicle)))&&s.bankIdentity?.bankSha256===expected&&s.frames===n.stats.frames&&s.frames>0}catch{return false}}""",arg={'expected':expected,'baseline':baseline},timeout=15000)
 diagnostic=json.loads(p.locator('#diagnostics').text_content())
 return diagnostic.get('stats',diagnostic)
def start(p,timeout=30000):
 before=p.evaluate("()=>{try{return JSON.parse(document.getElementById('diagnostics').textContent).runId||null}catch{return null}}")
 p.locator('#start').click();status(p,'正在播放',timeout)
 p.evaluate("before=>{const d=JSON.parse(document.getElementById('diagnostics').textContent);if(!window.testAllowLegacyDiagnostics&&(!d.runId||d.runId===before))throw new Error('Start did not create a new diagnostic runId');window.testExpectedRunId=d.runId}",before)
def stop(p):p.locator('#stop').click();status(p,'尚未启动')
def mode(p,name):p.locator(f'#mode-{name}').click();status(p,'尚未启动')
def garage(p):p.locator('#back-garage').click();p.locator('#garage').wait_for(state='visible')
def choose(p,i=0):p.locator('.vehicle-card').nth(i).click();p.locator('#drive').wait_for(state='visible');status(p,'尚未启动')
def instrument(p,rate=None):
 p.add_init_script("""(()=>{window.testContexts=[];window.geo={calls:0};const Native=AudioContext;window.AudioContext=class extends Native{constructor(o){super(RATE===null?o:{...o,sampleRate:RATE});testContexts.push(this)}};Object.defineProperty(navigator,'geolocation',{value:{watchPosition(ok,fail){geo.calls++;geo.ok=ok;geo.fail=fail;return geo.calls},clearWatch(){}}});})();""".replace('RATE',json.dumps(rate)))
 p.add_init_script("""(()=>{window.testNodes=[];const Native=AudioWorkletNode;window.AudioWorkletNode=class extends Native{constructor(ctx,...rest){super(ctx,...rest);const record={ctx,seen:0,stats:null,node:this};testNodes.push(record);this.port.addEventListener('message',e=>{if(e.data.type==='stats'){record.seen++;record.stats=e.data.stats}});this.port.start()}}})();""")
def capture(p,out,name,w,h,drive=True):
 p.set_viewport_size({'width':w,'height':h});p.wait_for_timeout(150);p.screenshot(path=str(out/f'{name}-{w}x{h}.png'),full_page=False)
 selectors=['#vehicle-name','#speed','.r4-field .r4-micro','#rpm','#gear','#redline-rpm','#start','#stop','#mode-demo','#mode-manual','#mode-gps'] if drive else ['.vehicle-card']
 e=p.evaluate("""selectors=>{const rows=selectors.flatMap(s=>Array.from(document.querySelectorAll(s)).filter(e=>e.getClientRects().length).map(e=>{const r=e.getBoundingClientRect();return {selector:s,text:e.textContent.trim(),x:r.x,y:r.y,width:r.width,height:r.height,inViewport:r.x>=-1&&r.y>=-1&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1}}));const stop=document.getElementById('stop'),r=stop.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},route:location.hash,appearance:document.documentElement.dataset.appearance,build:document.getElementById('build-id').textContent,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight,controls:rows,stopUncovered:stop===hit||stop.contains(hit),stopSize:{width:r.width,height:r.height},readableState:document.getElementById('play-status').textContent,message:document.getElementById('message').textContent}}""",selectors)
 e['overflowElements']=p.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getClientRects().length).map(e=>{const r=e.getBoundingClientRect();return {tag:e.tagName,id:e.id,class:String(e.className),right:r.right,bottom:r.bottom}}).filter(r=>r.right>innerWidth+1||r.bottom>innerHeight+1)")
 portrait=h>w
 bounds=all(r['inViewport'] for r in e['controls'] if not portrait or r['selector'] in ['#speed','#stop'])
 e['name']=name;e['portraitSecondaryScrollAllowed']=portrait;e['pass']=e['scrollWidth']<=w+1 and len(e['controls'])==(len(selectors) if drive else 6) and bounds and (not drive or ((portrait or e['scrollHeight']<=h+1) and e['stopUncovered'] and e['stopSize']['width']>=144 and e['stopSize']['height']>=56));return e

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--url',required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--executable',required=True);ap.add_argument('--appearance',choices=['cyber','minimal','baseline'],default='cyber');ap.add_argument('--origin-ip');a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 events=[];errors=[];console=[];network=[];failure=None
 with sync_playwright() as pw:
  launch_args=[]
  if a.origin_ip:
   hostname=urlparse(a.url).hostname
   assert hostname and a.url.startswith('https://')
   launch_args=['--no-proxy-server',f'--host-resolver-rules=MAP {hostname} {a.origin_ip}, EXCLUDE localhost']
  b=pw.chromium.launch(headless=True,executable_path=a.executable,args=launch_args);c=b.new_context(viewport={'width':1440,'height':900});p=c.new_page();instrument(p)
  p.on('pageerror',lambda e:errors.append(str(e)));p.on('console',lambda e:console.append({'type':e.type,'text':e.text}));p.on('request',lambda r:network.append({'method':r.method,'url':r.url,'body':r.post_data}));p.on('response',lambda r:network.append({'status':r.status,'url':r.url}))
  try:
   p.goto(a.url,wait_until='networkidle');p.locator('#garage').wait_for(state='visible',timeout=3000);assert p.locator('.vehicle-card').count()==6
   if a.appearance!='baseline':
    p.locator(f'[data-appearance-choice="{a.appearance}"]').click()
    assert p.evaluate('appearance=>document.documentElement.dataset.appearance===appearance&&localStorage.getItem("vico-web-appearance-v1")===appearance',a.appearance)
   assert p.evaluate('testContexts.length===0&&geo.calls===0');events.append(capture(p,a.out,'garage',1440,900,False))
   choose(p);assert p.evaluate('testContexts.length===0&&geo.calls===0');events.append(capture(p,a.out,'drive-idle',1440,900))
   catalog=p.evaluate("async()=>await (await fetch('catalog.json')).json()")
   for i in range(6):
    if i:garage(p);choose(p,i)
    p.locator('[data-scenario="launch"]').click();start(p,90000 if a.origin_ip else 30000);s=stats(p,catalog['vehicles'][i]['bankSha256']);assert s['frames']>0 and s['preClipPeak']>0 and s['nonfinite']==0
    name=p.locator('#vehicle-name').text_content();redline=p.locator('#redline-rpm').text_content();assert name==catalog['vehicles'][i]['name'];assert str(catalog['vehicles'][i]['redlineRpm']) in redline.replace(',','')
    events.append({'test':'actual six-car worklet','vehicle':name,'redline':redline,'stats':s,'diagnostic':json.loads(p.locator('#diagnostics').text_content())})
    if i==0:events.append(capture(p,a.out,'drive-demo',1280,720))
    stop(p);assert p.evaluate("testContexts.every(c=>c.state==='closed')")
   mode(p,'manual');p.locator('#target').fill('80');p.locator('#target').dispatch_event('input');start(p,90000 if a.origin_ip else 30000);stats(p);events.append(capture(p,a.out,'drive-manual',1280,600));stop(p)
   mode(p,'gps');p.locator('#gps').click();p.evaluate('geo.fail({code:1})');e=capture(p,a.out,'drive-gps-invalid',1024,600);e['invalidSpeed']=p.locator('#speed').text_content();e['pass']=e['pass'] and e['invalidSpeed']=='—';events.append(e)
   mode(p,'demo');held=[]
   def hold(r):held.append(r)
   p.route('**/bank.json',hold);p.locator('#start').click();status(p,'资源校验中');events.append(capture(p,a.out,'drive-loading',1280,600));stop(p)
   for r in held:r.abort()
   p.unroute('**/bank.json',hold)
   garage(p);choose(p,1);p.locator('#settings-toggle').click();events.append(capture(p,a.out,'drive-settings',1920,1080));p.locator('#settings-toggle').click();events.append(capture(p,a.out,'drive-portrait',390,844))
   assert not errors,errors;assert all(r.get('method','GET')=='GET' and not r.get('body') for r in network);assert all(e.get('pass',True) and (a.appearance=='baseline' or e.get('appearance',a.appearance)==a.appearance) for e in events),'Viewport layout or appearance assertion failed'
  except Exception as e:failure=f'{type(e).__name__}: {e}';p.screenshot(path=str(a.out/'failure.png'),full_page=False)
  (a.out/'receipt.json').write_text(json.dumps({'scope':'HEADLESS_DESKTOP_NOT_PHYSICAL_OUTPUT','browser':b.version,'url':a.url,'originOverrideIp':a.origin_ip,'appearance':a.appearance,'events':events,'page_errors':errors,'console':console,'network':network,'failure':failure,'GPS':'INJECTED_CALLBACKS','physical':'NOT_RUN'},ensure_ascii=False,indent=2),encoding='utf8');c.close();b.close()
 if failure:raise AssertionError(failure)
 print('Browser/worklet and viewport matrix PASS')
if __name__=='__main__':main()
