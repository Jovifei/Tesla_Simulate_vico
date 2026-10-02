package com.vico.simulator.sound.s17
import kotlin.math.*

/** Seeded opportunity-domain hazard; no clip, block RNG reset or shift input. */
internal class C63AR2AfterfireRuntime(private val seed:Long,private val amplitudeSpread:Double=0.0) {
    init {require(seed!=0L && amplitudeSpread.isFinite() && amplitudeSpread>=0 && amplitudeSpread<=.6)}
    class Snapshot internal constructor(internal val seed:Long,internal val spread:Double,internal val scalars:DoubleArray,
        internal val counters:LongArray,internal val eventFrames:LongArray,internal val eventAmplitudes:DoubleArray,internal val impulseFrames:LongArray,internal val impulseAmplitudes:DoubleArray)
    private var rng=seed;private var frame=0L;private var episode=0L
    private var age=Long.MAX_VALUE;private var thermal=0.0;private var lastThrottle=0.0
    private var hazard=0.0;private var threshold=1.0
    private val lowRadius=exp(-1/(.040*48000));private val highRadius=exp(-1/(.012*48000))
    private val lowFeedback=2*lowRadius*cos(2*PI*90/48000);private val highFeedback=2*highRadius*cos(2*PI*850/48000)
    private val lowDrive=sin(2*PI*90/48000);private val highDrive=sin(2*PI*850/48000)
    private var low1=0.0;private var low2=0.0;private var high1=0.0;private var high2=0.0
    private val logFrames=LongArray(4096)
    var events=0L;private set
    val episodes get()=episode
    val thermalState get()=thermal
    val episodeAgeFrames get()=age
    var distinctImpulseFrames=0L;private set
    var lastImpulse=0.0;private set
    private val eventAmplitudes=DoubleArray(4096);private val impulseFrames=LongArray(4096);private val impulseAmplitudes=DoubleArray(4096)
    fun eventFrames():LongArray {
        val size=minOf(events,logFrames.size.toLong()).toInt();val first=if(events>size) (events%logFrames.size).toInt() else 0
        return LongArray(size){logFrames[(first+it)%logFrames.size]}
    }
    data class Observation(val episodes:Long,val rawArrivals:Long,val distinctImpulses:Long,val arrivalFrames:LongArray,
        val arrivalAmplitudes:DoubleArray,val impulseFrames:LongArray,val impulseAmplitudes:DoubleArray,val truncated:Boolean)
    fun observation():Observation {
        val count=minOf(events,4096L).toInt();val start=if(events>count)(events%4096).toInt() else 0
        val raw=LongArray(count){logFrames[(start+it)%4096]};val amps=DoubleArray(count){eventAmplitudes[(start+it)%4096]}
        val pulses=minOf(distinctImpulseFrames,4096L).toInt();val first=if(distinctImpulseFrames>pulses)(distinctImpulseFrames%4096).toInt() else 0
        val frames=LongArray(pulses){impulseFrames[(first+it)%4096]};val values=DoubleArray(pulses){impulseAmplitudes[(first+it)%4096]}
        return Observation(episode,events,distinctImpulseFrames,raw,amps,frames,values,events>4096 || distinctImpulseFrames>4096)
    }
    private fun random():Double {
        rng=rng xor(rng shl 13);rng=rng xor(rng ushr 7);rng=rng xor(rng shl 17)
        // An odd output scrambler avoids tiny initial draws from small seeds.
        return ((rng*2685821657736338717L) ushr 11).toDouble()/9007199254740992.0
    }
    private fun nextThreshold()=-ln(maxOf(random(),1.0/9007199254740992.0))
    fun sample(rpm:Double,load:Double,throttle:Double,opportunity:Boolean,validInput:Boolean=true):Double {
        require(rpm.isFinite() && rpm>=0 && rpm<=7200 && load.isFinite() && load>=0 && load<=1 && throttle.isFinite() && throttle>=0 && throttle<=1)
        thermal+=((if(validInput)((rpm-1200)/5800).coerceIn(0.0,1.0)*(.18+.82*load) else 0.0)-thermal)/(.22*48000)
        if(!validInput || throttle>=.15)age=Long.MAX_VALUE
        else if(lastThrottle>=.15){age=0;episode++;hazard=0.0;threshold=nextThreshold()}
        else if(age!=Long.MAX_VALUE)age++
        lastThrottle=throttle;lastImpulse=0.0
        if(validInput && opportunity && age<24960 && throttle<.15 && rpm>=3300 && thermal>=.16) {
            hazard+=3.0/17.0
            var batch=0
            while(hazard>=threshold) {
                check(++batch<=8){"Afterfire opportunity overflow; no events silently dropped"}
                hazard-=threshold;threshold=nextThreshold()
                val variation=if(amplitudeSpread==0.0)1.0 else 1+amplitudeSpread*(2*random()-1)
                val amplitude=.090*thermal*((rpm-3300)/2600).coerceIn(.25,1.0)*variation
                lastImpulse+=amplitude;val index=(events%logFrames.size).toInt()
                logFrames[index]=frame;eventAmplitudes[index]=amplitude;events++
            }
        }
        val low=lowFeedback*low1-lowRadius*lowRadius*low2+lowDrive*lastImpulse
        val high=highFeedback*high1-highRadius*highRadius*high2+highDrive*lastImpulse
        low2=low1;low1=low;high2=high1;high1=high
        if(lastImpulse>0){val index=(distinctImpulseFrames%impulseFrames.size).toInt();impulseFrames[index]=frame;impulseAmplitudes[index]=lastImpulse;distinctImpulseFrames++}
        frame++
        return (low+.42*high)*.81
    }
    fun snapshot()=Snapshot(seed,amplitudeSpread,doubleArrayOf(thermal,lastThrottle,hazard,threshold,low1,low2,high1,high2,lastImpulse),
        longArrayOf(rng,frame,episode,age,events,distinctImpulseFrames),logFrames.copyOf(),eventAmplitudes.copyOf(),impulseFrames.copyOf(),impulseAmplitudes.copyOf())
    fun restore(snapshot:Snapshot) {
        require(snapshot.seed==seed && snapshot.spread==amplitudeSpread && snapshot.scalars.size==9 && snapshot.counters.size==6 && snapshot.eventFrames.size==4096 && snapshot.eventAmplitudes.size==4096 && snapshot.impulseFrames.size==4096 && snapshot.impulseAmplitudes.size==4096)
        require(snapshot.scalars.all{it.isFinite()} && snapshot.scalars[3]>=0)
        val s=snapshot.scalars;val c=snapshot.counters
        thermal=s[0];lastThrottle=s[1];hazard=s[2];threshold=s[3];low1=s[4];low2=s[5];high1=s[6];high2=s[7];lastImpulse=s[8]
        rng=c[0];frame=c[1];episode=c[2];age=c[3];events=c[4];distinctImpulseFrames=c[5];snapshot.eventFrames.copyInto(logFrames);snapshot.eventAmplitudes.copyInto(eventAmplitudes);snapshot.impulseFrames.copyInto(impulseFrames);snapshot.impulseAmplitudes.copyInto(impulseAmplitudes)
    }
}
