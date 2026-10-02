package com.vico.simulator.sound
import com.vico.simulator.sound.s17.*
import com.vico.simulator.sound.s18.*
import org.junit.Assert.*
import org.junit.Test

class C63HybridRendererTest {
    private fun state(t:Double,closed:Boolean=false)=SoundState(t,if(closed)4000.0 else 5000.0,0.0,if(closed).05 else .9,.9,floatArrayOf(),false,if(closed).05 else .9,.9)
    @Test fun fullTextureControlMatchesFrozenChainExactly() {
        val a=C63AR2Renderer(C63AR2Profile(),C63AR2Mode.T,true);val b=C63HybridRenderer(HybridTestProfiles.create(),C63HybridMode.T,true)
        repeat(150){n->val s=state(n*.02,n>=100);assertArrayEquals(a.render(s,960),b.render(s,960),0f)}
    }
    @Test fun allSupportedBlockPartitionsHaveIdenticalPcm() {
        fun run(block:Int):FloatArray {val r=C63HybridRenderer(HybridTestProfiles.create(),C63HybridMode.SE,true);val output=FloatArray(5760);var offset=0
            while(offset<output.size){val count=minOf(block,output.size-offset);r.render(state(0.0),count).copyInto(output,offset);offset+=count};return output}
        val expected=run(1);for(block in intArrayOf(96,192,240,256,480,960,4800))assertArrayEquals(expected,run(block),0f)
    }
    @Test fun fullSnapshotResumesDuringHotEpisodeAndShiftTail() {
        val a=C63HybridRenderer(HybridTestProfiles.create(),C63HybridMode.SE,true)
        repeat(118){n->a.render(state(n*.02,n>=100).copy(shiftTrigger=n==110),960)}
        val b=C63HybridRenderer(HybridTestProfiles.create(),C63HybridMode.SE,true);b.restore(a.snapshot())
        repeat(30){n->val s=state(2.36+n*.02,true);assertArrayEquals(a.render(s,960),b.render(s,960),0f)}
    }
    @Test fun malformedInputCannotAdvanceTheActualRenderer() {
        val a=C63HybridRenderer(HybridTestProfiles.create(),C63HybridMode.SE,true);val b=C63HybridRenderer(HybridTestProfiles.create(),C63HybridMode.SE,true)
        assertThrows(IllegalArgumentException::class.java){a.render(state(Double.NaN),960)}
        assertArrayEquals(a.render(state(0.0),960),b.render(state(0.0),960),0f)
    }
}
