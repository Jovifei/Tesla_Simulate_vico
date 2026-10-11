package com.vico.simulator.logging

import com.vico.simulator.sensor.*
import com.vico.simulator.sound.*
import java.security.MessageDigest

/** Main/control-thread producer. Raw callbacks stay raw; reused samples only appear in control rows. */
class SessionLogAdapter(private val owner: SessionRecordingCoordinator) {
    data class Config(val displayUnit: Int, val mountAxis: Int, val mountConfirmed: Boolean,
        val calibrationRevision: Long, val biasX: Double, val biasY: Double, val biasZ: Double,
        val gpsFreshMs: Double, val imuFreshMs: Double, val uncertaintyMps: Double) {
        fun values(revision: Long): Array<Number?> = arrayOf(revision,1,mountAxis,if(mountConfirmed)1 else 0,
            calibrationRevision,biasX,biasY,biasZ,gpsFreshMs,imuFreshMs,uncertaintyMps,displayUnit)
        fun hash(): String = MessageDigest.getInstance("SHA-256").digest(values(1).joinToString(",").toByteArray())
            .joinToString("") { "%02x".format(it) }
    }
    private var config: Config? = null
    private var revision = 1L
    private var eventId = 0L
    private val frameConfigurations = LinkedHashMap<Long, Long>()
    private data class EventKey(val frame: Long, val code: Int, val source: Long?)
    private data class EventOrigin(val id: Long, val requestedNs: Long, val revision: Long?)
    private val requestedEvents = LinkedHashMap<EventKey, EventOrigin>()
    var requested = false
        private set
    fun start(profile: String, value: Config, metadata: () -> SessionRecorder.Metadata) {
        config=value;revision=1;eventId=0;requested=true
        frameConfigurations.clear();requestedEvents.clear()
        owner.start(profile,value.hash(),value.values(revision),metadata)
    }
    fun stop(){requested=false;owner.stop()}
    private fun ensure(value: Config, ns: Long, frame: Long, epoch: Long, skippedRows: Long = 1L): Long? {
        if(!requested)return null
        if(owner.snapshot().phase != SessionRecordingCoordinator.Phase.RECORDING) {
            // Preserve explicit preparation/no-session loss rather than inventing a complete trace.
            owner.observeUnreadyRows(skippedRows)
            return null
        }
        if(config!=value){
            val next=revision+1
            if(!owner.offerConfig(ns,frame,epoch,value.values(next))){owner.observeConfigGap(skippedRows);return null}
            revision=next;config=value
        }
        return revision
    }
    fun recordFrame(input: SensorInputSnapshot, state: SoundState, quality: InputQualitySnapshot, value: Config, nowNs: Long) {
        val c=state.inputControl ?: return
        val frame=c.controlFrameId ?: return
        val rev=ensure(value,nowNs,frame,c.epoch,2L+(if(state.shiftTrigger)1 else 0)+(if(state.afterfireTrigger)1 else 0)) ?: return
        frameConfigurations[frame]=rev
        while(frameConfigurations.size>256)frameConfigurations.remove(frameConfigurations.keys.first())
        val d=input.diagnostics
        val source=when(c.source){DriveInputSource.REAL->1;DriveInputSource.DEMO->2;DriveInputSource.PREVIEW->3;DriveInputSource.QUALIFICATION->4;else->0}
        val mode=when(d.driveInputMode){InputDiagnostics.DriveInputMode.LIVE->1;InputDiagnostics.DriveInputMode.PREVIEW->2;InputDiagnostics.DriveInputMode.REFERENCE_BYPASS->3}
        val gps=when(quality.gps){GpsQuality.FRESH->1;GpsQuality.UNVERIFIED->2;GpsQuality.STALE->3;GpsQuality.LOW_QUALITY->4;GpsQuality.UNAVAILABLE->5;GpsQuality.SYNTHETIC->6}
        val imu=when(quality.imu){ImuQuality.FRESH->1;ImuQuality.UNCONFIRMED_FRAME->2;ImuQuality.UNAVAILABLE->3;ImuQuality.SYNTHETIC->4}
        val rawSpeed=input.speedKmh.takeIf{d.gpsValid||d.sourceMode==InputDiagnostics.SourceMode.DEMO}?.div(3.6)
        val selectedSpeed=input.speedKmh.takeIf{quality.speedUsable}?.div(3.6)
        val selectedAccel=input.accelMps2.takeIf{quality.accelerationUsable}
        owner.offerActive(SessionRecorder.Kind.CONTROL,nowNs,frame,c.epoch,arrayOf<Number?>(d.inputSession,frame,
            d.publishElapsedNanos,c.validUntilElapsedNanos,c.gpsSampleElapsedNanos,c.imuSampleElapsedNanos,
            rawSpeed,selectedSpeed,selectedAccel,source,mode,gps,imu,if(c.speedUsable)1 else 0,if(c.accelerationUsable)1 else 0,rev))
        owner.offerActive(SessionRecorder.Kind.MODEL,nowNs,frame,c.epoch,arrayOf<Number?>(d.inputSession,frame,
            d.publishElapsedNanos,c.controlTimeElapsedNanos,c.validUntilElapsedNanos,rawSpeed,selectedSpeed,
            state.modelSpeedKmh?.div(3.6),null,state.modelAccelerationMps2,state.rpm,state.gear,state.load,
            state.throttle.takeIf{it.isFinite()},source,mode,gps,imu,if(c.speedUsable)1 else 0,if(c.accelerationUsable)1 else 0,
            state.afterfireCauseCode,state.afterfireSourceId,rev))
        if(state.shiftTrigger)recordEvent(3,2,frame,c.epoch,c.gpsSampleElapsedNanos,state,nowNs,null,rev)
        if(state.afterfireTrigger)recordEvent(4,state.afterfireCauseCode,frame,c.epoch,state.afterfireSourceId,state,nowNs,null,rev)
    }
    fun recordGps(sourceNs: Long, receiveNs: Long, speedMps: Double?, accuracy: SpeedAccuracy,
                  accepted: Boolean, hasSpeed: Boolean, value: Config) {
        if(ensure(value,receiveNs,0,0)==null)return
        val code=when(accuracy.status){SpeedAccuracy.Status.AVAILABLE->1;SpeedAccuracy.Status.NOT_REPORTED->2;SpeedAccuracy.Status.UNSUPPORTED_API->3;SpeedAccuracy.Status.INVALID->4}
        owner.offerActive(SessionRecorder.Kind.GPS,receiveNs,0,0,arrayOf<Number?>(sourceNs,receiveNs,
            speedMps?.takeIf{hasSpeed&&it.isFinite()},accuracy.metersPerSecond,code,if(accepted)1 else 0,1,
            (receiveNs-sourceNs).takeIf{it>=0}?.div(1e6),if(hasSpeed)1 else 0))
    }
    fun recordImu(sourceNs: Long, receiveNs: Long, raw: FloatArray, bias: FloatArray,
                  longitudinal: Double?, accepted: Boolean, value: Config) {
        val rev=ensure(value,receiveNs,0,0) ?: return
        fun a(v:FloatArray,i:Int)=v.getOrNull(i)?.toDouble()?.takeIf{it.isFinite()}
        owner.offerActive(SessionRecorder.Kind.IMU,receiveNs,0,0,arrayOf<Number?>(sourceNs,receiveNs,
            a(raw,0),a(raw,1),a(raw,2),a(bias,0),a(bias,1),a(bias,2),longitudinal,null,
            value.mountAxis,if(accepted)1 else 0,(receiveNs-sourceNs).takeIf{it>=0}?.div(1e6),rev))
    }
    fun recordUi(dispatch: UiFrameLedger.Dispatch, receivedNs: Long, displayUnit: Int, displayValue: Double?) {
        if(!requested)return
        val kmh=when(displayUnit){1->displayValue;2->displayValue?.div(.621371);else->null}
        owner.offerActive(SessionRecorder.Kind.UI_ACK,receivedNs,dispatch.frameId,0,arrayOf<Number?>(dispatch.publishNs,
            dispatch.consumeNs,dispatch.dispatchNs,receivedNs,kmh,displayUnit,displayValue))
    }
    fun recordAudio(record: AudioDiagnosticRing.Record, @Suppress("UNUSED_PARAMETER") value: Config) {
        if(!requested)return
        val rev=frameConfigurations[record.frameId]
        owner.offerActive(SessionRecorder.Kind.AUDIO,record.elapsedNs,record.frameId,record.epoch,arrayOf<Number?>(
            record.blockId,record.sampleRate,record.bufferFrames,record.underruns.takeIf{it>=0},record.renderNs,record.writeNs,
            record.writtenFrames,record.clipCount,record.peak.takeIf{it.isFinite()},record.routeCode,record.blocksInWindow))
        if(record.eventMask and 1 != 0)recordEvent(3,2,record.frameId,record.epoch,record.eventSourceId,null,null,record.elapsedNs,rev)
        if(record.eventMask and 2 != 0)recordEvent(4,record.causeCode,record.frameId,record.epoch,record.eventSourceId,null,null,record.elapsedNs,rev)
        if(record.eventMask and 8 != 0)recordEvent(0,4,record.frameId,record.epoch,null,null,null,record.elapsedNs,rev)
        if(record.eventMask and 4 != 0)recordEvent(5,3,record.frameId,record.epoch,null,null,null,record.elapsedNs,rev)
    }
    fun lifecycle(event: Int, cause: Int, ns: Long, value: Config) {
        val rev=ensure(value,ns,0,0) ?: return
        recordEvent(event,cause,0,0,null,null,ns,null,rev)
    }
    private fun recordEvent(event:Int,cause:Int,frame:Long,epoch:Long,source:Long?,state:SoundState?,requestedNs:Long?,consumedNs:Long?,rev:Long?){
        val time=consumedNs ?: requestedNs ?: return
        val key=EventKey(frame,event,source)
        val origin=if(consumedNs!=null)requestedEvents.remove(key) else null
        val id=origin?.id ?: ++eventId
        if(requestedNs!=null&&consumedNs==null&&event in 3..4){
            requestedEvents[key]=EventOrigin(id,requestedNs,rev)
            while(requestedEvents.size>256)requestedEvents.remove(requestedEvents.keys.first())
        }
        owner.offerActive(SessionRecorder.Kind.EVENT,time,frame,epoch,arrayOf<Number?>(event,cause,id,source,frame,
            state?.rpm,state?.gear,state?.throttle?.takeIf{it.isFinite()},state?.load,origin?.requestedNs ?: requestedNs,consumedNs,origin?.revision ?: rev))
    }
}
