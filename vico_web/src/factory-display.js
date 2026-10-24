/* VICO ATELIER — display only. Original vectors, no audio/GPS/network/control ownership. */
(function () {
 'use strict';
 const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
 const OPTIONS=Object.freeze(['auto','mercedes','bmw','audi','vw','honda']);
 const AUTO=Object.freeze({c63_w204_v6:'mercedes',hellcat_v6:'muscle',ferrari_458:'maranello',lfa:'precision',gtr_r35:'technical',supra_jza80:'heritage'});
 const LABELS=Object.freeze({mercedes:'CLASSIC 204 · 三圆仪表',muscle:'AMERICAN V8 · 双筒仪表',maranello:'ITALIA · 中央转速',precision:'V10 PRECISION · 单环仪表',technical:'R PERFORMANCE · 偏置仪表',heritage:'HERITAGE 80 · 复古三联',bmw:'M CLASSIC · 双圆仪表',audi:'VIRTUAL · 双圆座舱',vw:'GTI SPORT · 中央转速',honda:'S ROADSTER · 半圆转速'});
 const SPEED_MAX=Object.freeze({mercedes:320,muscle:320,maranello:320,precision:320,technical:340,heritage:280,bmw:320,audi:300,vw:280,honda:260});
 const KEY='vico-web-display-style-v1';
 let preference='auto',entry={id:'c63_w204_v6',redlineRpm:7200},activeStyle='mercedes',rpmMax=8000,speedMax=320,lastStats=null,lastActive=false,mobile=innerWidth<=700,descriptors=[],resizePending=false;
 try{const p=localStorage.getItem(KEY);if(OPTIONS.includes(p))preference=p;}catch(_){}
 const clamp=(n,a,b)=>Number.isFinite(n)?Math.max(a,Math.min(b,n)):a;
 const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const pt=(cx,cy,r,a)=>[cx+Math.cos(a*Math.PI/180)*r,cy+Math.sin(a*Math.PI/180)*r];
 const fmt=n=>Number(n.toFixed(3));
 const arc=(cx,cy,r,a,b)=>{const p=pt(cx,cy,r,a),q=pt(cx,cy,r,b);return `M${fmt(p[0])} ${fmt(p[1])} A${r} ${r} 0 ${b-a>180?1:0} 1 ${fmt(q[0])} ${fmt(q[1])}`;};
 const txt=(x,y,value,size=17,cls='r5-caption',anchor='middle',extra='')=>`<text x="${x}" y="${y}" font-size="${size}" text-anchor="${anchor}" class="${cls}" ${extra}>${esc(value)}</text>`;
 const value=(id,x,y,size,unit,unitY,extra='')=>`<g class="r5-field" data-field="${id}">${txt(x,y,id==='gear'?'N':id==='speed'?'000':'0',size,'r5-value','middle',`id="${id}" ${extra}`)}${unit?txt(x,unitY,unit,17,'r5-unit'):''}</g>`;
 function section(x,y,w,h){return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${Math.min(30,w/8)}" class="r5-panel"/>`;}
 function pod(kind,cx,cy,r){return `<g data-pod="${kind}"><circle cx="${cx}" cy="${cy}" r="${r+10}" class="r5-face"/><circle cx="${cx}" cy="${cy}" r="${r+9}" class="r5-bezel"/><path d="${arc(cx,cy,r,145,395)}" class="r5-track"/></g>`;}
 function readout(x,y,w,h){return `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="11" class="r5-readout"/>`;}
 function clusterShell(){return mobile?'<rect x="8" y="8" width="384" height="384" rx="20" data-cluster-shell="true" class="r5-housing"/>':'<path d="M22 315 V129 C22 56 153 20 302 20 H898 C1047 20 1178 56 1178 129 V315 Q1178 342 1150 342 H50 Q22 342 22 315 Z" data-cluster-shell="true" class="r5-housing"/><path d="M52 97 C140 42 272 35 600 35 S1060 42 1148 97" class="r5-brow"/>' ;}
 function dial(kind,cx,cy,r,{start=145,sweep=250,yellow=false,perimeter=false,half=false,pod=false,labelInset,majorStep}={}){
  const max=kind==='rpm'?rpmMax:speedMax,minor=kind==='rpm'?100:10,major=majorStep??(kind==='rpm'?1000:40);
  const end=start+sweep,group=`r5-dial ${yellow?'r5-yellow':''}`;
  const shape=half?`<path d="M${cx-r-12} ${cy+8} V${cy} A${r+12} ${r+12} 0 0 1 ${cx+r+12} ${cy} V${cy+8}" class="r5-face"/>`:`<circle cx="${cx}" cy="${cy}" r="${r+10}" class="r5-face"/><circle cx="${cx}" cy="${cy}" r="${r+9}" class="r5-bezel"/>`;
  let out=`<g class="${group}" data-dial="${kind}" data-range="${max}" data-cx="${cx}" data-cy="${cy}" ${pod?`data-pod="${kind}"`:''}>${shape}<path d="${arc(cx,cy,r,start,end)}" class="r5-track"/>`;
  if(kind==='rpm'&&entry.redlineRpm<max)out+=`<path data-redline="${entry.redlineRpm}" data-red-start="${start+sweep*entry.redlineRpm/max}" d="${arc(cx,cy,r-1,start+sweep*entry.redlineRpm/max,end)}" class="r5-red"/>`;
  for(let n=0;n<=max;n+=minor){
   const a=start+sweep*n/max,big=n%major===0,mid=!big&&kind==='rpm'&&n%500===0;
   const p=pt(cx,cy,r-(big?15:mid?10:6),a),q=pt(cx,cy,r-2,a);
   out+=`<line x1="${fmt(p[0])}" y1="${fmt(p[1])}" x2="${fmt(q[0])}" y2="${fmt(q[1])}" class="${big?'r5-major':mid?'r5-medium':'r5-minor'}" data-tick="${n}"/>`;
   if(big){const numeralRadius=activeStyle==='vw'&&kind==='rpm'&&(n===0||n===max)?r+30:r-(labelInset??(kind==='speed'?18:30));const z=pt(cx,cy,numeralRadius,a);out+=txt(fmt(z[0]),fmt(z[1]+6),kind==='rpm'?n/1000:n,17,'r5-scale','middle',`data-scale="${n}"`);}
  }
  const id=kind==='rpm'?'rpm-needle':'speed-needle';
  out+=`<g id="${id}" class="r5-hand" data-zero="${start}" data-sweep="${sweep}" data-max="${max}">`;
  if(perimeter){out+=`<line class="r5-needle" x1="${cx+r-20}" y1="${cy}" x2="${cx+r-2}" y2="${cy}"/>`;}
  else{out+=`<line class="r5-tail" x1="${cx-13}" y1="${cy}" x2="${cx}" y2="${cy}"/><line class="r5-needle" x1="${cx}" y1="${cy}" x2="${cx+r-28}" y2="${cy}"/>`;}
  out+='</g>';
  if(!perimeter)out+=`<circle cx="${cx}" cy="${cy}" r="6" class="r5-hub" data-hub="true"/>`;
  descriptors.push({id,kind,cx,cy,start,sweep,max});return out+'</g>';
 }
 function bar(x,y,width,height,curved=false){
  let out='<g class="r5-rpm-bar" data-range="'+rpmMax+'">';const count=rpmMax/100,dx=width/count;
  for(let i=0;i<count;i++){
   const t=i/count,yy=y-(curved?30*Math.sin(t*Math.PI):0);
   out+=`<rect x="${fmt(x+t*width)}" y="${fmt(yy)}" width="${fmt(dx*.68)}" height="${height}" rx="1" data-rpm-step="${(i+1)*100}" class="r5-segment ${(i+1)*100>entry.redlineRpm?'red':''}"/>`;
  }
  for(let n=0;n<=rpmMax;n+=1000){const t=n/rpmMax;out+=txt(fmt(x+t*width),fmt(y-12-(curved?30*Math.sin(t*Math.PI):0)),n/1000,mobile?12:18,'r5-scale','middle',`data-scale="${n}"`);}
  return out+'</g>';
 }
 function semicircleRpm(cx,cy,r){
  let out=`<g class="r5-rpm-bar" data-rpm-geometry="semicircle" data-range="${rpmMax}">`;
  const count=rpmMax/100;
  for(let i=0;i<count;i++){
   const a=180+180*(i+.14)/count,b=180+180*(i+.86)/count;
   out+=`<path d="${arc(cx,cy,r,a,b)}" data-rpm-step="${(i+1)*100}" class="r5-segment-stroke ${(i+1)*100>entry.redlineRpm?'red':''}"/>`;
  }
  for(let n=0;n<=rpmMax;n+=1000){const a=180+180*n/rpmMax,p=pt(cx,cy,r-31,a);out+=txt(fmt(p[0]),fmt(p[1]+6),n/1000,18,'r5-scale','middle',`data-scale="${n}"`);}
  return out+'</g>';
 }
 function load(x,y,width=180){return `<g class="r5-load"><rect x="${x}" y="${y}" width="${width}" height="4" rx="2" class="r5-load-base"/><rect id="load-bar" x="${x}" y="${y}" width="0" height="4" rx="2" class="r5-load-fill" data-width="${width}"/>${txt(x,y+28,'虚拟负载',mobile?12:16,'r5-meta','start')}${txt(x+width-17,y+28,'0',mobile?13:17,'r5-meta','end','id="load"')}${txt(x+width,y+28,'%',mobile?12:16,'r5-meta','end')}</g>`;}
 function redline(x,y){const baseline=mobile?y:Math.min(y,330);return `<g class="r5-redline">${txt(x,baseline,'REDLINE',mobile?10:14,'r5-meta','end')}${txt(x+12,baseline,entry.redlineRpm,mobile?12:17,'r5-meta','start','id="redline-rpm"')}${txt(x+(mobile?58:79),baseline,'rpm',mobile?10:14,'r5-meta','start')}</g>`;}
 function footerLabel(x,y,s){return txt(x,y,s,16,'r5-caption');}
 function original(style){
  switch(style){
   case 'mercedes':return `${pod('gear',205,170,92)}${dial('speed',600,147,118,{start:180,sweep:180,pod:true})}${dial('rpm',986,170,116,{pod:true})}${readout(480,202,240,138)}${value('speed',600,274,130,'km/h',329)}${value('gear',205,203,90,'虚拟挡位',251)}${readout(913,221,146,67)}${value('rpm',986,248,44,'RPM',282)}${load(105,287,190)}${redline(1005,326)}`;
   case 'muscle':case 'bmw':return `${dial('speed',266,147,127,{start:145,sweep:250})}${dial('rpm',934,147,127,{start:145,sweep:250})}${section(470,66,260,265)}${value('speed',600,163,129,'km/h',207)}${value('gear',600,294,92,'虚拟挡位',330)}${readout(866,216,136,73)}${value('rpm',934,258,42,'RPM',282)}${load(157,292,220)}${redline(1010,326)}`;
   case 'maranello':return `${dial('rpm',600,151,132,{yellow:true})}${section(61,58,288,268)}${section(885,66,254,257)}${value('speed',205,217,136,'km/h',267)}<g class="r5-yellow-readout">${value('rpm',600,247,38,'RPM',273)}</g>${value('gear',1012,210,98,'虚拟挡位',261)}${load(89,281,232)}${redline(990,307)}`;
   case 'precision':return `${section(66,68,275,250)}${dial('rpm',600,160,145,{perimeter:true})}${section(916,78,215,242)}${value('speed',206,219,132,'km/h',281)}${value('gear',600,199,108,'虚拟挡位',256)}${value('rpm',1022,217,57,'RPM',263)}${load(931,277,181)}${redline(205,312)}${footerLabel(205,87,'V10 / DIGITAL')}`;
   case 'technical':return `${dial('speed',185,143,93)}${dial('rpm',530,151,135)}${section(759,42,378,280)}${value('speed',960,162,129,'km/h',226)}${value('gear',1075,278,92,'虚拟挡位',313)}${value('rpm',530,280,44,'RPM',316)}${load(791,270,191)}${redline(183,327)}`;
   case 'heritage':return `${dial('speed',235,125,100,{start:180,sweep:180,half:true})}${dial('rpm',639,151,134)}${section(920,47,215,272)}${value('speed',235,272,133,'km/h',328)}${value('rpm',639,282,44,'RPM',319)}${value('gear',1028,185,94,'虚拟挡位',229)}${load(937,251,178)}${redline(1010,311)}`;
   case 'audi':return `${dial('rpm',265,164,119)}${dial('speed',935,164,119)}${section(445,44,310,304)}${value('speed',600,164,135,'km/h',213)}${value('gear',600,301,92,'虚拟挡位',339)}${readout(203,210,124,74)}${value('rpm',265,253,43,'RPM',279)}${load(830,298,198)}${redline(260,330)}`;
   case 'vw':return `${dial('rpm',600,138,118,{start:205,sweep:130,perimeter:true,labelInset:18,majorStep:2000})}${readout(475,132,250,156)}${value('speed',600,222,136,'km/h',285)}${value('gear',1000,212,91,'虚拟挡位',259)}${value('rpm',203,218,58,'RPM',260)}${load(102,291,212)}${redline(1005,328)}<path d="M468 22 H732" stroke="var(--red)" stroke-width="4"/>${footerLabel(205,66,'GTI / SPORT VIEW')}`;
   case 'honda':return `${semicircleRpm(600,318,291)}${readout(451,174,298,137)}${value('speed',600,248,143,'km/h',301)}${value('rpm',208,246,55,'RPM',274)}${value('gear',999,249,93,'虚拟挡位',292)}${load(77,302,202)}${redline(996,326)}${footerLabel(190,75,'S / ROADSTER · ×1000 RPM')}`;
  }
  return '';
 }
 function digital(){return `${bar(80,49,1040,17)}${value('speed',600,246,174,'km/h',316)}${value('gear',1020,228,109,'虚拟挡位',285)}${value('rpm',200,226,66,'RPM',277)}${load(72,299,235)}${redline(990,348)}<path d="M386 105 V297 M812 105 V297" class="r5-line"/>`;}
 function compact(){return `${bar(29,48,342,14)}${value('speed',200,193,111,'km/h',243)}${value('gear',91,310,66,'虚拟挡位',348)}${value('rpm',285,303,40,'RPM',339)}${load(23,365,150)}${redline(262,389)}`;}
 function resolve(id,desired=preference){return desired==='auto'?(Object.hasOwn(AUTO,id)?AUTO[id]:'mercedes'):(OPTIONS.includes(desired)?desired:'mercedes');}
 function render(){
  activeStyle=resolve(entry.id);rpmMax=Math.max(activeStyle==='honda'?10000:0,Math.floor(entry.redlineRpm/1000)*1000+1000);speedMax=SPEED_MAX[activeStyle]||320;descriptors=[];
  const stage=$('r4-stage');if(!stage)return;
  const vw=mobile?400:1200,vh=mobile?400:360;
  stage.style.aspectRatio=mobile?'1 / 1':'';
  stage.innerHTML=`<svg id="r4-svg" class="r4-svg" viewBox="0 0 ${vw} ${vh}" xmlns="${NS}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="原创虚拟汽车仪表；数值来自当前模型，不是真实车辆仪表"><defs><linearGradient id="cluster-body" x2="0" y2="1"><stop offset="0" stop-color="#26343c"/><stop offset=".24" stop-color="#111b21"/><stop offset="1" stop-color="#080d12"/></linearGradient><radialGradient id="dial-depth"><stop offset="0" stop-color="#17222a"/><stop offset=".73" stop-color="#0d151b"/><stop offset="1" stop-color="#05090d"/></radialGradient><linearGradient id="cluster-glass" x2="0" y2="1"><stop offset="0" stop-color="#51606b" stop-opacity=".56"/><stop offset="1" stop-color="#2c3840" stop-opacity=".04"/></linearGradient></defs><rect x="1" y="1" width="${vw-2}" height="${vh-2}" rx="${mobile?12:28}" class="r5-shell"/>${clusterShell()}<path id="rpm-arc" visibility="hidden" d=""/>${mobile?compact():document.documentElement.dataset.cluster==='digital'?digital():original(activeStyle)}</svg>`;
  document.documentElement.dataset.instrument=activeStyle;document.documentElement.dataset.factoryStyle=preference;
  if($('display-style'))$('display-style').value=preference;
  if($('instrument-style'))$('instrument-style').textContent=(mobile?'COMPACT · ': '')+LABELS[activeStyle];
  update(lastStats,lastActive);
 }
 function prepare(next){if(next&&typeof next.id==='string')entry={id:next.id,redlineRpm:Number.isFinite(next.redlineRpm)&&next.redlineRpm>0?next.redlineRpm:9000};lastStats=null;lastActive=false;render();}
 function update(stats,active){
  lastStats=stats||null;lastActive=Boolean(active);
  const valid=Boolean(active&&stats&&stats.inputUsable&&Number.isFinite(stats.speedKmh)&&Number.isFinite(stats.rpm)&&Number.isFinite(stats.load));
  const s=valid?stats:null,gps=$('mode-gps')?.getAttribute('aria-pressed')==='true'||stats?.source==='WEB_GPS_ESTIMATED';
  const unknown=Boolean(active)||gps,put=(id,v)=>{const e=$(id);if(e)e.textContent=String(v);};
  put('speed',s?String(Math.round(Math.max(0,s.speedKmh))).padStart(3,'0'):(unknown?'—':'000'));
  put('rpm',s?Math.round(Math.max(0,s.rpm)).toLocaleString('en-US'):(unknown?'—':'0'));
  put('gear',s&&(s.gear==='N'||Number.isFinite(s.gear))?s.gear:(unknown?'—':'N'));put('load',s?Math.round(clamp(s.load,0,1)*100):(unknown?'—':'0'));put('redline-rpm',entry.redlineRpm);
  put('speed-label',gps?'GPS 实验 · 非真实车辆仪表':'模型速度 · 非真实车辆仪表');put('input-state',active?(valid?'输入有效':'输入失效 · 已静音'):'等待启动');
  $('input-state')?.classList.toggle('invalid',Boolean(active&&!valid));
  for(const d of descriptors){const e=$(d.id);if(!e)continue;const v=s?(d.kind==='rpm'?s.rpm:s.speedKmh):0;e.setAttribute('transform',`rotate(${d.start+d.sweep*clamp(v/d.max,0,1)} ${d.cx} ${d.cy})`);e.setAttribute('visibility',unknown&&!valid?'hidden':'visible');}
  const lb=$('load-bar');if(lb)lb.setAttribute('width',String(s?Number(lb.dataset.width)*clamp(s.load,0,1):0));
  $('r4-svg')?.querySelectorAll('[data-rpm-step]').forEach(e=>e.classList.toggle('lit',Boolean(s)&&Number(e.dataset.rpmStep)<=s.rpm));
 }
 function switchStyle(v){if(!OPTIONS.includes(v))return false;preference=v;try{localStorage.setItem(KEY,v);}catch(_){}render();return true;}
 document.addEventListener('change',e=>{if(e.target?.id==='display-style')switchStyle(e.target.value);});
 document.addEventListener('click',e=>{if(e.target?.closest?.('[data-cluster-choice]'))Promise.resolve().then(render);});
 window.addEventListener('resize',()=>{if(resizePending)return;resizePending=true;requestAnimationFrame(()=>{resizePending=false;const n=innerWidth<=700;if(n!==mobile){mobile=n;render();}});});
 window.VicoFactory=Object.freeze({prepare,update,resolve,options:OPTIONS,style:()=>preference});
 prepare(entry);
})();