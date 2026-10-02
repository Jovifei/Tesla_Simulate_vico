package com.vico.simulator.sound

import android.content.res.AssetManager
import org.json.JSONObject

data class MatlabLoop(
    val rpm: Double,
    val load: Double,
    val samples: FloatArray,
)

data class MatlabTransient(
    val file: String,
    val samples: FloatArray,
)

data class MatlabSoundBank(
    val vehicleKey: String,
    val sampleRateHz: Int,
    val powertrain: MatlabPowertrainSpec,
    val loops: List<MatlabLoop>,
    val afterfire: FloatArray,
    val shiftEvents: List<MatlabTransient> = emptyList(),
) {
    val rpmLevels: DoubleArray = loops.map { it.rpm }.distinct().sorted().toDoubleArray()
    val loadLevels: DoubleArray = loops.map { it.load }.distinct().sorted().toDoubleArray()

    fun loop(rpm: Double, load: Double): MatlabLoop = loops.first {
        it.rpm == rpm && it.load == load
    }
}

object MatlabSoundBankLoader {
    fun load(assets: AssetManager, vehicleKey: String): MatlabSoundBank {
        val root = findRoot(assets, vehicleKey)
        val manifest = JSONObject(assets.open("$root/manifest.json").bufferedReader().use { it.readText() })
        require(manifest.getString("schema") in setOf("vico.matlab.soundbank.v1", "vico.s12.soundbank.v1"))
        val sampleRate = manifest.getInt("sample_rate_hz")
        require(sampleRate == 48000 || sampleRate == 96000)
        val ratiosJson = manifest.getJSONArray("gear_ratios")
        val ratios = DoubleArray(ratiosJson.length()) { ratiosJson.getDouble(it) }
        val spec = MatlabPowertrainSpec(
            idleRpm = manifest.getDouble("idle_rpm"),
            redlineRpm = manifest.getDouble("redline_rpm"),
            gearRatios = ratios,
            finalDrive = manifest.getDouble("final_drive"),
            wheelRadiusM = manifest.getDouble("wheel_radius_m"),
            launchRpm = manifest.getDouble("launch_rpm"),
            shiftRpm = manifest.getDouble("shift_rpm"),
            shiftAttackS = manifest.getDouble("shift_attack_s"),
            shiftHoldS = manifest.getDouble("shift_hold_s"),
            shiftRecoveryS = manifest.getDouble("shift_recovery_s"),
            shiftSettleS = manifest.getDouble("shift_settle_s"),
            shiftMinTorque = manifest.getDouble("shift_min_torque"),
            shiftReengageGain = manifest.getDouble("shift_reengage_gain"),
            minimumShiftIntervalS = manifest.getDouble("minimum_shift_interval_s"),
            downshiftRatio = manifest.getDouble("downshift_ratio"),
            speedCeilingKmh = manifest.getDouble("speed_ceiling_kmh"),
            afterfireMinimumRpm = manifest.getDouble("afterfire_minimum_rpm"),
        )
        val loopsJson = manifest.getJSONArray("loops")
        val loops = List(loopsJson.length()) { index ->
            val entry = loopsJson.getJSONObject(index)
            val decoded = FloatWavDecoder.decode(assets.open("$root/${entry.getString("file")}").use { it.readBytes() })
            require(decoded.sampleRateHz == sampleRate)
            MatlabLoop(entry.getDouble("rpm"), entry.getDouble("load"), decoded.samples)
        }
        val afterfireJson = manifest.getJSONObject("afterfire")
        val afterfire = FloatWavDecoder.decode(
            assets.open("$root/${afterfireJson.getString("file")}").use { it.readBytes() }
        )
        require(afterfire.sampleRateHz == sampleRate)
        val shiftEvents = if (manifest.has("shift_events")) {
            val entries = manifest.getJSONArray("shift_events")
            List(entries.length()) { index ->
                val entry = entries.getJSONObject(index)
                val decoded = FloatWavDecoder.decode(
                    assets.open("$root/${entry.getString("file")}").use { it.readBytes() }
                )
                require(decoded.sampleRateHz == sampleRate)
                MatlabTransient(entry.getString("file"), decoded.samples)
            }
        } else {
            emptyList()
        }
        if (manifest.getString("schema") == "vico.s12.soundbank.v1") {
            val contract = manifest.getJSONObject("audio_contract")
            require(contract.getInt("sample_rate_hz") == sampleRate)
            require(contract.getInt("channels") == 1)
            require(contract.getString("channel_layout") == "mono")
            require(shiftEvents.isNotEmpty())
        }
        return MatlabSoundBank(vehicleKey, sampleRate, spec, loops, afterfire.samples, shiftEvents)
    }

    private fun findRoot(assets: AssetManager, vehicleKey: String): String {
        val roots = listOf("s12_v10/$vehicleKey", "matlab_v6/$vehicleKey")
        return roots.firstOrNull { root ->
            runCatching { assets.open("$root/manifest.json").close() }.isSuccess
        } ?: error("No sound bank for $vehicleKey")
    }
}
