package com.vico.simulator.sensor
import com.vico.simulator.logging.UiFrameLedger
import org.junit.Assert.*
import org.junit.Test
class UiFrameLedgerTest {
    @Test fun sameFrameMultipleDispatchesKeepTheirOwnTime(){val l=UiFrameLedger();val a=l.register(7,1,10,11,12);val b=l.register(7,1,10,11,20);assertEquals(12,l.acknowledge(a.id,7,1,15)!!.dispatchNs);assertEquals(20,l.acknowledge(b.id,7,1,21)!!.dispatchNs)}
    @Test fun oldPageWrongFrameDuplicateAndBackwardsTimeCannotAcknowledge(){val l=UiFrameLedger();val a=l.register(1,1,null,null,10);assertNull(l.acknowledge(a.id,1,2,11));val b=l.register(1,2,null,null,10);assertNull(l.acknowledge(b.id,2,2,11));val c=l.register(1,2,null,null,10);assertNull(l.acknowledge(c.id,1,2,9));val d=l.register(1,2,null,null,10);assertNotNull(l.acknowledge(d.id,1,2,11));assertNull(l.acknowledge(d.id,1,2,12))}
    @Test fun unacknowledgedRendererDoesNotGrowLedgerWithoutBound(){val l=UiFrameLedger(2);val a=l.register(1,1,null,null,1);l.register(2,1,null,null,2);l.register(3,1,null,null,3);assertEquals(1,l.discarded);assertNull(l.acknowledge(a.id,1,1,4))}
    @Test fun restartRejectsLateAckFromSamePagePreviousSession(){
        val l=UiFrameLedger();val old=l.register(40,2,10,11,12)
        assertNull(l.acknowledge(old.id,40,2,20,41))
        val current=l.register(41,2,20,21,22)
        assertNotNull(l.acknowledge(current.id,41,2,23,41))
        assertEquals(1,l.discarded)
    }
}
