package com.vico.simulator.sensor
import com.vico.simulator.logging.AudioDiagnosticRing
import org.junit.Assert.*
import org.junit.Test
class AudioDiagnosticRingTest {
    private fun put(r:AudioDiagnosticRing,id:Long)=r.publish(id,id,1,9_007_199_254_740_993L+id,48000,1920,0,100,200,4800,0,.5,1,0,0,0,5)
    @Test fun overflowIsBoundedAndCounted(){val r=AudioDiagnosticRing(3);for(i in 1..8)put(r,i.toLong());val b=r.drain();assertEquals(5,b.dropped);assertEquals(listOf(6L,7L,8L),b.records.map{it.blockId});assertTrue(r.drain().records.isEmpty())}
    @Test fun timestampsStayExactBeyondJavascriptIntegerRange(){val r=AudioDiagnosticRing();put(r,1);val x=r.drain().records.single();assertEquals(9_007_199_254_740_994L,x.elapsedNs);assertEquals(.5,x.peak,0.0)}
    @Test fun concurrentWriterNeverProducesMixedRecords(){val r=AudioDiagnosticRing(64);val writer=Thread{for(i in 1..10000)put(r,i.toLong())};writer.start();var count=0L;var drop=0L
        while(writer.isAlive){val b=r.drain();drop+=b.dropped;count+=b.records.size;for(x in b.records){assertEquals(x.blockId,x.frameId);assertEquals(9_007_199_254_740_993L+x.blockId,x.elapsedNs)}}
        writer.join();val tail=r.drain();count+=tail.records.size;drop+=tail.dropped;assertEquals(10000,count+drop)
    }
}
