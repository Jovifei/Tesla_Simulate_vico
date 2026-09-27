package com.jovi.s12player;

final class ReplayDriveCycle {
    static final long SAMPLE_PERIOD_NS = 10_000_000L;
    private long sequence;

    MotionInput next(long nowNs) {
        return sampleAt(sequence++, nowNs);
    }

    static MotionInput sampleAt(long sequence, long measuredNs) {
        double seconds = (sequence % 1000L) / 100.0;
        double speed;
        double acceleration;
        if (seconds < 2.0) {
            speed = 0.0;
            acceleration = 0.0;
        } else if (seconds < 4.0) {
            speed = 22.0;
            acceleration = 0.1;
        } else if (seconds < 6.0) {
            double elapsed = seconds - 4.0;
            speed = 4.0 + 9.0 * elapsed;
            acceleration = 9.0;
        } else if (seconds < 8.0) {
            double elapsed = seconds - 6.0;
            speed = 32.0 - 8.0 * elapsed;
            acceleration = -4.0;
        } else {
            double elapsed = seconds - 8.0;
            speed = 12.0 + 15.0 * elapsed;
            acceleration = 15.0;
        }
        int direction = speed < 0.1 ? MotionInput.STATIONARY : MotionInput.FORWARD;
        return new MotionInput(sequence, measuredNs, measuredNs, speed, acceleration,
                direction, true, "Synthetic deterministic replay");
    }
}
