package com.vico.simulator.web

import android.webkit.JavascriptInterface
import android.webkit.WebView
import com.vico.simulator.MainActivity

/**
 * JS <-> Kotlin 桥。HTML 侧 (bridge.js) 调用 window.AndroidBridge.*。
 * 所有方法在 WebKit JS 线程触发, 统一 marshal 到 UI 线程执行。
 */
class VicoBridge(private val activity: MainActivity, private val webView: WebView) {

    // ---- 导航 (原有) ----
    @JavascriptInterface
    fun navigate(route: String) {
        activity.runOnUiThread {
            android.util.Log.d("VicoNav", "navigate: $route")
            val file = when (route) {
                "dashboard" -> "screens/dashboard.html"
                "library" -> "screens/library.html"
                "settings" -> "screens/settings.html"
                "calibration" -> "screens/calibration.html"
                else -> return@runOnUiThread
            }
            activity.invalidateCalibrationPage()
            webView.loadUrl("file:///android_asset/$file")
        }
    }

    // ---- 音频引擎 ----
    @JavascriptInterface
    fun startAudio() = activity.runOnUiThread { activity.startAudio() }

    @JavascriptInterface
    fun stopAudio() = activity.runOnUiThread { activity.stopAudio() }

    @JavascriptInterface
    fun setS15Prototype(enabled:Boolean)=activity.runOnUiThread {activity.setS15Prototype(enabled)}
    @JavascriptInterface
    fun submitS15Feedback(assessment:String,notes:String)=activity.runOnUiThread{activity.submitS15Feedback(assessment,notes)}

    @JavascriptInterface
    fun startS13Review() = activity.runOnUiThread { activity.startS13Review() }

    @JavascriptInterface
    fun startS14Reference(label: String) = activity.runOnUiThread { activity.startS14Reference(label) }

    @JavascriptInterface
    fun startS14Controlled(number: Int) = activity.runOnUiThread { activity.startS14Controlled(number) }

    @JavascriptInterface
    fun nextS14Pair() = activity.runOnUiThread { activity.nextS14Pair() }

    @JavascriptInterface
    fun retryS14Pair() = activity.runOnUiThread { activity.retryS14Pair() }

    @JavascriptInterface
    fun submitS14Feedback(preference: String, notes: String) = activity.runOnUiThread { activity.submitS14Feedback(preference, notes) }

    @JavascriptInterface
    fun stopS13Review() = activity.runOnUiThread { activity.stopAudio() }

    @JavascriptInterface
    fun setProfile(key: String) = activity.runOnUiThread { activity.setProfile(key) }

    @JavascriptInterface
    fun previewProfile(key: String) = activity.runOnUiThread { activity.previewProfile(key) }

    @JavascriptInterface
    fun setVehicle(key: String) = activity.runOnUiThread { activity.setVehicle(key) }

    @JavascriptInterface
    fun previewVehicle(key: String) = activity.runOnUiThread { activity.previewVehicle(key) }

    @JavascriptInterface
    fun setMasterVol(v: Float) = activity.runOnUiThread { activity.setMasterVol(v) }

    @JavascriptInterface
    fun setMuted(on: Boolean) = activity.runOnUiThread { activity.setMuted(on) }

    @JavascriptInterface
    fun setLanguage(key: String) = activity.runOnUiThread { activity.setLanguage(key) }

    @JavascriptInterface
    fun setOutputMode(mode: String) = activity.runOnUiThread { activity.setOutputMode(mode) }

    @JavascriptInterface
    fun selectOutputDevice(id: Int) = activity.runOnUiThread { activity.selectOutputDevice(id) }

    @JavascriptInterface
    fun getAudioOutputsJson(): String = activity.getAudioOutputsJson()

    // ---- 调试 / 数据 ----
    @JavascriptInterface
    fun exportCsv() = activity.runOnUiThread { activity.exportCsv() }

    @JavascriptInterface
    fun resetConfig() = activity.runOnUiThread { activity.resetConfig() }

    @JavascriptInterface
    fun resetAll() = activity.runOnUiThread { activity.resetAll() }

    @JavascriptInterface
    fun startRecording() = activity.runOnUiThread { activity.startRecording() }

    @JavascriptInterface
    fun stopRecording() = activity.runOnUiThread { activity.stopRecording() }

    // ---- 演示模式 ----
    @JavascriptInterface
    fun setDemoMode(on: Boolean) = activity.runOnUiThread { activity.setDemoMode(on) }

    @JavascriptInterface
    fun setDemoScenario(key: String) = activity.runOnUiThread { activity.setDemoScenario(key) }

    // ---- 校准 ----
    private fun calibrationCommand(action: () -> Unit) {
        val epoch = activity.calibrationPageEpoch
        activity.runOnUiThread {
            if (activity.acceptsCalibrationCommand(epoch)) action()
        }
    }

    @JavascriptInterface
    fun beginCalibration(session: String) = calibrationCommand { activity.beginCalibration(session) }

    @JavascriptInterface
    fun finishCalibration(session: String) = calibrationCommand { activity.finishCalibration(session) }

    @JavascriptInterface
    fun cancelCalibration(session: String) = calibrationCommand { activity.cancelCalibration(session) }

    @JavascriptInterface
    fun resetCalibration() = activity.runOnUiThread { activity.resetCalibration() }

    @JavascriptInterface
    fun getStateJson(): String = activity.getStateJson()
}
