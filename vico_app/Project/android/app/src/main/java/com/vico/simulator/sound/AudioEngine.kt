package com.vico.simulator.sound

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import com.vico.simulator.logging.AudioDiagnosticRing
import com.vico.simulator.audio.AudioOutputCatalog
import com.vico.simulator.audio.AudioOutputCategory
import com.vico.simulator.audio.AudioOutputDevice
import java.io.OutputStream

/**
 * 原生 PCM 音频引擎。播放 S12/Matlab 导出的 mono IEEE-float 声库，
 * 流式写入 [AudioTrack]。无点击启停（短淡入淡出）。
 */
class AudioEngine(context: Context) {

    private var sampleRate: Int = 48000
    private val blockSize: Int get() = sampleRate / 50
    private val model = MatlabV6SoundBankEngine(context.assets)
    private val qualificationRoute = C63QualificationRoute()

    internal fun setQualificationProvider(provider: C63QualificationPcmProvider?): Boolean =
        debuggable && !running && qualificationRoute.prepare(provider)

    @Volatile private var current: SoundState? = null
    @Volatile private var masterVol: Float = 1.0f
    @Volatile private var running: Boolean = false
    @Volatile private var muted: Boolean = false
    @Volatile private var digitalCapture: BoundedPcmCapture? = null
    @Volatile private var reviewCoreCapture: BoundedPcmCapture? = null
    @Volatile private var reviewSession: S13ReviewSession? = null
    @Volatile private var referenceSession: S14ReferenceSession? = null
    @Volatile private var referenceTicket: S14TrialCoordinator.Ticket? = null
    @Volatile private var referenceCancelReason: String? = null
    private var failNextReferenceStartup = false
    private val debuggable = context.applicationInfo.flags and android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE != 0
    @Volatile var onS14Finished: ((S14CompletedCapture) -> Unit)? = null
    @Volatile var onS14Progress: ((S14TrialCoordinator.Ticket, Int, String) -> Unit)? = null
    @Volatile var referenceRouteId: Int? = null
        private set
    @Volatile var lastAudioError: String? = null
        private set
    @Volatile var lastMixStats: S13MixSnapshot? = null
        private set
    @Volatile var onReviewFinished: ((Boolean, String?) -> Unit)? = null
    @Volatile var onAudioFailure: ((Long,String) -> Unit)? = null
    @Volatile var onPlaybackFinished: ((Long) -> Unit)? = null
    @Volatile var diagnosticLoggingEnabled = false
    private val diagnosticRing = AudioDiagnosticRing()
    @Volatile private var diagnosticRouteCode = 0
    /** Non-audio collector samples platform routing; the writer reads only the cached integer. */
    fun drainDiagnosticAudio(): AudioDiagnosticRing.Batch {
        val type = runCatching { track?.routedDevice?.type }.getOrNull()
        diagnosticRouteCode = when(type?.let(AudioOutputCatalog::categoryFor)) {
            AudioOutputCategory.BUILTIN -> 1; AudioOutputCategory.BLUETOOTH -> 3
            AudioOutputCategory.WIRED -> if(type==11||type==12||type==22||type==23)4 else 2
            AudioOutputCategory.OTHER -> 5; null -> 0
        }
        return diagnosticRing.drain()
    }
    @Volatile var onS15Finished: ((Long,String) -> Unit)? = null
    @Volatile private var playbackId=0L
    fun playbackIdentity()=playbackId
    private val s15WriteTiming=SessionTiming()
    @Volatile private var s15UnderrunStart=0
    @Volatile private var s15UnderrunEnd=0
    @Volatile private var s15BufferFrames=0
    @Volatile private var s15RouteId:Int?=null
    @Volatile private var s15SubmittedPeak=0.0
    @Volatile private var s15AcceptedFrames=0L
    fun s15OutputJson()=org.json.JSONObject().put("submitted_peak",s15SubmittedPeak)
        .put("accepted_frames",s15AcceptedFrames)
        .put("route_id",s15RouteId ?: org.json.JSONObject.NULL).put("buffer_frames",s15BufferFrames)
        .put("underrun_start",s15UnderrunStart).put("underrun_end",s15UnderrunEnd)
        .put("whole_session_write_calls",s15WriteTiming.count).put("max_write_wait_ns",s15WriteTiming.maxNs)
        .put("p99_write_wait_ns_upper",s15WriteTiming.percentile(99) ?: org.json.JSONObject.NULL).toString()
    private val runEnvelope = GainEnvelope()
    private val contentEnvelope = GainEnvelope()

    @Volatile private var track: AudioTrack? = null
    private var thread: Thread? = null
    private var preferredDevice: AudioDeviceInfo? = null
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val deviceInstance = context.getSharedPreferences("s14-device", Context.MODE_PRIVATE).let { prefs ->
        prefs.getString("instance", null) ?: java.util.UUID.randomUUID().toString().also {
            prefs.edit().putString("instance", it).apply()
        }
    }

    @Synchronized
    fun start(): Boolean {
        if (running) return true
        if (thread?.isAlive == true) return false
        lastAudioError = null
        lastMixStats = null
        val capture = digitalCapture?.takeUnless { it.isFinished }
        if (capture != null && sampleRate != S13ReviewContract.SAMPLE_RATE) {
            return failCaptureStart(capture, "S13 digital capture requires 48 kHz mono")
        }
        ensureTrack()
        val t = track ?: return failCaptureStart(capture, "AudioTrack was not created")
        if (t.state != AudioTrack.STATE_INITIALIZED) {
            return failCaptureStart(capture, "AudioTrack is not initialized")
        }
        try {
            t.play()
        } catch (error: Throwable) {
            return failCaptureStart(capture, "AudioTrack.play failed: ${error.message}")
        }
        if (t.playState != AudioTrack.PLAYSTATE_PLAYING) {
            return failCaptureStart(capture, "AudioTrack did not enter PLAYING state")
        }
        running = true
        val owner=++playbackId
        thread = Thread({ playLoop(capture,owner) }, "vico-audio").apply {
            isDaemon = true
            start()
        }
        return true
    }

    private fun failCaptureStart(capture: BoundedPcmCapture?, message: String): Boolean {
        lastAudioError = message
        capture?.markFailed()
        capture?.finish()
        return false
    }

    @Synchronized
    fun startS13Review(vehicleKey: String): Boolean {
        if (running || thread?.isAlive == true) {
            lastAudioError = "Stop normal playback before starting S13 review"
            return false
        }
        if (digitalCapture?.isFinished == false) {
            lastAudioError = "Finish or cancel the previous PCM capture first"
            return false
        }
        if (reviewCoreCapture?.isFinished == false) {
            lastAudioError = "Export or finish the previous review capture first"
            return false
        }
        if (!setVehicle(vehicleKey)) {
            lastAudioError = "Unable to load vehicle bank: $vehicleKey"
            return false
        }
        val session = try {
            model.newS13ReviewSession(vehicleKey)
        } catch (error: Exception) {
            lastAudioError = "S13 review rejected: ${error.message}"
            return false
        }
        reviewSession = session
        digitalCapture = BoundedPcmCapture(binding = session.captureBinding)
        reviewCoreCapture = BoundedPcmCapture(
            binding = session.captureBinding,
            captureDomain = "POST_ENVELOPES_PRE_AUDIOTRACK_SUBMISSION",
        )
        current = null
        if (!start()) {
            reviewSession = null
            reviewCoreCapture?.markFailed()
            reviewCoreCapture?.finish()
            return false
        }
        return true
    }

    @Synchronized
    fun startS14Reference(session: S14ReferenceSession, ticket: S14TrialCoordinator.Ticket): Boolean {
        if (muted) { lastAudioError = "请先关闭应用静音，再进行原始声音对照"; return false }
        if (running || thread?.isAlive == true || digitalCapture?.isFinished == false || reviewCoreCapture?.isFinished == false) {
            lastAudioError = "Finish current playback/capture first"
            return false
        }
        if (sampleRate != S13ReviewContract.SAMPLE_RATE) disposeTrack()
        sampleRate = S13ReviewContract.SAMPLE_RATE
        referenceRouteId = null
        referenceSession = session
        referenceTicket = ticket
        referenceCancelReason = null
        digitalCapture = BoundedPcmCapture()
        reviewCoreCapture = BoundedPcmCapture(captureDomain = "S14_REFERENCE_PRE_AUDIOTRACK_SUBMISSION")
        val started = try {
            if (failNextReferenceStartup) { failNextReferenceStartup = false; error("DEBUG_REFERENCE_START_FAILURE") }
            start()
        } catch (error: Exception) {
            lastAudioError = "Reference start failed: ${error.message}"
            false
        }
        if (!started) {
            running = false
            referenceSession = null
            referenceTicket = null
            digitalCapture?.markFailed()
            digitalCapture?.finish()
            reviewCoreCapture?.markFailed()
            reviewCoreCapture?.finish()
            runCatching { disposeTrack() }
            return false
        }
        return true
    }

    fun failNextReferenceStartupForDebug() {
        check(debuggable)
        failNextReferenceStartup = true
    }

    fun isReviewing(): Boolean = reviewSession != null || referenceSession != null

    /** Arm an unbound application-side PCM capture; select the vehicle first. */
    @Synchronized
    fun armDigitalCapture() {
        check(!running && thread?.isAlive != true) { "Stop audio before arming capture" }
        check(sampleRate == S13ReviewContract.SAMPLE_RATE)
        check(digitalCapture?.isFinished != false) { "A capture is already armed" }
        digitalCapture = BoundedPcmCapture()
    }

    @Synchronized
    fun cancelDigitalCapture() {
        check(!running && thread?.isAlive != true) { "Stop audio before cancelling capture" }
        digitalCapture?.takeUnless { it.isFinished }?.let {
            it.markFailed()
            it.finish()
        }
    }

    /** Export only after stop; the caller owns the stream and must run off the audio thread. */
    fun exportDigitalCapture(output: OutputStream): S13PcmCaptureReport {
        val capture = checkNotNull(digitalCapture) { "No digital capture was armed" }
        return capture.exportF32le(output)
    }

    fun exportReviewCoreCapture(output: OutputStream): S13PcmCaptureReport {
        val capture = checkNotNull(reviewCoreCapture) { "No S13 core capture was armed" }
        return capture.exportF32le(output)
    }

    fun stop(reason: String = "USER_STOP") {
        qualificationRoute.clear()
        if (referenceSession != null) referenceCancelReason = reason
        running = false
        // playLoop 自行淡出后停 track
    }

    fun setMasterVol(v: Float) {
        masterVol = v.coerceIn(0f, 1f)
    }

    fun setMuted(on: Boolean) {
        muted = on
    }

    fun outputDevices(): List<AudioOutputDevice> {
        val routedId = track?.routedDevice?.id
        return audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
            .mapNotNull { device ->
                val category = AudioOutputCatalog.categoryFor(device.type)
                if (category == AudioOutputCategory.OTHER) return@mapNotNull null
                AudioOutputDevice(
                    id = device.id,
                    type = device.type,
                    category = category,
                    label = friendlyLabel(device.type, category),
                    connected = true,
                    selectable = true,
                    routed = device.id == routedId,
                )
            }
            .distinctBy { it.id }
    }

    fun routedOutputDeviceId(): Int? = track?.routedDevice?.id

    fun selectOutputDevice(id: Int): Boolean {
        val device = audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
            .firstOrNull { it.id == id } ?: return false
        val category = AudioOutputCatalog.categoryFor(device.type)
        if (!AudioOutputCatalog.isSelectable(category, connected = true)) return false
        preferredDevice = device
        return track?.setPreferredDevice(device) ?: true
    }

    fun selectOutput(mode: String): String {
        val devices = audioManager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
        val device = when (mode) {
            "speaker" -> devices.firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_SPEAKER }
            "bluetooth" -> devices.firstOrNull {
                it.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP ||
                    it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
                    it.type == AudioDeviceInfo.TYPE_BLE_HEADSET
            }
            else -> null
        }
        preferredDevice = device
        val applied = device != null && (track?.setPreferredDevice(device) ?: true)
        return if (applied) device!!.productName.toString() else ""
    }

    /** Explicit measured or synthetic controls for the current S12 / historical MATLAB bank. */
    fun mapMeasuredPoint(point: DrivePoint, control: DriveInputControl): SoundState =
        model.mapMeasuredPoint(point, control)

    fun mapSyntheticPoint(point: DrivePoint, source: DriveInputSource, frameId: Long = 0L, controlTimeNanos: Long? = null): SoundState =
        model.mapSyntheticPoint(point, source, frameId, controlTimeNanos)

    @Synchronized
    fun setS15Prototype(enabled:Boolean):Boolean {
        if(running || thread?.isAlive==true || referenceSession!=null || reviewSession!=null || digitalCapture?.isFinished==false) return false
        return model.setPrototype(enabled)
    }
    val s15PrototypeEnabled get()=model.prototypeEnabled
    fun s15TimingJson()=model.prototypeTimingJson()
    fun s15InputsJson()=model.prototypeInputsJson()

    @Synchronized
    fun setVehicle(vehicleKey: String): Boolean {
        qualificationRoute.clear()
        if (digitalCapture?.isFinished == false) {
            lastAudioError = "Finish or cancel digital capture before changing vehicle"
            return false
        }
        val loaded = model.setVehicle(vehicleKey)
        if (loaded) {
            val nextSampleRate = model.sampleRateHz()
            if (track != null && nextSampleRate != sampleRate) disposeTrack()
            sampleRate = nextSampleRate
        }
        current = null
        return loaded
    }

    @Suppress("UNUSED_PARAMETER")
    fun setCharacter(p: SoundProfile) = Unit

    fun pushState(state: SoundState) {
        current = state
    }

    fun release() {
        if (referenceSession != null) referenceCancelReason = "ACTIVITY_DESTROY"
        running = false
        try { track?.pause(); track?.stop() } catch (_: Exception) {}
        try { thread?.join(500) } catch (_: InterruptedException) {}
        if (thread?.isAlive == true) {
            lastAudioError = "Writer still alive; resources retained until it exits"
            return
        }
        disposeTrack()
    }

    private fun disposeTrack() {
        check(thread?.isAlive != true) { "Cannot release a live audio writer" }
        track?.run {
            try { stop() } catch (_: Throwable) {}
            release()
        }
        track = null
        thread = null
    }

    private fun ensureTrack() {
        if (track != null) return
        val minBuf = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_FLOAT,
        ).coerceAtLeast(blockSize * 4 * 2)
        @Suppress("DEPRECATION")
        track = AudioTrack(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .build(),
            AudioFormat.Builder()
                .setSampleRate(sampleRate)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
                .build(),
            minBuf,
            AudioTrack.MODE_STREAM,
            AudioManager.AUDIO_SESSION_ID_GENERATE,
        )
        preferredDevice?.let { track?.setPreferredDevice(it) }
    }

    private fun playLoop(capture: BoundedPcmCapture?,owner:Long) {
        val t = track
        val review = reviewSession
        val reference = referenceSession
        val ticket = referenceTicket
        val startedAtMs = System.currentTimeMillis()
        var startConditions: S14OutputConditions? = null
        var endConditions: S14OutputConditions? = null
        var playbackHeadFrames: Long? = null
        var playbackPositionComplete: Boolean? = null
        var candidateStartConditions:S14OutputConditions?=null
        val reviewCore = reviewCoreCapture
        val inputGate = AudioInputGate()
        val diagnosticBufferFrames = t?.bufferSizeInFrames ?: 0
        var diagnosticBlock = 0L
        var windowBlocks = 0L; var windowWritten = 0L; var windowClips = 0L
        var windowRender = 0L; var windowWrite = 0L; var windowPeak = 0.0
        var lastDiagnosticShift = Double.NaN; var lastDiagnosticAfterfire = Double.NaN
        var previousDiagnosticUsable = false
        var previousDiagnosticSource: DriveInputSource? = null
        var lastContinuousState: SoundState? = null
        if (t == null) {
            capture?.markFailed()
            capture?.finish()
            running = false
            return
        }
        try {
            if(model.prototypeEnabled && review==null && reference==null) {
                android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_AUDIO)
                s15WriteTiming.clear();s15SubmittedPeak=0.0;s15RouteId=null;s15AcceptedFrames=0L
                s15BufferFrames=t.bufferSizeInFrames;s15UnderrunStart=t.underrunCount;s15UnderrunEnd=s15UnderrunStart
            }
            while (running || runEnvelope.value > 0.001f) {
                if (reference != null) {
                    if (!running) break
                    val route = t.routedDevice?.id ?: error("S14 actual output route unavailable")
                    if (referenceRouteId == null) referenceRouteId = route
                    check(referenceRouteId == route) { "S14 output route changed" }
                    val conditions = outputConditions(t)
                    if (startConditions == null) startConditions = conditions
                    check(conditions == startConditions) { "S14 route or media volume/mute changed" }
                    val pcm = reference.renderNext() ?: break
                    reviewCore?.beginBlock(pcm.size)
                    reviewCore?.accept(pcm, 0, pcm.size)
                    writeAllPcm(pcm, capture) { data, offset, count ->
                        t.write(data, offset, count, AudioTrack.WRITE_BLOCKING)
                    }
                    check(t.routedDevice?.id == referenceRouteId) { "S14 output route changed during write" }
                    ticket?.let { onS14Progress?.invoke(it, reference.framesRendered, "PLAYING") }
                    if (reference.isComplete) { break }
                    continue
                }
                if (review != null) {
                    if (!running) break
                    val pcm = review.renderNext()
                    if (pcm == null) {
                        running = false
                        break
                    }
                    reviewCore?.beginBlock(pcm.size)
                    reviewCore?.accept(pcm, 0, pcm.size)
                    writeAllPcm(pcm, capture) { data, offset, count ->
                        t.write(data, offset, count, AudioTrack.WRITE_BLOCKING)
                    }
                    if (review.isComplete) {
                        running = false
                        break
                    }
                    continue
                }
                // Read publication before the stop flag: stop writes running=false before a
                // restored REAL publication. Observing that publication must observe the stop.
                val diagnosticStarted = android.os.SystemClock.elapsedRealtimeNanos()
                val published = current
                val writerRunning = running
                if (!writerRunning && lastContinuousState == null) break
                val state = selectAudioWriterSnapshot(writerRunning, published, lastContinuousState)
                val renderInputValid = state != null && state.amplitude > 0.0 && C63QualificationRoute.validInput(state)
                check(model.acceptsPlaybackInput(state?.inputControl, renderInputValid)) {
                    "Experimental renderer accepts only explicit qualification input; prepare it again before retrying"
                }
                val control = state?.inputControl?.let {
                    if (renderInputValid) it else it.copy(speedUsable = false, accelerationUsable = false)
                }
                val gate = inputGate.evaluate(control, state?.timeS ?: Double.NaN,
                    android.os.SystemClock.elapsedRealtimeNanos(), writerRunning)
                if (gate.clearTransients) {
                    lastDiagnosticShift = Double.NaN; lastDiagnosticAfterfire = Double.NaN
                    model.clearTransientEvents()
                    // An explicitly prepared qualification provider is not a live-input epoch.
                    if (state?.inputControl?.source != DriveInputSource.QUALIFICATION) qualificationRoute.clear()
                }
                val sourceAvailable = gate.usable && renderInputValid
                if (!sourceAvailable) qualificationRoute.clear()
                val runGain = runEnvelope.step(running)
                val contentGain = contentEnvelope.step(running && sourceAvailable && !muted && state?.muted != true)
                val diagnosticConsumedNs = android.os.SystemClock.elapsedRealtimeNanos()
                val pcm: FloatArray = if (sourceAvailable) {
                    val eventState = if (gate.allowEvents) state!! else state!!.copy(
                        afterfireTrigger = false, shiftTrigger = false)
                    val renderState = if(model.prototypeEnabled) eventState else eventState.copy(muted = false)
                    // The bounded fade tail must never carry shift/afterfire or a torque-cut envelope.
                    lastContinuousState = renderState.copy(afterfireTrigger = false, shiftTrigger = false, shiftGain = 1.0)
                    val legacy = model.renderState(renderState, blockSize)
                    if (model.prototypeEnabled) legacy else qualificationRoute.render(renderState, blockSize, sampleRate) ?: legacy
                } else if (contentGain > 0f && lastContinuousState != null && !model.prototypeEnabled) {
                    // Existing GainEnvelope reaches exact zero in bounded blocks; never replay stale input indefinitely.
                    model.renderState(lastContinuousState!!, blockSize)
                } else {
                    lastContinuousState = null
                    FloatArray(blockSize)
                }
                val scale = (masterVol * runGain * contentGain).coerceIn(0f, 1f)
                if (scale < 1f) {
                    for (i in pcm.indices) pcm[i] *= scale
                }
                if(model.prototypeEnabled) {
                    if(candidateStartConditions==null)candidateStartConditions=runCatching{outputConditions(t)}.getOrNull()
                    for(value in pcm)s15SubmittedPeak=maxOf(s15SubmittedPeak,kotlin.math.abs(value.toDouble()))
                    val route=t.routedDevice?.id
                    if(s15RouteId==null)s15RouteId=route
                    else check(route==s15RouteId){"C63 candidate output route changed"}
                }
                val diagnosticRenderNs = android.os.SystemClock.elapsedRealtimeNanos() - diagnosticStarted
                var eventMask = 0
                if (sourceAvailable && gate.allowEvents && state != null) {
                    if (state.shiftTrigger && state.timeS != lastDiagnosticShift) {eventMask = eventMask or 1;lastDiagnosticShift = state.timeS}
                    if (state.afterfireTrigger && state.timeS != lastDiagnosticAfterfire) {eventMask = eventMask or 2;lastDiagnosticAfterfire = state.timeS}
                }
                if (previousDiagnosticUsable && previousDiagnosticSource == DriveInputSource.REAL && !gate.usable && control?.source == DriveInputSource.REAL)
                    eventMask = eventMask or (if (android.os.SystemClock.elapsedRealtimeNanos() > control.validUntilElapsedNanos) 4 else 8)
                previousDiagnosticUsable = gate.usable
                previousDiagnosticSource = control?.source
                var submittedFrames = 0L
                val diagnosticWriteStart = android.os.SystemClock.elapsedRealtimeNanos()
                try {
                    writeAllPcm(pcm, capture) { data, offset, count ->
                        val start=System.nanoTime()
                        try {t.write(data, offset, count, AudioTrack.WRITE_BLOCKING).also {written ->
                            if(written>0){submittedFrames+=written;if(model.prototypeEnabled)s15AcceptedFrames+=written}
                        }} finally {if(model.prototypeEnabled)s15WriteTiming.record(System.nanoTime()-start)}
                    }
                } finally {
                    diagnosticBlock++
                    if(diagnosticLoggingEnabled) {
                        windowBlocks++;windowWritten+=submittedFrames
                        windowRender=maxOf(windowRender,diagnosticRenderNs)
                        windowWrite=maxOf(windowWrite,android.os.SystemClock.elapsedRealtimeNanos()-diagnosticWriteStart)
                        for(value in pcm){val magnitude=kotlin.math.abs(value.toDouble());if(magnitude.isFinite())windowPeak=maxOf(windowPeak,magnitude);if(magnitude>1.0)windowClips++}
                        if(windowBlocks>=5 || eventMask!=0 || !running) {
                            val route = diagnosticRouteCode
                            diagnosticRing.publish(diagnosticBlock,control?.controlFrameId ?: 0L,control?.epoch ?: 0L,
                                diagnosticConsumedNs,sampleRate,diagnosticBufferFrames,t.underrunCount,
                                windowRender,windowWrite,windowWritten,windowClips,windowPeak,route,eventMask,
                                state?.afterfireCauseCode ?: 0,state?.afterfireSourceId ?: control?.gpsSampleElapsedNanos ?: 0L,windowBlocks)
                            windowBlocks=0;windowWritten=0;windowClips=0;windowRender=0;windowWrite=0;windowPeak=0.0
                        }
                    } else {windowBlocks=0;windowWritten=0;windowClips=0;windowRender=0;windowWrite=0;windowPeak=0.0}
                }
                if (!running && runEnvelope.value <= 0f) break
            }
        } catch (error: Exception) {
            lastAudioError = "${error.javaClass.simpleName}: ${error.message}"
            capture?.markFailed()
        } finally {
            qualificationRoute.clear()
            if (reference != null && reference.isComplete && running && lastAudioError == null) {
                ticket?.let { onS14Progress?.invoke(it, reference.framesRendered, "DRAINING") }
                val deadline = android.os.SystemClock.elapsedRealtime() + 2000L
                while (running && android.os.SystemClock.elapsedRealtime() < deadline) {
                    playbackHeadFrames = t.playbackHeadPosition.toLong() and 0xffffffffL
                    if (playbackHeadFrames >= S13ReviewContract.TOTAL_FRAMES) break
                    try { Thread.sleep(10) } catch (_: InterruptedException) { break }
                }
                playbackPositionComplete = playbackHeadFrames?.let { it >= S13ReviewContract.TOTAL_FRAMES }
            }
            if (reference != null) {
                endConditions = runCatching { outputConditions(t) }.getOrNull()
                if (endConditions != startConditions && lastAudioError == null) lastAudioError = "S14 output conditions changed"
            }
            running = false
            if(model.prototypeEnabled)s15UnderrunEnd=t.underrunCount
            if(model.prototypeEnabled && review==null && reference==null) {
                val receipt=org.json.JSONObject().put("candidate_id",com.vico.simulator.sound.s15.C63HeadroomProfile.ID)
                    .put("playback_head_frames",t.playbackHeadPosition.toLong() and 0xffffffffL)
                    .put("frames_generated",org.json.JSONObject(model.prototypeTimingJson()).optLong("frames"))
                    .put("output",org.json.JSONObject(s15OutputJson())).put("audio_error",lastAudioError ?: org.json.JSONObject.NULL)
                    .put("start_media_volume",candidateStartConditions?.mediaVolume ?: org.json.JSONObject.NULL)
                    .put("start_media_muted",candidateStartConditions?.mediaMuted ?: org.json.JSONObject.NULL)
                    .put("end_media_volume",audioManager.getStreamVolume(AudioManager.STREAM_MUSIC))
                    .put("headroom_scalar",com.vico.simulator.sound.s15.C63HeadroomProfile.SCALAR)
                    .put("source_inventory_sha",com.vico.simulator.sound.s15.C63HeadroomProfile.A_SOURCE_INVENTORY_SHA)
                onS15Finished?.invoke(owner,receipt.toString())
            }
            lastMixStats = review?.mixStats() ?: model.renderStats()
            capture?.finish()
            reviewCore?.finish()
            reviewSession = null
            referenceSession = null
            referenceTicket = null
            try { t.stop() } catch (_: Throwable) {}
            if (review != null) {
                onReviewFinished?.invoke(review.isComplete && lastAudioError == null, lastAudioError)
            }
            if(review==null && reference==null) lastAudioError?.let {onAudioFailure?.invoke(owner,it)}
            if (reference != null && ticket != null && capture != null && reviewCore != null) {
                val result = S14PlaybackResult(ticket, reference.expectedSha, startedAtMs, System.currentTimeMillis(),
                    startConditions, endConditions, reference.framesRendered, playbackHeadFrames, playbackPositionComplete,
                    reference.isComplete && lastAudioError == null && referenceCancelReason == null,
                    lastAudioError ?: referenceCancelReason)
                onS14Finished?.invoke(S14CompletedCapture(result, reviewCore, capture))
            }
            if (review == null && reference == null) onPlaybackFinished?.invoke(owner)
        }
    }

    private fun outputConditions(t: AudioTrack): S14OutputConditions {
        val route = checkNotNull(t.routedDevice) { "Actual audio route unavailable" }
        return S14OutputConditions(deviceInstance, android.os.Build.MODEL, android.os.Build.VERSION.SDK_INT,
            route.id, route.type, AudioOutputCatalog.categoryFor(route.type).name, route.productName.toString(),
            audioManager.getStreamVolume(AudioManager.STREAM_MUSIC), audioManager.getStreamMaxVolume(AudioManager.STREAM_MUSIC),
            audioManager.isStreamMute(AudioManager.STREAM_MUSIC))
    }

    private fun friendlyLabel(type: Int, category: AudioOutputCategory): String = when (category) {
        AudioOutputCategory.BUILTIN -> "本机扬声器"
        AudioOutputCategory.BLUETOOTH -> "蓝牙输出"
        AudioOutputCategory.WIRED -> when (type) {
            11, 12, 22, 23 -> "USB 有线输出"
            else -> "有线耳机"
        }
        AudioOutputCategory.OTHER -> "其他输出"
    }
}
