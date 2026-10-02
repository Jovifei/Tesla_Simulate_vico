package com.vico.simulator.sound.n2

/** Transaction boundary helper: validation must complete before live mutation. */
internal object N2TransactionalRestore {
    fun <T> restoreAtomically(
        validate: () -> T,
        apply: (T) -> Unit,
    ) {
        val prepared = validate()
        apply(prepared)
    }
}
