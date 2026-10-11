package com.vico.simulator.sound
import org.junit.Assert.*
import org.junit.Test
import java.io.File
class LiveLoopVariantTest {
 private val assets=File("app/src/main/assets").takeIf{it.isDirectory} ?: File("src/main/assets")
 private val original=File(assets,"s12_v10/c63_w204_v6")
 private val candidate=File(assets,"live_loop_variants/c63_low_rpm_preroll_v1")
 private fun read()=LiveLoopVariantManifest.validate(File(candidate,"manifest.properties").readBytes(),File(original,"manifest.json").readBytes(),{File(original,it).readBytes()},{File(candidate,it).readBytes()})
 @Test fun actualFourLoopsLoadWithPinnedIdentityAndUnchangedPeriod(){val x=read();assertEquals("c63_low_rpm_preroll_v1",x.variantId);assertEquals(4,x.replacements.size);assertEquals(setOf(700.0,1400.0),x.replacements.map{it.rpm}.toSet());for(e in x.replacements){assertEquals(17280,e.audio.samples.size);assertEquals(48000,e.audio.sampleRateHz);assertTrue(e.audio.samples.all{it.isFinite()})}}
 @Test fun registryNeverSelectsVariantForOtherVehicle(){assertEquals("c63_low_rpm_preroll_v1",LiveLoopVariantManifest.normalIdentity("c63_w204_v6"));for(v in listOf("hellcat_v6","ferrari_458","lfa","gtr_r35","supra_jza80"))assertEquals("legacy_unmodified",LiveLoopVariantManifest.normalIdentity(v))}
 @Test fun changedManifestFailsBeforeReadingAnyWave(){var reads=0;val bytes=File(candidate,"manifest.properties").readBytes()+byteArrayOf(32);assertThrows(IllegalArgumentException::class.java){LiveLoopVariantManifest.validate(bytes,File(original,"manifest.json").readBytes(),{reads++;byteArrayOf()},{reads++;byteArrayOf()})};assertEquals(0,reads)}
 @Test fun wrongBaselineManifestCannotActivateLiveVariant(){assertThrows(IllegalArgumentException::class.java){LiveLoopVariantManifest.validate(File(candidate,"manifest.properties").readBytes(),byteArrayOf(1),{File(original,it).readBytes()},{File(candidate,it).readBytes()})}}
 @Test fun changedOriginalOrCandidateWavFailClosed(){for(changeOld in listOf(true,false)){assertThrows(IllegalArgumentException::class.java){LiveLoopVariantManifest.validate(File(candidate,"manifest.properties").readBytes(),File(original,"manifest.json").readBytes(),{if(changeOld)byteArrayOf(0) else File(original,it).readBytes()},{if(!changeOld)byteArrayOf(0) else File(candidate,it).readBytes()})}}}
 @Test fun referenceWaveBytesRemainDifferentFromExplicitNewLoops(){val v=read();for(e in v.replacements){val old=File(original,e.file).readBytes();val new=File(candidate,e.file).readBytes();assertFalse(old.contentEquals(new));assertEquals(17280,FloatWavDecoder.decode(old).samples.size)}}
 @Test fun localeDoesNotChangeAssetNamesOrHashes(){val before=java.util.Locale.getDefault();try{java.util.Locale.setDefault(java.util.Locale("ar"));assertEquals(4,read().replacements.size)}finally{java.util.Locale.setDefault(before)}}
}
