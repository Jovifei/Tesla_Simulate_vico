package com.jovi.s12player;

/** Fixed-mount phone estimate. All timestamps use elapsedRealtimeNanos. */
final class MotionEstimator {
    private static final long GPS_AGE_NS = 2_000_000_000L;
    private static final long IMU_AGE_NS = 250_000_000L;
    private static final long GRAVITY_AGE_NS = 2_000_000_000L;
    private int axis;
    private final double[] gravity = new double[3];
    private long gravityTime;
    private long gpsTime;
    private long imuTime;
    private boolean gpsValid;
    private boolean imuValid;
    private double predictedSpeed;
    private double gpsSpeed;
    private double acceleration;

    MotionEstimator(int axis) { forwardAxis(axis); }

    void forwardAxis(int choice) {
        if (choice < 0 || choice > 3) throw new IllegalArgumentException("forward axis");
        axis = choice;
        imuValid = false;
    }

    void gravity(double x, double y, double z, long timeNs) {
        if (timeNs <= gravityTime || !Double.isFinite(x) || !Double.isFinite(y)
                || !Double.isFinite(z)) return;
        double oldLength = Math.sqrt(gravity[0] * gravity[0] + gravity[1] * gravity[1]
                + gravity[2] * gravity[2]);
        double newLength = Math.sqrt(x * x + y * y + z * z);
        if (oldLength > 1 && newLength > 1
                && (x * gravity[0] + y * gravity[1] + z * gravity[2])
                / (oldLength * newLength) < 0.995) imuValid = false;
        gravity[0] = x;
        gravity[1] = y;
        gravity[2] = z;
        gravityTime = timeNs;
    }

    void gps(double speedMps, double accuracyMps, long timeNs) {
        if (timeNs <= gpsTime) { gpsValid = false; return; }
        gpsTime = timeNs;
        gpsValid = Double.isFinite(speedMps) && speedMps >= 0 && speedMps <= 100
                && Double.isFinite(accuracyMps) && accuracyMps >= 0 && accuracyMps <= 5;
        if (gpsValid) predictedSpeed = gpsSpeed = speedMps;
        if (imuTime < gpsTime) imuValid = false;
    }

    void acceleration(double x, double y, double z, long timeNs) {
        if (timeNs <= imuTime) { imuValid = false; return; }
        if (!Double.isFinite(x) || !Double.isFinite(y) || !Double.isFinite(z)) {
            imuValid = false;
            return;
        }
        long previous = imuTime;
        imuTime = timeNs;
        double length = Math.sqrt(gravity[0] * gravity[0] + gravity[1] * gravity[1]
                + gravity[2] * gravity[2]);
        int component = axis % 2;
        double sign = axis < 2 ? 1 : -1;
        double unit = length > 1 ? gravity[component] / length : 1;
        double horizontalLength = Math.sqrt(1 - unit * unit);
        imuValid = gravityTime > 0 && timeNs >= gravityTime && timeNs >= gpsTime
                && timeNs - gravityTime <= GRAVITY_AGE_NS && horizontalLength >= 0.25;
        if (!imuValid) return;
        double vertical = (x * gravity[0] + y * gravity[1] + z * gravity[2]) / length;
        double selected = component == 0 ? x : y;
        acceleration = sign * (selected - vertical * unit) / horizontalLength;
        acceleration = Math.max(-12, Math.min(12, acceleration));
        if (gpsValid && previous > 0 && timeNs > previous && timeNs - previous <= IMU_AGE_NS
                && timeNs >= gpsTime && timeNs - gpsTime <= GPS_AGE_NS) {
            predictedSpeed = Math.max(0, Math.min(100,
                    Math.max(gpsSpeed - 3, Math.min(gpsSpeed + 3,
                            predictedSpeed + acceleration * (timeNs - previous) / 1e9))));
        }
    }

    MotionInput sample(long sequence, long nowNs) {
        double gravityLength = Math.sqrt(gravity[0] * gravity[0] + gravity[1] * gravity[1]
                + gravity[2] * gravity[2]);
        double verticalAxis = gravityLength > 1 ? gravity[axis % 2] / gravityLength : 1;
        boolean fresh = gpsValid && imuValid && gpsTime > 0 && imuTime > 0
                && nowNs >= gpsTime && nowNs - gpsTime <= GPS_AGE_NS
                && nowNs >= imuTime && nowNs - imuTime <= IMU_AGE_NS
                && nowNs >= gravityTime && nowNs - gravityTime <= GRAVITY_AGE_NS
                && Math.sqrt(1 - verticalAxis * verticalAxis) >= 0.25;
        double speed = fresh ? predictedSpeed : 0;
        int direction = speed < 0.1 ? MotionInput.STATIONARY : MotionInput.FORWARD;
        return new MotionInput(sequence, imuTime, nowNs, speed,
                fresh ? acceleration : 0, direction, fresh,
                fresh ? "GNSS + calibrated IMU" : "Stale or uncalibrated motion");
    }
}
