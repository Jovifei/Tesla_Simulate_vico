package com.jovi.s12player;

import static org.junit.Assert.*;
import org.junit.Test;

public final class DriveSessionStateTest {
    private static final long SECOND = 1_000_000_000L;

    private MotionInput sample(long sequence, long measured, double speed, boolean valid) {
        return new MotionInput(sequence, measured, measured + 10_000_000L,
                speed, 0, MotionInput.FORWARD, valid, "test");
    }

    @Test public void driveExpiresOnceAndOnlyNewMeasurementRestoresSpeed() {
        DriveSessionState state = new DriveSessionState();
        long epoch = state.begin(DriveSessionState.Source.DRIVE);
        assertEquals(DriveSessionState.Quality.WAITING, state.snapshot().quality);
        assertTrue(Double.isNaN(state.snapshot().speedKmh));
        MotionInput first = sample(0, SECOND, 10, true);
        assertEquals(DriveSessionState.Effect.SUBMIT_VALID, state.observe(epoch, first));
        assertEquals(36.0, state.snapshot().speedKmh, 0.001);
        assertEquals(DriveSessionState.Effect.NONE, state.tick(epoch, SECOND + 250_000_000L));
        assertEquals(DriveSessionState.Effect.SUBMIT_INVALID,
                state.tick(epoch, SECOND + 250_000_001L));
        assertTrue(Double.isNaN(state.snapshot().speedKmh));
        assertEquals(DriveSessionState.Quality.STALE, state.snapshot().quality);
        assertEquals(DriveSessionState.Effect.NONE, state.tick(epoch, SECOND + 400_000_000L));
        assertEquals(DriveSessionState.Effect.NONE, state.observe(epoch, first));
        assertEquals(DriveSessionState.Effect.SUBMIT_VALID,
                state.observe(epoch, sample(1, SECOND + 500_000_000L, 11, true)));
        assertEquals(39.6, state.snapshot().speedKmh, 0.001);
    }

    @Test public void staleSessionCallbackCannotAffectNewMode() {
        DriveSessionState state = new DriveSessionState();
        long replayEpoch = state.begin(DriveSessionState.Source.REPLAY);
        assertEquals(DriveSessionState.Effect.SUBMIT_VALID,
                state.observe(replayEpoch, sample(0, SECOND, 20, true)));
        state.stop();
        long driveEpoch = state.begin(DriveSessionState.Source.DRIVE);
        assertEquals(DriveSessionState.Effect.NONE,
                state.observe(replayEpoch, sample(1, SECOND + 100_000_000L, 30, true)));
        assertEquals(DriveSessionState.Effect.NONE,
                state.tick(replayEpoch, SECOND + 500_000_000L));
        assertEquals(DriveSessionState.Source.DRIVE, state.snapshot().source);
        assertEquals(DriveSessionState.Quality.WAITING, state.snapshot().quality);
        assertTrue(Double.isNaN(state.snapshot().speedKmh));
        assertEquals(DriveSessionState.Effect.SUBMIT_VALID,
                state.observe(driveEpoch, sample(2, SECOND + 600_000_000L, 15, true)));
    }

    @Test public void invalidSensorSampleOnlyTriggersOneFallback() {
        DriveSessionState state = new DriveSessionState();
        long epoch = state.begin(DriveSessionState.Source.DRIVE);
        assertEquals(DriveSessionState.Effect.SUBMIT_VALID,
                state.observe(epoch, sample(0, SECOND, 10, true)));
        assertEquals(DriveSessionState.Effect.SUBMIT_INVALID,
                state.observe(epoch, sample(1, SECOND + 50_000_000L, 0, false)));
        assertEquals(DriveSessionState.Effect.NONE,
                state.observe(epoch, sample(2, SECOND + 60_000_000L, 0, false)));
        assertEquals(DriveSessionState.Effect.NONE, state.tick(epoch, SECOND + 500_000_000L));
    }

    @Test public void replayDoesNotUseDriveImuTimeout() {
        DriveSessionState state = new DriveSessionState();
        long epoch = state.begin(DriveSessionState.Source.REPLAY);
        assertEquals(DriveSessionState.Effect.SUBMIT_VALID,
                state.observe(epoch, sample(0, SECOND, 8, true)));
        assertEquals(DriveSessionState.Effect.NONE, state.tick(epoch, SECOND + 2 * SECOND));
        assertEquals(DriveSessionState.Quality.FRESH, state.snapshot().quality);
    }
}
