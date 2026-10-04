package com.vico.simulator

import android.annotation.SuppressLint
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.vico.simulator.csv.CsvExporter
import com.vico.simulator.audio.AudioOutputCategory
import com.vico.simulator.audio.AudioOutputDevice
import com.vico.simulator.logging.*
import com.vico.simulator.sensor.RawInputObserver
import com.vico.simulator.sensor.SpeedAccuracy
import com.vico.simulator.sensor.VehicleMountAxis
import com.vico.simulator.sensor.VehicleMountingSession
import com.vico.simulator.sensor.ImuQuality
import com.vico.simulator.sensor.hasPortraitNaturalOrientation
import com.vico.simulator.sensor.InputQualityPolicy
import com.vico.simulator.sensor.InputContinuityTracker
import com.vico.simulator.sensor.InputDiagnostics
import com.vico.simulator.sensor.SensorInputSnapshot
import com.vico.simulator.sensor.CalibrationSession
import com.vico.simulator.sensor.SensorProvider
import com.vico.simulator.sound.AudioEngine
import com.vico.simulator.sound.DriveInputControl
import com.vico.simulator.sound.DriveInputSource
import com.vico.simulator.sound.SoundState
import com.vico.simulator.sound.DrivePoint
import com.vico.simulator.sound.SoundProfile
import com.vico.simulator.sound.S14ReferenceSession
import com.vico.simulator.sound.S14TrialCoordinator
import com.vico.simulator.sound.S14CallbackEpoch
import com.vico.simulator.sound.S14CompletedCapture
import com.vico.simulator.sound.S14OutputConditions
import com.vico.simulator.state.VehicleSelectionState
import com.vico.simulator.vehicle.CurrentVehicleCatalog
import com.vico.simulator.web.VicoBridge
import java.io.File
import org.json.JSONObject
import java.util.Locale

/**
 * 单 Activity 宿主: WebView(Stitch 1:1 UI) + 传感器管线 + 声浪模型 + AudioTrack + CSV。
 * 传感器循环 ~20Hz: DrivePoint -> SoundModel.mapPoint -> AudioEngine + CsvExporter + JS push。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var sensorProvider: SensorProvider
    private lateinit var audioEngine: AudioEngine
    private lateinit var csvExporter: CsvExporter
    private val handler = Handler(Looper.getMainLooper())

    @Volatile private var character: SoundProfile = SoundProfile.DEFAULT
    @Volatile private var audioRunning: Boolean = false
    @Volatile private var s13ReviewActive: Boolean = false
    @Volatile private var s13ReviewVehicleKey: String? = null
    @Volatile private var s14ReferenceLabel: String? = null
    @Volatile private var reviewExportInProgress = false
    private val s14 = S14TrialCoordinator()
    private val playbackEpoch = S14CallbackEpoch()
    private var previewRestore: Runnable? = null
    private var activityDestroyed = false
    private var s14PairId = "s14-" + System.currentTimeMillis()
    private var s14PairIndex = 0
    private var s14Controlled = false
    private var s14Revealed = false
    private var s14FeedbackSaving = false
    private var s14Frames = 0
    private var s14Status = "IDLE"
    @Volatile private var s14StateJson = "{\"state\":\"IDLE\",\"frames\":0,\"busy\":false,\"pair_index\":0,\"pair_matched\":false,\"first_done\":false,\"second_done\":false,\"revealed\":false}"
    private val s14Trials = linkedMapOf<String, JSONObject>()
    @Volatile private var recording: Boolean = false
    @Volatile private var previewUntilMs: Long = 0L
    @Volatile private var masterVol: Float = 1.0f
    @Volatile private var muted: Boolean = false
    @Volatile private var language: String = "zh"
    @Volatile private var demoScenario: String = "stop"
    private var s15SmokeInProgress=false
    @Volatile private var s15PreparationEpoch=0L
    @Volatile private var s15Preparing=false
    private var s15LastRun:String?=null
    private var s15StopReason="NOT_RECORDED"
    @Volatile private var selectedVehicleName: String = "Mercedes-Benz W204 C63 AMG V6.3"
    @Volatile private var vehicleName: String = "Mercedes-Benz W204 C63 AMG V6.3"
    @Volatile private var previewVehicleKey: String? = null
    @Volatile private var outputMode: String = "speaker"
    @Volatile private var outputLabel: String = ""
    @Volatile private var requestedOutputId: Int? = null
    @Volatile private var outputDevices: List<AudioOutputDevice> = emptyList()
    private var activeVehicleKey: String = CurrentVehicleCatalog.defaultKey
    private val vehicleState = VehicleSelectionState(CurrentVehicleCatalog.defaultKey)
    private var lastSpeedKmh = 0.0
    private var lastAccelMps2 = 0.0
    private var lastGear = 1
    @Volatile var calibrationPageEpoch = 0L
        private set
    private var calibrationPageActive = false
    @Volatile private var dashboardPageActive = false
    private var calibrationResumed = false
    @Volatile private var lastInputSnapshot = SensorInputSnapshot()
    private val inputQualityPolicy = InputQualityPolicy()
    private val inputContinuity = InputContinuityTracker()
    private var controlFrameSequence = 0L
    private val uiFrames = UiFrameLedger()
    private lateinit var testLogOwner: SessionRecordingCoordinator
    private lateinit var testLog: SessionLogAdapter
    private val testLogRoot by lazy { File(filesDir, "test-sessions") }
    private val logIo = java.util.concurrent.Executors.newSingleThreadExecutor { task -> Thread(task, "vico-log-files").apply { isDaemon = true } }
    @Volatile private var cachedApkIdentity: String? = null
    @Volatile private var displayUnitCode = 0
    private var testLogGeneration = 0L
    private var testLogPlaybackId = 0L
    private var testLogFirstFrameId = 0L
    @Volatile private var stoppingTestLog = false
    private var testLogWaitsForAudio = false
    private var testLogFailure = false
    private var testLogStopCause = 5
    private var audioDiagnosticDropped = 0L
    private var testLogExporting = false
    private var pendingTestLogExport: File? = null
    private var recoveredTestLog: File? = null
    private var lastLogPhase: SessionRecordingCoordinator.Phase? = null
    @Volatile private var lastQueuedLogStatus: SessionRecordingCoordinator.Snapshot? = null
    private val TEST_LOG_EXPORT_REQUEST = 6104
    @Volatile private var mounting = VehicleMountingSession()
    private val mountingFrameConfirmed: Boolean get() = mounting.trusted
    @Volatile private var naturalMountDiagramSupported = false
    @Volatile private var mountingRequestRevision = 0L
    @Volatile private var mountingRequestResult = "IDLE"
    private var startMs: Long = 0L
    private val prefs by lazy { getSharedPreferences("vico_state", MODE_PRIVATE) }
    private val audioDeviceCallback = object : AudioDeviceCallback() {
        override fun onAudioDevicesAdded(addedDevices: Array<out AudioDeviceInfo>) {
            refreshOutputDevices()
        }

        override fun onAudioDevicesRemoved(removedDevices: Array<out AudioDeviceInfo>) {
            refreshOutputDevices()
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webview)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            allowFileAccess = true
            allowContentAccess = true
            mediaPlaybackRequiresUserGesture = false
            loadWithOverviewMode = true
            useWideViewPort = true
            cacheMode = android.webkit.WebSettings.LOAD_NO_CACHE
        }
        webView.webChromeClient = WebChromeClient()

        audioEngine = AudioEngine(this).also { engine ->
            engine.onS15Finished={owner,receipt->runOnUiThread {
                if(!activityDestroyed && owner==engine.playbackIdentity() && !s15SmokeInProgress)
                    s15LastRun=JSONObject(receipt).put("stop_reason",if(engine.lastAudioError!=null)"AUDIO_FAILURE" else s15StopReason).toString()
            }}
            engine.setMasterVol(masterVol)
            engine.onReviewFinished = { complete, error ->
                runOnUiThread { finishS13Review(complete, error) }
            }
            engine.onAudioFailure = { owner,error -> runOnUiThread {
                if(!activityDestroyed && owner==engine.playbackIdentity()) {
                    audioRunning=false;vehicleState.stopEngine();pushUiState()
                    toast("音频安全停止：$error")
                    if(!s15SmokeInProgress) handler.postDelayed({
                        if(!activityDestroyed && owner==engine.playbackIdentity() && !audioRunning && !s14.busy) {
                            engine.setS15Prototype(false);pushUiState()
                        }
                    },100L)
                }
            } }
            engine.onS14Finished = { capture -> runOnUiThread { finishS14Reference(capture) } }
            engine.onS14Progress = { ticket, frames, phase ->
                runOnUiThread {
                    if (!activityDestroyed && s14.owns(ticket) && s14.state in setOf(S14TrialCoordinator.State.PLAYING, S14TrialCoordinator.State.DRAINING)) {
                        s14Frames = frames
                        s14Status = phase
                        if (phase == "DRAINING") s14.advance(ticket, S14TrialCoordinator.State.DRAINING)
                        pushUiState()
                    }
                }
            }
        }
        getSystemService(android.media.AudioManager::class.java)
            .registerAudioDeviceCallback(audioDeviceCallback, handler)
        csvExporter = CsvExporter()
        testLogOwner = SessionRecordingCoordinator(testLogRoot, onStatus = status@ { update ->
            val previous = lastQueuedLogStatus
            if(previous?.generation==update.generation && previous.phase==update.phase)return@status
            lastQueuedLogStatus=update
            handler.post {
            if (!activityDestroyed && this::testLogOwner.isInitialized && testLogOwner.snapshot().generation == update.generation) {
                requestTestLogStartWhenReady()
                finishTestLogWhenReady()
                if (lastLogPhase != update.phase) { lastLogPhase=update.phase;pushUiState() }
            }
        } })
        testLog = SessionLogAdapter(testLogOwner)
        logIo.execute { val found=AndroidSessionLogFiles.latest(testLogRoot);runOnUiThread { if(!activityDestroyed){recoveredTestLog=found;pushUiState()} } }
        audioEngine.onPlaybackFinished = { owner -> handler.post {
            if (!activityDestroyed && owner == testLogPlaybackId) {
                testLogWaitsForAudio=false
                if(audioEngine.lastAudioError!=null){testLogFailure=true;testLogStopCause=7}
                if (!stoppingTestLog) requestStopTestLog(7,false,audioEngine.lastAudioError!=null)
                finishTestLogWhenReady()
            }
        } }
        sensorProvider = SensorProvider(this) { speed, accel, gpsOk, raw, grav, diagnostics ->
            onSensorSample(speed, accel, gpsOk, raw, grav, diagnostics)
        }
        webView.webViewClient = object : android.webkit.WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                calibrationPageEpoch++
                calibrationPageActive = url == "file:///android_asset/screens/calibration.html"
                dashboardPageActive = url == "file:///android_asset/screens/dashboard.html"
                sensorProvider.cancelCalibration()
            }
        }
        webView.addJavascriptInterface(VicoBridge(this, webView), "AndroidBridge")
        restoreState()
        refreshOutputDevices()

        startMs = android.os.SystemClock.elapsedRealtime()
        webView.loadUrl("file:///android_asset/screens/dashboard.html")
        handleS13ReviewIntent(intent)

        if (!sensorProvider.hasLocationPermission()) {
            sensorProvider.requestLocationPermission(this)
        }
    }

    override fun onNewIntent(intent: android.content.Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleS13ReviewIntent(intent)
    }

    private fun handleS13ReviewIntent(intent: android.content.Intent) {
        val isDebuggable = applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0
        if(isDebuggable && intent.getBooleanExtra("vico_s15_smoke",false)) {
            val smokeDurationMs=intent.getLongExtra("vico_s15_duration_ms",20000L).coerceIn(20000L,1800000L)
            intent.removeExtra("vico_s15_duration_ms")
            intent.removeExtra("vico_s15_smoke")
            if(s15SmokeInProgress) return
            s15SmokeInProgress=true
            Thread({
                val prepared=runCatching {com.vico.simulator.sound.s15.C63RuntimePreparation.warmup()}
                handler.post {
                if(prepared.isFailure){android.util.Log.e("VicoS15Smoke","Preparation failed",prepared.exceptionOrNull());s15SmokeInProgress=false;toast("诊断准备失败，未播放");return@post}
                if(audioRunning || s14.busy || reviewExportInProgress){s15SmokeInProgress=false;return@post}
                s15SmokeInProgress=true
                val oldDemo=sensorProvider.isDemoMode();val oldScenario=demoScenario
                setVehicle("c63_w204_v6")
                if(!audioEngine.setVehicle("c63_w204_v6") || !audioEngine.setS15Prototype(true)) {s15SmokeInProgress=false;return@post}
                sensorProvider.setDemoMode(true);setDemoScenario("launch")
                audioEngine.armDigitalCapture()
                audioEngine.pushState(audioEngine.mapSyntheticPoint(DrivePoint(0.0,0.0,.8,2.4,false), DriveInputSource.QUALIFICATION, ++controlFrameSequence, android.os.SystemClock.elapsedRealtimeNanos()))
                audioRunning=audioEngine.start();vehicleState.startEngine();pushUiState()
                val owner=audioEngine.playbackIdentity()
                handler.postDelayed({if(owner==audioEngine.playbackIdentity() && audioRunning)setDemoScenario("decel")},12000L)
                handler.postDelayed({
                    if(owner!=audioEngine.playbackIdentity()){s15SmokeInProgress=false;return@postDelayed}
                    audioEngine.stop();audioRunning=false;vehicleState.stopEngine()
                    sensorProvider.setDemoMode(oldDemo);setDemoScenario(oldScenario)
                    handler.postDelayed({
                        Thread({
                            val saved=runCatching {
                                val dir=getExternalFilesDir("s15-review") ?: error("No diagnostic directory")
                                dir.mkdirs();val name="smoke-"+System.currentTimeMillis()
                                val capture=java.io.File(dir,"$name.f32le").outputStream().use(audioEngine::exportDigitalCapture)
                                val receipt=org.json.JSONObject().put("schema","vico.s15.smoke.v1").put("scope","GM1910_DEMO_LAUNCH_DECEL_NOT_ORIGINAL_TRACE")
                                    .put("intended_duration_ms",smokeDurationMs).put("capture_scope","FIRST_30_SECONDS_ONLY")
                                    .put("timing",org.json.JSONObject(audioEngine.s15TimingJson())).put("capture",org.json.JSONObject(capture.toJson()))
                                    .put("input_trace",org.json.JSONObject(audioEngine.s15InputsJson()))
                                    .put("output",org.json.JSONObject(audioEngine.s15OutputJson()))
                                    .put("audio_error",audioEngine.lastAudioError ?: org.json.JSONObject.NULL).put("human_acceptance","NOT_RUN")
                                java.io.File(dir,"$name.json").writeText(receipt.toString(2))
                            }
                            runOnUiThread {s15SmokeInProgress=false;if(owner==audioEngine.playbackIdentity()){audioEngine.setS15Prototype(false);pushUiState();toast(if(saved.isSuccess)"候选真机诊断记录已保存，已恢复原声库" else "诊断导出失败")}}
                        },"s15-smoke-export").start()
                    },1000L)
                },smokeDurationMs)
                }
            },"s15-smoke-prepare-discard").start()
            return
        }
        if (isDebuggable && intent.hasExtra("vico_s14_reference")) {
            val label = intent.getStringExtra("vico_s14_reference") ?: return
            if (intent.getBooleanExtra("vico_s14_start_failure", false)) audioEngine.failNextReferenceStartupForDebug()
            if (intent.getBooleanExtra("vico_s14_preview_regression", false)) {
                handler.post {
                    previewVehicle("c63_w204_v6")
                    handler.postDelayed({ stopAudio() }, 100L)
                    handler.postDelayed({ startS14Reference(label) }, 700L)
                }
                return
            }
            handler.post { startS14Reference(label) }
            return
        }
        if (!isDebuggable || !intent.getBooleanExtra("vico_s13_review", false)) return
        val key = intent.getStringExtra("vico_s13_vehicle") ?: vehicleState.selectedKey
        handler.post { startS13Review(key) }
    }

    override fun onResume() {
        super.onResume()
        calibrationResumed = true
        @Suppress("DEPRECATION")
        val displayRotation = windowManager.defaultDisplay.rotation
        naturalMountDiagramSupported = resources.configuration.orientation != android.content.res.Configuration.ORIENTATION_UNDEFINED &&
            hasPortraitNaturalOrientation(displayRotation, resources.configuration.orientation == android.content.res.Configuration.ORIENTATION_PORTRAIT)
        sensorProvider.start()
        if (audioRunning && !s13ReviewActive && !audioEngine.start()) {
            audioRunning = false
            pushUiState()
        }
    }

    override fun onPause() {
        super.onPause()
        calibrationResumed = false
        calibrationPageEpoch++
        mounting.invalidate("APP_BACKGROUND")
        requestStopTestLog(6, true)
        sensorProvider.stop()
        val previousDiagnostics = lastInputSnapshot.diagnostics
        lastInputSnapshot = SensorInputSnapshot(diagnostics = InputDiagnostics(inputSession = previousDiagnostics.inputSession,
            sourceMode = previousDiagnostics.sourceMode, driveInputMode = previousDiagnostics.driveInputMode))
        pushUiState()
        cancelPreviewCallbacks()
        audioEngine.stop("ACTIVITY_PAUSE")
        if (!s13ReviewActive) { audioRunning=false;vehicleState.stopEngine() }
        if (s14.state == S14TrialCoordinator.State.LOADING) stopAudio("ACTIVITY_PAUSE")
    }

    override fun onDestroy() {
        s15PreparationEpoch++
        activityDestroyed = true
        calibrationResumed = false
        calibrationPageEpoch++
        sensorProvider.cancelCalibration()
        cancelPreviewCallbacks()
        getSystemService(android.media.AudioManager::class.java)
            .unregisterAudioDeviceCallback(audioDeviceCallback)
        super.onDestroy()
        audioEngine.release()
        sensorProvider.rawInputObserver = null
        if(this::testLogOwner.isInitialized)testLogOwner.close()
        handler.removeCallbacks(audioLogCollector)
        logIo.shutdown()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == SensorProvider.LOC_PERM_REQUEST) {
            val ok = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
            toast(if (ok) "位置权限已授予, 可读取车速" else "未授位置权限, 可用演示模式")
            if (ok) sensorProvider.refreshLocation()
        }
    }

    private fun onSensorSample(
        speedKmh: Double, forwardAccel: Double, gpsOk: Boolean, rawAccel: FloatArray, gravity: FloatArray,
        inputDiagnostics: InputDiagnostics,
    ) {
        val consumedNanos = android.os.SystemClock.elapsedRealtimeNanos()
        val frameId = ++controlFrameSequence
        val vehicleAccel = if (inputDiagnostics.sourceMode == InputDiagnostics.SourceMode.DEMO) forwardAccel
            else mounting.project(rawAccel, inputDiagnostics.inputSession, sensorProvider.calibrationStatus) ?: 0.0
        lastSpeedKmh = speedKmh
        lastAccelMps2 = vehicleAccel
        val now = android.os.SystemClock.elapsedRealtime()
        val diagnostics = inputDiagnostics.copy(consumeElapsedNanos = consumedNanos,
            driveInputMode = when {
                s13ReviewActive -> InputDiagnostics.DriveInputMode.REFERENCE_BYPASS
                now < previewUntilMs -> InputDiagnostics.DriveInputMode.PREVIEW
                else -> InputDiagnostics.DriveInputMode.LIVE
            })
        lastInputSnapshot = SensorInputSnapshot.capture(speedKmh, vehicleAccel, gpsOk, rawAccel, gravity, diagnostics, frameId)
        if (s13ReviewActive) {
            pushUiState()
            return
        }
        val timeS = (now - startMs) / 1000.0
        val throttle = (vehicleAccel / 3.0).coerceIn(0.0, 1.0)
        val brake = vehicleAccel < -1.2
        val realPoint = DrivePoint(timeS, speedKmh, throttle, vehicleAccel, brake)

        val state = if (now < previewUntilMs) {
            inputContinuity.advance("PREVIEW", true, Long.MAX_VALUE, consumedNanos)
            audioEngine.mapSyntheticPoint(DrivePoint(timeS, 50.0, 0.4, 0.5, false), DriveInputSource.PREVIEW, frameId, consumedNanos)
        } else {
            mapCurrentInput(realPoint, diagnostics, consumedNanos, frameId)
        }
        lastGear = state.gear

        if (audioRunning) audioEngine.pushState(state)
        if (testLog.requested && !stoppingTestLog) testLog.recordFrame(lastInputSnapshot, state,
            inputQualityPolicy.assess(diagnostics, consumedNanos, mountingFrameConfirmed), currentLogConfig(), consumedNanos)
        if (recording) {
            csvExporter.append(timeS, speedKmh, vehicleAccel, state.rpm, state.frequencyHz, "$selectedVehicleName/${character.label}", diagnostics)
        }

        val json = buildString {
            append('{')
            append("\"controlFrameId\":\"").append(frameId).append("\",")
            append("\"normalBankVariant\":\"").append(audioEngine.normalBankIdentity()).append("\",")
            append("\"normalBankVariantActive\":").append(!s13ReviewActive && s14ReferenceLabel == null && !audioEngine.s15PrototypeEnabled).append(',')
            append("\"speed\":").append(speedKmh.toInt()).append(',')
            append("\"speedKmh\":\"").append(String.format(Locale.US, "%.1f", speedKmh)).append("\",")
            append("\"accel\":\"").append(String.format(Locale.US, "%.2f", vehicleAccel)).append("\",")
            append("\"rpm\":").append(state.rpm.toInt()).append(',')
            append("\"gear\":").append(state.gear).append(',')
            append("\"shiftGain\":").append(String.format(Locale.US, "%.3f", state.shiftGain)).append(',')
            append("\"freq\":\"").append(String.format(Locale.US, "%.1f", state.frequencyHz)).append("\",")
            append("\"gpsOk\":").append(gpsOk).append(',')
            append("\"vehicle\":\"").append(selectedVehicleName).append("\",")
            append("\"selectedVehicleKey\":\"").append(vehicleState.selectedKey).append("\",")
            append("\"playingVehicleKey\":\"").append(vehicleState.playingKey ?: "").append("\",")
            append("\"previewVehicleKey\":\"").append(previewVehicleKey ?: "").append("\",")
            append("\"profile\":\"").append(character.label).append("\",")
            append("\"profileKey\":\"").append(character.name.lowercase()).append("\",")
            append("\"running\":").append(audioRunning).append(',')
            append("\"muted\":").append(muted || state.muted).append(',')
            append("\"language\":\"").append(language).append("\",")
            append("\"demoScenario\":\"").append(demoScenario).append("\",")
            append(calibrationStateJson()).append(',')
            append("\"inputDiagnostics\":").append(diagnostics.toJson()).append(',')
            append("\"inputQuality\":").append(inputQualityPolicy.assess(diagnostics, consumedNanos, mountingFrameConfirmed).toJson()).append(',')
            append("\"mounting\":").append(mountingStateJson()).append(',')
            append("\"testLog\":").append(testLogStateJson()).append(',')
            append("\"demo\":").append(diagnostics.sourceMode == InputDiagnostics.SourceMode.DEMO).append(',')
            append("\"recording\":").append(recording).append(',')
            append("\"sampleCount\":").append(csvExporter.sampleCount).append(',')
            append("\"ax\":").append(rawAccel[0]).append(',')
            append("\"ay\":").append(rawAccel[1]).append(',')
            append("\"az\":").append(rawAccel[2]).append(',')
            append("\"gx\":").append(gravity[0]).append(',')
            append("\"gy\":").append(gravity[1]).append(',')
            append("\"gz\":").append(gravity[2]).append(',')
            append("\"s15Prototype\":").append(audioEngine.s15PrototypeEnabled).append(',')
            append("\"s15Preparing\":").append(s15Preparing).append(',')
            append("\"masterVolume\":").append(masterVol)
            append('}')
        }
        val deliveredJson = withUiDispatch(json, lastInputSnapshot)
        webView.evaluateJavascript("window.__vicoUpdate&&window.__vicoUpdate($deliveredJson)", null)
    }

    private fun mapCurrentInput(point: DrivePoint, diagnostics: InputDiagnostics, nowNanos: Long, frameId: Long): SoundState {
        if (diagnostics.sourceMode == InputDiagnostics.SourceMode.DEMO) {
            inputContinuity.advance("DEMO/${diagnostics.inputSession}", true, Long.MAX_VALUE, nowNanos)
            val source = if (s15SmokeInProgress) DriveInputSource.QUALIFICATION else DriveInputSource.DEMO
            return audioEngine.mapSyntheticPoint(point, source, frameId, nowNanos)
        }
        val quality = inputQualityPolicy.assess(diagnostics, nowNanos, mountingFrameConfirmed)
        val epoch = inputContinuity.advance("REAL/${diagnostics.inputSession}", quality.controlUsable,
            quality.validUntilElapsedNanos, nowNanos)
        return audioEngine.mapMeasuredPoint(point, DriveInputControl(DriveInputSource.REAL, epoch,
            quality.validUntilElapsedNanos, quality.speedUsable, quality.accelerationUsable,
            imuSampleElapsedNanos = diagnostics.imuTiming?.sourceElapsedNanos,
            gpsSampleElapsedNanos = diagnostics.gpsTiming?.sourceElapsedNanos,
            controlTimeElapsedNanos = nowNanos, controlFrameId = frameId))
    }

    // ---- bridge handlers (UI thread) ----
    fun startAudio() {
        if(activityDestroyed || !calibrationResumed)return
        if(s15Preparing){toast("候选尚在准备；完成后再启用声浪");return}
        if(audioRunning)return
        if(audioEngine.s15PrototypeEnabled){s15LastRun=null;s15StopReason="NOT_RECORDED"}
        cancelPreviewCallbacks()
        if (s13ReviewActive) {
            toast("请先停止基准回放")
            return
        }
        val key = vehicleState.selectedKey
        character = SoundProfile.DEFAULT
        audioEngine.setCharacter(character)
        prefs.edit().remove("manual_character").apply()
        if (!audioEngine.setVehicle(key)) {
            audioRunning = false
            pushUiState()
            toast("该车型 S12 声库未导入")
            return
        }
        activeVehicleKey = key
        val nowNanos = android.os.SystemClock.elapsedRealtimeNanos()
        val timeS = (android.os.SystemClock.elapsedRealtime() - startMs) / 1000.0
        val input = lastInputSnapshot
        val throttle = (input.accelMps2 / 3.0).coerceIn(0.0, 1.0)
        val frameId = ++controlFrameSequence
        lastInputSnapshot = input.copy(controlFrameId = frameId)
        val initialState = mapCurrentInput(
            DrivePoint(timeS, input.speedKmh, throttle, input.accelMps2, input.accelMps2 < -1.2),
            input.diagnostics, nowNanos, frameId,
        )
        lastGear = initialState.gear
        audioEngine.pushState(initialState)
        startTestLog(frameId)
        if (!audioEngine.start()) {
            requestStopTestLog(7, false, true)
            audioRunning = false
            pushUiState()
            toast("声浪启动失败，请检查音频输出设备")
            return
        }
        audioRunning = true
        testLogPlaybackId = audioEngine.playbackIdentity()
        requestTestLogStartWhenReady()
        vehicleState.startEngine()
        pushUiState()
        toast("声浪已启动 · $vehicleName / ${character.label}")
    }

    fun stopAudio(reason: String = "USER_STOP") {
        s15PreparationEpoch++;s15Preparing=false
        if(audioEngine.s15PrototypeEnabled)s15StopReason=reason
        cancelPreviewCallbacks()
        if (s14.state == S14TrialCoordinator.State.EXPORTING) { toast("正在保存，请稍候"); return }
        if (s14.state == S14TrialCoordinator.State.LOADING) {
            s14.ticket?.let { s14.abort(it, reason) }
            s14Status = "ABORTED"
            s13ReviewActive = false
            audioRunning = false
            pushUiState()
            return
        }
        if (s13ReviewActive) {
            audioEngine.stop(reason)
            toast("正在停止并保存基准回放证据")
            return
        }
        requestStopTestLog(5, true)
        audioEngine.stop(); audioRunning = false
        vehicleState.stopEngine()
        previewVehicleKey = null
        pushUiState()
        toast("声浪已停止")
    }

    fun startS14Reference(label: String, controlled: Boolean = false) {
        if (audioRunning || s13ReviewActive || reviewExportInProgress || s14.busy || label !in setOf("R", "M")) {
            android.util.Log.i("VicoS14", "Reference start rejected: playback active or invalid label")
            toast("请先停止播放，再选择对照材料")
            return
        }
        cancelPreviewCallbacks()
        val owner = s14.begin(label, controlled)
        s14Controlled = controlled
        s14Frames = 0
        s14Status = "LOADING"
        s13ReviewActive = true
        pushUiState()
        Thread({
            val loaded = runCatching {
                val directory = getExternalFilesDir("s14-reference") ?: error("Reference directory unavailable")
                val file = File(directory, "$label.f32le")
                require(file.length() == 5_760_000L) { "Reference length mismatch" }
                S14ReferenceSession(file.readBytes(), label)
            }
            runOnUiThread {
                if (activityDestroyed || !s14.owns(owner) || s14.state != S14TrialCoordinator.State.LOADING) return@runOnUiThread
                try {
                    val session = loaded.getOrThrow()
                    s14.advance(owner, S14TrialCoordinator.State.READY)
                    s14.advance(owner, S14TrialCoordinator.State.PLAYING)
                    if (!audioEngine.startS14Reference(session, owner)) error(audioEngine.lastAudioError ?: "Reference start failed")
                    audioRunning = true
                    s14Status = "PLAYING"
                } catch (error: Exception) {
                    android.util.Log.e("VicoS14", "Owned reference startup failed: " + error.message)
                    s14.fail(owner, error.message ?: "Reference loading failed")
                    s14Status = "FAILED"
                    s13ReviewActive = false
                    audioRunning = false
                    toast("对照材料校验失败: " + error.message)
                }
                pushUiState()
            }
        }, "vico-s14-load").start()
    }

    private fun cancelPreviewCallbacks() {
        playbackEpoch.next()
        previewRestore?.let(handler::removeCallbacks)
        previewRestore = null
        previewUntilMs = 0L
        previewVehicleKey = null
    }

    fun startS14Controlled(number: Int) {
        if (number !in 1..2) return
        val order = if (s14PairIndex == 0) listOf("R", "M") else listOf("M", "R")
        if ((number == 2 && !controlledTrialDone(order[0])) || controlledTrialDone(order[number - 1])) {
            toast("请按材料 1、材料 2 的顺序完成本组对照")
            return
        }
        startS14Reference(order[number - 1], true)
    }

    private fun controlledTrialDone(label: String): Boolean = s14Trials[label]?.let {
        it.optBoolean("controlled") && it.optBoolean("digital_reference_match") &&
            it.optBoolean("submitted_complete") && it.optBoolean("playback_position_complete")
    } ?: false

    fun nextS14Pair() {
        if (s14.busy || !s14Revealed || s14PairIndex >= 1) { toast("最多两组对照，请先完成当前组反馈"); return }
        s14PairIndex++
        s14PairId = "s14-" + System.currentTimeMillis()
        s14Trials.clear()
        s14Revealed = false
        s14Status = "IDLE"
        pushUiState()
    }

    fun retryS14Pair() {
        if (s14.busy || pairMatched() || s14Revealed) return
        s14PairId = "s14-" + System.currentTimeMillis()
        s14Trials.clear()
        s14Frames = 0
        s14Status = "IDLE"
        pushUiState()
    }

    private fun conditionsJson(c: S14OutputConditions?): JSONObject? = c?.let {
        JSONObject().put("device_instance", it.deviceInstance).put("model", it.model).put("sdk", it.sdk).put("route_id", it.routeId)
            .put("route_type", it.routeType).put("route_category", it.routeCategory).put("route_name", it.routeName)
            .put("media_volume", it.mediaVolume).put("media_volume_max", it.mediaVolumeMax).put("media_muted", it.mediaMuted)
            .put("sample_rate_hz", 48000).put("channels", 1)
    }

    private fun pairMatched(): Boolean {
        val r = s14Trials["R"] ?: return false
        val m = s14Trials["M"] ?: return false
        val conditions = r.optJSONObject("start_conditions") ?: return false
        if (conditions.optInt("media_volume") <= 0 || conditions.optBoolean("media_muted", true) ||
            conditions.optInt("route_type") <= 0 || conditions.optString("device_instance").isBlank()) return false
        return r.optBoolean("digital_reference_match") && m.optBoolean("digital_reference_match") &&
            r.optBoolean("submitted_complete") && m.optBoolean("submitted_complete") &&
            r.optBoolean("playback_position_complete") && m.optBoolean("playback_position_complete") &&
            r.optBoolean("controlled") == m.optBoolean("controlled") &&
            r.optString("session_id") != m.optString("session_id") &&
            r.getJSONObject("start_conditions").toString() == m.getJSONObject("start_conditions").toString()
    }

    fun submitS14Feedback(preference: String, notes: String) {
        if (s14.busy || s14FeedbackSaving || s14Revealed || s14Trials.isEmpty()) { toast("请先试听并等待记录保存；中止试听也可提交意见"); return }
        if (preference !in setOf("first", "second", "no_difference", "neither", "unsure")) return
        val qualifiedPair = pairMatched()
        if (!qualifiedPair && notes.isBlank()) { toast("未完成对照，请填写已试听部分的意见或中止原因"); return }
        val receipt = JSONObject().put("author", "Jovi").put("confirmed", true).put("pair_id", s14PairId)
            .put("schema", "vico.s15.listening_feedback.v1").put("pair_conditions_matched", qualifiedPair)
            .put("evidence_level", if (qualifiedPair) "QUALIFIED_PAIR_FEEDBACK" else "QUALITATIVE_PARTIAL_FEEDBACK")
            .put("preference", preference).put("notes", notes.take(2000)).put("controlled", s14Controlled)
            .put("trials", org.json.JSONArray(s14Trials.values.toList())).put("submitted_at_ms", System.currentTimeMillis())
        val pair = s14PairId
        val body = receipt.toString(2)
        s14FeedbackSaving = true
        reviewExportInProgress = true
        s14Status = "EXPORTING"
        pushUiState()
        Thread({
            val saved = runCatching {
                val directory = getExternalFilesDir("s14-review") ?: error("Feedback directory unavailable")
                directory.mkdirs()
                File(directory, pair + "-feedback-" + System.currentTimeMillis() + ".json").writeText(body)
            }
            runOnUiThread {
                if (activityDestroyed || pair != s14PairId) return@runOnUiThread
                s14FeedbackSaving = false
                reviewExportInProgress = false
                saved.onSuccess {
                    s14Revealed = true
                    s14Status = if (qualifiedPair) "LISTENING_RECORDED" else "PARTIAL_FEEDBACK_RECORDED"
                    toast("Jovi 的反馈已保存；未自动判定音色通过")
                }.onFailure { s14Status = "FEEDBACK_SAVE_FAILED"; toast("反馈保存失败，请重试") }
                pushUiState()
            }
        }, "vico-s14-feedback").start()
    }

    private fun finishS14Reference(capture: S14CompletedCapture) {
        val result = capture.result
        if (activityDestroyed || !s14.advance(result.ticket, S14TrialCoordinator.State.EXPORTING)) return
        val pairId = s14PairId
        reviewExportInProgress = true
        s14Status = "EXPORTING"
        audioRunning = false
        s13ReviewActive = false
        pushUiState()
        Thread({
            val exported = runCatching {
                val directory = getExternalFilesDir("s14-review") ?: error("Export directory unavailable")
                directory.mkdirs()
                val name = result.ticket.id
                val core = File(directory, "$name.core.f32le").outputStream().use(capture::exportCore)
                val accepted = File(directory, "$name.accepted.f32le").outputStream().use(capture::exportAccepted)
                val digital = core.fullWindow && accepted.fullWindow && core.sha256 == result.sourceSha && accepted.sha256 == result.sourceSha
                val receipt = JSONObject().put("schema", "vico.s14.trial.v2").put("diagnostic_phase", "S14")
                    .put("controlled", result.ticket.controlled)
                    .put("trial_number", if ((result.ticket.label == "R") == (s14PairIndex == 0)) 1 else 2)
                    .put("pair_id", pairId).put("session_id", name).put("reference_label", result.ticket.label)
                    .put("vehicle_key", "c63_w204_v6").put("source_pcm_sha256", result.sourceSha)
                    .put("presentation_gain", 1.0).put("submitted_complete", result.submittedComplete)
                    .put("rendered_frames", result.renderedFrames)
                    .put("accepted_complete", accepted.fullWindow).put("physical_output_complete", JSONObject.NULL)
                    .put("session_complete", result.submittedComplete).put("session_error", result.error ?: JSONObject.NULL)
                    .put("start_conditions", conditionsJson(result.startConditions) ?: JSONObject.NULL)
                    .put("end_conditions", conditionsJson(result.endConditions) ?: JSONObject.NULL)
                    .put("started_at_ms", result.startedAtMs).put("ended_at_ms", result.endedAtMs)
                    .put("reference_route_device_id", result.startConditions?.routeId ?: JSONObject.NULL)
                    .put("audio_route_device_id", result.endConditions?.routeId ?: JSONObject.NULL)
                    .put("playback_head_frames", result.playbackHeadFrames ?: JSONObject.NULL)
                    .put("playback_position_complete", result.playbackPositionComplete ?: JSONObject.NULL)
                    .put("digital_reference_match", digital)
                    .put("review_core", JSONObject(core.toJson())).put("track_accepted", JSONObject(accepted.toJson()))
                File(directory, "$name.json").writeText(receipt.toString(2))
                receipt
            }
            runOnUiThread {
                if (activityDestroyed || !s14.owns(result.ticket)) return@runOnUiThread
                reviewExportInProgress = false
                exported.onSuccess {
                    s14Trials[result.ticket.label] = it
                    if (result.error in setOf("USER_STOP", "ACTIVITY_PAUSE", "ACTIVITY_DESTROY")) {
                        s14.abort(result.ticket, result.error!!); s14Status = "ABORTED"
                    } else if (result.error != null) {
                        s14.fail(result.ticket, result.error); s14Status = "FAILED"
                    } else {
                        s14.advance(result.ticket, S14TrialCoordinator.State.FINISHED)
                        s14Status = if (!it.optBoolean("digital_reference_match") || !result.submittedComplete) "INCOMPLETE"
                            else if (result.playbackPositionComplete != true) "PLAYBACK_UNCONFIRMED" else "FINISHED"
                    }
                }.onFailure { s14.fail(result.ticket, it.message ?: "Export failed"); s14Status = "FAILED" }
                pushUiState()
            }
        }, "vico-s14-export").start()
    }

    fun setS15Prototype(enabled:Boolean) {
        val epoch=++s15PreparationEpoch
        s15Preparing=false
        if(audioRunning || s14.busy || reviewExportInProgress) {toast("请先停止播放并等待保存完成");return}
        if(enabled && vehicleState.selectedKey!="c63_w204_v6") {toast("请先在车型库选择 C63 W204");return}
        if(enabled) {
            s15Preparing=true
            toast("正在后台准备 C63_AH_V1；准备完成后才可启用")
            Thread({
                val prepared=runCatching {com.vico.simulator.sound.s15.C63RuntimePreparation.warmup {epoch!=s15PreparationEpoch}}
                runOnUiThread {
                    if(epoch!=s15PreparationEpoch)return@runOnUiThread
                    s15Preparing=false
                    if(prepared.isFailure){toast("候选准备失败，未启用");return@runOnUiThread}
                    if(audioRunning || s14.busy || reviewExportInProgress || vehicleState.selectedKey!="c63_w204_v6") {toast("状态已变化，候选未启用");return@runOnUiThread}
                    if(audioEngine.setS15Prototype(true)){toast("C63_AH_V1 已就绪；音色尚待验收");pushUiState()}
                }
            },"s15-prepare-discard").start()
            return
        }
        if(!audioEngine.setS15Prototype(enabled)){toast("切换未完成，请等待音频停止后重试");return}
        toast(if(enabled) "已选择 C63 连续声源实验候选；尚未通过音色验收" else "已恢复原声库")
        pushUiState()
    }
    fun submitS15Feedback(assessment:String,notes:String) {
        if(audioRunning || reviewExportInProgress || s15SmokeInProgress){toast("请先停止试听并等待保存完成");return}
        val run=s15LastRun ?: run {toast("请先试听 C63_AH_V1，再停止并提交意见");return}
        if(!com.vico.simulator.sound.C63FeedbackInput.valid(assessment,notes)){toast("请选择评价并填写试听意见或中止原因");return}
        val body=JSONObject().put("schema","vico.s15.candidate_feedback.v1").put("author","Jovi")
            .put("assessment",assessment).put("notes",notes.take(2000)).put("run",JSONObject(run))
            .put("evidence_level","QUALITATIVE_SINGLE_CANDIDATE_FEEDBACK").put("human_acceptance",if(assessment=="rejected")"REJECTED_BY_JOVI" else "PENDING")
            .put("submitted_at_ms",System.currentTimeMillis()).toString(2)
        reviewExportInProgress=true
        Thread({
            val saved=runCatching {
                val dir=getExternalFilesDir("s15-feedback") ?: error("No feedback directory")
                check(dir.exists() || dir.mkdirs())
                File(dir,"c63-ah-feedback-${System.currentTimeMillis()}.json").writeText(body)
            }
            runOnUiThread {reviewExportInProgress=false;toast(if(saved.isSuccess)"候选意见已保存，中止意见同样保留" else "保存失败，请重试")}
        },"s15-feedback-save").start()
    }
    fun startS13Review() = startS13Review(vehicleState.selectedKey)

    private fun startS13Review(key: String) {
        if (audioRunning || s13ReviewActive || reviewExportInProgress) {
            toast("请先停止当前声浪播放")
            return
        }
        if (!CurrentVehicleCatalog.isSupported(key)) {
            toast("该车型暂不在当前车型库")
            return
        }
        vehicleState.select(key)
        selectedVehicleName = CurrentVehicleCatalog.displayName(key)
        s13ReviewActive = true
        s13ReviewVehicleKey = key
        if (!audioEngine.startS13Review(key)) {
            s13ReviewActive = false
            s13ReviewVehicleKey = null
            toast(audioEngine.lastAudioError ?: "基准回放校验失败")
            return
        }
        activeVehicleKey = key
        vehicleName = CurrentVehicleCatalog.displayName(key)
        selectedVehicleName = vehicleName
        audioRunning = true
        vehicleState.startEngine()
        pushUiState()
        toast("开始30秒同输入回放；不读取传感器、不改系统音量")
    }

    private fun finishS13Review(complete: Boolean, error: String?) {
        val vehicleKey = s13ReviewVehicleKey ?: vehicleState.selectedKey
        val referenceLabel = s14ReferenceLabel
        val referenceRoute = audioEngine.referenceRouteId
        reviewExportInProgress = true
        s14ReferenceLabel = null
        s13ReviewActive = false
        s13ReviewVehicleKey = null
        audioRunning = false
        vehicleState.stopEngine()
        pushUiState()
        Thread({
            try {
                val directory = getExternalFilesDir("s13-review") ?: File(filesDir, "s13-review")
                if (!directory.exists() && !directory.mkdirs()) {
                    throw IllegalStateException("Cannot create S13 review output directory")
                }
                val runId = "${vehicleKey}_${System.currentTimeMillis()}"
                val corePcmFile = File(directory, "$runId.core.f32le")
                val acceptedPcmFile = File(directory, "$runId.track-accepted.f32le")
                val receiptFile = File(directory, "$runId.json")
                val coreReport = corePcmFile.outputStream().use { audioEngine.exportReviewCoreCapture(it) }
                val acceptedReport = acceptedPcmFile.outputStream().use { audioEngine.exportDigitalCapture(it) }
                val receipt = JSONObject()
                    .put("diagnostic_phase", if (referenceLabel == null) "S13" else "S14")
                    .put("reference_label", referenceLabel ?: JSONObject.NULL)
                    .put("reference_route_device_id", referenceRoute ?: JSONObject.NULL)
                    .put("session_complete", complete)
                    .put("session_error", error ?: JSONObject.NULL)
                    .put("review_core", JSONObject(coreReport.toJson()))
                    .put("track_accepted", JSONObject(acceptedReport.toJson()))
                    .put("core_equals_track_accepted", coreReport.sha256 == acceptedReport.sha256)
                    .put("audio_route_device_id", audioEngine.routedOutputDeviceId() ?: JSONObject.NULL)
                audioEngine.lastMixStats?.takeIf { referenceLabel == null }?.let { stats ->
                    receipt.put("mix_stats", JSONObject()
                        .put("evaluated_frames", stats.evaluatedFrames)
                        .put("pre_clip_peak", stats.preClipPeak)
                        .put("above_contract_frames", stats.aboveContractFrames)
                        .put("hard_clip_frames", stats.hardClipFrames)
                        .put("non_finite_frames", stats.nonFiniteFrames)
                        .put("load_out_of_bank_frames", stats.loadOutOfBankFrames)
                        .put("rpm_out_of_bank_frames", stats.rpmOutOfBankFrames))
                }
                receiptFile.writeText(receipt.toString(2), Charsets.UTF_8)
                runOnUiThread {
                    val full = complete && coreReport.fullWindow && acceptedReport.fullWindow
                    val label = if (full) "完整" else "不完整"
                    toast("$label D1/D2 数字 PCM 已保存；需 adb pull 分析，非扬声器回录")
                }
            } catch (failure: Exception) {
                runOnUiThread { toast("回放证据保存失败: ${failure.message}") }
            } finally {
                reviewExportInProgress = false
            }
        }, "vico-s13-review-export").start()
    }

    @Suppress("UNUSED_PARAMETER")
    fun setProfile(key: String) {
        toast("车型声浪系数已锁定")
    }

    @Suppress("UNUSED_PARAMETER")
    fun previewProfile(key: String) {
        toast("车型声浪系数已锁定")
    }

    fun setMasterVol(v: Float) {
        if (s13ReviewActive) {
            toast("基准回放使用固定数字增益；音量滑块不参与对照")
            return
        }
        masterVol = v.coerceIn(0f, 1f)
        audioEngine.setMasterVol(masterVol)
        prefs.edit().putFloat("master_volume", masterVol).apply()
        pushUiState()
    }

    fun setMuted(on: Boolean) {
        if (s13ReviewActive) {
            toast("请先停止基准回放再切换静音")
            return
        }
        muted = on
        audioEngine.setMuted(on)
        pushUiState()
    }

    fun setLanguage(key: String) {
        language = if (key == "en") "en" else "zh"
        prefs.edit().putString("language", language).apply()
        webView.evaluateJavascript("window.__vicoApplyLanguage&&window.__vicoApplyLanguage('$language')", null)
        pushUiState()
    }

    fun setOutputMode(mode: String) {
        if (s13ReviewActive) {
            toast("请先停止基准回放再切换输出设备")
            return
        }
        outputMode = if (mode == "bluetooth") "bluetooth" else "speaker"
        val speakerOn = outputMode == "speaker"
        outputLabel = audioEngine.selectOutput(outputMode)
        requestedOutputId = outputDevices.firstOrNull { it.category.name.equals(outputMode, ignoreCase = true) }?.id
        refreshOutputDevices()
        if (outputMode == "bluetooth" && outputLabel.isBlank()) {
            outputMode = "speaker"
            outputLabel = audioEngine.selectOutput(outputMode)
            prefs.edit().putString("output_mode", outputMode).apply()
            pushUiState()
            Toast.makeText(this, "No Bluetooth media output connected", Toast.LENGTH_SHORT).show()
            return
        }
        prefs.edit().putString("output_mode", outputMode).apply()
        pushUiState()
        toast(if (speakerOn) "输出: 内置扬声器" else "输出: 蓝牙 (需系统已连接, 媒体自动路由)")
    }

    fun selectOutputDevice(id: Int) {
        if (s13ReviewActive) {
            toast("请先停止基准回放再切换输出设备")
            return
        }
        val selected = outputDevices.firstOrNull { it.id == id }
        if (selected == null || !selected.selectable) {
            toast("该输出设备当前未连接")
            return
        }
        if (!audioEngine.selectOutputDevice(id)) {
            toast("输出设备切换失败")
            return
        }
        requestedOutputId = id
        outputMode = selected.category.name.lowercase(Locale.US)
        outputLabel = selected.label
        prefs.edit().putString("output_mode", outputMode).putInt("output_id", id).apply()
        refreshOutputDevices()
        pushUiState()
    }

    fun setVehicle(key: String) {
        s15PreparationEpoch++;s15Preparing=false
        if (s13ReviewActive) {
            toast("请先停止基准回放再切换车型")
            return
        }
        if (!CurrentVehicleCatalog.isSupported(key)) {
            toast("该车型暂不在当前车型库")
            return
        }
        vehicleState.select(key)
        selectedVehicleName = CurrentVehicleCatalog.displayName(key)
        vehicleName = selectedVehicleName
        prefs.edit().putString("selected_vehicle", key).apply()
        pushUiState()
        toast("车型: $selectedVehicleName")
    }

    fun previewVehicle(key: String) {
        if (s13ReviewActive) {
            toast("请先停止基准回放再试听其他车型")
            return
        }
        if (!CurrentVehicleCatalog.isSupported(key)) {
            toast("该车型暂不在当前车型库")
            return
        }
        cancelPreviewCallbacks()
        val resumeTestLogging = testLog.requested
        if(resumeTestLogging){
            collectAudioLogRows();testLog.lifecycle(6,5,android.os.SystemClock.elapsedRealtimeNanos(),currentLogConfig())
            audioEngine.diagnosticLoggingEnabled=false;requestStopTestLog(5,false)
        }
        val previewOwner = playbackEpoch.next()
        val originalKey = activeVehicleKey
        val originalCharacter = character
        previewVehicleKey = key
        if (!audioEngine.setVehicle(key)) {
            previewVehicleKey = null
            toast("该车型 S12 声库未导入")
            return
        }
        activeVehicleKey = key
        audioEngine.setCharacter(SoundProfile.DEFAULT)
        val wasRunning = audioRunning
        if (!wasRunning) {
            if (!audioEngine.start()) {
                previewVehicleKey = null
                toast("试听启动失败，请检查音频输出设备")
                return
            }
            audioRunning = true
        }
        previewUntilMs = android.os.SystemClock.elapsedRealtime() + 2500
        pushUiState()
        previewRestore = Runnable {
            if (!playbackEpoch.owns(previewOwner) || activityDestroyed) return@Runnable
            if (android.os.SystemClock.elapsedRealtime() >= previewUntilMs) {
                previewVehicleKey = null
                audioEngine.setVehicle(originalKey)
                activeVehicleKey = originalKey
                audioEngine.setCharacter(originalCharacter)
                if (!wasRunning) { audioEngine.stop(); audioRunning = false }
                else if(resumeTestLogging){startTestLog(controlFrameSequence+1);testLogPlaybackId=audioEngine.playbackIdentity()}
                pushUiState()
            }
        }
        handler.postDelayed(previewRestore!!, 2600)
    }

    fun exportCsv() {
        val uri = csvExporter.export(this)
        toast(if (uri != null) "CSV 已导出: Downloads/Vico" else "无数据可导出")
    }

    fun resetConfig() {
        toast("车型声浪系数已锁定")
    }

    fun resetAll() {
        if (s14.busy) { toast("请先结束原始声音对照"); return }
        cancelPreviewCallbacks()
        requestStopTestLog(5,true)
        audioEngine.stop(); audioRunning = false; recording = false
        vehicleState.stopEngine()
        character = SoundProfile.DEFAULT; audioEngine.setCharacter(character)
        masterVol = 1.0f; audioEngine.setMasterVol(masterVol)
        muted = false; audioEngine.setMuted(false)
        vehicleState.select(CurrentVehicleCatalog.defaultKey)
        selectedVehicleName = CurrentVehicleCatalog.displayName(CurrentVehicleCatalog.defaultKey)
        vehicleName = selectedVehicleName
        language = "zh"
        prefs.edit().clear().apply()
        mounting = VehicleMountingSession()
        csvExporter.clear()
        sensorProvider.resetCalibration()
        pushUiState()
        toast("全部已重置")
    }

    fun startRecording() {
        recording = true; csvExporter.start()
        pushUiState()
        toast("开始录制轨迹")
    }

    fun stopRecording() {
        recording = false
        pushUiState()
        toast("已停止录制 · 共 ${csvExporter.sampleCount} 条")
    }

    fun setDemoMode(on: Boolean) {
        sensorProvider.setDemoMode(on)
        pushUiState()
        toast(if (on) "演示模式开启" else "演示模式关闭")
    }

    fun setDemoScenario(key: String) {
        demoScenario = key
        sensorProvider.setDemoScenario(key)
        pushUiState()
    }

    fun acceptsCalibrationCommand(epoch: Long): Boolean =
        !activityDestroyed && calibrationResumed && calibrationPageActive && epoch == calibrationPageEpoch

    fun beginCalibration(session: String) {
        mounting.invalidate("CALIBRATION_CHANGED")
        sensorProvider.beginCalibration(session)
        pushUiState()
    }

    fun finishCalibration(session: String) {
        val complete = sensorProvider.finishCalibration(session)
        pushUiState()
        if (complete) toast("校准完成")
    }

    fun cancelCalibration(session: String? = null) {
        sensorProvider.cancelCalibration(session)
        pushUiState()
    }

    fun invalidateCalibrationPage() {
        calibrationPageEpoch++
        calibrationPageActive = false
        cancelCalibration()
    }

    private fun calibrationStateJson(): String {
        val status = sensorProvider.calibrationStatus
        return "\"calibrated\":" + (status.status == CalibrationSession.Status.COMPLETE) +
            ",\"calibration\":" + JSONObject().put("session", status.session).put("status", status.status.name)
            .put("samples", status.samples).put("required", status.required)
            .put("revision", status.revision).toString()
    }

    fun resetCalibration() {
        mounting.invalidate("CALIBRATION_CHANGED")
        sensorProvider.resetCalibration()
        pushUiState()
        toast("校准已重置")
    }

    fun acceptsMountingCommand(epoch: Long): Boolean =
        !activityDestroyed && calibrationResumed && dashboardPageActive && epoch == calibrationPageEpoch

    private fun mountingStateJson(): String {
        val input = lastInputSnapshot
        val quality = inputQualityPolicy.assess(input.diagnostics, android.os.SystemClock.elapsedRealtimeNanos(), false)
        val real = input.diagnostics.sourceMode == InputDiagnostics.SourceMode.REAL
        val moving = real && quality.speedUsable && input.speedKmh > 3.0
        val bound = mounting.snapshot
        return JSONObject().put("selected", bound.selected?.name ?: "").put("trusted", bound.trusted)
            .put("reason", bound.reason).put("requestRevision", mountingRequestRevision).put("result", mountingRequestResult)
            .put("naturalPortrait", naturalMountDiagramSupported)
            .put("canConfirm", real && !moving && !audioRunning && naturalMountDiagramSupported &&
                sensorProvider.isCalibrated && quality.imu == ImuQuality.UNCONFIRMED_FRAME && input.diagnostics.inputSession > 0)
            .put("calibrated", sensorProvider.isCalibrated).put("moving", moving)
            .put("inputSession", bound.inputSession).put("calibrationSession", bound.calibrationSession)
            .put("calibrationRevision", bound.calibrationRevision).toString()
    }

    fun confirmMounting(axisKey: String, parkedAcknowledged: Boolean) {
        val axis = runCatching { VehicleMountAxis.valueOf(axisKey) }.getOrNull()
        val input = lastInputSnapshot
        val q = inputQualityPolicy.assess(input.diagnostics, android.os.SystemClock.elapsedRealtimeNanos(), false)
        val real = input.diagnostics.sourceMode == InputDiagnostics.SourceMode.REAL
        val accepted = axis != null && real && !audioRunning && naturalMountDiagramSupported && mounting.confirm(
            axis, parkedAcknowledged, input.diagnostics.inputSession, sensorProvider.calibrationStatus,
            q.imu == ImuQuality.UNCONFIRMED_FRAME, if (q.speedUsable) input.speedKmh else null)
        if (accepted) prefs.edit().putString("mount_axis", axis!!.name).apply()
        mountingRequestRevision++
        mountingRequestResult = if (accepted) "CONFIRMED" else "REJECTED_CHECK_PARKING_CALIBRATION_IMU"
        refreshMountedSnapshot()
        pushUiState()
    }

    fun invalidateMounting() {
        mounting.invalidate("PHONE_MOVED")
        refreshMountedSnapshot()
        pushUiState()
    }

    private fun refreshMountedSnapshot() {
        val input = lastInputSnapshot
        if (input.diagnostics.sourceMode != InputDiagnostics.SourceMode.REAL) return
        val projected = mounting.project(floatArrayOf(input.ax, input.ay, input.az),
            input.diagnostics.inputSession, sensorProvider.calibrationStatus) ?: 0.0
        val frameId = ++controlFrameSequence
        lastInputSnapshot = input.copy(accelMps2 = projected, controlFrameId = frameId)
        if (audioRunning) {
            val now = android.os.SystemClock.elapsedRealtimeNanos()
            val point = DrivePoint((android.os.SystemClock.elapsedRealtime() - startMs) / 1000.0,
                input.speedKmh, (projected / 3.0).coerceIn(0.0, 1.0), projected, projected < -1.2)
            val state = mapCurrentInput(point, input.diagnostics, now, frameId)
            audioEngine.pushState(state)
            if(testLog.requested && !stoppingTestLog)testLog.recordFrame(lastInputSnapshot,state,
                inputQualityPolicy.assess(input.diagnostics,now,mountingFrameConfirmed),currentLogConfig(),now)
        }
    }

    private fun currentLogConfig(): SessionLogAdapter.Config {
        val bias = sensorProvider.calibrationBias()
        val axis = when (mounting.selected) {
            VehicleMountAxis.RIGHT -> 1; VehicleMountAxis.TOP -> 2; VehicleMountAxis.SCREEN -> 3
            VehicleMountAxis.LEFT -> 4; VehicleMountAxis.BOTTOM -> 5; VehicleMountAxis.BACK -> 6; null -> 0
        }
        return SessionLogAdapter.Config(displayUnitCode, axis, mounting.trusted, sensorProvider.calibrationStatus.revision,
            bias[0].toDouble(), bias[1].toDouble(), bias[2].toDouble(), inputQualityPolicy.gpsFreshMs,
            inputQualityPolicy.imuFreshMs, inputQualityPolicy.speedUncertaintyLimitMps)
    }

    private fun startTestLog(firstFrameId: Long) {
        if (activityDestroyed) return
        handler.removeCallbacks(audioLogCollector)
        audioEngine.drainDiagnosticAudio()
        stoppingTestLog = false
        testLogWaitsForAudio = true
        testLogFailure = false
        testLogPlaybackId = 0L
        testLogFirstFrameId = firstFrameId
        testLogStopCause = 5
        val anchor = android.os.SystemClock.elapsedRealtimeNanos()
        val wall = System.currentTimeMillis()
        val config = currentLogConfig()
        val profile = if (audioEngine.s15PrototypeEnabled) "$activeVehicleKey:s15_qualification"
            else "$activeVehicleKey:${audioEngine.normalBankIdentity()}"
        val baseApk = applicationInfo.sourceDir
        val splits = applicationInfo.splitSourceDirs?.copyOf()
        val device = android.os.Build.MODEL.replace(Regex("[^A-Za-z0-9_.:-]"), "_").take(96).ifBlank { "UNKNOWN" }
        testLog.start(profile, config) {
            val build = cachedApkIdentity ?: AndroidSessionLogFiles.apkIdentity(baseApk, splits).also { cachedApkIdentity = it }
            SessionRecorder.Metadata(anchor, wall, build, profile, config.hash(), android.os.Build.VERSION.SDK_INT, device)
        }
        testLogGeneration = testLogOwner.snapshot().generation
        sensorProvider.rawInputObserver = rawLogObserver
        audioEngine.diagnosticLoggingEnabled = true
        handler.post(audioLogCollector)
    }

    private fun requestTestLogStartWhenReady() {
        if (activityDestroyed || !this::testLog.isInitialized || !testLog.requested ||
            stoppingTestLog || !audioRunning) return
        testLogOwner.requestSessionStart(testLogGeneration, android.os.SystemClock.elapsedRealtimeNanos())
    }

    private fun requestStopTestLog(cause: Int, waitForAudio: Boolean, failure: Boolean = false) {
        if (!this::testLog.isInitialized || !testLog.requested) return
        testLogOwner.cancelSessionStart(testLogGeneration)
        stoppingTestLog = true
        testLogStopCause = cause
        testLogFailure = failure
        testLogWaitsForAudio = waitForAudio
        sensorProvider.rawInputObserver = null
        if (!waitForAudio) finishTestLogWhenReady()
    }

    private fun finishTestLogWhenReady() {
        if (!stoppingTestLog || testLogWaitsForAudio || !testLog.requested) return
        val phase = testLogOwner.snapshot().phase
        if (phase == SessionRecordingCoordinator.Phase.STARTING) return
        collectAudioLogRows()
        val now = android.os.SystemClock.elapsedRealtimeNanos()
        if (testLogFailure) testLog.lifecycle(10, 7, now, currentLogConfig())
        testLog.lifecycle(2, testLogStopCause, now, currentLogConfig())
        testLog.stop()
        stoppingTestLog = false
        audioEngine.diagnosticLoggingEnabled = false
        handler.removeCallbacks(audioLogCollector)
        pushUiState()
    }

    private val rawLogObserver = object : RawInputObserver {
        override fun gps(sourceNanos: Long, receivedNanos: Long, speedMps: Double?, accuracy: SpeedAccuracy, accepted: Boolean, hasSpeed: Boolean) {
            if (testLog.requested && !stoppingTestLog) testLog.recordGps(sourceNanos, receivedNanos, speedMps, accuracy, accepted, hasSpeed, currentLogConfig())
        }
        override fun imu(sourceNanos: Long, receivedNanos: Long, values: FloatArray, bias: FloatArray, accepted: Boolean) {
            if (!testLog.requested || stoppingTestLog) return
            val selected = mounting.snapshot
            val axis = selected.selected
            val projected = if (selected.trusted && axis != null && values.size >= 3)
                ((values[axis.component] - bias[axis.component]) * axis.sign).takeIf { it.isFinite() } else null
            testLog.recordImu(sourceNanos, receivedNanos, values, bias, projected, accepted, currentLogConfig())
        }
    }

    private val audioLogCollector = object : Runnable {
        override fun run() {
            if (activityDestroyed || !testLog.requested) return
            requestTestLogStartWhenReady()
            collectAudioLogRows()
            handler.postDelayed(this, 100L)
        }
    }
    private fun collectAudioLogRows() {
        if (!this::testLog.isInitialized || !testLog.requested) return
        val batch = audioEngine.drainDiagnosticAudio()
        audioDiagnosticDropped += batch.dropped
        for (row in batch.records) {
            if (row.frameId >= testLogFirstFrameId) testLog.recordAudio(row, currentLogConfig())
            else testLogOwner.observeConfigGap(1)
        }
    }

    fun reportDisplayUnit(unit: String, pageEpoch: Long) {
        if(activityDestroyed || pageEpoch != calibrationPageEpoch)return
        displayUnitCode = when (unit) { "kmh", "km/h" -> 1; "mph" -> 2; else -> 0 }
    }
    fun reportDisplayFrame(dispatchId: String, frameId: String, shown: String, unit: String, receivedNs: Long) {
        if(activityDestroyed)return
        val delivery = dispatchId.toLongOrNull() ?: return
        val frame = frameId.toLongOrNull() ?: return
        val known = uiFrames.acknowledge(delivery, frame, calibrationPageEpoch, receivedNs,
            if(testLog.requested) testLogFirstFrameId else Long.MAX_VALUE) ?: return
        val code = when (unit) { "km/h" -> 1; "mph" -> 2; else -> 0 }
        val value = shown.toDoubleOrNull()?.takeIf { it.isFinite() && it >= 0.0 }
        testLog.recordUi(known, receivedNs, code, value)
    }
    private fun withUiDispatch(json: String, input: SensorInputSnapshot): String {
        val delivery = uiFrames.register(input.controlFrameId, calibrationPageEpoch,
            input.diagnostics.publishElapsedNanos, input.diagnostics.consumeElapsedNanos, android.os.SystemClock.elapsedRealtimeNanos())
        return json.dropLast(1) + ",\"uiDispatchId\":\"${delivery.id}\"}"
    }

    private fun testLogStateJson(): String {
        if (!this::testLogOwner.isInitialized) return "{\"phase\":\"IDLE\"}"
        val state = testLogOwner.snapshot()
        val stats = state.activeStatus ?: state.lastCompleted?.status
        val phase = when {
            stoppingTestLog -> "SAVING"
            state.phase == SessionRecordingCoordinator.Phase.COMPLETE && state.lastCompleted?.generation == testLogGeneration && stats?.state == SessionRecorder.State.IO_FAILED -> "FAILED"
            state.phase == SessionRecordingCoordinator.Phase.COMPLETE && state.lastCompleted?.generation == testLogGeneration && stats?.state == SessionRecorder.State.CAPACITY -> "CAPACITY"
            else -> state.phase.name
        }
        return JSONObject().put("phase", phase).put("bytes", stats?.bytes ?: 0)
            .put("written", stats?.written ?: 0).put("queueDropped", stats?.queueDropped ?: 0)
            .put("rejected", stats?.rejected ?: 0).put("unwritten", stats?.unwritten ?: 0)
            .put("coordinatorDropped", state.coordinatorContentionDrops)
            .put("startupGap", state.startupGapRows).put("configGap", state.configGapRows)
            .put("audioRingDropped", audioDiagnosticDropped).put("uiAckDiscarded", uiFrames.discarded)
            .put("failure", state.failure ?: "").put("exporting", testLogExporting)
            .put("exportAvailable", !testLog.requested && phase != "SAVING" &&
                (state.lastCompleted != null || recoveredTestLog != null))
            .put("latestIsCurrent", state.lastCompleted?.generation == testLogGeneration).toString()
    }

    fun exportTestLog() {
        if(activityDestroyed || !calibrationResumed)return
        if (testLogExporting || testLog.requested || stoppingTestLog) { toast("请先停止声浪并等待日志保存"); return }
        val completed = testLogOwner.snapshot().lastCompleted?.directory
        val recovered = recoveredTestLog
        testLogExporting = true; pushUiState()
        logIo.execute {
            val source = completed?.let(AndroidSessionLogFiles::recordFile) ?: recovered
            if (source == null) { runOnUiThread { testLogExporting=false;pushUiState();toast("本次未产生可导出的日志") }; return@execute }
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                val success = runCatching { AndroidSessionLogFiles.exportDownloads(this, testLogRoot, source) }.getOrDefault(false)
                runOnUiThread { if(!activityDestroyed){testLogExporting=false;pushUiState();toast(if(success)"测试日志已导出到 Downloads/VicoTests" else "导出失败，应用内日志仍保留")} }
            } else runOnUiThread {
                if(activityDestroyed)return@runOnUiThread
                pendingTestLogExport = source
                val intent = android.content.Intent(android.content.Intent.ACTION_CREATE_DOCUMENT).apply {
                    addCategory(android.content.Intent.CATEGORY_OPENABLE);type="text/tab-separated-values"
                    putExtra(android.content.Intent.EXTRA_TITLE,AndroidSessionLogFiles.exportName(source))
                }
                @Suppress("DEPRECATION")
                try { startActivityForResult(intent, TEST_LOG_EXPORT_REQUEST) }
                catch (_:android.content.ActivityNotFoundException) { pendingTestLogExport=null;testLogExporting=false;pushUiState();toast("此设备没有文件保存界面，应用内日志仍保留") }
            }
        }
    }

    @Deprecated("Legacy picker used only for Android 7–9 compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: android.content.Intent?) {
        super.onActivityResult(requestCode,resultCode,data)
        if(requestCode!=TEST_LOG_EXPORT_REQUEST)return
        val source=pendingTestLogExport;pendingTestLogExport=null
        val destination=data?.data
        if(resultCode!=RESULT_OK||source==null||destination==null){testLogExporting=false;pushUiState();return}
        logIo.execute {
            val success=runCatching { contentResolver.openOutputStream(destination)?.use { AndroidSessionLogFiles.copyOwned(testLogRoot,source,it) } ?: error("No export stream") }.isSuccess
            runOnUiThread { if(!activityDestroyed){testLogExporting=false;pushUiState();toast(if(success)"测试日志已导出" else "导出失败，应用内日志仍保留")} }
        }
    }

    fun getStateJson(): String { val input=lastInputSnapshot;return withUiDispatch(buildStateJson(input),input) }

    private fun restoreState() {
        val savedAxis = prefs.getString("mount_axis", null)?.let { runCatching { VehicleMountAxis.valueOf(it) }.getOrNull() }
        mounting = VehicleMountingSession(savedAxis)
        language = prefs.getString("language", "zh") ?: "zh"
        masterVol = prefs.getFloat("master_volume", 1.0f)
        audioEngine.setMasterVol(masterVol)
        outputMode = prefs.getString("output_mode", "speaker") ?: "speaker"
        outputLabel = audioEngine.selectOutput(outputMode)
        requestedOutputId = if (prefs.contains("output_id")) prefs.getInt("output_id", -1) else null
        val requested = prefs.getString("selected_vehicle", vehicleState.selectedKey) ?: vehicleState.selectedKey
        val candidate = if (CurrentVehicleCatalog.isSupported(requested)) requested else CurrentVehicleCatalog.defaultKey
        val key = if (audioEngine.setVehicle(candidate)) candidate else CurrentVehicleCatalog.defaultKey
        activeVehicleKey = key
        vehicleState.select(key)
        selectedVehicleName = CurrentVehicleCatalog.displayName(key)
        vehicleName = selectedVehicleName
    }

    private fun pushUiState() {
        runOnUiThread {
            s14StateJson = JSONObject().put("state", s14Status).put("frames", s14Frames)
                .put("first_done", controlledTrialDone(if (s14PairIndex == 0) "R" else "M"))
                .put("second_done", controlledTrialDone(if (s14PairIndex == 0) "M" else "R"))
                .put("busy", s14.busy || s14FeedbackSaving).put("pair_id", s14PairId).put("pair_index", s14PairIndex)
                .put("pair_matched", pairMatched()).put("revealed", s14Revealed)
                .put("feedback_available", s14Trials.isNotEmpty())
                .put("error", s14.error ?: JSONObject.NULL).toString()
            val input = lastInputSnapshot
            val json = withUiDispatch(buildStateJson(input), input)
            webView.evaluateJavascript("window.__vicoUpdate&&window.__vicoUpdate($json)", null)
        }
    }

    private fun buildStateJson(input: SensorInputSnapshot = lastInputSnapshot): String = buildString {
        append('{')
        append("\"controlFrameId\":\"").append(input.controlFrameId).append("\",")
        append("\"normalBankVariant\":\"").append(audioEngine.normalBankIdentity()).append("\",")
        append("\"normalBankVariantActive\":").append(!s13ReviewActive && s14ReferenceLabel == null && !audioEngine.s15PrototypeEnabled).append(',')
        append("\"speed\":").append(input.speedKmh.toInt()).append(',')
        append("\"speedKmh\":\"").append(String.format(Locale.US, "%.1f", input.speedKmh)).append("\",")
        append("\"accel\":\"").append(String.format(Locale.US, "%.2f", input.accelMps2)).append("\",")
        append("\"rpm\":0,")
        append("\"gear\":").append(lastGear).append(',')
        append("\"freq\":\"0.0\",")
        append("\"gpsOk\":").append(input.gpsOk).append(',')
        append("\"vehicle\":\"").append(selectedVehicleName).append("\",")
        append("\"selectedVehicleKey\":\"").append(vehicleState.selectedKey).append("\",")
        append("\"playingVehicleKey\":\"").append(vehicleState.playingKey ?: "").append("\",")
        append("\"previewVehicleKey\":\"").append(previewVehicleKey ?: "").append("\",")
        append("\"profile\":\"").append(character.label).append("\",")
        append("\"profileKey\":\"").append(character.name.lowercase()).append("\",")
        append("\"running\":").append(audioRunning).append(',')
        append("\"muted\":").append(muted).append(',')
        append(calibrationStateJson()).append(',')
        append("\"inputDiagnostics\":").append(input.diagnostics.toJson()).append(',')
        append("\"inputQuality\":").append(inputQualityPolicy.assess(input.diagnostics,
            android.os.SystemClock.elapsedRealtimeNanos(), mountingFrameConfirmed).toJson()).append(',')
        append("\"mounting\":").append(mountingStateJson()).append(',')
        append("\"testLog\":").append(testLogStateJson()).append(',')
        append("\"demo\":").append(input.diagnostics.sourceMode == InputDiagnostics.SourceMode.DEMO).append(',')
        append("\"demoScenario\":\"").append(demoScenario).append("\",")
        append("\"recording\":").append(recording).append(',')
        append("\"language\":\"").append(language).append("\",")
        append("\"s15Prototype\":").append(audioEngine.s15PrototypeEnabled).append(',')
        append("\"s15Preparing\":").append(s15Preparing).append(',')
        append("\"masterVolume\":").append(masterVol).append(',')
        append("\"outputMode\":\"").append(outputMode).append("\",")
        append("\"outputLabel\":\"").append(outputLabel).append("\",")
        append("\"outputDevices\":").append(buildOutputDevicesJson()).append(',')
        append("\"s14\":").append(s14StateJson).append(',')
        append("\"sampleCount\":").append(csvExporter.sampleCount).append(',')
        append("\"ax\":").append(input.ax).append(',')
        append("\"ay\":").append(input.ay).append(',')
        append("\"az\":").append(input.az).append(',')
        append("\"gx\":").append(input.gx).append(',')
        append("\"gy\":").append(input.gy).append(',')
        append("\"gz\":").append(input.gz)
        append('}')
    }

    private fun refreshOutputDevices() {
        val physical = audioEngine.outputDevices().toMutableList()
        val categories = listOf(
            AudioOutputCategory.BUILTIN,
            AudioOutputCategory.BLUETOOTH,
            AudioOutputCategory.WIRED,
        )
        categories.forEachIndexed { index, category ->
            if (physical.none { it.category == category }) {
                physical += AudioOutputDevice(
                    id = -100 - index,
                    type = 0,
                    category = category,
                    label = when (category) {
                        AudioOutputCategory.BUILTIN -> "本机扬声器（不可用）"
                        AudioOutputCategory.BLUETOOTH -> "蓝牙输出（未连接）"
                        AudioOutputCategory.WIRED -> "有线输出（未连接）"
                        AudioOutputCategory.OTHER -> "其他输出"
                    },
                    connected = false,
                    selectable = false,
                    routed = false,
                )
            }
        }
        outputDevices = physical.map { it.copy(routed = it.id == audioEngine.routedOutputDeviceId()) }
        val requested = outputDevices.firstOrNull { it.id == requestedOutputId }
        val routed = outputDevices.firstOrNull { it.routed }
        outputLabel = requested?.label ?: routed?.label ?: outputLabel
    }

    fun getAudioOutputsJson(): String = buildOutputDevicesJson()

    private fun buildOutputDevicesJson(): String = buildString {
        append('[')
        outputDevices.forEachIndexed { index, device ->
            if (index > 0) append(',')
            append('{')
            append("\"id\":").append(device.id).append(',')
            append("\"category\":\"").append(device.category.name.lowercase(Locale.US)).append("\",")
            append("\"label\":\"").append(device.label).append("\",")
            append("\"connected\":").append(device.connected).append(',')
            append("\"selectable\":").append(device.selectable).append(',')
            append("\"routed\":").append(device.routed)
            append('}')
        }
        append(']')
    }

    private fun toast(s: String) = Toast.makeText(this, s, Toast.LENGTH_SHORT).show()

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        invalidateCalibrationPage()
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

}
