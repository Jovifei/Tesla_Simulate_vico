package com.jovi.s12player;

/** Single-worker state for input validity; readers see one immutable snapshot. */
final class DriveSessionState {
    enum Source { NONE, REPLAY, DRIVE }
    enum Quality { STOPPED, WAITING, FRESH, STALE }
    enum Effect { NONE, SUBMIT_VALID, SUBMIT_INVALID }
    static final long MAX_IMU_AGE_NS = 250_000_000L;

    static final class Snapshot {
        final long epoch;
        final Source source;
        final Quality quality;
        final double speedKmh;
        final long measurementTimeNs;

        Snapshot(long epoch, Source source, Quality quality, double speedKmh,
                long measurementTimeNs) {
            this.epoch = epoch;
            this.source = source;
            this.quality = quality;
            this.speedKmh = speedKmh;
            this.measurementTimeNs = measurementTimeNs;
        }
    }

    private volatile Snapshot current = new Snapshot(0, Source.NONE, Quality.STOPPED,
            Double.NaN, 0);
    private long lastMeasurementTimeNs;

    Snapshot snapshot() { return current; }

    long begin(Source source) {
        if (source == Source.NONE) throw new IllegalArgumentException("source");
        lastMeasurementTimeNs = 0;
        current = new Snapshot(current.epoch + 1, source, Quality.WAITING, Double.NaN, 0);
        return current.epoch;
    }

    void stop() {
        lastMeasurementTimeNs = 0;
        current = new Snapshot(current.epoch + 1, Source.NONE, Quality.STOPPED, Double.NaN, 0);
    }

    boolean isActive(long epoch) {
        return current.epoch == epoch && current.source != Source.NONE;
    }

    boolean canAccept(long epoch, MotionInput sample) {
        return isActive(epoch) && sample.valid
                && sample.measurementTimeNs > lastMeasurementTimeNs
                && sample.measurementTimeNs > 0
                && sample.receivedTimeNs >= sample.measurementTimeNs
                && Double.isFinite(sample.speedMps);
    }

    Effect observe(long epoch, MotionInput sample) {
        if (!isActive(epoch)) return Effect.NONE;
        if (!sample.valid) return invalidate();
        if (!canAccept(epoch, sample)) return Effect.NONE;
        lastMeasurementTimeNs = sample.measurementTimeNs;
        current = new Snapshot(epoch, current.source, Quality.FRESH,
                sample.speedMps * 3.6, sample.measurementTimeNs);
        return Effect.SUBMIT_VALID;
    }

    Effect tick(long epoch, long nowNs) {
        if (!isActive(epoch) || current.source != Source.DRIVE
                || current.quality != Quality.FRESH) return Effect.NONE;
        if (nowNs >= lastMeasurementTimeNs
                && nowNs - lastMeasurementTimeNs <= MAX_IMU_AGE_NS) return Effect.NONE;
        return invalidate();
    }

    private Effect invalidate() {
        if (current.quality != Quality.FRESH) return Effect.NONE;
        current = new Snapshot(current.epoch, current.source, Quality.STALE,
                Double.NaN, current.measurementTimeNs);
        return Effect.SUBMIT_INVALID;
    }
}
