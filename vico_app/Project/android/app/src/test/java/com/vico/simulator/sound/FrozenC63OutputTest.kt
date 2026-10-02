package com.vico.simulator.sound
import com.vico.simulator.sound.s15.FrozenC63Output
import org.junit.Assert.*
import org.junit.Test

class FrozenC63OutputTest {
    @Test fun exported_output_uses_same_python_reference_domain() {
        val destination=System.getenv("VICO_S15_OUTPUT_PCM")
        org.junit.Assume.assumeTrue(!destination.isNullOrBlank())
        val input=java.nio.file.Files.readAllBytes(java.nio.file.Paths.get("E:\\Tesla_speed\\review_packages\\s15-20261001\\c63-prototype-preptr.f32le"))
        val source=java.nio.ByteBuffer.wrap(input).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        val bytes=java.nio.ByteBuffer.allocate(input.size).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        val output=FrozenC63Output()
        while(source.remaining()>0)bytes.putFloat(output.sample(source.float.toDouble()).toFloat())
        val expected=java.nio.ByteBuffer.wrap(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get("E:\\Tesla_speed\\review_packages\\s15-20261001\\c63-prototype-output.f32le"))).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        val actual=java.nio.ByteBuffer.wrap(bytes.array()).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        while(expected.remaining()>0)assertEquals(expected.float,actual.float,1e-6f)
        val path=java.nio.file.Paths.get(requireNotNull(destination))
        assertFalse(java.nio.file.Files.exists(path));java.nio.file.Files.write(path,bytes.array())
    }
    @Test fun original_output_delay_and_gain_are_not_bypassed() {
        val output=FrozenC63Output()
        val impulse=DoubleArray(96){output.sample(if(it==0)1.0 else 0.0)}
        for(n in 0 until 20)assertEquals(0.0,impulse[n],0.0)
        assertTrue(impulse.drop(20).any{kotlin.math.abs(it)>1e-8})
    }
    @Test(expected=IllegalArgumentException::class) fun invalid_sample_rejected() {
        FrozenC63Output().sample(Double.NaN)
    }
}
