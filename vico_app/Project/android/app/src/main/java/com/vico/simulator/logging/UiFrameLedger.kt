package com.vico.simulator.logging

/** Bounds acknowledgements and keeps repeated UI dispatches of one control frame distinct. */
class UiFrameLedger(private val capacity: Int = 64) {
    init { require(capacity in 1..512) }
    data class Dispatch(val id: Long, val frameId: Long, val pageEpoch: Long,
                        val publishNs: Long?, val consumeNs: Long?, val dispatchNs: Long)
    private val pending = LinkedHashMap<Long, Dispatch>()
    private var sequence = 0L
    @Volatile var discarded = 0L
        private set
    @Synchronized fun register(frameId: Long, pageEpoch: Long, publishNs: Long?, consumeNs: Long?, dispatchNs: Long): Dispatch {
        val entry = Dispatch(++sequence, frameId, pageEpoch, publishNs, consumeNs, dispatchNs)
        pending[entry.id] = entry
        while (pending.size > capacity) { pending.remove(pending.keys.first()); discarded++ }
        return entry
    }
    @Synchronized fun acknowledge(id: Long, frameId: Long, currentPageEpoch: Long, receivedNs: Long, minimumFrameId: Long = 0L): Dispatch? {
        val entry = pending.remove(id) ?: return null
        if (entry.frameId < minimumFrameId || entry.frameId != frameId || entry.pageEpoch != currentPageEpoch || receivedNs < entry.dispatchNs) { discarded++; return null }
        return entry
    }
}
