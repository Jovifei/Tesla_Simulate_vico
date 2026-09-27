package com.jovi.s12player;

import static org.junit.Assert.*;
import org.junit.Test;

public final class MotionEstimatorTest {
    private static final long SECOND = 1_000_000_000L;

    @Test public void chosenForwardAxisRejectsVerticalAndLateralMotion() {
        MotionEstimator estimator = new MotionEstimator(0);
        estimator.gravity(0, 0, 9.81, SECOND);
        estimator.gps(10, 1, SECOND);
        estimator.acceleration(2, 8, 0, SECOND + 10_000_000L);
        MotionInput sample = estimator.sample(0, SECOND + 20_000_000L);
        assertTrue(sample.valid);
        assertEquals(2, sample.accelerationMps2, 0.001);
        estimator.forwardAxis(1);
        estimator.acceleration(2, 8, 0, SECOND + 30_000_000L);
        assertEquals(8, estimator.sample(1, SECOND + 40_000_000L).accelerationMps2, 0.001);
        estimator.gravity(0, 9.81, 0, SECOND + 50_000_000L);
        assertFalse(estimator.sample(2, SECOND + 60_000_000L).valid);
    }

    @Test public void speedPredictionIsBoundedAndExpiresWithGps() {
        MotionEstimator estimator = new MotionEstimator(0);
        estimator.gravity(0, 0, 9.81, SECOND);
        estimator.gps(10, 1, SECOND);
        estimator.acceleration(2, 0, 0, SECOND + 10_000_000L);
        estimator.acceleration(2, 0, 0, SECOND + 110_000_000L);
        MotionInput predicted = estimator.sample(0, SECOND + 120_000_000L);
        assertTrue(predicted.valid);
        assertEquals(10.2, predicted.speedMps, 0.03);
        assertFalse(estimator.sample(1, SECOND + 2_100_000_000L).valid);
    }

    @Test public void badGpsAndReversedTimesNeverBecomeFreshMotion() {
        MotionEstimator estimator = new MotionEstimator(2);
        estimator.gravity(0, 0, 9.81, SECOND);
        estimator.gps(8, 1, SECOND);
        estimator.acceleration(1, 0, 0, SECOND + 10_000_000L);
        assertTrue(estimator.sample(0, SECOND + 20_000_000L).valid);
        estimator.gps(90, 30, SECOND + 20_000_000L);
        assertFalse(estimator.sample(1, SECOND + 30_000_000L).valid);
        estimator.gps(8, 1, SECOND - 1);
        assertFalse(estimator.sample(2, SECOND + 40_000_000L).valid);
        estimator.gps(8, 1, SECOND + 50_000_000L);
        estimator.acceleration(1, 0, 0, SECOND + 40_000_000L);
        assertFalse(estimator.sample(3, SECOND + 60_000_000L).valid);
    }

    @Test public void imuCannotDriftFarFromTheLastGnssSpeed() {
        MotionEstimator estimator = new MotionEstimator(0);
        estimator.gravity(0, 0, 9.81, SECOND);
        estimator.gps(10, 1, SECOND);
        for (int i = 1; i <= 15; i++) {
            estimator.acceleration(12, 0, 0, SECOND + i * 100_000_000L);
        }
        MotionInput sample = estimator.sample(0, SECOND + 1_510_000_000L);
        assertTrue(sample.valid);
        assertTrue("drift bounded to 3 m/s", sample.speedMps <= 13.0);
    }

    @Test public void routineGravityUpdatesDoNotDropEveryOtherImuSample() {
        MotionEstimator estimator = new MotionEstimator(0);
        estimator.gravity(0, 0, 9.81, SECOND);
        estimator.gps(10, 1, SECOND);
        estimator.acceleration(2, 0, 0, SECOND + 10_000_000L);
        estimator.gravity(0, 0, 9.81, SECOND + 11_000_000L);
        assertTrue(estimator.sample(0, SECOND + 12_000_000L).valid);
    }
}
