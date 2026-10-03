package com.vico.simulator.sensor

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.pm.PackageManager
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

/**
 * 传感器管线: LocationManager(速度 km/h) + SensorManager(TYPE_LINEAR_ACCELERATION 前向加速度) + 校准。
 *
 * MVP 校准假设: 手机竖装、顶部朝前, 前向 = 设备 Y 轴; 静止采样取 Y 轴偏置去漂移。
 *   (非完整 3 轴投影; 文档明确标注, 后续可升级。满足 PRD FR-06 基本校准动作。)
 * 演示模式: 内置场景发生器(停止/起步/巡航/减速/极速), 无传感器调试入口。
 *
 * 回调 ~20Hz(50ms): (speedKmh, forwardAccelMps2, gpsOk, rawAccel[3])。
 * PRD FR-01/FR-02/FR-06, NFR-04。
 */
class SensorProvider(
    private val context: Context,
    private val onSample: (speedKmh: Double, forwardAccelMps2: Double, gpsOk: Boolean, rawAccel: FloatArray, gravity: FloatArray) -> Unit,
) {
    private val handler = Handler(Looper.getMainLooper())
    private val tickMs = 50L

    private val locationSpeed = LocationSpeedState()
    private val linearAcceleration = LinearAccelerationState()
    private var sessionStartedNanos = 0L
    private var locationStartedNanos = 0L
    @Volatile private var gravity: FloatArray = FloatArray(3)
    @Volatile private var useAccelAsGravity: Boolean = false   // TYPE_GRAVITY 不可用时用 TYPE_ACCELEROMETER 兜底
    @Volatile private var gravityLogged: Boolean = false
    private val sourceState = SensorSourceState()

    // 校准
    private val calibration = CalibrationSession()
    val isCalibrated: Boolean get() = calibration.isCalibrated
    val calibrationStatus: CalibrationSession.Snapshot get() = calibration.snapshot

    // 演示模式
    @Volatile private var demoMode: Boolean = false
    @Volatile private var demoScenario: String = "stop"
    private val demoController = DemoMotionController()
    private var demoLastMs: Long = 0L

    private val sensorManager: SensorManager =
        context.getSystemService(Context.SENSOR_SERVICE) as SensorManager
    private val locationManager: LocationManager =
        context.getSystemService(Context.LOCATION_SERVICE) as LocationManager

    private val sensorListener = object : SensorEventListener {
        override fun onSensorChanged(event: SensorEvent) {
            if (!started || event.timestamp < sessionStartedNanos) return
            if (event.sensor.type == Sensor.TYPE_LINEAR_ACCELERATION) {
                if (linearAcceleration.update(event.values, event.timestamp, SystemClock.elapsedRealtimeNanos())) {
                    calibration.add(linearAcceleration.sample(), event.timestamp)
                }
            } else if (event.sensor.type == Sensor.TYPE_GRAVITY || (useAccelAsGravity && event.sensor.type == Sensor.TYPE_ACCELEROMETER)) {
                if (event.values.size < 3 || (0..2).any { !event.values[it].isFinite() }) return
                gravity = floatArrayOf(event.values[0], event.values[1], event.values[2])
                if (!gravityLogged && (event.values[0] != 0f || event.values[1] != 0f || event.values[2] != 0f)) {
                    gravityLogged = true
                    android.util.Log.d("VicoSensor", "gravity flowing type=${event.sensor.type} vals=${event.values[0]},${event.values[1]},${event.values[2]}")
                }
            }
        }
        override fun onAccuracyChanged(p0: Sensor?, p1: Int) {}
    }

    private val locationListener = object : LocationListener {
        override fun onLocationChanged(location: Location) = acceptLocations(listOf(location))
        override fun onLocationChanged(locations: MutableList<Location>) = acceptLocations(locations)
        override fun onProviderEnabled(p0: String) {}
        override fun onProviderDisabled(p0: String) { locationSpeed.clear() }
        @Suppress("DEPRECATION", "OVERRIDE_DEPRECATION")
        override fun onStatusChanged(p0: String?, p1: Int, p2: Bundle?) {}
    }

    private fun acceptLocations(locations: List<Location>) {
        if (!started) return
        val samples = locations.filter { it.elapsedRealtimeNanos >= locationStartedNanos }.map {
            LocationSpeedSample(it.speed.toDouble(), it.hasSpeed(), it.elapsedRealtimeNanos)
        }
        val accepted = locationSpeed.updateLatest(samples, SystemClock.elapsedRealtimeNanos())
        if (accepted && !demoMode) {
            // Publish the newest usable fix next turn, without an extra 50 ms wait.
            // Coalesce a burst so it cannot create a render/UI backlog.
            handler.removeCallbacks(tickRunnable)
            handler.post(tickRunnable)
        }
    }

    private val tickRunnable = object : Runnable {
        override fun run() {
            if (!started) return
            if (demoMode) sourceState.updateDemo(stepDemo())
            expireRealInput()
            sourceState.updateReal(realFrame())
            emit(sourceState.current())
            handler.postDelayed(this, tickMs)
        }
    }

    @Volatile private var started: Boolean = false

    fun start() {
        if (started) return
        clearRealInput()
        sessionStartedNanos = SystemClock.elapsedRealtimeNanos()
        started = true
        demoLastMs = SystemClock.elapsedRealtime()
        sensorManager.getDefaultSensor(Sensor.TYPE_LINEAR_ACCELERATION)?.let {
            sensorManager.registerListener(sensorListener, it, SensorManager.SENSOR_DELAY_GAME, 0)
        }
        val gravSensor = sensorManager.getDefaultSensor(Sensor.TYPE_GRAVITY)
        if (gravSensor != null) {
            sensorManager.registerListener(sensorListener, gravSensor, SensorManager.SENSOR_DELAY_GAME, 0)
        } else {
            useAccelAsGravity = true
            sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)?.let {
                sensorManager.registerListener(sensorListener, it, SensorManager.SENSOR_DELAY_GAME, 0)
            }
        }
        refreshLocation()
        handler.post(tickRunnable)
    }

    /** 重新注册位置更新（权限授予后调用）。 */
    fun refreshLocation() {
        try { locationManager.removeUpdates(locationListener) } catch (_: SecurityException) {}
        locationSpeed.clear()
        locationStartedNanos = SystemClock.elapsedRealtimeNanos()
        if (started && hasLocationPermission()) {
            try {
                @Suppress("DEPRECATION")
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER, 100L, 0f, locationListener
                )
            } catch (_: SecurityException) {
            } catch (_: IllegalArgumentException) {
            }
        }
    }

    fun stop() {
        calibration.cancel()
        started = false
        handler.removeCallbacks(tickRunnable)
        sensorManager.unregisterListener(sensorListener)
        try { locationManager.removeUpdates(locationListener) } catch (_: SecurityException) {}
        clearRealInput()
    }

    fun setDemoMode(on: Boolean) {
        if (on) {
            demoController.reset()
            demoLastMs = SystemClock.elapsedRealtime()
            sourceState.updateDemo(SensorFrame(0.0, 0.0, true, FloatArray(3)))
        }
        expireRealInput()
        sourceState.updateReal(realFrame())
        demoMode = on
        emit(sourceState.setDemoMode(on))
    }

    fun isDemoMode(): Boolean = demoMode

    fun setDemoScenario(key: String) { demoScenario = key }

    fun hasLocationPermission(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    fun requestLocationPermission(activity: Activity) {
        if (!hasLocationPermission()) {
            ActivityCompat.requestPermissions(activity, arrayOf(
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION,
            ), LOC_PERM_REQUEST)
        }
    }

    fun beginCalibration(session: String) =
        calibration.begin(session, SystemClock.elapsedRealtimeNanos(), available = started)

    fun finishCalibration(session: String): Boolean = calibration.finish(session)

    fun cancelCalibration(session: String? = null) = calibration.cancel(session)

    fun resetCalibration() = calibration.reset()

    /** 给校准页推送实时三轴的当前值 (供 UI 显示)。 */
    fun snapshotRawAccel(): FloatArray {
        expireRealInput()
        return correctedAcceleration()
    }

    private fun stepDemo(): SensorFrame {
        val now = SystemClock.elapsedRealtime()
        var dt = (now - demoLastMs) / 1000.0
        if (dt > 0.5) dt = 0.05
        demoLastMs = now
        demoController.setScenario(demoScenario)
        demoController.step(dt)
        val accel = demoController.accelMps2
        return SensorFrame(
            demoController.speedKmh,
            accel,
            true,
            floatArrayOf(0f, accel.toFloat(), 0f),
        )
    }

    private fun expireRealInput() {
        val now = SystemClock.elapsedRealtimeNanos()
        locationSpeed.expire(now)
        linearAcceleration.expire(now)
    }

    private fun clearRealInput() {
        locationSpeed.clear()
        linearAcceleration.clear()
        gravity = FloatArray(3)
        sourceState.updateReal(realFrame())
    }

    private fun correctedAcceleration(): FloatArray =
        if (linearAcceleration.valid) calibration.correct(linearAcceleration.sample()) else FloatArray(3)

    private fun realFrame(): SensorFrame {
        val corrected = correctedAcceleration()
        return SensorFrame(locationSpeed.speedKmh, corrected[1].toDouble(), locationSpeed.gpsOk, corrected)
    }

    private fun emit(frame: SensorFrame) {
        onSample(
            frame.speedKmh,
            frame.forwardAccelMps2,
            frame.gpsOk,
            frame.correctedAccel,
            gravity,
        )
    }

    companion object {
        const val LOC_PERM_REQUEST = 1001
    }

}
