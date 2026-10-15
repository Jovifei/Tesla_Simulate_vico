package com.vico.simulator.sound

import java.security.MessageDigest
import kotlin.math.abs
import kotlin.math.pow

class ValidatedLiveLoop internal constructor(val rpm:Double,val load:Double,val file:String,val audio:FloatWav)
class ValidatedLiveLoopVariant internal constructor(val variantId:String,val vehicleKey:String,val replacements:List<ValidatedLiveLoop>)

/** Fixed ASCII contract, not a general Properties parser. No escapes, duplicate or unknown keys. */
object LiveLoopVariantManifest {
    const val LEGACY_ID="legacy_unmodified"
    const val C63_ID="c63_low_rpm_preroll_v1"
    const val C63_ROOT="live_loop_variants/c63_low_rpm_preroll_v1"
    const val MANIFEST_SHA256="f26d7ae6736af106e6cbb38c2ce6fdb097ae86d39f23c3f5f70a46af6a72de91"
    private const val REFERENCE_MANIFEST_SHA256="7a03686ce671562fabd6f5160ce6fe6d2e04887e84d89a0ae4f3594bfb7d8869"
    fun normalIdentity(vehicleKey:String)=if(vehicleKey=="c63_w204_v6")C63_ID else LEGACY_ID
    private fun sha(bytes:ByteArray)=MessageDigest.getInstance("SHA-256").digest(bytes).joinToString(""){String.format(java.util.Locale.ROOT,"%02x",it.toInt() and 255)}

    fun validate(manifest:ByteArray,referenceManifest:ByteArray,
                 readReference:(String)->ByteArray,readCandidate:(String)->ByteArray):ValidatedLiveLoopVariant {
        require(manifest.size in 1..8192 && sha(manifest)==MANIFEST_SHA256){"Live loop manifest identity mismatch"}
        require(sha(referenceManifest)==REFERENCE_MANIFEST_SHA256){"Original S12 reference identity mismatch"}
        require(manifest.all{it==10.toByte() || (it.toInt() and 255) in 32..126}){"Manifest must be canonical ASCII/LF"}
        val values=linkedMapOf<String,String>()
        for(line in manifest.toString(Charsets.US_ASCII).lineSequence()){
            if(line.isEmpty())continue
            val at=line.indexOf('=');require(at>0&&line.indexOf('=',at+1)<0)
            val key=line.substring(0,at);val value=line.substring(at+1)
            require(key==key.trim()&&value==value.trim()&&!key.contains('\\')&&!value.contains('\\')&&values.put(key,value)==null)
        }
        val header=setOf("schema","variant_id","vehicle_key","sample_rate_hz","baseline_manifest_sha256","fixed_vehicle_gain","peak_limit_dbfs","loop_count")
        val fields=setOf("rpm","load","file","samples","baseline_wav_sha256","candidate_wav_sha256")
        val expected=header+(0..3).flatMap{index->fields.map{"loop.$index.$it"}}
        require(values.keys==expected.toSet()){"Unknown/missing live loop fields"}
        require(values["schema"]=="vico.live_loop_variant.v1"&&values["variant_id"]==C63_ID&&values["vehicle_key"]=="c63_w204_v6")
        require(values["sample_rate_hz"]=="48000"&&values["loop_count"]=="4")
        require(values["baseline_manifest_sha256"]==REFERENCE_MANIFEST_SHA256)
        require(values["fixed_vehicle_gain"]?.toDoubleOrNull()==3.7075542301539652)
        require(values["peak_limit_dbfs"]?.toDoubleOrNull()==-1.5)
        val seen=mutableSetOf<Pair<Double,Double>>()
        val replacements=(0..3).map { index ->
            fun value(key:String)=requireNotNull(values["loop.$index.$key"])
            val rpm=value("rpm").toDouble();val load=value("load").toDouble();val file=value("file")
            require(rpm in setOf(700.0,1400.0)&&load in setOf(.32,.92)&&seen.add(rpm to load))
            require(file==String.format(java.util.Locale.ROOT,"rpm_%04d_load_%02d.wav",rpm.toInt(),(load*100).toInt()))
            require(value("samples")=="17280")
            val old=readReference(file);val new=readCandidate(file)
            require(old.size in 44..200000 && new.size in 44..200000)
            require(sha(old)==value("baseline_wav_sha256")){"Original loop identity mismatch: $file"}
            require(sha(new)==value("candidate_wav_sha256")){"Live loop identity mismatch: $file"}
            val reference=FloatWavDecoder.decode(old);val candidate=FloatWavDecoder.decode(new)
            require(reference.sampleRateHz==48000&&candidate.sampleRateHz==48000&&reference.samples.size==17280&&candidate.samples.size==17280)
            require(reference.samples.all{it.isFinite()}&&candidate.samples.all{it.isFinite()&&abs(it.toDouble())<=10.0.pow(-1.5/20.0)+1e-7})
            ValidatedLiveLoop(rpm,load,file,candidate)
        }
        require(seen==setOf(700.0 to .32,700.0 to .92,1400.0 to .32,1400.0 to .92))
        return ValidatedLiveLoopVariant(C63_ID,"c63_w204_v6",replacements)
    }
}
