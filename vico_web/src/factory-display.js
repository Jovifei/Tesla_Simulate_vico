/* R4 factory-inspired display, independent of the selected sound bank and AudioSession.
 * Original SVG geometry: no OEM logos, photos, sound synthesis or vehicle telemetry added.
 */
(function () {
  'use strict';
  const KEY = 'vico-web-display-style-v1';
  const OPTIONS = Object.freeze(['auto','mercedes','bmw','audi','vw','honda']);
  const AUTO = Object.freeze({c63_w204_v6:'mercedes',hellcat_v6:'muscle',ferrari_458:'maranello',lfa:'precision',gtr_r35:'technical',supra_jza80:'heritage'});
  const LABELS = Object.freeze({mercedes:'经典三筒 · W204 灵感',bmw:'M 风格 · 机械双环',audi:'虚拟座舱 · 双弧',vw:'GTI 风格 · 中央转速',honda:'S2000 风格 · 横向转速',muscle:'美式双环 · 肌肉风格',maranello:'中央转速 · 竞速风格',precision:'精密单环 · 高转速',technical:'偏置双仪表 · 性能风格',heritage:'复古三联 · 机械风格'});
  const MAX_RPM = Object.freeze({mercedes:8000,bmw:9000,audi:9000,vw:8000,honda:10000,muscle:8000,maranello:10000,precision:10000,technical:8000,heritage:8000});
  const SPEED_RANGE = Object.freeze({mercedes:320,bmw:320,audi:300,vw:280,honda:260,muscle:320,maranello:320,precision:320,technical:340,heritage:280});
  let preference='auto', entry={id:'c63_w204_v6',redlineRpm:7200}, activeStyle='mercedes', rpmMax=8000, speedMax=320, lastStats=null, lastActive=false;
  try { const saved=localStorage.getItem(KEY); if(OPTIONS.includes(saved)) preference=saved; } catch (_) {}
  const $=id=>document.getElementById(id);
  const clamp=(x,lo,hi)=>Number.isFinite(x)?Math.max(lo,Math.min(hi,x)):lo;
  const point=(x,y,r,degree)=>[+(x+Math.cos(degree*Math.PI/180)*r).toFixed(3),+(y+Math.sin(degree*Math.PI/180)*r).toFixed(3)];
  const path=(cx,cy,r,a=135,b=405)=>{const p=point(cx,cy,r,a),q=point(cx,cy,r,b);return `M${p[0]} ${p[1]} A${r} ${r} 0 ${b-a>180?1:0} 1 ${q[0]} ${q[1]}`;};
  const text=(x,y,v,size=16,cls='',anchor='middle')=>`<text x="${x}" y="${y}" text-anchor="${anchor}" class="${cls}" font-size="${size}">${v}</text>`;
  const field=(id,x,y,size,subtitle,init)=>`<g class="r4-field">${text(x,y,init,size,'r4-number')}${text(x,y+Math.max(30,size*.24+24),subtitle,17,'r4-micro')}</g>`.replace('class="r4-number"',`id="${id}" class="r4-number"`);
  const needle=(id,cx,cy,r)=>`<line id="${id}" class="r4-needle" x1="${cx}" y1="${cy}" x2="${point(cx,cy,r,135)[0]}" y2="${point(cx,cy,r,135)[1]}"/><circle class="r4-hub" cx="${cx}" cy="${cy}" r="7"/>`;
  function dial(kind,cx,cy,r,range,redline=0,flags={}){
    const isRpm=kind==='rpm',steps=Math.round(range/(isRpm?500:20));
    let lines='',labels='';
    for(let i=0;i<=steps;i++){
      const val=i*(isRpm?500:20),angle=135+270*val/range;
      const major=isRpm?val%1000===0:val%40===0;
      const p=point(cx,cy,r-(major?15:9),angle),q=point(cx,cy,r-3,angle);
      lines+=`<line x1="${p[0]}" y1="${p[1]}" x2="${q[0]}" y2="${q[1]}" class="${major?'r4-tick-major':'r4-tick-minor'}"/>`;
      if(major){const n=point(cx,cy,r-((isRpm&&['precision','vw'].includes(activeStyle))?18:34),angle);labels+=text(n[0],n[1]+5,isRpm?val/1000:val,15,'r4-tick-label');}
    }
    const begin=135+270*clamp(redline/range,0,1),red=isRpm&&redline<range?`<path d="${path(cx,cy,r-1,begin,405)}" class="r4-red"/>`:'';
    return `<g class="r4-dial r4-${kind}"><circle cx="${cx}" cy="${cy}" r="${r+9}" class="r4-bezel"/><circle cx="${cx}" cy="${cy}" r="${r-2}" class="r4-face"/><path d="${path(cx,cy,r-1)}" class="r4-track"/>${red}${lines}${labels}${needle(kind==='rpm'?'rpm-needle':'speed-needle',cx,cy,r-24)}</g>`;
  }
  const panel=(x,y,w,h)=>`<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" class="r4-tile"/>`;
  function gauges(style){
    switch(style){
      case 'mercedes':return `${dial('speed',568,173,142,speedMax)}${dial('rpm',962,174,119,rpmMax,entry.redlineRpm)}${panel(58,64,218,222)}`;
      case 'muscle':return `${dial('speed',310,173,140,speedMax)}${dial('rpm',902,173,140,rpmMax,entry.redlineRpm)}${panel(486,60,230,266)}`;
      case 'maranello':return `${panel(55,75,230,202)}${dial('rpm',612,173,147,rpmMax,entry.redlineRpm)}${panel(927,75,218,202)}`;
      case 'precision':return `${dial('rpm',603,172,148,rpmMax,entry.redlineRpm)}${panel(62,80,218,190)}${panel(922,80,218,190)}`;
      case 'technical':return `${dial('speed',243,175,116,speedMax)}${dial('rpm',708,174,146,rpmMax,entry.redlineRpm)}${panel(964,70,192,216)}`;
      case 'heritage':return `${dial('speed',284,174,122,speedMax)}${dial('rpm',681,173,147,rpmMax,entry.redlineRpm)}${panel(961,60,227,266)}`;
      case 'bmw':return `${dial('speed',317,172,139,speedMax)}${dial('rpm',874,172,139,rpmMax,entry.redlineRpm)}${panel(486,60,230,266)}`;
      case 'audi':return `<path d="${path(294,174,130)}" class="r4-track r4-digital-arc"/><path d="${path(911,174,130)}" class="r4-track r4-digital-arc"/>${dial('rpm',294,174,104,rpmMax,entry.redlineRpm)}${dial('speed',911,174,104,speedMax)}${panel(465,60,275,265)}`;
      case 'vw':return `${panel(54,68,220,218)}${dial('rpm',597,175,144,rpmMax,entry.redlineRpm)}${panel(930,68,216,218)}`;
      case 'honda':{
        let bars='';const n=Math.round(rpmMax/100),pitch=1000/n;for(let i=0;i<n;i++){const x=104+i*pitch;bars+=`<rect data-rpm-step="${i+1}" x="${x.toFixed(2)}" y="${101-(i%10===0?5:0)}" width="${(pitch*.66).toFixed(2)}" height="${i%10===0?49:43}" rx="1" class="r4-honda-step${(i+1)*100>entry.redlineRpm?' red':''}"/>`;}
        let numbers='';for(let k=0;k<=10;k++)numbers+=text(103+k*99.9,88,String(k),15,'r4-tick-label');
        return `${panel(72,70,1056,208)}${bars}${numbers}${text(600,63,'ENGINE SPEED · ×1000 RPM',14,'r4-micro')}`;
      }
    }
    return '';
  }
  function indicators(style){
    const secondaryRpm=(x,y,s=46)=>field('rpm',x,y,s,'RPM','0');
    const speed=(x,y,s=105)=>field('speed',x,y,s,'km/h','000');
    const gear=(x,y,s=74)=>field('gear',x,y,s,'挡位','N');
    switch(style){
      case 'mercedes':return `${speed(167,215,112)}${gear(568,275,66)}${secondaryRpm(962,285,44)}`;
      case 'muscle':case 'bmw':return `${speed(601,150,108)}${gear(601,278,66)}${secondaryRpm(style==='muscle'?902:874,285,44)}`;
      case 'maranello':return `${speed(172,227,104)}${secondaryRpm(612,285,44)}${gear(1038,219,78)}`;
      case 'precision':return `${gear(168,215,66)}${speed(603,205,118)}${secondaryRpm(1030,217,55)}`;
      case 'technical':return `${speed(1060,160,101)}${secondaryRpm(708,285,44)}${gear(1060,290,66)}`;
      case 'heritage':return `${speed(1071,160,101)}${secondaryRpm(681,285,44)}${gear(1071,290,66)}`;
      case 'audi':return `${secondaryRpm(295,273,36)}${speed(600,150,101)}${gear(602,290,70)}`;
      case 'vw':return `${gear(167,218,74)}${speed(597,205,113)}${secondaryRpm(1038,222,63)}`;
      case 'honda':return `${speed(574,275,128)}${gear(1010,270,68)}${secondaryRpm(182,267,47)}`;
    }
    return '';
  }
  function digital(){return `${panel(53,63,1094,214)}<path class="r4-hud-track" d="M110 80 H1090"/><path id="r4-hud-fill" class="r4-hud-fill" d="M110 80 H110"/>${field('speed',590,230,154,'速度 / km/h','000')}${field('gear',1005,235,87,'GEAR / 虚拟挡位','N')}${field('rpm',185,230,59,'RPM / 模型转速','0')}`;}
  function compose(){
    const digitalMode=document.documentElement.dataset.cluster==='digital',style=activeStyle;
    return `<svg id="r4-svg" class="r4-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 340" preserveAspectRatio="xMidYMid meet" role="img" aria-label="模型驱动的虚拟仪表，不是原厂仪表或真实车辆数据">
      <rect x="2" y="2" width="1196" height="336" rx="24" class="r4-chassis"/><path id="rpm-arc" visibility="hidden" d=""/>
      ${digitalMode?digital():gauges(style)+indicators(style)}
      <g class="r4-footer">${text(55,330,'REDLINE / 虚拟红线',17,'r4-micro','start')}<text id="redline-rpm" x="233" y="330" class="r4-footer-value" text-anchor="start">${entry.redlineRpm}</text>${text(303,330,'rpm',17,'r4-micro','start')}
      </g>
      <rect id="load-bar" x="350" y="305" width="0" height="5" rx="2" class="r4-load-fill"/>
      <text x="350" y="330" class="r4-micro" text-anchor="start">负载</text>
      <text id="load" x="442" y="330" class="r4-micro" font-size="19">0</text>${text(487,330,'%',17,'r4-micro')}
    </svg>`;
  }
  function resolve(id,desired=preference){return desired==='auto'?(Object.hasOwn(AUTO,id)?AUTO[id]:'mercedes'):(OPTIONS.includes(desired)?desired:'mercedes');}
  function render(){
    activeStyle=resolve(entry.id); rpmMax=Math.max(MAX_RPM[activeStyle]||9000,(Math.floor(entry.redlineRpm/1000)+1)*1000); speedMax=SPEED_RANGE[activeStyle]||320;
    const stage=$('r4-stage'); if(!stage)return;
    stage.innerHTML=compose();
    document.documentElement.dataset.instrument=activeStyle;
    document.documentElement.dataset.factoryStyle=preference;
    if($('instrument-style'))$('instrument-style').textContent=LABELS[activeStyle];
    if($('display-style'))$('display-style').value=preference;
    update(lastStats,lastActive);
  }
  function prepare(next){
    if(next && typeof next.id==='string')entry={id:next.id,redlineRpm:Number.isFinite(next.redlineRpm)&&next.redlineRpm>0?next.redlineRpm:9000};
    const s=resolve(entry.id);rpmMax=Math.max(MAX_RPM[s]||9000,(Math.floor(entry.redlineRpm/1000)+1)*1000);speedMax=SPEED_RANGE[s]||320;
    lastStats=null;lastActive=false;render();
  }
  function rotateNeedle(id,cx,cy,r,val,max){const n=$(id);if(!n)return;const p=point(cx,cy,r-24,135+270*clamp(val/max,0,1));const perimeter=id==='rpm-needle'&&['precision','vw'].includes(activeStyle);const start=perimeter?point(cx,cy,r-12,135+270*clamp(val/max,0,1)):[cx,cy];n.setAttribute('x1',String(start[0]));n.setAttribute('y1',String(start[1]));n.setAttribute('x2',String(p[0]));n.setAttribute('y2',String(p[1]));}
  const GAUGES=Object.freeze({mercedes:{speed:[568,173,142],rpm:[962,174,119]},muscle:{speed:[310,173,140],rpm:[902,173,140]},maranello:{rpm:[612,173,147]},precision:{rpm:[603,172,148]},technical:{speed:[243,175,116],rpm:[708,174,146]},heritage:{speed:[284,174,122],rpm:[681,173,147]},bmw:{speed:[317,172,139],rpm:[874,172,139]},audi:{rpm:[294,174,104],speed:[911,174,104]},vw:{rpm:[597,175,144]}});
  function update(stats,active){
    lastStats=stats||null;lastActive=Boolean(active);
    const valid=active && stats && stats.inputUsable && Number.isFinite(stats.speedKmh)&&Number.isFinite(stats.rpm)&&Number.isFinite(stats.load);
    const s=valid?stats:null;
    const gpsMode=$('mode-gps')?.getAttribute('aria-pressed')==='true';
    const unknown=active||gpsMode;
    const put=(id,value)=>{const node=$(id);if(node)node.textContent=String(value);};
    put('speed',s?String(Math.round(s.speedKmh)).padStart(3,'0'):(unknown?'—':'000'));
    put('rpm',s?Math.round(s.rpm).toLocaleString('en-US'):(unknown?'—':'0'));
    put('gear',s?s.gear:(unknown?'—':'N'));
    put('load',s?Math.round(s.load*100):(unknown?'—':'0'));
    put('redline-rpm',entry.redlineRpm);
    const gps=gpsMode||s?.source==='WEB_GPS_ESTIMATED';put('speed-label',gps?'GPS 实验估算 · 虚拟': '虚拟速度 · 非实际车速');
    put('input-state',!active?'等待启动':s?'模型输入有效':'输入失效 · 已静音');
    const status=$('input-state');if(status)status.classList.toggle('invalid',Boolean(active&&!valid));
    for(const id of ['rpm-needle','speed-needle']){const n=$(id);if(n)n.setAttribute('visibility',unknown&&!valid?'hidden':'visible');}
    const bar=$('load-bar');if(bar)bar.setAttribute('width',String(s?clamp(s.load,0,1)*150:0));
    if(document.documentElement.dataset.cluster==='digital'){
      const hud=$('r4-hud-fill');if(hud)hud.setAttribute('d',`M110 80 H${110+980*clamp(s?s.rpm/rpmMax:0,0,1)}`);
    }else{
      const map=GAUGES[activeStyle]||{};
      if(map.rpm)rotateNeedle('rpm-needle',...map.rpm,s?s.rpm:0,rpmMax);
      if(map.speed)rotateNeedle('speed-needle',...map.speed,s?s.speedKmh:0,speedMax);
      const steps=$('r4-svg')?.querySelectorAll('[data-rpm-step]');if(steps)steps.forEach((node,i)=>node.classList.toggle('lit',Boolean(s)&&i<Math.floor(clamp(s.rpm/rpmMax,0,1)*steps.length)));
    }
  }
  function switchStyle(next){if(!OPTIONS.includes(next))return false;preference=next;try{localStorage.setItem(KEY,next);}catch(_){}render();return true;}
  document.addEventListener('change',e=>{if(e.target?.id==='display-style')switchStyle(e.target.value);});
  document.addEventListener('click',e=>{if(e.target?.closest?.('[data-cluster-choice]')){Promise.resolve().then(render);}});
  window.VicoFactory=Object.freeze({prepare,update,resolve,options:OPTIONS,style:()=>preference});
  // Populate the one set of live-readout IDs before app.mjs starts and calls resetDigits().
  prepare(entry);
})();
