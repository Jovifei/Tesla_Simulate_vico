package com.vico.simulator.sound

/** Called by the UI owner; a running preview temporarily borrows its existing session. */
internal fun startPreviewPlayback(
    wasRunning: Boolean,
    prepare: () -> Boolean,
    start: () -> Boolean,
    restore: () -> Unit,
): Boolean {
    if (wasRunning) return true
    if (prepare() && start()) return true
    restore()
    return false
}
