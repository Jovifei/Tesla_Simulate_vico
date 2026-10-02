package com.vico.simulator.sound.s17
import com.vico.simulator.sound.s16.C63MechanicalTexture

import kotlin.math.*

/** Isolated AR1 source; AH mode preserves frozen valid-input mathematics. */
internal class C63AR2Source(private val profile:C63AR2Profile,private val mode:C63AR2Mode) {
    private val sustained=mode!=C63AR2Mode.AH
    private val eventChange=mode==C63AR2Mode.E2 || mode==C63AR2Mode.SE2
    private val arrivals=if(mode==C63AR2Mode.S2 || mode==C63AR2Mode.SE2)C63BarkArrivalQueue(profile.arrivalSeed,profile.fixedDelay) else null
    val arrivalInjected get()=arrivals?.injectedArea ?: 0.0
    val arrivalEmitted get()=arrivals?.emittedArea ?: 0.0
    val arrivalPending get()=arrivals?.pendingArea() ?: 0.0
    private val texture=if(sustained)C63MechanicalTexture(profile.textureScale) else null
    private val eventProcess=if(eventChange)C63AR2AfterfireRuntime(profile.eventSeed,0.0) else null
    private val profileKey=profile.identity+"|"+mode
    val lastStems=DoubleArray(7)
    class Snapshot internal constructor(internal val scalars:DoubleArray,internal val counters:LongArray,internal val filters:List<DoubleArray>,internal val key:String,internal val stems:DoubleArray,internal val bark:C63BarkArrivalQueue.Snapshot?,internal val texture:C63MechanicalTexture.Snapshot?,internal val events:C63AR2AfterfireRuntime.Snapshot?,internal val sourceFrame:Long,internal val legacyFrames:LongArray,internal val legacyAmplitudes:DoubleArray)
    private fun rings()=listOf(exhaustL,exhaustR,*bark,intake,fireLow,fireHigh)
    private fun modes()=listOf(exhaustPressure,bodyPressure,ground)
    fun snapshot():Snapshot=Snapshot(doubleArrayOf(phase,thermal,lastThrottle,noise,flowRpm),longArrayOf(lastEvent,closeAge,noiseState,legacyAfterfireEvents,legacyAfterfireEpisodes),
        rings().map{it.save()}+modes().map{it.save()}+listOf(rumble1.save(),rumble2.save()),profileKey,lastStems.copyOf(),arrivals?.snapshot(),texture?.snapshot(),eventProcess?.snapshot(),sourceFrame,legacyFireFrames.copyOf(),legacyFireAmplitudes.copyOf())
    fun restore(snapshot:Snapshot) {
        require(snapshot.key==profileKey && snapshot.scalars.size==5 && snapshot.counters.size==5 && snapshot.filters.size==14 && snapshot.stems.size==7 && snapshot.legacyFrames.size==4096 && snapshot.legacyAmplitudes.size==4096) {"Audible source snapshot identity mismatch"}
        val s=snapshot.scalars;val c=snapshot.counters
        phase=s[0];thermal=s[1];lastThrottle=s[2];noise=s[3];flowRpm=s[4]
        lastEvent=c[0];closeAge=c[1];noiseState=c[2];legacyAfterfireEvents=c[3];legacyAfterfireEpisodes=c[4]
        var index=0
        for(ring in rings())ring.load(snapshot.filters[index++])
        for(mode in modes())mode.load(snapshot.filters[index++])
        rumble1.load(snapshot.filters[index++]);rumble2.load(snapshot.filters[index])
        snapshot.bark?.let{arrivals!!.restore(it)};snapshot.texture?.let{texture!!.restore(it)};snapshot.events?.let{eventProcess!!.restore(it)}
        snapshot.stems.copyInto(lastStems);sourceFrame=snapshot.sourceFrame;snapshot.legacyFrames.copyInto(legacyFireFrames);snapshot.legacyAmplitudes.copyInto(legacyFireAmplitudes)
    }
    private class Ring(hz: Double, decay: Double) {
        private val radius=exp(-1.0/(decay*48000.0))
        private val feedback=2*radius*cos(2*PI*hz/48000.0)
        private val drive=sin(2*PI*hz/48000.0)
        private var y1=0.0;private var y2=0.0
        fun save()=doubleArrayOf(y1,y2)
        fun load(s:DoubleArray){y1=s[0];y2=s[1]}
        fun step(x: Double): Double {
            val y=feedback*y1-radius*radius*y2+drive*x
            y2=y1;y1=y;return y
        }
    }
    private val exhaustL=Ring(140.0,.040);private val exhaustR=Ring(180.0,.034)
    private val bark=arrayOf(Ring(540.0,.045),Ring(820.0,.038),Ring(1100.0,.034),Ring(1500.0,.030))
    private val barkWeights=doubleArrayOf(.50,.40,.42,.10)
    private val intake=Ring(200.0,.022)
    private val fireLow=Ring(90.0,.040);private val fireHigh=Ring(850.0,.012)
    private class PressureMode(private val hz:Double,private val q:Double) {
        private val radius=DoubleArray(2049){exp(-PI*hz*(.9+.2*it/2048)/(q*48000))}
        private val feedback=DoubleArray(2049){2*radius[it]*cos(2*PI*hz*(.9+.2*it/2048)/48000)}
        private var x1=0.0;private var x2=0.0;private var y1=0.0;private var y2=0.0
        fun save()=doubleArrayOf(x1,x2,y1,y2)
        fun load(s:DoubleArray){x1=s[0];x2=s[1];y1=s[2];y2=s[3]}
        fun step(x:Double,factor:Double=1.0):Double {
            val position=((factor-.9)/.2*2048).coerceIn(0.0,2048.0)
            val index=min(position.toInt(),2047);val fraction=position-index
            val r=radius[index]+fraction*(radius[index+1]-radius[index])
            val f=feedback[index]+fraction*(feedback[index+1]-feedback[index])
            val y=(1-r)*(x-x2)+f*y1-r*r*y2
            x2=x1;x1=x;y2=y1;y1=y;return y
        }
    }
    private class Section(private val b0:Double,private val b1:Double,private val b2:Double,private val a1:Double,private val a2:Double) {
        private var z1=0.0;private var z2=0.0
        fun save()=doubleArrayOf(z1,z2)
        fun load(s:DoubleArray){z1=s[0];z2=s[1]}
        fun step(x:Double):Double {val y=b0*x+z1;z1=b1*x-a1*y+z2;z2=b2*x-a2*y;return y}
    }
    private val exhaustPressure=PressureMode(110.0,2.8);private val bodyPressure=PressureMode(80.0,2.4)
    private val ground=PressureMode(120.0,.75)
    private val rumble1=Section(1.5336008368362247e-5,3.0672016736724495e-5,1.5336008368362247e-5,-1.9921312297863443,.9922394889743252)
    private val rumble2=Section(1.0,-2.0,1.0,-1.9966694053814964,.9966890664222656)
    private var flowRpm=0.0
    private val pattern=intArrayOf(0,1,0,1,1,0,1,0)
    private var phase=0.0;private var lastEvent=-1L
    private var thermal=0.0;private var lastThrottle=0.0;private var closeAge=Long.MAX_VALUE
    private var noiseState=5900000L;private var noise=0.0
    private var legacyAfterfireEvents=0L
    private var legacyAfterfireEpisodes=0L
    val afterfireEvents get()=eventProcess?.events ?: legacyAfterfireEvents
    val afterfireThermal get()=eventProcess?.thermalState ?: thermal
    val afterfireAgeFrames get()=eventProcess?.episodeAgeFrames ?: closeAge
    private var sourceFrame=0L
    private val legacyFireFrames=LongArray(4096);private val legacyFireAmplitudes=DoubleArray(4096)
    data class EventObservation(val rawArrivals:Long,val distinctImpulseFrames:Long,val episodes:Long,
        val arrivalFrames:LongArray,val arrivalAmplitudes:DoubleArray,val impulseFrames:LongArray,val impulseAmplitudes:DoubleArray,val truncated:Boolean)
    fun eventObservation():EventObservation {
        eventProcess?.observation()?.let { return EventObservation(it.rawArrivals,it.distinctImpulses,it.episodes,it.arrivalFrames,it.arrivalAmplitudes,it.impulseFrames,it.impulseAmplitudes,it.truncated) }
        val count=minOf(legacyAfterfireEvents,4096L).toInt();val start=if(legacyAfterfireEvents>count)(legacyAfterfireEvents%4096).toInt() else 0
        val frames=LongArray(count){legacyFireFrames[(start+it)%4096]};val amplitudes=DoubleArray(count){legacyFireAmplitudes[(start+it)%4096]}
        return EventObservation(legacyAfterfireEvents,count.toLong(),legacyAfterfireEpisodes,frames,amplitudes,frames.copyOf(),amplitudes.copyOf(),legacyAfterfireEvents>4096)
    }
    fun barkArrivalHistory()=arrivals?.arrivalHistory()

    /** S12 source coefficients, but causal texture is a separately versioned T1 change.
     * Running flow RPM replaces offline whole-segment mean; mono nonlinear rumble
     * and causal texture are T1 behavior changes. Idle/shift/PTR still not integrated.
     */
    fun sample(rpm: Double, load: Double, throttle: Double,validInput:Boolean=true): Float {
        require(rpm.isFinite() && rpm>=0 && rpm<=7200 && load.isFinite() && load>=0 && load<=1 && throttle.isFinite() && throttle>=0 && throttle<=1)
        phase+=rpm/(60.0*48000.0)
        val event=floor(phase*4).toLong()
        val starts=event!=lastEvent
        val impulse=if(starts && rpm>0 && validInput) min((3000.0/max(rpm,850.0)).pow(1.2),2.0)*(.45+.55*load) else 0.0
        val bank=pattern[(event%8).toInt()]
        val left=if(bank==0)impulse else 0.0
        val right=if(bank==1)impulse else 0.0
        val excitation=left+right
        val exhaust=.072*.74*(exhaustL.step(left)*sin(2*PI*phase)+exhaustR.step(right)*sin(2*PI*phase+.2))
        var barkValue=0.0
        if(arrivals!=null && starts && rpm>0 && validInput)arrivals.inject(event,bank,impulse,sourceFrame)
        arrivals?.step()
        val barkExcitation=if(arrivals!=null)arrivals.left+arrivals.right else excitation
        for(i in bark.indices)barkValue+=barkWeights[i]*bark[i].step(barkExcitation)
        barkValue*=.125*(.60+.40*throttle)*.70
        val intakeValue=.040*(.1+.9*throttle)*intake.step(excitation)*.775
        noiseState=noiseState xor (noiseState shl 13);noiseState=noiseState xor (noiseState ushr 7);noiseState=noiseState xor (noiseState shl 17)
        val random=(noiseState ushr 11).toDouble()/9007199254740992.0*2-1
        noise+=(random-noise)/(48000.0/60.0)
        val mechanical=(.0045*(.4+.6*load)*sin(2*PI*phase)+.004*(texture?.push(random) ?: noise))*.75
        thermal+=(((rpm-1200)/5800).coerceIn(0.0,1.0)*(.18+.82*load)-thermal)/(.22*48000)
        if(lastThrottle>=.15 && throttle<.15){closeAge=0;legacyAfterfireEpisodes++} else if(closeAge!=Long.MAX_VALUE) closeAge++
        val cluster=event%17
        val clustered=cluster==0L || cluster==1L || cluster==4L
        val fire=if(validInput && eventProcess==null && starts && clustered && throttle<.15 && closeAge<(.52*48000).toLong() && rpm>=3300 && thermal>=.16) {
            val amplitude=.090*thermal*((rpm-3300)/2600).coerceIn(.25,1.0);val log=(legacyAfterfireEvents%4096).toInt()
            legacyFireFrames[log]=sourceFrame;legacyFireAmplitudes[log]=amplitude;legacyAfterfireEvents++;amplitude
        } else 0.0
        val afterfire=eventProcess?.sample(rpm,load,throttle,starts && rpm>0,validInput) ?: ((fireLow.step(fire)+.42*fireHigh.step(fire))*.81)
        flowRpm+=(rpm-flowRpm)/(.22*48000)
        val factor=.9+.2*(flowRpm/6000).coerceIn(0.0,1.0)
        val pressureState=(.18+.82*load)*(.35+.65*throttle)*(rpm/1800).coerceIn(.45,1.25)
        val pulse=.60*pressureState*exhaust
        val coupling=.24*exhaustPressure.step(pulse,factor)
        val resonance=.10*bodyPressure.step(coupling,factor)
        val radiation=.30*(coupling+resonance)
        val body=radiation+.5*ground.step(radiation)
        val rumble=.9*1.6*rumble2.step(rumble1.step(tanh(2.5*pulse)))*(.20+.55*load+.25*throttle)*(.20+.80*(rpm/4000).coerceIn(0.0,1.2))
        lastStems[0]=exhaust;lastStems[1]=barkValue;lastStems[2]=intakeValue;lastStems[3]=mechanical;lastStems[4]=afterfire;lastStems[5]=body;lastStems[6]=rumble
        lastEvent=event;lastThrottle=throttle;sourceFrame++
        val output=exhaust+barkValue+intakeValue+mechanical+afterfire+body+rumble
        check(output.isFinite())
        return output.toFloat()
    }
}
