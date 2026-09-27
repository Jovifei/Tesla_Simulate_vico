package com.jovi.s12player;

final class MotionInput {
    static final int FORWARD = 0;
    static final int REVERSE = 1;
    static final int STATIONARY = 2;
    static final int UNKNOWN = 3;

    final long sequence;
    final long measurementTimeNs;
    final long receivedTimeNs;
    final double speedMps;
    final double accelerationMps2;
    final int direction;
    final boolean valid;
    final String quality;

    MotionInput(long sequence, long measurementTimeNs, long receivedTimeNs,
                double speedMps, double accelerationMps2, int direction,
                boolean valid, String quality) {
        this.sequence = sequence;
        this.measurementTimeNs = measurementTimeNs;
        this.receivedTimeNs = receivedTimeNs;
        this.speedMps = speedMps;
        this.accelerationMps2 = accelerationMps2;
        this.direction = direction;
        this.valid = valid;
        this.quality = quality;
    }
}
