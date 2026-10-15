package com.vico.simulator.csv

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import com.vico.simulator.sensor.InputDiagnostics

/**
 * 调试轨迹 CSV 缓冲 + 导出至 Downloads/Vico（PRD FR-07 / AC-05）。
 * 通过 MediaStore.Downloads，无需存储运行时权限（API 29+）。
 */
class CsvExporter {

    private val rows = ArrayList<String>()

    val sampleCount: Int
        get() = synchronized(rows) { rows.size }

    fun start() {
        synchronized(rows) { rows.clear() }
    }

    fun append(
        timeS: Double,
        speedKmh: Double,
        accelMps2: Double,
        rpm: Double,
        freqHz: Double,
        profileLabel: String,
        diagnostics: InputDiagnostics,
    ) {
        synchronized(rows) {
            rows.add(CsvTraceFormat.row(timeS, speedKmh, accelMps2, rpm, freqHz, profileLabel, diagnostics))
        }
    }

    fun clear() {
        synchronized(rows) { rows.clear() }
    }

    fun export(context: Context): Uri? {
        val snapshot: List<String>
        synchronized(rows) {
            if (rows.isEmpty()) return null
            snapshot = ArrayList(rows)
        }
        val sb = StringBuilder()
        sb.append(CsvTraceFormat.HEADER).append('\n')
        for (r in snapshot) sb.append(r).append('\n')
        val data = sb.toString().toByteArray(Charsets.UTF_8)
        val name = "vico-trace-${System.currentTimeMillis()}.csv"

        val resolver = context.contentResolver
        val collection = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
            MediaStore.Downloads.EXTERNAL_CONTENT_URI
        else
            MediaStore.Files.getContentUri("external")

        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, name)
            put(MediaStore.MediaColumns.MIME_TYPE, "text/csv")
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                put(MediaStore.MediaColumns.RELATIVE_PATH, "Download/Vico")
                put(MediaStore.MediaColumns.IS_PENDING, 1)
            }
        }
        val uri = resolver.insert(collection, values) ?: return null
        try {
            resolver.openOutputStream(uri)?.use { it.write(data) } ?: run {
                resolver.delete(uri, null, null)
                return null
            }
        } catch (e: Exception) {
            resolver.delete(uri, null, null)
            return null
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            values.clear()
            values.put(MediaStore.MediaColumns.IS_PENDING, 0)
            resolver.update(uri, values, null, null)
        }
        return uri
    }
}
