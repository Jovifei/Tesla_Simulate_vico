"""R4 actual-browser acceptance: 6 sound banks, independent factory-inspired display presets.
Never labels headless AudioWorklet as speaker, Tesla, road or human evidence.
"""
import argparse, json, traceback
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_smoke import instrument, choose, garage, start, stats, stop

APPEARANCES=('cyber','minimal')
VIEWPORTS=((1440,900),(1280,720),(1280,600),(1024,600),(1010,1270),(390,844))
PRESETS=('auto','mercedes','bmw','audi','vw','honda')
AUTOS=('mercedes','muscle','maranello','precision','technical','heritage')

def geometry(page,width,height):
    page.set_viewport_size({'width':width,'height':height})
    page.wait_for_timeout(130)
    return page.evaluate("""()=>{
      const ids=['speed','rpm','gear','load','speed-label','input-state'];
      const stage=document.getElementById('r4-stage').getBoundingClientRect();
      const stop=document.getElementById('stop'),s=stop.getBoundingClientRect(),hit=document.elementFromPoint(s.x+s.width/2,s.y+s.height/2);
      const values=ids.map(id=>{const e=document.getElementById(id),r=e.getBoundingClientRect();return {id,text:e.textContent.trim(),x:r.x,y:r.y,right:r.right,bottom:r.bottom,height:r.height}});
      return {width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,
        scrollHeight:document.documentElement.scrollHeight,stage:{x:stage.x,y:stage.y,right:stage.right,bottom:stage.bottom,width:stage.width,height:stage.height},
        values,stop:{x:s.x,y:s.y,width:s.width,height:s.height,visible:s.y>=0&&s.bottom<=innerHeight&&s.width>=144&&s.height>=56&&(hit===stop||stop.contains(hit))},
        appearance:document.documentElement.dataset.appearance,style:document.documentElement.dataset.instrument,
        unique:ids.every(id=>document.querySelectorAll('#'+id).length===1),
        labelPlateCollisions:[...document.querySelectorAll('#r4-svg .r4-tick-label')].flatMap(label=>{
          const a=label.getBoundingClientRect();return [...document.querySelectorAll('#r4-svg .r4-value-plate')].filter(plate=>{
            const b=plate.getBoundingClientRect();return a.left<b.right-.2&&a.right>b.left+.2&&a.top<b.bottom-.2&&a.bottom>b.top+.2;
          }).map(()=>label.textContent);
        }),
        source:document.getElementById('speed-label').textContent};
    }""")

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--url',required=True);ap.add_argument('--out',required=True,type=Path);ap.add_argument('--expected-sha',required=True);ap.add_argument('--executable',required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    report={'sha':a.expected_sha,'url':a.url,'checks':[],'screenshots':[],'errors':[],'failure':None,'physicalTesla':'NOT_RUN','humanAudition':'NOT_EVALUATED'}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=a.executable,headless=True)
        context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();instrument(page)
        page.on('pageerror',lambda e:report['errors'].append(str(e)))
        page.on('console',lambda e:report['errors'].append('console '+e.text) if e.type=='error' else None)
        page.on('response',lambda r:report['errors'].append(f'HTTP {r.status} {r.url}') if r.status>=400 else None)
        def frame_identity():
            return page.evaluate("""()=>{const d=JSON.parse(document.getElementById('diagnostics').textContent);return {
              runId:d.runId,vehicle:d.vehicle,bank:d.stats?.bankIdentity?.bankSha256,contexts:testContexts.length,
              nodes:testNodes.length,volume:document.getElementById('volume').value,gps:geo.calls};}""")
        def capture(vehicle,preset,theme,w,h):
            z=geometry(page,w,h)
            assert z['unique'] and z['stop']['visible'] and z['scrollWidth']<=w+1,z
            if w>h:assert z['scrollHeight']<=h+1,z
            assert z['style']==vehicle if preset=='auto' else z['style']==preset,(z['style'],vehicle,preset)
            assert z['appearance']==theme,z
            assert not z['labelPlateCollisions'], ('Scale labels collide with value readouts', z['labelPlateCollisions'], vehicle, preset, w, h)
            assert all(z['stage']['x']-1<=v['x']<=v['right']<=z['stage']['right']+1 and z['stage']['y']-1<=v['y']<=v['bottom']<=z['stage']['bottom']+1 for v in z['values']),z
            if w==1280 and h==600:
                assert next(v['height'] for v in z['values'] if v['id']=='speed')>=64,z
                assert next(v['height'] for v in z['values'] if v['id']=='gear')>=44,z
                assert next(v['height'] for v in z['values'] if v['id']=='input-state')>=11,z
            if w==1440 and h==900:assert next(v['height'] for v in z['values'] if v['id']=='speed')>=80,z
            file=f'{vehicle}-{preset}-{theme}-{w}x{h}.png';page.screenshot(path=str(a.out/file),full_page=False)
            report['screenshots'].append({'name':file,'geometry':z})
        try:
            page.goto(a.url,wait_until='networkidle');catalog=page.evaluate("async()=>await(await fetch('catalog.json')).json()")
            assert catalog['webCommit']==a.expected_sha and catalog['testOnly'] is False and len(catalog['vehicles'])==6
            assert page.evaluate('testContexts.length===0&&geo.calls===0')
            for i,expected in enumerate(AUTOS):
                choose(page,i)
                page.select_option('#display-style','auto')
                assert page.locator('html').get_attribute('data-instrument')==expected
                page.locator('[data-scenario="cruise"]').click();start(page);first=stats(page);before=frame_identity()
                assert before['bank']==catalog['vehicles'][i]['bankSha256']
                for theme in APPEARANCES:
                    page.locator(f'[data-appearance-choice="{theme}"]').click()
                    for w,h in VIEWPORTS:capture(expected,'auto',theme,w,h)
                page.set_viewport_size({'width':1440,'height':900})
                last=stats(page);assert last['frames']>first['frames'] and frame_identity()==before
                report['checks'].append({'vehicle':catalog['vehicles'][i]['id'],'auto':expected,'frames':[first['frames'],last['frames']],'pass':True})
                stop(page);garage(page)
            choose(page,0);page.locator('[data-scenario="cruise"]').click();start(page);first=stats(page);before=frame_identity()
            for preset in PRESETS[1:]:
                page.select_option('#display-style',preset)
                assert page.locator('html').get_attribute('data-instrument')==preset
                for theme in APPEARANCES:
                    page.locator(f'[data-appearance-choice="{theme}"]').click()
                    for w,h in ((1440,900),(1280,600),(1010,1270),(390,844)):capture(preset,preset,theme,w,h)
                page.set_viewport_size({'width':1440,'height':900})
                now=stats(page);assert now['frames']>first['frames'] and frame_identity()==before
                report['checks'].append({'preset':preset,'pass':True,'frames':[first['frames'],now['frames']]});first=now
            page.select_option('#display-style','honda')
            page.reload(wait_until='networkidle')
            assert page.locator('#display-style').input_value()=='honda'
            assert page.evaluate('testContexts.every(c=>c.state==="closed")')
            assert not report['errors'],report['errors']
        except Exception as e:
            report['failure']=f'{type(e).__name__}: {e}\n{traceback.format_exc()}'
        report['browser']=browser.version
        (a.out/'receipt.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
        context.close();browser.close()
    if report['failure'] or any(c.get('pass') is not True for c in report['checks']):raise AssertionError('R4 browser acceptance did not pass; inspect receipt.json')
    print('R4 vehicle/preset/headless Worklet acceptance PASS. Physical/Human NOT_RUN')
if __name__=='__main__':main()
