package com.vico.simulator.sound
import com.vico.simulator.sound.s16.C63BarkModes
import kotlin.math.*
import org.junit.Assert.*
import org.junit.Test
class C63BarkModesTest {
    @Test fun disabledChangeExactlyMatchesFrozenFourModeRecurrence() {
        val hz=doubleArrayOf(540.0,820.0,1100.0,1500.0);val tau=doubleArrayOf(.045,.038,.034,.030)
        val weights=doubleArrayOf(.50,.40,.42,.10);val y1=DoubleArray(4);val y2=DoubleArray(4)
        val modes=C63BarkModes(tau)
        repeat(4800){n->val x=if(n%117==0).8 else 0.0;var expected=0.0
            for(i in 0..3){val r=exp(-1/(tau[i]*48000));val y=2*r*cos(2*PI*hz[i]/48000)*y1[i]-r*r*y2[i]+sin(2*PI*hz[i]/48000)*x;y2[i]=y1[i];y1[i]=y;expected+=weights[i]*y}
            assertEquals(expected,modes.sample(x),0.0)}
    }
    @Test fun snapshotBindsDecayAndRejectsInvalidMutation() {
        val a=C63BarkModes();repeat(500){a.sample(if(it==0)1.0 else 0.0)}
        val b=C63BarkModes();b.restore(a.snapshot())
        assertThrows(IllegalArgumentException::class.java){a.sample(Double.NaN)}
        repeat(500){assertEquals(a.sample(0.0),b.sample(0.0),0.0)}
        val different=C63BarkModes(doubleArrayOf(.0225,.019,.017,.015))
        assertThrows(IllegalArgumentException::class.java){different.restore(a.snapshot())}
        assertThrows(IllegalArgumentException::class.java){C63BarkModes(doubleArrayOf(.001,.038,.034,.030))}
    }
}
