#!/usr/bin/env python3
"""Real browser/AudioWorklet smoke against an already-built site; no GPS permission.
Requires an existing Playwright installation/browser. Does not install dependencies.
"""
from pathlib import Path
import argparse, json, time
from playwright.sync_api import sync_playwright

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',default='http://localhost:4173');p.add_argument('--out',type=Path,required=True);p.add_argument('--executable');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 events=[];errors=[]
 with sync_playwright() as pw:
  args={'headless':True}
  if a.executable:args['executable_path']=a.executable
  browser=pw.chromium.launch(**args);context=browser.new_context(viewport={'width':1440,'height':1100});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(a.url,wait_until='networkidle');page.wait_for_selector('.vehicle-card');assert page.locator('.vehicle-card').count()==6
  page.screenshot(path=str(a.out/'desktop.png'),full_page=True)
  page.locator('[data-scenario="launch"]').click();page.locator('#start').click();page.wait_for_function("document.getElementById('play-status').textContent === '正在播放'",timeout=15000)
  page.wait_for_function("Number(document.getElementById('rpm').textContent.replace(/,/g,'')) > 0",timeout=15000)
  stats=json.loads(page.locator('#diagnostics').inner_text());assert stats['frames']>0 and stats['preClipPeak']>0 and stats['nonfinite']==0
  events.append({'test':'actual AudioWorklet produces samples','stats':stats})
  page.locator('#stop').click();page.wait_for_function("document.getElementById('play-status').textContent === '尚未启动'")
  page.locator('.vehicle-card').nth(1).click();page.locator('#start').click();page.locator('.vehicle-card').nth(2).click();page.wait_for_timeout(900)
  assert page.locator('#vehicle-name').inner_text()=='Ferrari 458 Italia';assert page.locator('#play-status').inner_text()=='尚未启动';events.append({'test':'in-flight vehicle owner cancellation','pass':True})
  page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(a.out/'mobile.png'),full_page=True)
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
  events.append({'test':'mobile no horizontal overflow','pass':True})
  assert not errors,errors
  receipt={'scope':'HEADLESS_CHROMIUM_WEB_AUDIO_NOT_PHYSICAL_OUTPUT','url':a.url,'browser':browser.version,'page_build':page.locator('#build-id').inner_text(),'events':events,'page_errors':errors,'gps':'NOT_REQUESTED','device_acoustic':'NOT_EVALUATED'}
  (a.out/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8');context.close();browser.close()
 print('Browser/AudioWorklet smoke PASS; no device listening claim')
if __name__=='__main__':main()
