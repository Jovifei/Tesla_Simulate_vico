const test=require('node:test'), assert=require('node:assert/strict'), fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../../Project/android/app/src/main/assets');
function load(){const c={window:{}};vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(root,'input-quality-ui.js'),'utf8'),c);return c.window.VicoInputDisplay;}
const fresh={gps:'FRESH',imu:'FRESH',speedUsable:true,accelerationUsable:true,controlUsable:true,gpsAgeMs:0};
test('70 km/h preserves mph preference while standard debug remains 70.0',()=>{const f=load();for(const [unit,value] of [['kmh','70'],['mph','43']]){const d=f.format({speed:70,speedKmh:'70.0',accel:'2.00',inputQuality:fresh},unit);assert.equal(d.speed,value);assert.equal(d.standardSpeed,'70.0 km/h');assert.equal(d.unit,unit==='mph'?'mph':'km/h')}});
test('stale42 unavailable0 and recovery70 are visibly different from parking',()=>{const f=load();for(const q of ['STALE','UNAVAILABLE','LOW_QUALITY']){const d=f.format({speed:42,speedKmh:'42.0',inputQuality:{...fresh,gps:q,speedUsable:false,controlUsable:false}},'kmh');assert.equal(d.speed,'—');assert.equal(d.good,false);assert.ok(d.warning)}assert.equal(f.format({speed:70,speedKmh:'70.0',inputQuality:fresh},'kmh').speed,'70')});
test('unconfirmed IMU never hides usable speed or pretends measured acceleration',()=>{const d=load().format({speed:70,speedKmh:'70.0',accel:'2.00',inputQuality:{...fresh,imu:'UNCONFIRMED_FRAME',accelerationUsable:false,controlUsable:false}},'kmh');assert.equal(d.speed,'70');assert.equal(d.accel,'—');assert.match(d.warning,/安装方向/)});
test('unverified precision and synthetic mode are explicit',()=>{const f=load();let d=f.format({speed:70,speedKmh:'70.0',inputQuality:{...fresh,gps:'UNVERIFIED'}},'kmh');assert.equal(d.good,false);assert.match(d.gpsLabel,/精度/);d=f.format({speed:70,speedKmh:'70.0',inputQuality:{...fresh,gps:'SYNTHETIC',imu:'SYNTHETIC'}},'kmh');assert.match(d.gpsLabel,/演示/)});
test('no quality and illegal payload fail closed',()=>{const f=load();assert.equal(f.format({speed:70,speedKmh:'70.0'},'kmh').speed,'—');assert.equal(f.format({speed:NaN,speedKmh:'NaN',inputQuality:fresh},'kmh').speed,'—')});
test('dashboard uses quality contract and prominent unit without writing preferences',()=>{const s=fs.readFileSync(path.join(root,'screens/dashboard.html'),'utf8');assert.match(s,/VicoInputDisplay\.format/);assert.match(s,/id="speed-unit"[^>]*|id="speed-unit"/);assert.match(s,/font-weight: 700/);assert.doesNotMatch(s,/localStorage\.setItem\('vico-unit'/);assert.doesNotMatch(s,/GPS 信号丢失，当前使用加速度传感器数据/)});
test('actual dashboard update paints measured value unit and invalid status',()=>{
 const html=fs.readFileSync(path.join(root,'screens/dashboard.html'),'utf8'),code=html.match(/window\.__vicoUpdate = function\(s\)\{[\s\S]*?\n\s*\};/)[0];
 const ids=['live-speed','speed-unit','live-accel','debug-speed','gps-text','gps-warning','debug-quality','debug-age','debug-display'];
 const els={};ids.forEach(id=>els[id]={textContent:'',classList:{toggle(){},remove(){},add(){}}});
 const c={window:{},document:{getElementById(id){return els[id]||null}},localStorage:{getItem(){return 'mph'}},console};
 vm.createContext(c);vm.runInContext(fs.readFileSync(path.join(root,'input-quality-ui.js'),'utf8'),c);vm.runInContext(code,c);
 c.window.__vicoUpdate({speed:70,speedKmh:'70.0',accel:'2.00',inputQuality:fresh});
 assert.equal(els['live-speed'].textContent,'43');assert.equal(els['speed-unit'].textContent,'mph');assert.equal(els['debug-speed'].textContent,'70.0 km/h');
 c.window.__vicoUpdate({speed:0,speedKmh:'0.0',accel:'0.00',inputQuality:{...fresh,gps:'UNAVAILABLE',speedUsable:false,controlUsable:false}});
 assert.equal(els['live-speed'].textContent,'—');assert.match(els['gps-warning'].textContent,/车速未知/);
});
