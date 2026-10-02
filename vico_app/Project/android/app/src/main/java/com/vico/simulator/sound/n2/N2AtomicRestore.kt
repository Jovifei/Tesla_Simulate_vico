package com.vico.simulator.sound.n2

/** Two-phase restore: validate disposable state first, mutate live state second. */
internal object N2AtomicRestore {
    fun <T> commit(validate: () -> T, apply: (T) -> Unit) {
        val checked = validate()
        apply(checked)
    }
}

internal data class N2RestoreReceipt(val valid: Boolean, val reason: String? = null)
