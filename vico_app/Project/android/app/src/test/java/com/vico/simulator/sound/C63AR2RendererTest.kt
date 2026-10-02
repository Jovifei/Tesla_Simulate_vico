package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63RuntimeRenderer
import com.vico.simulator.sound.s17.*
import org.junit.Assert.*
import org.junit.Test
class C63AR2RendererTest {
    @Test fun maximumBlockMatchesFiveAudioBlocks() {
        val large=C63AR2Renderer(C63AR2Profile(),C63AR2Mode.SE2,true)
        val small=C63AR2Renderer(C63AR2Profile(),C63AR2Mode.SE2,true)
        val input=point(0.0);val expected=FloatArray(4800)
        repeat(5){small.render(input,960).copyInto(expected,it*960)}
        assertArrayEquals(expected,large.render(input,4800),0f)
    }
    private fun point(t:Double,closed:Boolean=false)=SoundState(t,4000.0,4000.0/15,if(closed).05 else .9,.9,floatArrayOf(),false,if(closed).05 else .9,if(closed).05 else .9,shiftTrigger=t==1.0)
    @Test fun AHBranchIsExactFrozenC63AH() {
        val old=C63RuntimeRenderer(false,false,true);val ah=C63AR2Renderer(C63AR2Profile(),C63AR2Mode.AH,true)
        repeat(150){n->val input=point(n*.02,n>110);assertArrayEquals(old.render(input,960),ah.render(input,960),0f)}
    }
    @Test fun zeroArrivalS2IsExactlyTextureControlAndOtherStemsAreIndependent() {
        val t=C63AR2Renderer(C63AR2Profile(),C63AR2Mode.T,true);val s=C63AR2Renderer(C63AR2Profile(fixedDelay=0),C63AR2Mode.S2,true)
        repeat(150){n->val input=point(n*.02);assertArrayEquals(t.render(input,960),s.render(input,960),0f)}
    }
    @Test fun rendererSnapshotAndInputValidationAreFailFast() {
        val a=C63AR2Renderer(C63AR2Profile(),C63AR2Mode.SE2,true);repeat(150){a.render(point(it*.02),960)}
        val b=C63AR2Renderer(C63AR2Profile(),C63AR2Mode.SE2,true);b.restore(a.snapshot())
        assertThrows(IllegalArgumentException::class.java){a.render(point(Double.NaN),960)}
        repeat(50){n->val input=point(3+n*.02,true);assertArrayEquals(a.render(input,960),b.render(input,960),0f)}
    }
}
