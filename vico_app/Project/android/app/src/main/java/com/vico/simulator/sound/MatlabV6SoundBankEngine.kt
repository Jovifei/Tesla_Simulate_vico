package com.vico.simulator.sound

import android.content.res.AssetManager
import kotlin.math.max

class MatlabV6SoundBankEngine(private val assets: AssetManager) {
    private val cache = mutableMapOf<String, MatlabSoundBank>()
    private var bank: MatlabSoundBank? = null
    private var controller: MatlabPowertrainController? = null
    private var renderer: MatlabStatefulBankRenderer? = null
    @Volatile var prototypeEnabled: Boolean = false
        private set
    private var prototype = com.vico.simulator.sound.s15.C63RuntimeRenderer(fixedHeadroom=true)
    private val renderTimes=LongArray(4096)
    private val completedAttempts=BooleanArray(4096)
    private val renderInputs=DoubleArray(4096*6)
    @Volatile private var inputCount=0
    @Volatile private var renderCount=0
    private val sessionTiming=SessionTiming()
    fun prototypeTimingJson():String {
        val count=renderCount;val size=minOf(count,renderTimes.size);val first=if(count>renderTimes.size) count%renderTimes.size else 0
        val times=(0 until size).map{renderTimes[(first+it)%renderTimes.size]}.filter{it>0}.sorted()
        return org.json.JSONObject().put("blocks",renderCount).put("frames",prototype.frames).put("pre_output_peak",prototype.peak)
            .put("candidate_id",prototype.candidateId).put("headroom_scalar",com.vico.simulator.sound.s15.C63HeadroomProfile.SCALAR)
            .put("raw_a_peak",prototype.rawPeak).put("whole_session_attempts",sessionTiming.count)
            .put("whole_session_max_compute_ns",sessionTiming.maxNs).put("whole_session_deadline_misses",sessionTiming.deadlineMisses)
            .put("whole_session_p50_compute_ns_upper",sessionTiming.percentile(50) ?: org.json.JSONObject.NULL)
            .put("whole_session_p95_compute_ns_upper",sessionTiming.percentile(95) ?: org.json.JSONObject.NULL)
            .put("whole_session_p99_compute_ns_upper",sessionTiming.percentile(99) ?: org.json.JSONObject.NULL)
            .put("peak_domain","POST_FIXED_OUTPUT_PRE_APP_ENVELOPES").put("timing_window_attempts",size)
            .put("failed_attempts_in_window",(0 until size).count{!completedAttempts[(first+it)%renderTimes.size]})
            .put("p50_compute_ns",if(times.isEmpty())org.json.JSONObject.NULL else times[(times.size-1)*50/100])
            .put("p95_compute_ns",if(times.isEmpty())org.json.JSONObject.NULL else times[(times.size-1)*95/100])
            .put("p99_compute_ns",if(times.isEmpty()) org.json.JSONObject.NULL else times[(times.size-1)*99/100])
            .put("max_compute_ns",times.lastOrNull() ?: org.json.JSONObject.NULL).put("block_frames",960).put("sample_rate_hz",48000).toString()
    }
    fun prototypeInputsJson():String {
        val rows=org.json.JSONArray()
        val count=inputCount;val size=minOf(count,4096);val first=if(count>4096)count%4096 else 0
        for(n in 0 until size) {
            val idx=((first+n)%4096)*6
            val row=org.json.JSONArray();for(k in 0 until 6)row.put(renderInputs[idx+k]);rows.put(row)
        }
        return org.json.JSONObject().put("start_attempt",maxOf(0,count-size)).put("fields",org.json.JSONArray(listOf("time_s","rpm","load","throttle","shift","frames"))).put("points",rows).toString()
    }

    fun setPrototype(enabled: Boolean): Boolean {
        if(enabled && bank?.vehicleKey != "c63_w204_v6") return false
        prototypeEnabled=enabled
        prototype=com.vico.simulator.sound.s15.C63RuntimeRenderer(fixedHeadroom=true)
        renderTimes.fill(0);renderCount=0;inputCount=0;sessionTiming.clear()
        return true
    }

    fun setVehicle(vehicleKey: String): Boolean {
        val loaded = try {
            cache.getOrPut(vehicleKey) { MatlabSoundBankLoader.load(assets, vehicleKey) }
        } catch (_: Exception) {
            return false
        }
        if (bank?.vehicleKey != vehicleKey) {
            prototypeEnabled=false
            bank = loaded
            controller = MatlabPowertrainController(loaded.powertrain)
            renderer = MatlabStatefulBankRenderer(loaded)
        }
        return true
    }

    fun mapPoint(point: DrivePoint): SoundState {
        requireNotNull(bank) { "MATLAB sound bank is not selected" }
        val state = requireNotNull(controller).update(
            point.timeS,
            point.speedKmh,
            point.accelMps2,
            point.throttle.coerceIn(0.0, 1.0),
        )
        return SoundState(
            timeS = point.timeS,
            rpm = state.rpm,
            frequencyHz = state.rpm / 60.0 * 4.0,
            amplitude = max(0.08, state.load),
            brightness = state.load,
            harmonics = floatArrayOf(),
            muted = point.speedKmh >= 148.0,
            throttle = point.throttle,
            load = state.load,
            braking = point.brake,
            gear = state.gear,
            shiftGain = state.torqueGain,
            afterfireTrigger = state.afterfireTrigger,
            shiftTrigger = state.shiftTrigger,
        )
    }

    fun renderState(state: SoundState, frameCount: Int): FloatArray {
        if (prototypeEnabled && bank?.vehicleKey == "c63_w204_v6") {
            val start=System.nanoTime()
            val idx=(inputCount%4096)*6
            renderInputs[idx]=state.timeS;renderInputs[idx+1]=state.rpm;renderInputs[idx+2]=state.load
            renderInputs[idx+3]=state.throttle;renderInputs[idx+4]=if(state.shiftTrigger)1.0 else 0.0;renderInputs[idx+5]=frameCount.toDouble()
            inputCount++
            var complete=false
            try {val result=prototype.render(state,frameCount);complete=true;return result}
            finally {val slot=renderCount%renderTimes.size;val elapsed=System.nanoTime()-start;renderTimes[slot]=elapsed;sessionTiming.record(elapsed);completedAttempts[slot]=complete;renderCount++}
        }
        return renderer?.render(state,frameCount) ?: FloatArray(frameCount)
    }

    fun sampleRateHz(): Int = bank?.sampleRateHz ?: 48000

    fun renderStats(): S13MixSnapshot? = renderer?.mixStats()

    fun newS13ReviewSession(vehicleKey: String): S13ReviewSession {
        require(bank?.vehicleKey == vehicleKey || setVehicle(vehicleKey)) {
            "Unable to load S13 bank for $vehicleKey"
        }
        val selectedBank = requireNotNull(bank)
        val reviewPackage = S13ReviewPackageLoader.load(assets, vehicleKey)
        return S13ReviewSession(selectedBank, reviewPackage)
    }
}
