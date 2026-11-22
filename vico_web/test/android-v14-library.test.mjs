import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

test('Android library uses fingerprint-checked catalog and does not optimistically select',async()=>{
  const html=await readFile(new URL('../../vico_app/Project/android/app/src/main/assets/screens/library.html',import.meta.url),'utf8');
  const script=html.match(/<script>\s*\/\/ Display only[\s\S]*?<\/script>/)?.[0].replace(/^<script>/,'').replace(/<\/script>$/,'');
  assert.ok(script);
  class Element {constructor(){this.children=[];this.dataset={};this.classList={add(){},remove(){},toggle(){}};}
    replaceChildren(){this.children=[]} append(...items){this.children.push(...items)} addEventListener(name,fn){this[name]=fn}}
  const grid=new Element(), calls=[];
  const vehicles=Array.from({length:9},(_,i)=>({display_name:`Vehicle ${i}`,legacy_key:`v${i}`}));
  const bridge={getV14RegistryJson:()=>JSON.stringify({schema_version:'1.0',vehicles}),isV14VehicleAvailable:()=>false,
    setVehicle:key=>calls.push(key),previewVehicle:key=>calls.push(key)};
  const document={getElementById:()=>grid,createElement:()=>new Element(),querySelector:()=>null,querySelectorAll:()=>[]};
  vm.runInNewContext(script,{window:{AndroidBridge:bridge},document});
  assert.equal(grid.children.length,9);
  for(const card of grid.children) {assert.equal(card.children[2].disabled,true);assert.equal(card.children[3].disabled,true);}
  assert.deepEqual(calls,[]);
});
