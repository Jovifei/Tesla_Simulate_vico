"""Production Atelier display geometry/contrast and GPS unknown regression.

Values are injected into the real display API ONLY; actual audio evidence comes
from browser_factory_review.py and browser_lifecycle.py, not this test.
"""
import argparse,json,re,traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import instrument,choose,mode,garage

VIEWS=((1440,900),(1280,720),(1280,600),(1024,600),(1010,1270),(390,844))
VALUES=(dict(inputUsable=True,speedKmh=0,rpm=0,gear='N',load=0),dict(inputUsable=True,speedKmh=144,rpm=7200,gear=1,load=1),dict(inputUsable=True,speedKmh=80,rpm=9000,gear=5,load=.42),dict(inputUsable=True,speedKmh=144,rpm=10000,gear=8,load=1),dict(inputUsable=False,speedKmh=144,rpm=9000,gear=8,load=1))
GEOMETRY = "()=>{\nconst r=e=>{let z=e.getBoundingClientRect();return {x:z.x,y:z.y,right:z.right,bottom:z.bottom,w:z.width,h:z.height}},ids=['speed','rpm','gear','load','redline-rpm'];\nconst svg=document.getElementById('r4-svg'),stage=r(svg),outside=(q,b)=>q.x<b.x-1||q.y<b.y-1||q.right>b.right+1||q.bottom>b.bottom+1;\nconst overlap=(a,b)=>Math.min(a.right,b.right)-Math.max(a.x,b.x)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>1;\nconst visible=e=>getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';\nconst metadata=[...svg.querySelectorAll('.r5-meta,.r5-unit,.r5-caption,.r5-value,.r5-scale')].filter(visible).map(e=>({id:e.id||e.textContent,...r(e)}));\nconst metaCollisions=metadata.flatMap((e,i)=>metadata.slice(i+1).filter(g=>overlap(e,g)).map(g=>[e.id,g.id]));\nlet fields=[...svg.querySelectorAll('.r5-field text,.r5-caption')].filter(visible).map(e=>({id:e.id||e.textContent,...r(e)}));\nlet scales=[...svg.querySelectorAll('.r5-scale')].map(e=>({text:e.textContent,...r(e)}));\nlet hubs=[...svg.querySelectorAll('[data-hub]')].map(r),allText=[...svg.querySelectorAll('text')].map(e=>({id:e.id||e.textContent,...r(e)}));\nconst s=document.getElementById('stop'),sr=r(s),hit=document.elementFromPoint(sr.x+sr.w/2,sr.y+sr.h/2);\nconst ctx=document.createElement('canvas').getContext('2d'),metrics={};\nfor(const id of ['speed','gear']){let e=document.getElementById(id),cs=getComputedStyle(e);ctx.font=`${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;let m=ctx.measureText(e.textContent),matrix=e.getScreenCTM();metrics[id]=(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent)*Math.hypot(matrix.c,matrix.d);}\nreturn {metaCollisions,viewport:[innerWidth,innerHeight],document:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],stage,unique:ids.every(id=>document.querySelectorAll('#'+id).length===1),fields,metrics,\nclipped:allText.filter(x=>outside(x,stage)),scaleCollisions:scales.flatMap(t=>fields.filter(f=>overlap(t,f)).map(f=>({scale:t.text,field:f.id}))),fieldCollisions:fields.flatMap((f,i)=>fields.slice(i+1).filter(g=>overlap(f,g)).map(g=>[f.id,g.id])),hubCollisions:hubs.flatMap(h=>fields.filter(f=>overlap(h,f)).map(f=>f.id)),stop:{...sr,hit:hit===s||s.contains(hit),visible:sr.y>=0&&sr.bottom<=innerHeight},scales:[...svg.querySelectorAll('[data-dial]')].map(d=>({kind:d.dataset.dial,range:Number(d.dataset.range),majors:d.querySelectorAll('.r5-major').length,labels:d.querySelectorAll('[data-scale]').length})),style:document.documentElement.dataset.instrument};}"

def contrast(a,b):
 def lum(c):
  if c.startswith('#'):
   s=c[1:];s=''.join(x*2 for x in s) if len(s)==3 else s;rgb=[int(s[i:i+2],16) for i in (0,2,4)]
  else:rgb=[float(v) for v in re.findall(r'[\d.]+',c)[:3]]
  assert len(rgb)==3,c
  rgb=[v/255 for v in rgb];v=[n/12.92 if n<=.04045 else ((n+.055)/1.055)**2.4 for n in rgb]
  return sum(n*w for n,w in zip(v,(.2126,.7152,.0722)))
 x,y=lum(a),lum(b);return (max(x,y)+.05)/(min(x,y)+.05)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--url',required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--expected-sha',required=True);ap.add_argument('--executable',required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 report={'sha':a.expected_sha,'scope':'PRODUCTION_DISPLAY_INJECTION_NOT_AUDIO','checks':[],'errors':[],'failure':None,'physicalTesla':'NOT_RUN'}
 def record(case,passed,**kw):report['checks'].append({'case':case,'pass':bool(passed),**kw})
 with sync_playwright() as pw:
  b=pw.chromium.launch(headless=True,executable_path=a.executable);p=b.new_page(viewport={'width':1440,'height':900});instrument(p)
  p.on('pageerror',lambda e:report['errors'].append(str(e)))
  p.on('console',lambda e:report['errors'].append('console '+e.text) if e.type=='error' else None)
  try:
   p.goto(a.url,wait_until='networkidle');catalog=p.evaluate("async()=>await(await fetch('catalog.json')).json()")
   assert catalog['webCommit']==a.expected_sha and catalog['testOnly'] is False and len(catalog['vehicles'])==6
   assert p.evaluate("!window.VicoPreview && !document.getElementById('preview-catalog') && document.documentElement.dataset.previewOnly!=='true'")
   for w,h in VIEWS[:-1]:
    p.set_viewport_size({'width':w,'height':h});size=p.evaluate('[document.documentElement.scrollWidth,document.documentElement.scrollHeight]')
    record('garage bounds',size[0]<=w and size[1]<=h,viewport=[w,h],document=size)
   p.set_viewport_size({'width':1440,'height':900});choose(p,0);mode(p,'gps');assert p.locator('#speed').text_content()=='—';p.select_option('#display-style','honda')
   actual=p.locator('#speed').text_content();record('never-authorized GPS unknown survives style',actual=='—',actual=actual)
   p.locator('[data-cluster-choice="digital"]').click();actual=p.locator('#speed').text_content();record('never-authorized GPS unknown survives layout',actual=='—',actual=actual)
   mode(p,'demo');ids=catalog['vehicles'];cases=[(i,'auto') for i in range(6)]+[(0,s) for s in ('mercedes','bmw','audi','vw','honda')]
   failure_screens=0
   for i,preset in cases:
    garage(p);choose(p,i);p.select_option('#display-style',preset)
    for layout in ('touring','digital'):
     p.locator(f'[data-cluster-choice="{layout}"]').click()
     for theme in ('cyber','minimal'):
      p.locator(f'[data-appearance-choice="{theme}"]').click()
      for w,h in VIEWS:
       p.set_viewport_size({'width':w,'height':h});p.wait_for_timeout(35)
       for vi,val in enumerate(VALUES):
        p.evaluate("v=>window.VicoFactory.update(Object.freeze({...v,source:'DEMO'}),true)",val);g=p.evaluate(GEOMETRY);fail=[]
        if not g['unique'] or len(g['fields'])<6:fail.append('missing/duplicate readouts or units')
        if g['document'][0]>w+1 or (w>h and g['document'][1]>h+1):fail.append('viewport overflow')
        if not g['stop']['visible'] or not g['stop']['hit'] or g['stop']['w']<144 or g['stop']['h']<56:fail.append('stop inaccessible')
        for key in ('clipped','scaleCollisions','fieldCollisions','hubCollisions','metaCollisions'):
         if g[key]:fail.append(key)
        if val['inputUsable'] and (w,h)==(1280,600) and (g['metrics']['speed']<64 or g['metrics']['gear']<44):fail.append('small glyphs')
        if val['inputUsable'] and (w,h)==(1440,900) and g['metrics']['speed']<80:fail.append('small desktop speed')
        if any(d['majors']!=d['labels'] for d in g['scales']):fail.append('missing major scale numerals')
        record('complete unclipped instrument',not fail,vehicle=ids[i]['id'],preset=preset,layout=layout,theme=theme,valueCase=vi,viewport=[w,h],failures=fail,geometry=g)
        if fail and failure_screens<20:p.screenshot(path=str(a.out/f'failure-{failure_screens}.png'));failure_screens+=1
   p.set_viewport_size({'width':1280,'height':600});garage(p);choose(p,2);p.select_option('#display-style','auto');p.locator('[data-cluster-choice="touring"]').click()
   for theme in ('cyber','minimal'):
    p.locator(f'[data-appearance-choice="{theme}"]').click()
    colors=p.evaluate("""()=>{const c=getComputedStyle(document.documentElement);return {bg:c.getPropertyValue('--bg').trim(),stage:c.getPropertyValue('--stage').trim(),muted:c.getPropertyValue('--muted').trim(),ink:c.getPropertyValue('--ink').trim(),tick:c.getPropertyValue('--tick').trim(),subtick:c.getPropertyValue('--subtick').trim(),yellow:getComputedStyle(document.querySelector('.r5-yellow .r5-face')).fill,rpm:getComputedStyle(document.getElementById('rpm')).fill}}""")
    for first,second in (('muted','bg'),('ink','bg'),('tick','stage'),('subtick','stage'),('rpm','yellow')):
     ratio=contrast(colors[first],colors[second]);record('text contrast',ratio>=4.5,theme=theme,pair=[first,second],ratio=ratio)
    for sel in (f'[data-appearance-choice="{theme}"]','[data-cluster-choice="touring"]','#mode-demo','#stop'):
     p.locator(sel).hover();colors=p.locator(sel).evaluate('e=>{const c=getComputedStyle(e);return[c.color,c.backgroundColor]}');ratio=contrast(*colors);record('selected/stop hover contrast',ratio>=4.5,theme=theme,selector=sel,ratio=ratio)
   assert p.evaluate('geo.calls===0&&testContexts.length===0'),'Display test unexpectedly invoked audio/GPS'
  except Exception:
   report['failure']=traceback.format_exc();p.screenshot(path=str(a.out/'exception.png'))
  report['browser']=b.version;b.close()
 (a.out/'receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
 failed=sum(not c['pass'] for c in report['checks']);print(json.dumps({'checks':len(report['checks']),'failed':failed,'errors':report['errors'],'failure':report['failure']},ensure_ascii=False));raise SystemExit(1 if failed or report['failure'] or report['errors'] else 0)
if __name__=='__main__':main()
