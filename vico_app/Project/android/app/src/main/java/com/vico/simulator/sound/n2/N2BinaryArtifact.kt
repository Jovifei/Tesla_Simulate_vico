package com.vico.simulator.sound.n2

import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest

/** Immutable CPU/Android shared N2 artifact. No runtime kernel generation. */
internal object N2BinaryArtifact {
    private const val MAGIC = 0x4e32424c
    const val VERSION = 1

    fun write(profile: N2Profile, out: OutputStream) {
        DataOutputStream(out).use { data ->
            data.writeInt(MAGIC)
            data.writeInt(VERSION)
            data.writeUTF(profile.identity)
            data.writeDouble(profile.sourceScale)
            data.writeDouble(profile.eventScale)
            repeat(N2Profile.BASIS_COUNT) { i ->
                val a = profile.basis(i)
                data.writeInt(a.size)
                a.forEach(data::writeDouble)
            }
            listOf(profile.eventResponse(), profile.eventNoiseA(), profile.eventNoiseB()).forEach { a ->
                data.writeInt(a.size)
                a.forEach(data::writeDouble)
            }
        }
    }

    fun read(input: InputStream): N2BinaryReceipt {
        DataInputStream(input).use { data ->
            require(data.readInt() == MAGIC)
            require(data.readInt() == VERSION)
            val identity = data.readUTF()
            val sourceScale = data.readDouble()
            val eventScale = data.readDouble()
            val arrays = ArrayList<DoubleArray>()
            repeat(N2Profile.BASIS_COUNT + 3) {
                val n = data.readInt()
                require(n > 0)
                arrays += DoubleArray(n) { data.readDouble() }
            }
            return N2BinaryReceipt(identity, sourceScale, eventScale, sha(identity, arrays))
        }
    }

    private fun sha(id: String, arrays: List<DoubleArray>): String {
        val h = MessageDigest.getInstance("SHA-256")
        h.update(id.toByteArray())
        arrays.forEach { a -> a.forEach { h.update(java.nio.ByteBuffer.allocate(8).putDouble(it).array()) } }
        return h.digest().joinToString("") { "%02x".format(it) }
    }
}

internal data class N2BinaryReceipt(
    val identity: String,
    val sourceScale: Double,
    val eventScale: Double,
    val artifactHash: String,
)
