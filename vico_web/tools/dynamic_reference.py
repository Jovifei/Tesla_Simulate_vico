"""Compile actual pinned parent Kotlin against shared 20ms trajectory CSVs."""
import argparse,json,os,subprocess,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--static',type=Path,required=True);p.add_argument('--trajectory',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
a.out.mkdir();receipt=json.loads((a.static/'receipt.json').read_text());cmd=receipt['commands'][0];src=a.static/'source'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if receipt['sourceCommit']!='477913e7500bb3ff13c3b72cf5b1a3cac1b28145':raise ValueError('Pinned source identity mismatch')
for name,expected in receipt['compiler_inputs'].items():
 if sha(src/name)!=expected:raise ValueError('Pinned compiler input hash mismatch: '+name)
for file in (a.static/'assets').glob('*/*'):
 expected=receipt['source_sha256'].get('vico_app/Project/android/app/src/main/assets/s12_v10/'+file.parent.name+'/'+file.name)
 if not expected or sha(file)!=expected:raise ValueError('Pinned asset hash mismatch: '+str(file))
original=(src/'WebReference.kt').read_text();prefix=original[:original.index('fun main(args:')]
body='''
fun main(args:Array<String>){
 val banks=listOf(bank0(File(args[0])),bank1(File(args[0])),bank2(File(args[0])),bank3(File(args[0])),bank4(File(args[0])),bank5(File(args[0])))
 val ids=listOf("c63_w204_v6","hellcat_v6","ferrari_458","lfa","gtr_r35","supra_jza80")
 for((bi,b) in banks.withIndex()) for(mode in LoopTraversalMode.values()) for(scenario in listOf("demo","cruise80")) {
  val rows=File(args[1],scenario+".csv").readLines().map{it.split(",").map{v->v.toDouble()}}
  val power=MatlabPowertrainController(b.powertrain);val renderer=MatlabStatefulBankRenderer(b,mode)
  val bytes=ByteBuffer.allocate(rows.size*b.sampleRateHz/50*4).order(ByteOrder.LITTLE_ENDIAN)
  val states=StringBuilder()
  for(row in rows){val s=power.update(row[0],row[1],row[2],row[3]);states.append(listOf(s.rpm,s.gear,s.load,s.torqueGain,if(s.shiftTrigger)1 else 0,if(s.afterfireTrigger)1 else 0).joinToString(",")).append("\\n")
   val state=SoundState(row[0],s.rpm,1.0,1.0,1.0,floatArrayOf(),false,load=s.load,shiftGain=s.torqueGain,shiftTrigger=s.shiftTrigger,afterfireTrigger=s.afterfireTrigger)
   for(v in renderer.render(state,b.sampleRateHz/50))bytes.putFloat(v)
  }
  val key=ids[bi]+"-"+mode.name+"-"+scenario
  File(args[2],key+".f32le").writeBytes(bytes.array());File(args[2],key+".csv").writeText(states.toString());println(key)
 }
}
'''
h=a.out/'DynamicReference.kt';h.write_text(prefix+body);sources=[str(q) for q in src.glob('*.kt') if q.name!='WebReference.kt']+[str(h)];cp=cmd[cmd.index('-classpath')+1];java=cmd[0]
commands=[[java,'-cp',cp,'org.jetbrains.kotlin.cli.jvm.K2JVMCompiler','-no-stdlib','-no-reflect','-jvm-target','17','-classpath',cp,'-d',str(a.out/'dynamic.jar'),*sources],[java,'-Xmx2g','-cp',str(a.out/'dynamic.jar')+os.pathsep+cp,'com.vico.simulator.sound.DynamicReferenceKt',str(a.static/'assets'),str(a.trajectory),str(a.out)]]
for i,c in enumerate(commands):
 r=subprocess.run(c,capture_output=True,text=True);(a.out/f'command-{i}.log').write_text(r.stdout+r.stderr)
 if r.returncode:raise RuntimeError(f'Kotlin dynamic command {i} exit {r.returncode}')
(a.out/'receipt.json').write_text(json.dumps({'schema':'vico.web.kotlin-dynamic.v2','sourceCommit':receipt['sourceCommit'],'commands':commands,'staticReceipt':str((a.static/'receipt.json').resolve()),'staticReceiptSha256':sha(a.static/'receipt.json'),'compilerSources':{str((src/name).resolve()):expected for name,expected in receipt['compiler_inputs'].items()},'banks':receipt['banks'],'trajectorySha256':{q.name:sha(q) for q in a.trajectory.glob('*.csv')},'artifacts':{q.name:sha(q) for q in a.out.iterdir() if q.suffix in ['.csv','.f32le','.jar','.kt']},'scope':'actual parent synthetic Powertrain + renderer; no Android measured/device evidence'},indent=2))
print('36 actual Kotlin dynamic cases complete')
