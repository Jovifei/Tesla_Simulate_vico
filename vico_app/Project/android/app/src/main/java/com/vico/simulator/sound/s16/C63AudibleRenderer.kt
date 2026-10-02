package com.vico.simulator.sound.s16
import com.vico.simulator.sound.s15.C63IdleRuntime
import com.vico.simulator.sound.s15.C63ShiftRuntime
import com.vico.simulator.sound.s15.FrozenC63Output
import com.vico.simulator.sound.s15.C63HeadroomProfile
import com.vico.simulator.sound.SoundState
import kotlin.math.*

/** Independent AR1 chain: frozen idle, shift, output and headroom. Never self-selects. */
internal class C63AudibleRenderer(private val profile:C63AudibleProfile,private val mode:C63AudibleMode,
    private val qualificationOnly:Boolean=false) {
    val candidateId get()=if(mode==C63AudibleMode.SE)"C63_AR1" else "C63_AR1_"+mode
    private val snapshotKey=profile.identity+"|"+mode
    class Snapshot internal constructor(internal val source:C63AudibleSource.Snapshot,internal val idle:C63IdleRuntime.Snapshot,
        internal val shift:C63ShiftRuntime.Snapshot,internal val output:FrozenC63Output.Snapshot,internal val scalars:DoubleArray,
        internal val frames:Long,internal val index:Int,internal val body:DoubleArray,internal val shifts:BooleanArray,internal val candidateId:String)
    fun snapshot()=Snapshot(source.snapshot(),idle.snapshot(),shift.snapshot(),output.snapshot(),doubleArrayOf(rpm,load,throttle,lastShift,peak,rawPeak),frames,delayIndex,bodyDelay.copyOf(),shiftDelay.copyOf(),snapshotKey)
    fun restore(s:Snapshot){require(s.candidateId==snapshotKey){"Candidate snapshot identity mismatch"};source.restore(s.source);idle.restore(s.idle);shift.restore(s.shift);output.restore(s.output)
        rpm=s.scalars[0];load=s.scalars[1];throttle=s.scalars[2];lastShift=s.scalars[3];peak=s.scalars[4];rawPeak=s.scalars[5];frames=s.frames;delayIndex=s.index;s.body.copyInto(bodyDelay);s.shifts.copyInto(shiftDelay)}
    private val source=C63AudibleSource(profile,mode)
    fun sourceStems()=source.lastStems
    private val idle=C63IdleRuntime()
    private val shift=C63ShiftRuntime()
    private val output=FrozenC63Output()
    private val audioBuffer=FloatArray(960)
    private val bodyDelay=DoubleArray(192);private val shiftDelay=BooleanArray(192);private var delayIndex=0
    private var rpm=Double.NaN;private var load=Double.NaN;private var throttle=Double.NaN
    private var lastShift=Double.NaN
    var peak=0.0
        private set
    var frames=0L
        private set
    var rawPeak=0.0
        private set
    fun render(state:SoundState,count:Int):FloatArray {
        require(count>0 && count<=4800)
        require(state.timeS.isFinite() && state.rpm.isFinite() && state.rpm>=0 && state.rpm<=7200 && state.load.isFinite() && state.load>=0 && state.load<=1 && state.throttle.isFinite() && state.throttle>=0 && state.throttle<=1)
        // AudioTrack's blocking writer consumes this960-frame buffer before reuse.
        val result=if(count==960)audioBuffer else FloatArray(count)
        if(!rpm.isFinite()){rpm=state.rpm;load=state.load;throttle=state.throttle}
        val alpha=1-exp(-1.0/(.035*48000))
        val event=state.shiftTrigger && state.timeS!=lastShift
        if(event)lastShift=state.timeS
        for(n in result.indices) {
            rpm+=alpha*(state.rpm-rpm);load+=alpha*(state.load-load);throttle+=alpha*(state.throttle-throttle)
            val r=rpm.coerceIn(0.0,7200.0);val l=load.coerceIn(0.0,1.0);val t=throttle.coerceIn(0.0,1.0)
            val delayedBody=bodyDelay[delayIndex];val delayedShift=shiftDelay[delayIndex]
            bodyDelay[delayIndex]=source.sample(r,l,t).toDouble();shiftDelay[delayIndex]=event && n==0
            delayIndex=(delayIndex+1)%192
            val body=delayedBody+idle.sample(r,l,t)
            val raw=output.sample(shift.sample(body,delayedShift))
            rawPeak=max(rawPeak,abs(raw))
            val value=raw*C63HeadroomProfile.SCALAR
            peak=max(peak,abs(value));frames++
            check(value.isFinite()) { "C63 candidate nonfinite output rejected" }
            if(!qualificationOnly) check(abs(value)<=.8413951416451951) { "C63 candidate peak/finite contract rejected" }
            result[n]=value.toFloat()
        }
        return result
    }
}
