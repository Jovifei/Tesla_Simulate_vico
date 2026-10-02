package com.vico.simulator.state

class VehicleSelectionState(initialKey: String) {
    var selectedKey: String = initialKey
        private set
    var playingKey: String? = null
        private set

    fun select(key: String) {
        selectedKey = key
    }

    fun startEngine() {
        playingKey = selectedKey
    }

    fun stopEngine() {
        playingKey = null
    }
}
