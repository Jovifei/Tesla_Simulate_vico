package com.vico.simulator.audio

enum class PlaybackCommand {
    START,
    STOP,
}

object PlaybackCommandPolicy {
    fun commandFor(isRunning: Boolean): PlaybackCommand =
        if (isRunning) PlaybackCommand.STOP else PlaybackCommand.START
}
