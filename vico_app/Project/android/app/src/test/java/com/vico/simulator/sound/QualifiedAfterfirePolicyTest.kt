package com.vico.simulator.sound
import org.junit.Assert.*
import org.junit.Test

class QualifiedAfterfirePolicyTest {
    private fun input(t: Double, demand: Double, seq: Long = (t*1000000).toLong(), valid: Boolean = true,
        epoch: Long = 1L, rpm: Double = 4000.0, shift: Long? = null, shiftTime: Double? = if (shift != null) t else null) =
        AfterfireEpisodeInput(t, seq, epoch, valid, rpm, demand, shift, shiftTime)

    @Test fun alternatingProxyNeverQualifiesAnEpisode() {
        val p = QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        val events = (0..600).mapNotNull { i -> p.update(input(i*.05, if(i%2==0) 1.4/3 else .2/3, i.toLong())) }
        assertEquals(0, events.size)
    }

    @Test fun oneSustainedReleaseIsOneEventAcrossSamplingRates() {
        // 1Hz explicitly needs a compatible freshness contract; production 250ms remains fail-closed at 1Hz.
        for(hz in listOf(1,10,20,100)) {
            val p = QualifiedAfterfirePolicy(AfterfireEpisodeConfig(maximumFreshSampleGapS=1.1))
            val events = (0..8*hz).mapNotNull { i ->
                val t=i.toDouble()/hz
                p.update(input(t, if(t<3) .6 else .0, i.toLong()))
            }
            assertEquals("Hz=$hz",1,events.size)
            assertEquals(AfterfireCause.QUALIFIED_RELEASE,events.single().cause)
            assertTrue(events.single().timeS >= 3.08-1e-9)
            assertTrue(events.single().timeS <= 3.08+1.0/hz+1e-9)
        }
    }

    @Test fun gradualReleaseQualifiesFromArmedBaselineNotAdjacentDelta() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        val events=(0..100).mapNotNull { i ->
            val t=i*.05
            p.update(input(t, if(t<1) .7 else (.7-(t-1)*.35).coerceAtLeast(0.0), i.toLong()))
        }
        assertEquals(1,events.size)
    }

    @Test fun gapEpochAndInvalidityRequireFullRearming() {
        for (mode in listOf("gap","epoch","invalid")) {
            val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
            for(i in 0..8) assertNull(p.update(input(i*.05,.6,i.toLong())))
            val base=if(mode=="gap")2.0 else .5
            val epoch=if(mode=="epoch")2L else 1L
            if(mode=="invalid")assertNull(p.update(input(.45,.6,9,false)))
            for(i in 0..20) assertNull(p.update(input(base+i*.05,.0,100+i.toLong(),epoch=epoch)))
            val events=(0..30).mapNotNull { i -> p.update(input(base+1.1+i*.05,if(i<12).6 else .0,200+i.toLong(),epoch=epoch)) }
            assertEquals(mode,1,events.size)
        }
    }

    @Test fun repeatedShiftIdEmitsOnceAndConsumesPendingRelease() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        for(i in 0..8)p.update(input(i*.05,.6,i.toLong()))
        p.update(input(.45,.0,9))
        val event=p.update(input(.55,.0,10,shift=3))
        assertEquals(AfterfireCause.QUALIFIED_SHIFT,event?.cause)
        for(i in 1..30)assertNull(p.update(input(.55+i*.05,.0,10+i.toLong(),shift=3)))
    }

    @Test fun duplicateBackwardAndLowRpmSamplesDoNotTrigger() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        assertNull(p.update(input(0.0,.6,0)))
        repeat(100){assertNull(p.update(input(0.0,.6,0)))}
        assertNull(p.update(input(-1.0,.0,1)))
        for(i in 1..80)assertNull(p.update(input(i*.05,if(i<40).6 else .0,i.toLong(),rpm=700.0)))
    }

    @Test fun sparseOneHertzCannotArmUnderProductionFreshness() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        for(i in 0..10) assertNull(p.update(input(i.toDouble(),if(i<5).6 else .0,i.toLong())))
    }
    @Test fun consumedReleaseCannotRearmFromShortHighNoiseAfterCooldown() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        var events=0
        for(i in 0..600) {
            val t=i*.05
            val demand=when { t<1 -> .6; t<2 -> .0; else -> if(i%2==0).6 else .0 }
            if(p.update(input(t,demand,i.toLong()))!=null)events++
        }
        assertEquals(1,events)
    }

    @Test fun firstAndSecondRecoveredSamplesCannotInheritReleaseHistory() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        for(i in 0..20)p.update(input(i*.05,.6,i.toLong()))
        assertNull(p.update(input(1.05,.6,21,valid=false)))
        assertNull(p.update(input(1.10,.6,22)))
        assertNull(p.update(input(1.15,.0,23)))
        for(i in 24..100)assertNull(p.update(input(i*.05,.0,i.toLong())))
    }

    @Test fun oldEpochCannotReplayShiftOrDiscardNewEpochDeduplication() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        p.update(input(0.0,.6,0,epoch=2))
        assertNotNull(p.update(input(.05,.6,1,epoch=2,shift=5)))
        assertNull(p.update(input(.1,.6,2,epoch=1,shift=6)))
        assertNull(p.update(input(.15,.6,3,epoch=2,shift=5)))
    }

    @Test fun nonfiniteInputResetsTheArmedEpisode() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        for(i in 0..20)p.update(input(i*.05,.6,i.toLong()))
        assertNull(p.update(input(1.05,Double.NaN,21)))
        for(i in 22..60)assertNull(p.update(input(i*.05,.0,i.toLong())))
    }

    @Test fun repeatedSourceSequenceCannotBorrowPublisherTimeToArm() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        assertNull(p.update(input(0.0,.6,0)))
        for(i in 1..100)assertNull(p.update(input(i*.05,.6,0)))
        assertNull(p.update(input(5.05,.0,1)))
        for(i in 2..20)assertNull(p.update(input(5.0+i*.05,.0,i.toLong())))
    }

    @Test fun recoveryWarmupInvalidationDoesNotDeferALiftUntilTrustReturns() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        for(i in 0..20)p.update(input(i*.05,.6,i.toLong()))
        for(i in 21..30)assertNull(p.update(input(i*.05,if(i<25).6 else .0,i.toLong(),valid=false)))
        for(i in 31..80)assertNull(p.update(input(i*.05,.0,i.toLong())))
    }

    @Test fun actualShiftOnExactRepeatedImuIsImmediateOnceWithoutDeferredRelease() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        for(i in 0..20)p.update(input(i*.05,.6,i.toLong()))
        val shift=p.update(input(1.0,.6,20,shift=8,shiftTime=1.05))
        assertEquals(AfterfireCause.QUALIFIED_SHIFT,shift?.cause)
        assertEquals(1.05,requireNotNull(shift).timeS,0.0)
        assertNull(p.update(input(1.0,.6,20,shift=8,shiftTime=1.05)))
        assertNull(p.update(input(1.05,.0,21)))
        for(i in 22..60)assertNull(p.update(input(i*.05,.0,i.toLong())))
    }

    @Test fun olderOrInconsistentSourceCannotUseIndependentShiftChannel() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        p.update(input(1.0,.6,20))
        assertNull(p.update(input(.95,.6,19,shift=1)))
        assertNull(p.update(input(1.05,.6,20,shift=1)))
        assertNull(p.update(input(1.0,.6,21,shift=1)))
        assertNotNull(p.update(input(1.0,.6,20,shift=1)))
    }

    @Test fun repeatedSourceShiftIsStillBlockedUntilRecoveryBaselineExists() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        p.update(input(1.0,.6,20))
        p.invalidate()
        assertNull(p.update(input(1.0,.6,20,shift=7)))
        assertNull(p.update(input(1.05,.6,21)))
        assertNull(p.update(input(1.10,.6,22,shift=7)))
    }

    @Test fun missingBackwardOrNonfiniteShiftTimeCannotEmitOrDeferAnEvent() {
        for(time in listOf<Double?>(null,.9,Double.NaN)) {
            val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
            p.update(input(1.0,.6,20))
            assertNull(p.update(input(1.0,.6,20,shift=1,shiftTime=time)))
            assertNull(p.update(input(1.05,.6,21,shift=1,shiftTime=1.05)))
        }
    }

    @Test fun shiftCooldownUsesControlTimeAndSurvivesInvalidation() {
        val p=QualifiedAfterfirePolicy(AfterfireEpisodeConfig())
        p.update(input(1.0,.6,20))
        assertNotNull(p.update(input(1.0,.6,20,shift=1,shiftTime=1.2)))
        p.invalidate()
        for(i in 1..30) {
            val t=1.05+i*.05
            assertNull(p.update(input(t,if(t<1.3).6 else .0,20+i.toLong())))
        }
    }

}
