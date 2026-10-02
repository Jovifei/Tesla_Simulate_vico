package com.vico.simulator.sound
import com.vico.simulator.sound.s18.C63HybridProfile
import org.junit.Assert.*
import org.junit.Test
import kotlin.math.sqrt

internal object HybridTestProfiles {
    private fun pair(size:Int,offset:Int)=DoubleArray(size){if(it==offset)1/sqrt(2.0) else if(it==offset+1)-1/sqrt(2.0) else 0.0}
    fun create()=C63HybridProfile(pair(2048,0),pair(12288,0),pair(12288,2),pair(12288,4),
        1.0,1.0,.1,.2,doubleArrayOf(.5,.5,.5,.5),"0".repeat(64))
}
class C63HybridProfileTest {
    @Test fun binaryContractPreservesEveryCoefficientAndIdentity() {
        val a=HybridTestProfiles.create();val bytes=a.toBytes();val b=C63HybridProfile.fromBytes(bytes)
        assertEquals(311432,bytes.size);assertEquals(a.identity,b.identity)
        assertArrayEquals(a.periodicKernel,b.periodicKernel,0.0);assertArrayEquals(a.afterfirePressure,b.afterfirePressure,0.0)
        assertArrayEquals(a.toBytes(),b.toBytes())
    }
    @Test fun wrongSizeMagicAndNonfiniteCoefficientsFailClosed() {
        val bytes=HybridTestProfiles.create().toBytes()
        assertThrows(IllegalArgumentException::class.java){C63HybridProfile.fromBytes(bytes.copyOf(bytes.size-1))}
        bytes[0]=0;assertThrows(IllegalArgumentException::class.java){C63HybridProfile.fromBytes(bytes)}
    }
    @Test fun returnedKernelCannotMutateTheBoundProfile() {
        val a=HybridTestProfiles.create();val before=a.toBytes();a.periodicKernel.fill(0.0)
        assertArrayEquals(before,a.toBytes())
    }
}
