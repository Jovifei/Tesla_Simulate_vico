package com.vico.simulator.sound.s18
import com.vico.simulator.sound.s16.C63MechanicalTexture

import kotlin.math.*

/** Versioned source fork: frozen lower-layer mathematics plus finite HY1 bark/event representations. */
internal class C63HybridSource(private val profile:C63HybridProfile,private val mode:C63HybridMode,private val eventsAudible:Boolean=true) {
    private val sustainedChange=mode==C63HybridMode.S || mode==C63HybridMode.SE
    private val eventChange=mode==C63HybridMode.E || mode==C63HybridMode.SE
    private val periodic=if(sustainedChange)C63FiniteResponseSource(profile.periodicKernel.map{it*profile.periodicScale*sqrt(1-profile.randomFraction)}.toDoubleArray()) else null
    private val broadNoise=C63HybridNoise(profile.sourceSeed,profile.noiseWeights)
    private val texture=C63MechanicalTexture(9.786453030584157)
    private val eventProcess=if(eventChange)C63HybridAfterfire(profile) else null
    private val profileKey="C63_HY1_SOURCE_V1|"+profile.identity+"|"+mode+"|"+eventsAudible
    private val driveAlpha=1-exp(-1.0/(.035*48000))
    private var driveLevel=1.0;private var lastAmplitude=0.0
    val driveState get()=driveLevel
    val pendingFrames get()=maxOf(periodic?.pendingFrames ?: 0,eventProcess?.pendingFrames ?: 0)
    val noiseBands get()=broadNoise.lastBands
    val lastResponseAngle get()=eventProcess?.lastAngle ?: 0.0
    val legacyEventSignal get()=eventProcess?.legacySignal ?: lastEventSignal
    var lastCombustionImpulse=0.0;private set
    var lastCombustionBank=0;private set
    var lastAfterfireImpulse=0.0;private set
    var lastEventSignal=0.0;private set
    val lastStems=DoubleArray(7)
    class Snapshot internal constructor(internal val scalars:DoubleArray,internal val counters:LongArray,internal val filters:List<DoubleArray>,
        internal val key:String,internal val stems:DoubleArray,internal val periodic:C63FiniteResponseSource.Snapshot?,
        internal val texture:C63MechanicalTexture.Snapshot,internal val noise:C63HybridNoise.Snapshot,internal val events:C63HybridAfterfire.Snapshot?,
        internal val sourceFrame:Long,internal val legacyFrames:LongArray,internal val legacyAmplitudes:DoubleArray)
    private fun rings()=listOf(exhaustL,exhaustR,*bark,intake,fireLow,fireHigh)
    private fun modes()=listOf(exhaustPressure,bodyPressure,ground)
    fun snapshot()=Snapshot(doubleArrayOf(phase,thermal,lastThrottle,noise,flowRpm,driveLevel,lastAmplitude,lastEventSignal,lastCombustionImpulse,lastCombustionBank.toDouble(),lastAfterfireImpulse),
        longArrayOf(lastEvent,closeAge,noiseState,legacyAfterfireEvents,legacyAfterfireEpisodes),
        rings().map{it.save()}+modes().map{it.save()}+listOf(rumble1.save(),rumble2.save()),profileKey,lastStems.copyOf(),
        periodic?.snapshot(),texture.snapshot(),broadNoise.snapshot(),eventProcess?.snapshot(),sourceFrame,legacyFireFrames.copyOf(),legacyFireAmplitudes.copyOf())
    fun restore(saved:Snapshot) {
        require(saved.key==profileKey && saved.scalars.size==11 && saved.scalars.all{it.isFinite()} && saved.counters.size==5 &&
            saved.filters.size==rings().size+5 && saved.filters.all{it.all{v->v.isFinite()}} && saved.stems.size==7 &&
            saved.legacyFrames.size==4096 && saved.legacyAmplitudes.size==4096){"HY1 source snapshot mismatch"}
        val s=saved.scalars;val c=saved.counters
        phase=s[0];thermal=s[1];lastThrottle=s[2];noise=s[3];flowRpm=s[4];driveLevel=s[5];lastAmplitude=s[6]
        lastEventSignal=s[7];lastCombustionImpulse=s[8];lastCombustionBank=s[9].toInt();lastAfterfireImpulse=s[10]
        lastEvent=c[0];closeAge=c[1];noiseState=c[2];legacyAfterfireEvents=c[3];legacyAfterfireEpisodes=c[4]
        var i=0;for(ring in rings())ring.load(saved.filters[i++]);for(mode in modes())mode.load(saved.filters[i++])
        rumble1.load(saved.filters[i++]);rumble2.load(saved.filters[i])
        saved.periodic?.let{periodic!!.restore(it)};texture.restore(saved.texture);broadNoise.restore(saved.noise);saved.events?.let{eventProcess!!.restore(it)}
        saved.stems.copyInto(lastStems);sourceFrame=saved.sourceFrame;saved.legacyFrames.copyInto(legacyFireFrames);saved.legacyAmplitudes.copyInto(legacyFireAmplitudes)
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
    private val bark=if(sustainedChange)emptyArray() else arrayOf(Ring(540.0,.045),Ring(820.0,.038),Ring(1100.0,.034),Ring(1500.0,.030))
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
        lastCombustionImpulse=excitation;lastCombustionBank=bank
        if(starts && impulse>0)lastAmplitude=impulse
        val driveTarget=if(!validInput || rpm>=3300 && throttle<.15 && load<.2)0.0 else 1.0
        if(sourceFrame==0L)driveLevel=driveTarget else driveLevel+=driveAlpha*(driveTarget-driveLevel)
        val broad=broadNoise.sample()
        var barkValue=0.0
        if(periodic!=null) {
            if(starts && rpm>0 && validInput)periodic.inject(event,bank,impulse*driveLevel)
            periodic.step()
            val noiseLevel=profile.periodicScale*sqrt(profile.randomFraction*rpm*4/(60*48000))*lastAmplitude*driveLevel
            barkValue=periodic.left+periodic.right+noiseLevel*broad
        } else for(i in bark.indices)barkValue+=barkWeights[i]*bark[i].step(excitation)
        barkValue*=.125*(.60+.40*throttle)*.70
        val intakeValue=.040*(.1+.9*throttle)*intake.step(excitation)*.775
        noiseState=noiseState xor (noiseState shl 13);noiseState=noiseState xor (noiseState ushr 7);noiseState=noiseState xor (noiseState shl 17)
        val random=(noiseState ushr 11).toDouble()/9007199254740992.0*2-1
        noise+=(random-noise)/(48000.0/60.0)
        val mechanical=(.0045*(.4+.6*load)*sin(2*PI*phase)+.004*texture.push(random))*.75
        thermal+=(((rpm-1200)/5800).coerceIn(0.0,1.0)*(.18+.82*load)-thermal)/(.22*48000)
        if(lastThrottle>=.15 && throttle<.15){closeAge=0;legacyAfterfireEpisodes++} else if(closeAge!=Long.MAX_VALUE) closeAge++
        val cluster=event%17
        val clustered=cluster==0L || cluster==1L || cluster==4L
        val fire=if(validInput && eventProcess==null && starts && clustered && throttle<.15 && closeAge<(.52*48000).toLong() && rpm>=3300 && thermal>=.16) {
            val amplitude=.090*thermal*((rpm-3300)/2600).coerceIn(.25,1.0);val log=(legacyAfterfireEvents%4096).toInt()
            legacyFireFrames[log]=sourceFrame;legacyFireAmplitudes[log]=amplitude;legacyAfterfireEvents++;amplitude
        } else 0.0
        lastEventSignal=eventProcess?.sample(rpm,load,throttle,starts && rpm>0,validInput) ?: ((fireLow.step(fire)+.42*fireHigh.step(fire))*.81)
        lastAfterfireImpulse=eventProcess?.lastImpulse ?: fire
        val afterfire=if(eventsAudible)lastEventSignal else 0.0
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


