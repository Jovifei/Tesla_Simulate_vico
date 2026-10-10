package com.jovi.s12player;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

public final class ReplayDriveCycleTest {
    @Test
    public void replayCoversIdleCruiseAccelerationCoastAndShift() {
        MotionInput idle = ReplayDriveCycle.sampleAt(0, 1_000_000_000L);
        MotionInput cruise = ReplayDriveCycle.sampleAt(250, 3_500_000_000L);
        MotionInput acceleration = ReplayDriveCycle.sampleAt(450, 5_500_000_000L);
        MotionInput coast = ReplayDriveCycle.sampleAt(650, 7_500_000_000L);
        MotionInput shift = ReplayDriveCycle.sampleAt(850, 9_500_000_000L);

        assertEquals(0.0, idle.speedMps, 0.0);
        assertEquals(MotionInput.STATIONARY, idle.direction);
        assertEquals(22.0, cruise.speedMps, 0.0);
        assertEquals(9.0, acceleration.accelerationMps2, 0.0);
        assertEquals(-4.0, coast.accelerationMps2, 0.0);
        assertEquals(15.0, shift.accelerationMps2, 0.0);
        assertEquals(850, shift.sequence);
        assertEquals(9_500_000_000L, shift.receivedTimeNs);
    }

    @Test
    public void generatedSequenceDoesNotResetWhenScenarioLoopRepeats() {
        ReplayDriveCycle replay = new ReplayDriveCycle();
        long now = 4_000_000_000L;
        MotionInput last = null;
        for (int i = 0; i < 1002; i++) {
            last = replay.next(now + i * ReplayDriveCycle.SAMPLE_PERIOD_NS);
        }
        assertEquals(1001, last.sequence);
        assertEquals(0.0, last.speedMps, 0.0);
    }
}
