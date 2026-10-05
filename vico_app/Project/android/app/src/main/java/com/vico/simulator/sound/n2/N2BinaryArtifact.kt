package com.vico.simulator.sound.n2

import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest
import kotlin.math.abs

/** Canonical CPU/Android binary profile. The bytes are the profile; kernels are never regenerated. */
internal object N2BinaryArtifact {
    private const val MAGIC = 0x4e324250
    private const val VERSION = 2
    private const val MAX_ARRAY = 20000
    private const val BYTES = 20 + 66 + 32 + 24 + 12 * 4 + (8 + 8 * 4096 + 3 * 12288) * 8

    internal data class Loaded(
        val profile: N2Profile,
        val artifactSha256: String,
    )

    fun write(profile: N2Profile, out: OutputStream) {
        val data = DataOutputStream(out)
        data.writeInt(MAGIC)
        data.writeInt(VERSION)
        data.writeInt(N2Profile.BASIS_COUNT)
        data.writeInt(N2Profile.BASIS_LENGTH)
        data.writeInt(N2Profile.EVENT_LENGTH)
        data.writeUTF(profile.identity)
        data.writeDouble(profile.sourceScale)
        data.writeDouble(profile.randomFraction)
        data.writeDouble(profile.eventScale)
        data.writeDouble(profile.eventNoiseFraction)
        data.writeLong(profile.sourceSeed)
        data.writeLong(profile.occurrenceSeed)
        data.writeLong(profile.responseSeed)
        writeArray(data, profile.coefficients())
        repeat(N2Profile.BASIS_COUNT) { writeArray(data, profile.basis(it)) }
        writeArray(data, profile.eventResponse())
        writeArray(data, profile.eventNoiseA())
        writeArray(data, profile.eventNoiseB())
        data.flush()
    }

    fun read(input: InputStream): Loaded {
        val bytes = ByteArray(BYTES)
        var offset = 0
        while (offset < bytes.size) {
            val count = input.read(bytes, offset, bytes.size - offset)
            require(count > 0) { "N2 artifact truncated" }
            offset += count
        }
        require(input.read() == -1) { "N2 artifact trailing bytes" }
        return try { decode(bytes) } catch (error: java.io.IOException) {
            throw IllegalArgumentException("Malformed N2 binary artifact", error)
        }
    }

    private fun decode(bytes: ByteArray): Loaded {
        val data = DataInputStream(bytes.inputStream())
        val magic = data.readInt()
        require(magic == MAGIC)
        require(data.readInt() == VERSION)
        require(data.readInt() == N2Profile.BASIS_COUNT)
        require(data.readInt() == N2Profile.BASIS_LENGTH)
        require(data.readInt() == N2Profile.EVENT_LENGTH)
        val storedIdentity = data.readUTF()
        require(storedIdentity.matches(Regex("[0-9a-f]{64}"))) { "N2 artifact identity format" }
        val sourceScale = data.readDouble()
        val randomFraction = data.readDouble()
        val eventScale = data.readDouble()
        val eventNoiseFraction = data.readDouble()
        val sourceSeed = data.readLong()
        val occurrenceSeed = data.readLong()
        val responseSeed = data.readLong()
        val coefficients = readArray(data, N2Profile.BASIS_COUNT)
        val basis = Array(N2Profile.BASIS_COUNT) { readArray(data, N2Profile.BASIS_LENGTH) }
        val event = readArray(data, N2Profile.EVENT_LENGTH)
        val noiseA = readArray(data, N2Profile.EVENT_LENGTH)
        val noiseB = readArray(data, N2Profile.EVENT_LENGTH)
        require(data.available() == 0) { "N2 artifact trailing bytes" }
        val profile = N2Profile(
            basis, coefficients, event, noiseA, noiseB,
            sourceScale, randomFraction, eventScale, eventNoiseFraction,
            sourceSeed, occurrenceSeed, responseSeed,
        )
        require(profile.identity == storedIdentity) { "N2 artifact identity mismatch" }
        require(sourceScale.isFinite() && sourceScale > 0.0 && sourceScale < 100.0)
        require(eventScale.isFinite() && eventScale > 0.0 && eventScale < 100.0)
        return Loaded(profile, sha(bytes))
    }

    private fun writeArray(data: DataOutputStream, values: DoubleArray) {
        data.writeInt(values.size)
        values.forEach(data::writeDouble)
    }

    private fun readArray(data: DataInputStream, expected: Int): DoubleArray {
        val n = data.readInt()
        require(n == expected && n <= MAX_ARRAY)
        return DoubleArray(n) { data.readDouble() }
    }

    private fun sha(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes).joinToString("") { "%02x".format(it) }
}
