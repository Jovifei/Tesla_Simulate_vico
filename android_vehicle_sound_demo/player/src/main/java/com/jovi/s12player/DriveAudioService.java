package com.jovi.s12player;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.media.AudioAttributes;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.AudioDeviceCallback;
import android.media.AudioDeviceInfo;
import android.os.Binder;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.SystemClock;

/** Owns the single JNI command producer and the live driving session. */
public final class DriveAudioService extends Service {
    static final String REPLAY = "com.jovi.s12player.REPLAY";
    static final String DRIVE = "com.jovi.s12player.DRIVE";
    static final String STOP = "com.jovi.s12player.STOP";
    static final String PROFILE = "profile";
    static final String AXIS = "axis";
    static final String VOLUME = "volume";
    private static final int NOTIFICATION_ID = 71;
    private static final String CHANNEL = "drive_audio";

    static { System.loadLibrary("player-native"); }
    private static native long nativeStart(int profileIndex, float initialVolume);
    private static native void nativeStop(long handle);
    private static native void nativeRequestStop(long handle);
    private static native boolean nativeStopReady(long handle);
    private static native void nativeInvalidateMotion(long handle);
    private static native boolean nativeSubmitMotion(long handle, long sequence, long measurementTimeNs,
            long receivedTimeNs, double speedMps, double accelerationMps2, int direction, boolean valid);
    private static native boolean nativeSelectProfile(long handle, int index);
    private static native String nativeGetDiagnostics(long handle);
    private static native boolean nativeHasStreamError(long handle);
    private static native boolean nativeSetVolume(long handle, float volume);

    final class LocalBinder extends Binder {
        DriveAudioService service() { return DriveAudioService.this; }
    }

    private final LocalBinder binder = new LocalBinder();
    private HandlerThread thread;
    private Handler worker;
    private SensorManager sensors;
    private LocationManager locations;
    private AudioManager audio;
    private AudioFocusRequest focusRequest;
    private Sensor linearSensor;
    private Sensor gravitySensor;
    private SensorEventListener sensorListener;
    private LocationListener locationListener;
    private MotionEstimator estimator;
    private final DriveSessionState motionState = new DriveSessionState();
    private ReplayDriveCycle replay;
    private Runnable replayTask;
    private Runnable diagnosticsTask;
    private Runnable freshnessTask;
    private Runnable stopPollTask;
    private Runnable pendingStart;
    private long handle;
    private long sequence;
    private volatile String status;
    private volatile String qualityIssue;
    private volatile String diagnostics = "audio=stopped";
    private volatile boolean running;
    private int profile;
    private volatile int latestStartId;
    private int sessionStartId;
    private int stopStartId;
    private int focusEpoch;
    private boolean normalStopPending;
    private String normalStopReason;
    private long stopDeadlineNs;
    private boolean bluetoothAvailableAtStart;
    private final BroadcastReceiver noisyReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (AudioManager.ACTION_AUDIO_BECOMING_NOISY.equals(intent.getAction())) {
                long epoch = motionState.snapshot().epoch;
                worker.post(() -> {
                    if (motionState.isActive(epoch))
                        stopSession(getString(R.string.status_output_disconnected));
                });
            }
        }
    };
    private final AudioDeviceCallback deviceCallback = new AudioDeviceCallback() {
        @Override public void onAudioDevicesRemoved(AudioDeviceInfo[] removed) {
            if (!running || !bluetoothAvailableAtStart) return;
            for (AudioDeviceInfo device : removed) {
                int type = device.getType();
                if (type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP
                        || type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) {
                    long epoch = motionState.snapshot().epoch;
                    worker.post(() -> {
                        if (motionState.isActive(epoch))
                            stopSession(getString(R.string.status_bluetooth_disconnected));
                    });
                    return;
                }
            }
        }
    };

    @Override public void onCreate() {
        super.onCreate();
        sensors = (SensorManager) getSystemService(SENSOR_SERVICE);
        locations = (LocationManager) getSystemService(LOCATION_SERVICE);
        audio = (AudioManager) getSystemService(AUDIO_SERVICE);
        status = getString(R.string.status_stopped);
        thread = new HandlerThread("s12-drive-control");
        thread.start();
        worker = new Handler(thread.getLooper());
        audio.registerAudioDeviceCallback(deviceCallback, worker);
        IntentFilter noisy = new IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY);
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(noisyReceiver, noisy, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(noisyReceiver, noisy);
        }
        NotificationManager notifications = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        notifications.createNotificationChannel(new NotificationChannel(CHANNEL,
                getString(R.string.notification_channel), NotificationManager.IMPORTANCE_LOW));
    }

    @Override public IBinder onBind(Intent intent) { return binder; }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        latestStartId = startId;
        String action = intent == null ? null : intent.getAction();
        if (STOP.equals(action)) {
            worker.post(() -> {
                pendingStart = null;
                beginNormalStop(getString(R.string.status_stopped), startId);
            });
            return START_NOT_STICKY;
        }
        if (!REPLAY.equals(action) && !DRIVE.equals(action)) return START_NOT_STICKY;
        boolean drive = DRIVE.equals(action);
        if (drive && checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            status = getString(R.string.status_permission_denied);
            stopSelf();
            return START_NOT_STICKY;
        }
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                int type = ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK;
                if (drive) type |= ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION;
                startForeground(NOTIFICATION_ID, notification(), type);
            } else {
                startForeground(NOTIFICATION_ID, notification());
            }
        } catch (RuntimeException error) {
            status = getString(R.string.status_service_failed, error.getClass().getSimpleName());
            stopSelf();
            return START_NOT_STICKY;
        }
        int requestedProfile = Math.max(0, Math.min(1, intent.getIntExtra(PROFILE, 0)));
        int axis = Math.max(0, Math.min(3, intent.getIntExtra(AXIS, 0)));
        float volume = Math.max(0, Math.min(1, intent.getFloatExtra(VOLUME, 1)));
        worker.post(() -> startSession(drive, requestedProfile, axis, volume, startId));
        return START_NOT_STICKY;
    }

    private Notification notification() {
        PendingIntent open = PendingIntent.getActivity(this, 0,
                new Intent(this, PlayerActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Intent stop = new Intent(this, DriveAudioService.class).setAction(STOP);
        PendingIntent stopAction = PendingIntent.getService(this, 1, stop,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        return new Notification.Builder(this, CHANNEL)
                .setSmallIcon(R.drawable.ic_player).setContentTitle(getString(R.string.app_name))
                .setContentText(getString(R.string.notification_active)).setOngoing(true)
                .setContentIntent(open).addAction(android.R.drawable.ic_media_pause,
                        getString(R.string.button_stop), stopAction).build();
    }

    private void startSession(boolean drive, int requestedProfile, int axis, float volume,
            int requestId) {
        if (handle != 0) {
            pendingStart = () -> startSession(drive, requestedProfile, axis, volume, requestId);
            beginNormalStop(getString(R.string.status_stopped), requestId);
            return;
        }
        stopAudioAndInputs();
        sessionStartId = requestId;
        diagnostics = "audio=starting";
        profile = requestedProfile;
        bluetoothAvailableAtStart = hasBluetoothOutput();
        int activeEpoch = ++focusEpoch;
        focusRequest = new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_GAME)
                        .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
                .setOnAudioFocusChangeListener(change -> {
                    if (change != AudioManager.AUDIOFOCUS_GAIN) {
                        worker.post(() -> {
                            if (activeEpoch == focusEpoch && handle != 0)
                                stopSession(getString(R.string.status_audio_focus_lost));
                        });
                    }
                }, worker).build();
        if (audio.requestAudioFocus(focusRequest) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
            stopSession(getString(R.string.status_audio_focus_unavailable));
            return;
        }
        handle = nativeStart(profile, volume);
        if (handle == 0) { stopSession(getString(R.string.status_audio_open_failed)); return; }
        running = true;
        if (drive) startSensors(axis);
        else startReplay();
        diagnosticsTask = new Runnable() {
            @Override public void run() {
                if (handle == 0) return;
                if (nativeHasStreamError(handle)) {
                    stopSession(getString(R.string.status_output_disconnected));
                    return;
                }
                diagnostics = nativeGetDiagnostics(handle);
                worker.postDelayed(this, 500);
            }
        };
        worker.post(diagnosticsTask);
    }

    private void startReplay() {
        long epoch = motionState.begin(DriveSessionState.Source.REPLAY);
        qualityIssue = null;
        replay = new ReplayDriveCycle();
        status = getString(R.string.status_replay_playing);
        replayTask = new Runnable() {
            @Override public void run() {
                if (handle == 0 || replay == null || !motionState.isActive(epoch)) return;
                MotionInput generated = replay.next(SystemClock.elapsedRealtimeNanos());
                MotionInput sample = new MotionInput(sequence++, generated.measurementTimeNs,
                        generated.receivedTimeNs, generated.speedMps, generated.accelerationMps2,
                        generated.direction, generated.valid, generated.quality);
                submit(epoch, sample);
                worker.postDelayed(this, 10);
            }
        };
        worker.post(replayTask);
    }

    private void startSensors(int axis) {
        long epoch = motionState.begin(DriveSessionState.Source.DRIVE);
        qualityIssue = null;
        linearSensor = sensors.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION);
        gravitySensor = sensors.getDefaultSensor(Sensor.TYPE_GRAVITY);
        if (linearSensor == null || gravitySensor == null) {
            stopSession(getString(R.string.status_motion_sensor_unavailable));
            return;
        }
        estimator = new MotionEstimator(axis);
        sensorListener = new SensorEventListener() {
            @Override public void onSensorChanged(SensorEvent event) {
                if (!motionState.isActive(epoch) || estimator == null || event.values.length < 3) return;
                if (event.sensor.getType() == Sensor.TYPE_GRAVITY) {
                    estimator.gravity(event.values[0], event.values[1], event.values[2], event.timestamp);
                } else if (event.sensor.getType() == Sensor.TYPE_LINEAR_ACCELERATION) {
                    estimator.acceleration(event.values[0], event.values[1], event.values[2], event.timestamp);
                    submit(epoch, estimator.sample(sequence++, SystemClock.elapsedRealtimeNanos()));
                }
            }

            @Override public void onAccuracyChanged(Sensor sensor, int accuracy) {}
        };
        locationListener = new LocationListener() {
            @Override public void onLocationChanged(Location location) {
                if (!motionState.isActive(epoch) || estimator == null) return;
                double accuracy = location.hasSpeedAccuracy()
                        ? location.getSpeedAccuracyMetersPerSecond() : Double.NaN;
                estimator.gps(location.hasSpeed() ? location.getSpeed() : Double.NaN,
                        accuracy, location.getElapsedRealtimeNanos());
            }

            @Override public void onProviderDisabled(String provider) {
                if (motionState.isActive(epoch) && LocationManager.GPS_PROVIDER.equals(provider))
                    stopSession(getString(R.string.status_gps_disabled));
            }
        };
        try {
            if (!locations.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                stopSession(getString(R.string.status_gps_disabled));
                return;
            }
            locations.requestLocationUpdates(LocationManager.GPS_PROVIDER, 250L, 0,
                    locationListener, thread.getLooper());
            if (!sensors.registerListener(sensorListener, gravitySensor, SensorManager.SENSOR_DELAY_GAME, worker)
                    || !sensors.registerListener(sensorListener, linearSensor, SensorManager.SENSOR_DELAY_GAME, worker)) {
                stopSession(getString(R.string.status_sensor_registration_failed));
                return;
            }
            status = getString(R.string.status_drive_mode);
            freshnessTask = new Runnable() {
                @Override public void run() {
                    if (handle == 0 || !motionState.isActive(epoch)) return;
                    if (motionState.tick(epoch, SystemClock.elapsedRealtimeNanos())
                            == DriveSessionState.Effect.SUBMIT_INVALID) {
                        qualityIssue = null;
                        nativeInvalidateMotion(handle);
                    }
                    worker.postDelayed(this, 50);
                }
            };
            worker.postDelayed(freshnessTask, 50);
        } catch (SecurityException | IllegalArgumentException error) {
            stopSession(getString(R.string.status_sensor_source_unavailable,
                    error.getClass().getSimpleName()));
        }
    }

    private void submit(long epoch, MotionInput sample) {
        if (handle == 0 || !motionState.isActive(epoch)) return;
        if (!sample.valid) {
            if (motionState.observe(epoch, sample) == DriveSessionState.Effect.SUBMIT_INVALID)
                nativeInvalidateMotion(handle);
            return;
        }
        if (!motionState.canAccept(epoch, sample)) return;
        if (nativeSubmitMotion(handle, sample.sequence, sample.measurementTimeNs,
                sample.receivedTimeNs, sample.speedMps, sample.accelerationMps2,
                sample.direction, true)) {
            motionState.observe(epoch, sample);
            qualityIssue = null;
        } else {
            motionState.observe(epoch, new MotionInput(sample.sequence, sample.measurementTimeNs,
                    sample.receivedTimeNs, 0, 0, MotionInput.UNKNOWN, false, "queue full"));
            nativeInvalidateMotion(handle);
            qualityIssue = getString(R.string.quality_command_queue_full);
        }
    }

    void selectProfile(int index) {
        worker.post(() -> {
            profile = Math.max(0, Math.min(1, index));
            if (handle != 0 && !nativeSelectProfile(handle, profile))
                qualityIssue = getString(R.string.status_profile_queue_full);
        });
    }

    void setVolume(float volume) {
        worker.post(() -> {
            if (handle != 0 && !nativeSetVolume(handle, volume))
                qualityIssue = getString(R.string.quality_command_queue_full);
        });
    }

    void stop() {
        int requestId = latestStartId;
        worker.post(() -> {
            pendingStart = null;
            beginNormalStop(getString(R.string.status_stopped), requestId);
        });
    }

    private void beginNormalStop(String reason, int requestId) {
        if (normalStopPending) return;
        stopInputsOnWorker();
        running = false;
        status = getString(R.string.status_stopping);
        normalStopReason = reason;
        stopStartId = requestId;
        if (handle == 0) { finishNormalStop(true); return; }
        normalStopPending = true;
        stopDeadlineNs = SystemClock.elapsedRealtimeNanos() + 250_000_000L;
        nativeRequestStop(handle);
        stopPollTask = new Runnable() {
            @Override public void run() {
                if (handle == 0) return;
                long now = SystemClock.elapsedRealtimeNanos();
                if (nativeStopReady(handle)) finishNormalStop(true);
                else if (nativeHasStreamError(handle) || now >= stopDeadlineNs)
                    finishNormalStop(false);
                else worker.postDelayed(this, 10);
            }
        };
        worker.post(stopPollTask);
    }

    private void finishNormalStop(boolean faded) {
        if (stopPollTask != null) worker.removeCallbacks(stopPollTask);
        stopPollTask = null;
        if (handle != 0) { nativeStop(handle); handle = 0; }
        if (focusRequest != null) { audio.abandonAudioFocusRequest(focusRequest); focusRequest = null; }
        normalStopPending = false;
        diagnostics = faded ? "stop=NORMAL_FADE_STOP" : "stop=ERROR_HARD_STOP";
        status = faded ? normalStopReason : getString(R.string.status_stop_timeout);
        qualityIssue = null;
        Runnable next = pendingStart;
        pendingStart = null;
        if (next != null) { next.run(); return; }
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelfResult(stopStartId);
    }

    private void stopSession(String reason) {
        pendingStart = null;
        stopAudioAndInputs();
        status = reason;
        qualityIssue = null;
        diagnostics = "stop=ERROR_HARD_STOP";
        running = false;
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelfResult(sessionStartId);
    }

    private void stopAudioAndInputs() {
        stopInputsOnWorker();
        if (stopPollTask != null) worker.removeCallbacks(stopPollTask);
        stopPollTask = null;
        normalStopPending = false;
        if (handle != 0) { nativeStop(handle); handle = 0; }
        if (focusRequest != null) { audio.abandonAudioFocusRequest(focusRequest); focusRequest = null; }
        bluetoothAvailableAtStart = false;
    }

    private void stopInputsOnWorker() {
        ++focusEpoch;
        motionState.stop();
        if (replayTask != null) worker.removeCallbacks(replayTask);
        if (diagnosticsTask != null) worker.removeCallbacks(diagnosticsTask);
        if (freshnessTask != null) worker.removeCallbacks(freshnessTask);
        replayTask = null;
        diagnosticsTask = null;
        freshnessTask = null;
        replay = null;
        if (sensorListener != null) sensors.unregisterListener(sensorListener);
        if (locationListener != null) {
            try { locations.removeUpdates(locationListener); } catch (SecurityException ignored) {}
        }
        sensorListener = null;
        locationListener = null;
        estimator = null;
    }

    private boolean hasBluetoothOutput() {
        for (AudioDeviceInfo device : audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
            if (device.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP
                    || device.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO) return true;
        }
        return false;
    }

    static final class ViewState {
        final String status;
        final String quality;
        final String diagnostics;
        final double speedKmh;

        ViewState(String status, String quality, String diagnostics, double speedKmh) {
            this.status = status;
            this.quality = quality;
            this.diagnostics = diagnostics;
            this.speedKmh = speedKmh;
        }
    }

    ViewState viewState() {
        DriveSessionState.Snapshot motion = motionState.snapshot();
        String qualityText = qualityIssue;
        if (qualityText == null) {
            switch (motion.quality) {
                case FRESH:
                    qualityText = getString(motion.source == DriveSessionState.Source.REPLAY
                            ? R.string.quality_replay : R.string.quality_drive_fresh);
                    break;
                case WAITING:
                    qualityText = getString(motion.source == DriveSessionState.Source.REPLAY
                            ? R.string.quality_replay : R.string.quality_sensors_waiting);
                    break;
                case STALE:
                    qualityText = getString(R.string.quality_drive_invalid);
                    break;
                default:
                    qualityText = getString(R.string.quality_stopped);
            }
        }
        return new ViewState(status, qualityText, diagnostics, motion.speedKmh);
    }

    @Override public void onDestroy() {
        audio.unregisterAudioDeviceCallback(deviceCallback);
        unregisterReceiver(noisyReceiver);
        worker.post(this::stopAudioAndInputs);
        thread.quitSafely();
        super.onDestroy();
    }
}
