import {readFileSync} from 'node:fs';
import vm from 'node:vm';
export const cockpitSource=readFileSync(new URL('../src/cockpit.js',import.meta.url),'utf8');
export const factorySource=readFileSync(new URL('../src/factory-display.js',import.meta.url),'utf8');
export const productionHtml=readFileSync(new URL('../index.html',import.meta.url),'utf8');

// IDs exist only after real HTML/SVG creates them; retain every event listener.
export function bootDisplay({layout,style,denied=false,width=1440,loading=false}={}){
 const elements=new Map(),listeners=new Map(),windowListeners=new Map(),frames=[],storage=new Map();
 if(layout!==undefined)storage.set('vico-web-cluster-v1',layout);
 if(style!==undefined)storage.set('vico-web-display-style-v1',style);
 const dataKey=key=>key.replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase());
 function matches(node,selector){
  if(selector.startsWith('['))return Object.hasOwn(node.attrs,selector.slice(1,-1));
  if(selector.startsWith('.'))return node.classes.has(selector.slice(1));
  if(selector.startsWith('#'))return node.id===selector.slice(1);
  return node.tagName===selector;
 }
 function element(tagName,attrs={}){
  const node={tagName,attrs:{},dataset:{},style:{},children:[],classes:new Set(),textContent:'',value:'',disabled:false,
   setAttribute(key,value){this.attrs[key]=String(value);if(key==='id'){this.id=String(value);elements.set(this.id,this);}if(key==='class')this.classes=new Set(String(value).split(/\s+/));if(key.startsWith('data-'))this.dataset[dataKey(key.slice(5))]=String(value);},
   getAttribute(key){return this.attrs[key]??null;},
   querySelectorAll(selector){return this.children.flatMap(child=>[...(matches(child,selector)?[child]:[]),...child.querySelectorAll(selector)]);},
   closest(selector){return matches(this,selector)?this:this.parent?.closest(selector)??null;},
   append(child){child.parent=this;this.children.push(child);},
   replaceChildren(){for(const child of this.querySelectorAll('[id]'))elements.delete(child.id);this.children=[];},
  };
  node.classList={toggle(name,force){const enabled=force??!node.classes.has(name);if(enabled)node.classes.add(name);else node.classes.delete(name);return enabled;},contains:name=>node.classes.has(name)};
  Object.defineProperty(node,'innerHTML',{get(){return this.markup??'';},set(markup){this.replaceChildren();this.markup=markup;parse(markup,this);}});
  for(const [key,value]of Object.entries(attrs))node.setAttribute(key,value);
  return node;
 }
 function parse(markup,root){
  const stack=[root];
  for(const match of markup.matchAll(/<\/?([\w-]+)\b([^>]*)>/g)){
   const [token,tag,body]=match;
   if(token.startsWith('</')){if(stack.length>1)stack.pop();continue;}
   const attrs={};for(const a of body.matchAll(/([\w-]+)(?:="([^"]*)"|='([^']*)')?/g))attrs[a[1]]=a[2]??a[3]??'';
   const node=element(tag,attrs);node.disabled=Object.hasOwn(attrs,'disabled');stack.at(-1).append(node);
   if(!token.endsWith('/>')&&!['meta','link','input','br','hr','img'].includes(tag))stack.push(node);
  }
 }
 const root=element('document');parse(productionHtml,root);
 const register=(map,type,fn)=>{if(!map.has(type))map.set(type,[]);map.get(type).push(fn);};
 const document={documentElement:root.querySelectorAll('html')[0],readyState:loading?'loading':'complete',
  getElementById:id=>elements.get(id)??null,querySelectorAll:selector=>root.querySelectorAll(selector),
  addEventListener:(type,fn)=>register(listeners,type,fn)};
 const window={addEventListener:(type,fn)=>register(windowListeners,type,fn)};
 const context=vm.createContext({document,window,console,innerWidth:width,requestAnimationFrame:fn=>frames.push(fn),
  localStorage:{getItem(key){if(denied)throw Error('storage denied');return storage.get(key)??null;},setItem(key,value){if(denied)throw Error('storage denied');storage.set(key,String(value));}}});
 for(const [name,source]of [['cockpit.js',cockpitSource],['factory-display.js',factorySource]])vm.runInContext(source,context,{filename:name});
 const emit=(map,type,event)=>{for(const fn of map.get(type)??[])fn(event);};
 return {context,document,window,storage,listeners,get:document.getElementById,api:window.VicoCockpit,factory:window.VicoFactory,
  choose(layout){const button=document.querySelectorAll('[data-cluster-choice]').find(node=>node.dataset.clusterChoice===layout);emit(listeners,'click',{target:button});},
  changeStyle(value){const select=elements.get('display-style');select.value=value;emit(listeners,'change',{target:select});},
  ready(){document.readyState='complete';emit(listeners,'DOMContentLoaded',{});},
  resize(width){context.innerWidth=width;emit(windowListeners,'resize',{});},
  flushFrames(){for(const fn of frames.splice(0))fn();},
 };
}
