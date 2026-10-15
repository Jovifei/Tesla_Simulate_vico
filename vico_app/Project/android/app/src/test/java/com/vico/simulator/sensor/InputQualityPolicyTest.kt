package com.vico.simulator.sensor

import org.junit.Assert.*
import org.junit.Test

class InputQualityPolicyTest {
    private val now = 10_000_000_000L
    private fun sample(ageMs: Long = 0, accuracy: SpeedAccuracy = SpeedAccuracy.fromPlatform(true, true, 0.5)) = InputDiagnostics(
        publishElapsedNanos = now, gpsTiming = SampleTiming(now - ageMs * 1_000_000, now), gpsValid = true,
        gpsAccuracy = accuracy, imuTiming = SampleTiming(now, now), imuValid = true)
    @Test fun stale42IsNotCurrent70AndLostIsNotParking() {
        val q = InputQualityPolicy().assess(sample(2800), now, true)
        assertEquals(GpsQuality.STALE, q.gps)
        assertFalse(q.speedUsable)
        assertFalse(InputQualityPolicy().assess(sample(3001), now, true).speedUsable)
    }
    @Test fun freshUncertaintyAndBoundaryAreExplicit() {
        val p = InputQualityPolicy()
        assertEquals(GpsQuality.FRESH, p.assess(sample(1500), now, true).gps)
        assertEquals(GpsQuality.STALE, p.assess(sample(1501), now, true).gps)
        assertEquals(GpsQuality.LOW_QUALITY, p.assess(sample(0, SpeedAccuracy.fromPlatform(true,true,20.0)), now, true).gps)
        val missing=p.assess(sample(0,SpeedAccuracy.fromPlatform(true,false,null)),now,true)
        assertEquals(GpsQuality.UNVERIFIED,missing.gps)
        assertTrue(missing.speedUsable)
    }
    @Test fun latestConsumptionRechecksAgeInsteadOfPublishedFreshness() {
        assertFalse(InputQualityPolicy().assess(sample(), now+2_000_000_000, true).speedUsable)
        assertFalse(InputQualityPolicy().assess(sample(), now-1, true).speedUsable)
    }
    @Test fun unknownAxisDoesNotHideGoodSpeedOrClaimVehicleAcceleration() {
        val q=InputQualityPolicy().assess(sample(),now,false)
        assertTrue(q.speedUsable);assertFalse(q.accelerationUsable)
        assertEquals(ImuQuality.UNCONFIRMED_FRAME,q.imu)
    }
    @Test fun imuTimeoutHasIndependentStatusAndAudioDeadline() {
        val p=InputQualityPolicy()
        val q=p.assess(sample(),now,true)
        assertEquals(now+250_000_000,q.validUntilElapsedNanos)
        val later=p.assess(sample(),now+250_000_001,true)
        assertTrue(later.speedUsable);assertFalse(later.accelerationUsable)
    }
    @Test fun continuityInvalidationCannotDisappearWhenIntermediateFrameIsDropped() {
        val t=InputContinuityTracker()
        val a=t.advance("REAL/1",true,now+250_000_000,now)
        val b=t.advance("REAL/1",false,now+100_000_000,now+100_000_000)
        val c=t.advance("REAL/1",true,now+400_000_000,now+150_000_000)
        assertTrue(b>a);assertTrue(c>b)
        val d=t.advance("REAL/1",true,now+2_000_000_000,now+1_000_000_000)
        assertTrue(d>c)
        assertTrue(t.advance("DEMO/1",true,Long.MAX_VALUE,now+1_000_000_001)>d)
    }
}
