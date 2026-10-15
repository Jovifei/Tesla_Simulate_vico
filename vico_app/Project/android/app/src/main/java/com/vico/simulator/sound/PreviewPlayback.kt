package com.vico.simulator.sound

/** Called by the UI owner only after rejecting running and fading playback. */
internal fun startPreviewPlayback(
    isBusy: Boolean,
    prepare: () -> Boolean,
    start: () -> Boolean,
    restore: () -> Unit,
): Boolean {
    if (isBusy) return false
    val started = try { prepare() && start() } catch (_: Exception) { false }
    if (started) return true
    restore()
    return false
}

/** UI-owned, bounded retries: the writer's completion callback can precede thread exit. */
internal fun restorePreviewWhenIdle(
    owns: () -> Boolean,
    isBusy: () -> Boolean,
    stop: () -> Unit,
    restore: () -> Unit,
    retry: (Runnable) -> Unit,
    onTimeout: () -> Unit,
    maxBusyChecks: Int = 50,
): Runnable = object : Runnable {
    private var stopped = false
    private var finished = false
    private var busyChecks = 0

    override fun run() {
        if (finished) return
        if (!owns()) { finished = true; return }
        if (!stopped) { stopped = true; stop() }
        if (isBusy()) {
            if (++busyChecks >= maxBusyChecks) {
                finished = true
                onTimeout()
            } else retry(this)
            return
        }
        finished = true
        restore()
    }
}
