package com.vico.simulator.sound
import org.junit.Assert.*
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
class LiveLoopReferenceIsolationTest {
 private val assets=File("app/src/main/assets").takeIf{it.isDirectory} ?: File("src/main/assets")
 private val root=File(assets,"s12_v10/c63_w204_v6")
 private fun original():MatlabSoundBank {
  fun wav(n:String)=FloatWavDecoder.decode(File(root,n).readBytes()).samples
  val spec=MatlabPowertrainSpec(700.0,7200.0,doubleArrayOf(4.38,2.86,1.92),2.85,.335,2300.0,7000.0,.018,.032,.075,.055,.22,1.08,.35,.68,144.0,2600.0)
  val loops=listOf(700,1400,2200,3200,4300,5500,6800,7200).flatMap{rpm->listOf(32,92).map{load->MatlabLoop(rpm.toDouble(),load/100.0,wav(String.format(java.util.Locale.ROOT,"rpm_%04d_load_%02d.wav",rpm,load)))}}
  return MatlabSoundBank("c63_w204_v6",48000,spec,loops,wav("afterfire_tipout_s12.wav"),(1..3).map{val name=String.format(java.util.Locale.ROOT,"shift_event_%02d_s12.wav",it);MatlabTransient(name,wav(name))})
 }
 private fun overlay(bank:MatlabSoundBank):MatlabSoundBank {
  val new=File(assets,LiveLoopVariantManifest.C63_ROOT)
  val v=LiveLoopVariantManifest.validate(File(new,"manifest.properties").readBytes(),File(root,"manifest.json").readBytes(),{File(root,it).readBytes()},{File(new,it).readBytes()})
  return LiveLoopBankOverlay.apply(bank,v)
 }
 private fun renderHash(bank:MatlabSoundBank):String {
  val renderer=MatlabStatefulBankRenderer(bank);val bytes=ByteBuffer.allocate(480000*4).order(ByteOrder.LITTLE_ENDIAN)
  repeat(500){val state=SoundState(it*.02,700.0,700.0/60*4,.32,.32,floatArrayOf(),false,.32,.32);for(x in renderer.render(state,960))bytes.putFloat(x)}
  return MessageDigest.getInstance("SHA-256").digest(bytes.array()).joinToString(""){String.format(java.util.Locale.ROOT,"%02x",it.toInt() and 255)}
 }
 @Test fun realOverlayKeepsReferenceObjectsHighLoopsAndEvents(){val original=original();val prior=original.loops.map{it.samples.copyOf()};val live=overlay(original);assertNotSame(original,live);assertSame(original.powertrain,live.powertrain);assertSame(original.afterfire,live.afterfire);assertSame(original.shiftEvents,live.shiftEvents)
  for(i in original.loops.indices){assertArrayEquals(prior[i],original.loops[i].samples,0f);if(original.loops[i].rpm>=2200)assertSame(original.loops[i],live.loops[i]) else assertNotSame(original.loops[i].samples,live.loops[i].samples)}
 }
 @Test fun normalRenderingCannotMutateFrozenReferencePcm(){val original=original();val live=overlay(original);assertNotEquals(renderHash(original),renderHash(live));assertEquals("12f079680eb3cca5f6a0fda36f39e3ee1df3e5a4d3fa562f11574e75b2f2e198",renderHash(original))}
}
