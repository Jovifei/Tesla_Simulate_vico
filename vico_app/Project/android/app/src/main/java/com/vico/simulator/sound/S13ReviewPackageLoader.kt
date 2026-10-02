package com.vico.simulator.sound

import android.content.res.AssetManager
import org.json.JSONArray
import org.json.JSONObject

data class S13ReviewPackage(
    val vehicleKey: String,
    val sourceCommit: String,
    val traceSha256: String,
    val bankManifestSha256: String,
    val fixedVehicleGain: Double,
    val trace: S13TraceCursor,
    val events: List<S13EventPlacement>,
) {
    val eventScheduleSha256: String by lazy {
        val canonical = events.sortedBy { it.startFrame }.joinToString("\n") { placement ->
            val event = placement.binding
            listOf(
                event.id,
                event.kind,
                event.assetPath,
                event.assetSha256,
                event.sourceFrame,
                event.cropStartFrame,
                event.triggerOffsetFrames,
                event.sampleCount,
            ).joinToString("|")
        }
        S13ReviewContract.sha256(canonical.toByteArray(Charsets.UTF_8))
    }

    val captureBinding: S13CaptureBinding
        get() = S13CaptureBinding(
            vehicleKey, sourceCommit, traceSha256, bankManifestSha256, eventScheduleSha256,
        )
}

object S13ReviewPackageLoader {
    fun load(assets: AssetManager, vehicleKey: String): S13ReviewPackage {
        require(vehicleKey.matches(Regex("[a-z0-9_]+"))) { "Invalid vehicle key" }
        val sidecarBytes = assets.open("s13_review_v1/$vehicleKey.json").use { it.readBytes() }
        val sidecar = JSONObject(String(sidecarBytes, Charsets.UTF_8))
        val bankPrefix = "s12_v10/$vehicleKey"
        val fileBytes = linkedMapOf<String, ByteArray>()
        val decodedFrames = linkedMapOf<String, Int>()
        val hashes = sidecar.getJSONObject("bank_assets_sha256")
        val names = jsonKeys(hashes)
        for (name in names) {
            require(isFileName(name)) { "Unsafe bank filename" }
            val bytes = assets.open("$bankPrefix/$name").use { it.readBytes() }
            val wav = FloatWavDecoder.decode(bytes)
            require(wav.sampleRateHz == S13ReviewContract.SAMPLE_RATE)
            require(wav.samples.all { it.isFinite() })
            fileBytes[name] = bytes
            decodedFrames[name] = wav.samples.size
        }
        val traceBytes = assets.open("$bankPrefix/common_input_trace.json").use { it.readBytes() }
        val manifestBytes = assets.open("$bankPrefix/manifest.json").use { it.readBytes() }
        return parse(vehicleKey, sidecarBytes, traceBytes, manifestBytes, fileBytes, decodedFrames)
    }

    internal fun parse(
        expectedVehicleKey: String,
        sidecarBytes: ByteArray,
        traceBytes: ByteArray,
        manifestBytes: ByteArray,
        bankAssetBytes: Map<String, ByteArray>,
        decodedFrames: Map<String, Int>,
    ): S13ReviewPackage {
        val sidecar = JSONObject(String(sidecarBytes, Charsets.UTF_8))
        require(sidecar.getString("schema") == "vico.s13.review_sidecar.v1")
        require(sidecar.getString("vehicle_key") == expectedVehicleKey)
        require(sidecar.getInt("sample_rate_hz") == S13ReviewContract.SAMPLE_RATE)
        require(sidecar.getInt("channels") == 1)
        require(sidecar.getDouble("duration_s") == 30.0)
        require(sidecar.getInt("total_frames") == S13ReviewContract.TOTAL_FRAMES)
        require(sidecar.getString("control_interpolation") == "linear_per_audio_frame")
        require(sidecar.getBoolean("gain_is_embedded_in_assets"))
        require(sidecar.getString("audio_pcm_verification") == "EXACT_FLOAT32_MATCH")

        val bankPrefix = "s12_v10/$expectedVehicleKey/"
        val trace = sidecar.getJSONObject("trace")
        val tracePath = trace.getString("asset_path")
        require(tracePath == "${bankPrefix}common_input_trace.json")
        val traceSha = trace.getString("sha256")
        S13ReviewContract.requireSha256(traceBytes, traceSha)

        val manifestBinding = sidecar.getJSONObject("bank_manifest")
        require(manifestBinding.getString("asset_path") == "${bankPrefix}manifest.json")
        val manifestSha = manifestBinding.getString("sha256")
        S13ReviewContract.requireSha256(manifestBytes, manifestSha)
        val manifest = JSONObject(String(manifestBytes, Charsets.UTF_8))
        require(manifest.getString("schema") == "vico.s12.soundbank.v1")
        require(manifest.getString("vehicle_key") == expectedVehicleKey)
        val sourceCommit = sidecar.getString("source_commit")
        require(manifest.getString("source_commit") == sourceCommit)
        require(manifest.getInt("sample_rate_hz") == S13ReviewContract.SAMPLE_RATE)
        require(kotlin.math.abs(
            manifest.getDouble("fixed_vehicle_gain") - sidecar.getDouble("fixed_vehicle_gain"),
        ) < 1e-12)

        val manifestTrace = manifest.getJSONObject("common_input_trace")
        require(manifestTrace.getString("file") == "common_input_trace.json")
        require(manifestTrace.getDouble("duration_s") == 30.0)
        require(manifestTrace.getDouble("sample_period_s") == 0.02)
        val traceJson = JSONObject(String(traceBytes, Charsets.UTF_8))
        require(traceJson.getString("schema") == "vico.s12.common_input_trace.v1")
        require(traceJson.getDouble("sample_period_s") == 0.02)
        require(trace.getInt("point_count") == S13ReviewContract.TRACE_POINTS)
        val expectedFields = listOf("time_s", "rpm", "load", "throttle", "acceleration_mps2")
        require(jsonStrings(traceJson.getJSONArray("fields")) == expectedFields)
        require(jsonStrings(manifestTrace.getJSONArray("fields")) == expectedFields)
        val pointsJson = traceJson.getJSONArray("points")
        require(pointsJson.length() == S13ReviewContract.TRACE_POINTS)
        val points = List(pointsJson.length()) { index ->
            val point = pointsJson.getJSONObject(index)
            S13TracePoint(
                point.getDouble("time_s"),
                point.getDouble("rpm"),
                point.getDouble("load"),
                point.getDouble("throttle"),
                point.getDouble("acceleration_mps2"),
            )
        }
        val cursor = S13TraceCursor(points)

        val expectedAssets = linkedSetOf<String>()
        val loops = manifest.getJSONArray("loops")
        repeat(loops.length()) { expectedAssets += loops.getJSONObject(it).getString("file") }
        expectedAssets += manifest.getJSONObject("afterfire").getString("file")
        val shiftManifest = manifest.getJSONArray("shift_events")
        repeat(shiftManifest.length()) { expectedAssets += shiftManifest.getJSONObject(it).getString("file") }
        val assetHashes = sidecar.getJSONObject("bank_assets_sha256")
        require(jsonKeys(assetHashes).toSet() == expectedAssets)
        require(bankAssetBytes.keys == expectedAssets && decodedFrames.keys == expectedAssets)
        for (name in expectedAssets) {
            val bytes = requireNotNull(bankAssetBytes[name])
            S13ReviewContract.requireSha256(bytes, assetHashes.getString(name))
        }

        val manifestShifts = linkedMapOf<String, JSONObject>()
        repeat(shiftManifest.length()) { index ->
            val event = shiftManifest.getJSONObject(index)
            manifestShifts[event.getString("file")] = event
        }
        val eventsJson = sidecar.getJSONArray("events")
        require(eventsJson.length() == shiftManifest.length() + 1)
        val eventIds = hashSetOf<String>()
        val events = List(eventsJson.length()) { index ->
            val event = eventsJson.getJSONObject(index)
            val assetPath = event.getString("asset_path")
            require(assetPath.startsWith(bankPrefix) && isSafeAssetPath(assetPath))
            val file = assetPath.removePrefix(bankPrefix)
            require(file in expectedAssets && event.getString("asset_sha256") == assetHashes.getString(file))
            val kind = event.getString("kind")
            if (kind == "shift") {
                val source = requireNotNull(manifestShifts[file]) { "Shift event is absent from bank manifest" }
                require(kotlin.math.abs(source.getDouble("time_s") - event.getDouble("source_time_s")) <=
                    0.500001 / S13ReviewContract.SAMPLE_RATE)
            } else {
                require(kind == "afterfire" && manifest.getJSONObject("afterfire").getString("file") == file)
            }
            val binding = S13EventBinding(
                id = event.getString("id"),
                kind = kind,
                assetPath = assetPath,
                assetSha256 = event.getString("asset_sha256"),
                traceSha256 = traceSha,
                sourceDomain = event.getString("source_domain"),
                sourceTimeS = event.getDouble("source_time_s"),
                sourceFrame = event.getInt("source_frame"),
                cropStartFrame = event.getInt("crop_start_frame"),
                triggerOffsetFrames = event.getInt("trigger_offset_frames"),
                sampleCount = event.getInt("samples"),
            )
            require(eventIds.add(binding.id)) { "Duplicate event ID" }
            binding.validate(
                traceBytes,
                requireNotNull(bankAssetBytes[file]),
                requireNotNull(decodedFrames[file]),
            )
        }
        require(events.count { it.binding.kind == "afterfire" } == 1)
        require(events.count { it.binding.kind == "shift" } == shiftManifest.length())
        return S13ReviewPackage(
            expectedVehicleKey,
            sourceCommit,
            traceSha,
            manifestSha,
            manifest.getDouble("fixed_vehicle_gain"),
            cursor,
            events.sortedBy { it.startFrame },
        )
    }

    private fun jsonKeys(value: JSONObject): List<String> {
        val keys = value.keys()
        val result = mutableListOf<String>()
        while (keys.hasNext()) result += keys.next()
        return result
    }

    private fun jsonStrings(value: JSONArray): List<String> =
        List(value.length()) { value.getString(it) }

    private fun isFileName(value: String): Boolean =
        value.isNotBlank() && '/' !in value && '\\' !in value && ':' !in value &&
            value != "." && value != ".."

    private fun isSafeAssetPath(value: String): Boolean =
        '\\' !in value && ':' !in value &&
            value.split('/').none { it.isEmpty() || it == "." || it == ".." }
}
