package com.vico.simulator.audio

enum class AudioOutputCategory {
    BUILTIN,
    BLUETOOTH,
    WIRED,
    OTHER,
}

object AudioOutputCatalog {
    fun categoryFor(type: Int): AudioOutputCategory = when (type) {
        2 -> AudioOutputCategory.BUILTIN // TYPE_BUILTIN_SPEAKER
        7, 8, 26, 27, 30 -> AudioOutputCategory.BLUETOOTH
        3, 4, 5, 6, 11, 12, 22, 23 -> AudioOutputCategory.WIRED
        else -> AudioOutputCategory.OTHER
    }

    fun isSelectable(category: AudioOutputCategory, connected: Boolean): Boolean =
        connected && category != AudioOutputCategory.OTHER

    fun labelFor(category: AudioOutputCategory): String = when (category) {
        AudioOutputCategory.BUILTIN -> "本机扬声器"
        AudioOutputCategory.BLUETOOTH -> "蓝牙输出"
        AudioOutputCategory.WIRED -> "有线输出"
        AudioOutputCategory.OTHER -> "其他输出"
    }
}
