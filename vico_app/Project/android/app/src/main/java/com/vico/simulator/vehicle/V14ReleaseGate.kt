package com.vico.simulator.vehicle

import java.security.MessageDigest

/** The current build has no trusted owner-audition verifier or bound runtime package. */
object V14ReleaseGate {
    fun canPlay(key: String): Boolean {
        if (!CurrentVehicleCatalog.isSupported(key)) return false
        return false
    }

    fun checkedRegistry(bytes: ByteArray): String? {
        if (bytes.size > 65_536) return null
        val sha = MessageDigest.getInstance("SHA-256").digest(bytes)
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        return if (sha == V14_REGISTRY_SHA256) bytes.toString(Charsets.UTF_8) else null
    }
}
