package com.vico.simulator.sensor
import org.junit.Assert.*
import org.junit.Test

class VehicleMountingSessionTest {
    private val calibrated=CalibrationSession.Snapshot("calibration-one",CalibrationSession.Status.COMPLETE,24,24,25)
    @Test fun allSixNaturalDeviceAxesProduceSignedVehicleAccelerationAndBrake() {
        for(axis in VehicleMountAxis.values()) {
            val m=VehicleMountingSession(axis)
            assertFalse(m.trusted)
            assertTrue(m.confirm(axis,true,1,calibrated,true,0.0))
            val input=FloatArray(3);input[axis.component]=(2.0*axis.sign).toFloat()
            assertEquals(2.0,m.project(input,1,calibrated)!!,0.0)
            input[axis.component]=(-2.0*axis.sign).toFloat()
            assertEquals(-2.0,m.project(input,1,calibrated)!!,0.0)
            assertEquals(0.0,m.project(FloatArray(3),1,calibrated)!!,0.0)
        }
    }
    @Test fun selectionIsNotTrustAndFailedConfirmationDoesNotChangePreference() {
        val m=VehicleMountingSession(VehicleMountAxis.TOP)
        assertFalse(m.confirm(VehicleMountAxis.SCREEN,false,1,calibrated,true,0.0))
        assertEquals(VehicleMountAxis.TOP,m.selected);assertFalse(m.trusted)
        assertFalse(m.confirm(VehicleMountAxis.SCREEN,true,1,calibrated,true,30.0))
        assertEquals(VehicleMountAxis.TOP,m.selected)
    }
    @Test fun calibrationAndInputSessionsAreBoundButNavigationDoesNotAlterTrust() {
        val m=VehicleMountingSession();assertTrue(m.confirm(VehicleMountAxis.BOTTOM,true,1,calibrated,true,null))
        repeat(3){assertEquals(2.0,m.project(floatArrayOf(0f,-2f,0f),1,calibrated)!!,0.0)}
        assertNull(m.project(floatArrayOf(0f,-2f,0f),2,calibrated));assertFalse(m.trusted)
        assertTrue(m.confirm(VehicleMountAxis.BOTTOM,true,2,calibrated,true,0.0))
        assertNull(m.project(floatArrayOf(0f,-2f,0f),2,calibrated.copy(revision=26)))
    }
    @Test fun backgroundMoveAndInvalidSampleFailClosedWithoutErasingChoice() {
        val m=VehicleMountingSession();m.confirm(VehicleMountAxis.LEFT,true,1,calibrated,true,0.0)
        m.invalidate("APP_BACKGROUND");assertFalse(m.trusted);assertEquals(VehicleMountAxis.LEFT,m.selected)
        assertNull(m.project(floatArrayOf(1f,0f,0f),1,calibrated))
        m.confirm(VehicleMountAxis.LEFT,true,1,calibrated,true,0.0)
        assertNull(m.project(floatArrayOf(Float.NaN,0f,0f),1,calibrated));assertFalse(m.trusted)
    }
    @Test fun calibrationBiasCorrectionPrecedesAnySignedAxisProjection() {
        val cal=CalibrationSession();cal.begin("bias",1L)
        repeat(24){cal.add(floatArrayOf(.25f,-.5f,1f),it+1L)}
        assertTrue(cal.finish("bias"))
        val m=VehicleMountingSession();assertTrue(m.confirm(VehicleMountAxis.BACK,true,1,cal.snapshot,true,0.0))
        val corrected=cal.correct(floatArrayOf(.25f,-.5f,-1f))
        assertEquals(2.0,m.project(corrected,1,cal.snapshot)!!,0.0)
        cal.reset();assertNull(m.project(corrected,1,cal.snapshot))
    }
    @Test fun missingCalibrationOrImuCannotConfirm() {
        val m=VehicleMountingSession()
        assertFalse(m.confirm(VehicleMountAxis.TOP,true,1,CalibrationSession.Snapshot(),true,0.0))
        assertFalse(m.confirm(VehicleMountAxis.TOP,true,1,calibrated,false,0.0))
        assertFalse(m.confirm(VehicleMountAxis.TOP,true,0,calibrated,true,0.0))
    }
    @Test fun uiRotationDoesNotRedefineNaturalPhysicalSensorAxes() {
        for(rotation in 0..3){
            val currentPortrait=rotation%2==0
            assertTrue(hasPortraitNaturalOrientation(rotation,currentPortrait))
            assertFalse(hasPortraitNaturalOrientation(rotation,!currentPortrait))
        }
    }
}
