package com.vico.simulator.sensor
import com.vico.simulator.logging.*
import com.vico.simulator.sound.*
import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files

class SessionLogAdapterTest {
    private fun config(bias:Double=0.0)=SessionLogAdapter.Config(2,2,true,1,bias,0.0,0.0,1500.0,250.0,2.0)
    private fun await(owner:SessionRecordingCoordinator,phase:SessionRecordingCoordinator.Phase){
        val end=System.nanoTime()+5_000_000_000L
        while(owner.snapshot().phase!=phase&&System.nanoTime()<end)Thread.sleep(1)
        assertEquals(phase,owner.snapshot().phase)
    }
    private fun lifecycleAccepted(owner: SessionRecordingCoordinator, adapter: SessionLogAdapter, code: Int, ns: Long) {
        val before = owner.snapshot().activeStatus!!.accepted
        val end = System.nanoTime() + 2_000_000_000L
        while (owner.snapshot().activeStatus!!.accepted == before) {
            adapter.lifecycle(code, if(code==10)7 else 5, ns, config())
            if (System.nanoTime() > end) fail("Lifecycle test setup could not enqueue")
            Thread.sleep(1)
        }
    }
    @Test fun readySessionHasConfigThenOneStartThenRealStopAndFailureDoesNotInventStart() {
        val root=Files.createTempDirectory("vico-start-chain-").toFile()
        val owner=SessionRecordingCoordinator(root); val adapter=SessionLogAdapter(owner)
        try {
            adapter.start("c63",config()){SessionRecorder.Metadata(100,1,"test","c63",config().hash())}
            await(owner,SessionRecordingCoordinator.Phase.RECORDING)
            val id=owner.snapshot().generation
            val end=System.nanoTime()+2_000_000_000L
            while(!owner.requestSessionStart(id,200)){if(System.nanoTime()>end)fail("start enqueue");Thread.sleep(1)}
            while(owner.snapshot().activeStatus!!.written<2){if(System.nanoTime()>end)fail("start retry");Thread.sleep(1)}
            repeat(5){owner.requestSessionStart(id,201)}
            lifecycleAccepted(owner,adapter,2,300);adapter.stop();await(owner,SessionRecordingCoordinator.Phase.COMPLETE)
            val rows=java.io.File(owner.snapshot().lastCompleted!!.directory,"records.tsv").readLines().filter{!it.startsWith("#")}.map{it.split('\t')}
            assertEquals(listOf("CONFIG","EVENT","EVENT"),rows.map{it[0]})
            assertEquals(listOf("1","2"),rows.filter{it[0]=="EVENT"}.map{it[4]})
            assertEquals(listOf("0","1"),rows.filter{it[0]=="EVENT"}.map{it[6]})

            val entered=java.util.concurrent.CountDownLatch(1);val release=java.util.concurrent.CountDownLatch(1)
            adapter.start("failed",config()){entered.countDown();release.await(5,java.util.concurrent.TimeUnit.SECONDS);SessionRecorder.Metadata(400,1,"test","failed",config().hash())}
            assertTrue(entered.await(2,java.util.concurrent.TimeUnit.SECONDS))
            val failedId=owner.snapshot().generation;owner.observeUnreadyRows(3);owner.cancelSessionStart(failedId)
            release.countDown();await(owner,SessionRecordingCoordinator.Phase.RECORDING)
            assertFalse(owner.requestSessionStart(failedId,500))
            lifecycleAccepted(owner,adapter,10,600);lifecycleAccepted(owner,adapter,2,700)
            adapter.stop();await(owner,SessionRecordingCoordinator.Phase.COMPLETE)
            val failed=owner.snapshot().lastCompleted!!
            val events=java.io.File(failed.directory,"records.tsv").readLines().filter{it.startsWith("EVENT\t")}.map{it.split('\t')[4]}
            assertEquals(listOf("10","2"),events);assertEquals(3L,failed.status.preReadyDropped)
        } finally {owner.close();root.deleteRecursively()}
    }
    @Test fun realRecorderAcceptsAllAdapterShapesAndExactFrameSources(){
        val root=Files.createTempDirectory("vico-adapter-").toFile();val owner=SessionRecordingCoordinator(root)
        val adapter=SessionLogAdapter(owner);val config=config();val base=9_007_199_254_740_993L
        try {
            adapter.start("c63_w204_v6",config){SessionRecorder.Metadata(base,1,"apk:"+"0".repeat(64),"c63_w204_v6",config.hash())}
            await(owner,SessionRecordingCoordinator.Phase.RECORDING)
            for(i in 1..30){
                val ns=base+i*50_000_000L;val f=i.toLong();val diag=InputDiagnostics(inputSession=1,publishElapsedNanos=ns,consumeElapsedNanos=ns+1,
                    gpsTiming=SampleTiming(ns,ns),gpsValid=true,gpsAccuracy=SpeedAccuracy.fromPlatform(true,true,.5),imuTiming=SampleTiming(ns,ns),imuValid=true)
                val input=SensorInputSnapshot(speedKmh=70.0,accelMps2=2.0,gpsOk=true,diagnostics=diag,controlFrameId=f)
                val c=DriveInputControl(DriveInputSource.REAL,1,ns+250_000_000L,true,true,ns,ns,f,ns+1)
                val state=SoundState(1.0,4000.0,266.0,.5,.5,floatArrayOf(),false,throttle=.5,load=.5,inputControl=c,modelSpeedKmh=70.0,modelAccelerationMps2=2.0)
                adapter.recordGps(ns,ns,0.0,SpeedAccuracy.fromPlatform(true,false,null),false,false,config)
                adapter.recordImu(ns,ns,floatArrayOf(0f,2f,0f),FloatArray(3),2.0,true,config)
                adapter.recordFrame(input,state,InputQualityPolicy().assess(diag,ns,true),config,ns)
                val ledger=UiFrameLedger();val dispatch=ledger.register(f,1,ns,ns+1,ns+2)
                adapter.recordUi(dispatch,ns+3,2,43.0)
                adapter.recordAudio(AudioDiagnosticRing.Record(f,f,1,ns+4,48000,1920,0,100,200,4800,0,.5,1,0,0,0,5),config)
                Thread.sleep(1)
            }
            adapter.stop();await(owner,SessionRecordingCoordinator.Phase.COMPLETE)
            val complete=owner.snapshot().lastCompleted!!;assertEquals(0,complete.status.rejected)
            val lines=java.io.File(complete.directory,"records.tsv").readLines().filter{!it.startsWith("#")}.map{it.split('\t')}
            for(kind in listOf("CONFIG","GPS","IMU","CONTROL","MODEL","UI_ACK","AUDIO"))assertTrue(kind,lines.any{it[0]==kind})
            for(row in lines)assertEquals(row[0],4+SessionRecorder.Kind.valueOf(row[0]).fieldNames.size,row.size)
            val gps=lines.first{it[0]=="GPS"};assertEquals("",gps[6]);assertEquals("0",gps[12])
            val ui=lines.first{it[0]=="UI_ACK"};assertEquals("2",ui[9]);assertEquals("43.0",ui[10])
            assertTrue(lines.filter{it[0]=="IMU"}.all{it[4].toLong()>9_007_199_254_740_992L})
        } finally {owner.close();root.deleteRecursively()}
    }
    @Test fun changedCalibrationConfigPrecedesEveryReferencingImuRow(){
        val root=Files.createTempDirectory("vico-config-").toFile();val owner=SessionRecordingCoordinator(root);val adapter=SessionLogAdapter(owner)
        try {
            adapter.start("c63_w204_v6",config()){SessionRecorder.Metadata(1,1,"test","c63_w204_v6",config().hash())};await(owner,SessionRecordingCoordinator.Phase.RECORDING)
            repeat(40){i->val value=config(if(i<20)0.0 else .5);adapter.recordImu((i+1).toLong(),(i+1).toLong(),floatArrayOf(1f,2f,3f),floatArrayOf(value.biasX.toFloat(),0f,0f),2.0,true,value);Thread.sleep(1)}
            adapter.stop();await(owner,SessionRecordingCoordinator.Phase.COMPLETE)
            val rows=java.io.File(owner.snapshot().lastCompleted!!.directory,"records.tsv").readLines().filter{!it.startsWith("#")}.map{it.split('\t')}
            val configs=mutableMapOf<Long,Double>()
            for(row in rows){if(row[0]=="CONFIG")configs[row[4].toLong()]=row[9].toDouble();if(row[0]=="IMU")assertEquals(configs[row[17].toLong()]!!,row[9].toDouble(),0.0)}
            assertEquals(setOf(0.0,.5),configs.values.toSet())
        } finally {owner.close();root.deleteRecursively()}
    }
}
