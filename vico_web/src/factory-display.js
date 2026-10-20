/* VICO ATELIER — display only. Original vectors, no audio/GPS/network/control ownership. */
(function () {
 'use strict';
 const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
 const OPTIONS=Object.freeze(['auto','mercedes','bmw','audi','vw','honda']);
 const AUTO=Object.freeze({c63_w204_v6:'mercedes',hellcat_v6:'muscle',ferrari_458:'maranello',lfa:'precision',gtr_r35:'technical',supra_jza80:'heritage'});
 const LABELS=Object.freeze({mercedes:'CLASSIC 204 · 三筒仪表',muscle:'AMERICAN V8 · 双筒仪表',maranello:'ITALIA · 中央转速',precision:'V10 PRECISION · 单环仪表',technical:'R PERFORMANCE · 偏置仪表',heritage:'HERITAGE 80 · 复古三联',bmw:'M CLASSIC · 双圆仪表',audi:'VIRTUAL · 数字双弧',vw:'GTI SPORT · 中央转速',honda:'S ROADSTER · 数字转速条'});
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
 function dial(kind,cx,cy,r,{start=145,sweep=250,yellow=false,perimeter=false,half=false}={}){
  const max=kind==='rpm'?rpmMax:speedMax,minor=kind==='rpm'?100:10,major=kind==='rpm'?1000:40;
  const end=start+sweep,group=`r5-dial ${yellow?'r5-yellow':''}`;
  const shape=half?`<path d="M${cx-r-12} ${cy+8} V${cy} A${r+12} ${r+12} 0 0 1 ${cx+r+12} ${cy} V${cy+8}" class="r5-face"/>`:`<circle cx="${cx}" cy="${cy}" r="${r+10}" class="r5-face"/><circle cx="${cx}" cy="${cy}" r="${r+9}" class="r5-bezel"/>`;
  let out=`<g class="${group}" data-dial="${kind}" data-range="${max}" data-cx="${cx}" data-cy="${cy}">${shape}<path d="${arc(cx,cy,r,start,end)}" class="r5-track"/>`;
  if(kind==='rpm'&&entry.redlineRpm<max)out+=`<path data-redline="${entry.redlineRpm}" data-red-start="${start+sweep*entry.redlineRpm/max}" d="${arc(cx,cy,r-1,start+sweep*entry.redlineRpm/max,end)}" class="r5-red"/>`;
  for(let n=0;n<=max;n+=minor){
   const a=start+sweep*n/max,big=n%major===0,mid=!big&&kind==='rpm'&&n%500===0;
   const p=pt(cx,cy,r-(big?15:mid?10:6),a),q=pt(cx,cy,r-2,a);
   out+=`<line x1="${fmt(p[0])}" y1="${fmt(p[1])}" x2="${fmt(q[0])}" y2="${fmt(q[1])}" class="${big?'r5-major':mid?'r5-medium':'r5-minor'}" data-tick="${n}"/>`;
   if(big){const z=pt(cx,cy,r-30,a);out+=txt(fmt(z[0]),fmt(z[1]+6),kind==='rpm'?n/1000:n,17,'r5-scale','middle',`data-scale="${n}"`);}
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
 function load(x,y,width=180){return `<g class="r5-load"><rect x="${x}" y="${y}" width="${width}" height="4" rx="2" class="r5-load-base"/><rect id="load-bar" x="${x}" y="${y}" width="0" height="4" rx="2" class="r5-load-fill" data-width="${width}"/>${txt(x,y+28,'虚拟负载',mobile?12:16,'r5-meta','start')}${txt(x+width-17,y+28,'0',mobile?13:17,'r5-meta','end','id="load"')}${txt(x+width,y+28,'%',mobile?12:16,'r5-meta','end')}</g>`;}
 function redline(x,y){return `<g class="r5-redline">${txt(x,y,'REDLINE',mobile?10:14,'r5-meta','end')}${txt(x+12,y,entry.redlineRpm,mobile?12:17,'r5-meta','start','id="redline-rpm"')}${txt(x+(mobile?58:79),y,'rpm',mobile?10:14,'r5-meta','start')}</g>`;}
 function footerLabel(x,y,s){return txt(x,y,s,16,'r5-caption');}
 function original(style){
  switch(style){
   case 'mercedes':return `${section(70,51,250,272)}${section(405,10,390,340)}${dial('speed',600,140,118,{start:180,sweep:180,half:true})}${dial('rpm',982,142,113)}${value('speed',600,280,138,'km/h',340)}${value('gear',195,204,100,'虚拟挡位',253)}${value('rpm',982,297,46,'RPM',335)}${load(105,276,180)}${redline(1020,357)}`;
   case 'muscle':case 'bmw':return `${dial('speed',266,147,127,{start:145,sweep:250})}${dial('rpm',934,147,127,{start:145,sweep:250})}<path d="M470 38 H730 V324 H470 Z" class="r5-line"/>${value('speed',600,157,136,'km/h',209)}${value('gear',600,301,90,'虚拟挡位',347)}${value('rpm',934,303,43,'RPM',340)}${load(157,292,220)}${footerLabel(266,45,style==='bmw'?'M / PRECISION':'V8 / PERFORMANCE')}${redline(1010,353)}`;
   case 'maranello':return `${dial('rpm',600,151,132,{yellow:true})}${section(61,66,288,241)}${section(885,66,254,241)}${value('speed',205,228,144,'km/h',285)}<g class="r5-yellow-readout">${value('rpm',600,247,38,'RPM',273)}</g>${value('gear',1012,214,106,'虚拟挡位',266)}${load(89,318,232)}${redline(985,348)}`;
   case 'precision':return `${dial('rpm',600,155,135,{perimeter:true})}${value('speed',209,231,148,'km/h',290)}${value('gear',600,200,106,'虚拟挡位',254)}${value('rpm',1000,205,61,'RPM',251)}${load(906,282,202)}${redline(992,349)}${footerLabel(205,65,'V10 / DIGITAL')}`;
   case 'technical':return `${dial('speed',185,143,93)}${dial('rpm',530,151,135)}${section(719,37,424,286)}${value('speed',950,185,138,'km/h',242)}${value('gear',766,276,90,'虚拟挡位',320)}${value('rpm',530,303,44,'RPM',340)}${load(876,281,216)}${redline(180,340)}${footerLabel(940,60,'R / PERFORMANCE')}`;
   case 'heritage':return `${dial('speed',235,125,100,{start:180,sweep:180,half:true})}${dial('rpm',639,151,134)}${section(920,47,215,274)}${value('speed',235,278,138,'km/h',337)}${value('rpm',639,303,44,'RPM',340)}${value('gear',1028,198,102,'虚拟挡位',249)}${load(938,275,178)}${redline(1010,352)}`;
   case 'audi':return `<path d="M62 312 V133 L157 30 H1043 L1138 133 V312" class="r5-bezel"/>${dial('rpm',265,142,99,{start:180,sweep:180,half:true})}${dial('speed',944,142,99,{start:180,sweep:180,half:true})}${value('speed',600,245,154,'km/h',304)}${value('rpm',265,262,56,'RPM',310)}${value('gear',944,269,96,'虚拟挡位',318)}${load(460,324,280)}${redline(255,350)}`;
   case 'vw':return `${dial('rpm',600,151,132,{perimeter:true})}${value('speed',212,234,145,'km/h',292)}${value('gear',600,202,100,'虚拟挡位',254)}${value('rpm',990,206,60,'RPM',252)}${load(899,282,204)}${redline(990,349)}<path d="M468 15 H732" stroke="var(--red)" stroke-width="4"/>${footerLabel(210,60,'GTI / SPORT VIEW')}`;
   case 'honda':return `${bar(110,99,980,30,true)}${value('speed',584,275,147,'km/h',338)}${value('rpm',213,256,54,'RPM',302)}${value('gear',1016,260,106,'虚拟挡位',311)}${load(72,320,232)}${redline(1018,351)}${footerLabel(595,23,'S / ROADSTER · ×1000 RPM')}`;
  }
  return '';
 }
 function digital(){return `${bar(80,49,1040,17)}${value('speed',600,246,174,'km/h',316)}${value('gear',1020,228,109,'虚拟挡位',285)}${value('rpm',200,226,66,'RPM',277)}${load(72,317,235)}${redline(990,348)}<path d="M386 105 V297 M812 105 V297" class="r5-line"/>`;}
 function compact(){return `${bar(29,48,342,14)}${value('speed',200,193,111,'km/h',243)}${value('gear',91,310,66,'虚拟挡位',348)}${value('rpm',285,303,40,'RPM',339)}${load(23,365,150)}${redline(262,389)}`;}
 function resolve(id,desired=preference){return desired==='auto'?(Object.hasOwn(AUTO,id)?AUTO[id]:'mercedes'):(OPTIONS.includes(desired)?desired:'mercedes');}
 function render(){
  activeStyle=resolve(entry.id);rpmMax=Math.max(activeStyle==='honda'?10000:0,Math.floor(entry.redlineRpm/1000)*1000+1000);speedMax=SPEED_MAX[activeStyle]||320;descriptors=[];
  const stage=$('r4-stage');if(!stage)return;
  const vw=mobile?400:1200,vh=mobile?400:360;
  stage.style.aspectRatio=mobile?'1 / 1':'';
  stage.innerHTML=`<svg id="r4-svg" class="r4-svg" viewBox="0 0 ${vw} ${vh}" xmlns="${NS}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="原创虚拟汽车仪表；数值来自当前模型，不是真实车辆仪表"><defs><linearGradient id="edge" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--metal)" stop-opacity=".35"/><stop offset="1" stop-color="var(--metal)" stop-opacity=".03"/></linearGradient></defs><rect x="1" y="1" width="${vw-2}" height="${vh-2}" rx="${mobile?12:28}" class="r5-shell"/><path id="rpm-arc" visibility="hidden" d=""/>${mobile?compact():document.documentElement.dataset.cluster==='digital'?digital():original(activeStyle)}</svg>`;
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
