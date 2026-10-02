package com.vico.simulator.sound
import com.vico.simulator.sound.s15.FinitePressureExcitation
import org.junit.Assert.*
import org.junit.Test

class FinitePressureExcitationTest {
    @Test fun snapshot_mid_pulse_preserves_tail_and_area() {
        val a=FinitePressureExcitation();a.inject(0,1.2,700.0);repeat(11){a.step()}
        val b=FinitePressureExcitation();b.restore(a.snapshot())
        repeat(64){a.step();b.step();assertEquals(a.left,b.left,0.0);assertEquals(a.right,b.right,0.0)}
        assertEquals(a.injectedLeft,a.emittedLeft+a.remainingLeft(),1e-10)
        assertEquals(b.injectedLeft,b.emittedLeft+b.remainingLeft(),1e-10)
    }
    @Test fun cap_and_floor_are_fixed_not_block_dependent() {
        for(pair in listOf(700.0 to 57,7200.0 to 15)) {
            val p=FinitePressureExcitation();p.inject(0,1.0,pair.first);var active=0
            repeat(64){p.step();if(p.left>0)active++}
            assertEquals(pair.second,active)
        }
    }
    @Test fun preserves_area_and_bank_without_preserving_delta_energy() {
        val p=FinitePressureExcitation();p.inject(0,1.75,700.0)
        var sum=0.0;var energy=0.0
        repeat(64){p.step();assertTrue(p.left>=0);assertEquals(0.0,p.right,0.0);sum+=p.left;energy+=p.left*p.left}
        assertEquals(1.75,sum,1e-10);assertTrue(energy<1.75*1.75)
    }
    @Test fun overlap_and_wrap_do_not_overwrite_remaining_area() {
        val p=FinitePressureExcitation();repeat(63){p.step()};p.inject(0,1.0,700.0);p.inject(0,.5,700.0);p.inject(1,2.0,7200.0)
        var l=0.0;var r=0.0;repeat(64){p.step();l+=p.left;r+=p.right}
        assertEquals(1.5,l,1e-10);assertEquals(2.0,r,1e-10)
    }
    @Test fun single_cell_control_equals_original_impulse() {
        val p=FinitePressureExcitation();p.inject(1,.7,4000.0,1);p.step();assertEquals(.7,p.right,0.0);p.step();assertEquals(0.0,p.right,0.0)
    }
    @Test(expected=IllegalArgumentException::class) fun invalid_area_rejected() {
        FinitePressureExcitation().inject(0,Double.NaN,4000.0)
    }
}
