package com.vico.simulator.sound.s18

/**
 * Lifecycle safety boundary for future opt-in renderer ownership.
 * It does not replace the existing AudioEngine lifecycle.
 */
internal class C63P3LifecycleGuard {
    private var active = false

    fun start(validInput: Boolean): Boolean {
        if (!validInput) {
            active = false
            return false
        }
        active = true
        return true
    }

    fun pause() {
        active = false
    }

    fun restore(validInput: Boolean): Boolean {
        return start(validInput)
    }

    fun isActive(): Boolean = active
}
