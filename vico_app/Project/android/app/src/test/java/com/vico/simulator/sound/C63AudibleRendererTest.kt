package com.vico.simulator.sound
import com.vico.simulator.sound.s15.C63RuntimeRenderer
import com.vico.simulator.sound.s16.*
import org.junit.Assert.*
import org.junit.Test
class C63AudibleRendererTest {
    private fun state(t:Double,closed:Boolean=false)=SoundState(t,4000.0,4000.0/15,if(closed).05 else .9,.9,floatArrayOf(),false,if(closed).05 else .9,if(closed).05 else .9,shiftTrigger=t==1.0)
    @Test fun disabledCompleteChainIsExactAh() {
        val old=C63RuntimeRenderer(false,false,true);val shadow=C63AudibleRenderer(C63AudibleProfile(),C63AudibleMode.AH)
        repeat(200){n->val input=state(n*.02,n>150);assertArrayEquals(old.render(input,960),shadow.render(input,960),0f)}
    }
    @Test fun completeSnapshotAndInvalidInputPreserveFuture() {
        val a=C63AudibleRenderer(C63AudibleProfile(),C63AudibleMode.SE)
        repeat(120){a.render(state(it*.02),960)};repeat(5){a.render(state(3+it*.02,true),960)}
        val b=C63AudibleRenderer(C63AudibleProfile(),C63AudibleMode.SE);b.restore(a.snapshot())
        assertThrows(IllegalArgumentException::class.java){a.render(state(Double.NaN),960)}
        repeat(50){n->val input=state(4+n*.02,true);assertArrayEquals(a.render(input,960),b.render(input,960),0f)}
    }
    @Test fun sixOutputPartitionsKeepControlAndShiftFramesFixed() {
        fun run(block:Int):FloatArray {
            val runtime=C63AudibleRenderer(C63AudibleProfile(),C63AudibleMode.SE);val output=FloatArray(192000);var frame=0
            repeat(200){point->val input=state(point*.02,point>=150);var remaining=960
                while(remaining>0){val count=minOf(remaining,block);runtime.render(input,count).copyInto(output,frame);frame+=count;remaining-=count}}
            return output
        }
        val reference=run(960)
        for(block in listOf(96,192,240,256,480))assertArrayEquals(reference,run(block),0f)
    }
}
