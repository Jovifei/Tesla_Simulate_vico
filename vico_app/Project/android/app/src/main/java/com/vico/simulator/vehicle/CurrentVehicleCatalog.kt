package com.vico.simulator.vehicle

/** Product-facing vehicle set for the current Vico mobile milestone. */
object CurrentVehicleCatalog {
    const val defaultKey = "c63_w204_v6"

    private val entries = linkedMapOf(
        "hellcat_v6" to "Dodge Challenger SRT Hellcat",
        "ferrari_458" to "Ferrari 458 Italia",
        "lfa" to "Lexus LFA",
        "gtr_r35" to "Nissan GT-R R35",
        "c63_w204_v6" to "Mercedes-Benz C63 W204",
        "supra_jza80" to "Toyota Supra JZA80",
    )
    val keys: List<String> = entries.keys.toList()

    fun isSupported(key: String): Boolean = key in keys

    fun displayName(key: String): String = entries[key] ?: "Unknown vehicle"
}
