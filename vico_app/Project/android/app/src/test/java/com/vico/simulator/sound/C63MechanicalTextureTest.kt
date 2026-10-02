package com.vico.simulator.sound
import com.vico.simulator.sound.s16.C63MechanicalTexture
import org.junit.Assert.*
import org.junit.Test
class C63MechanicalTextureTest {
    @Test fun causalBoxHasExactlyEightHundredSamplesOfMemory() {
        val texture=C63MechanicalTexture(1.0)
        repeat(800){assertEquals((it+1)/800.0,texture.push(1.0),0.0)}
        repeat(800){assertEquals((799-it)/800.0,texture.push(0.0),0.0)}
    }
    @Test fun fullRingAndRandomStateRestoreWithoutChangingFuture() {
        val a=C63MechanicalTexture(3.0);repeat(1377){a.sample()}
        val b=C63MechanicalTexture(3.0);b.restore(a.snapshot())
        repeat(2000){assertEquals(a.sample(),b.sample(),0.0)}
    }
    @Test fun invalidInputDoesNotChangeState() {
        val a=C63MechanicalTexture(1.0);val b=C63MechanicalTexture(1.0)
        assertThrows(IllegalArgumentException::class.java){a.push(Double.NaN)}
        assertThrows(IllegalArgumentException::class.java){a.push(1.1)}
        repeat(900){assertEquals(a.sample(),b.sample(),0.0)}
    }
}
