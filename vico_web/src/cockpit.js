/* Display adapter only; compatible VicoCockpit API, no audio or control logic. */
(function(){
 'use strict';
 const key='vico-web-cluster-v1';
 let layout='touring';try{if(localStorage.getItem(key)==='digital')layout='digital';}catch(_){}
 function apply(){document.documentElement.dataset.cluster=layout;document.querySelectorAll('[data-cluster-choice]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.clusterChoice===layout)));}
 apply();if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',apply,{once:true});
 document.addEventListener('click',e=>{const b=e.target?.closest?.('[data-cluster-choice]');if(!b||b.disabled||!['touring','digital'].includes(b.dataset.clusterChoice))return;layout=b.dataset.clusterChoice;try{localStorage.setItem(key,layout);}catch(_){}apply();});
 window.VicoCockpit=Object.freeze({prepare(entry){window.VicoFactory?.prepare(entry);},update(stats,active){window.VicoFactory?.update(stats,active);}});
})();
