package com.vico.simulator.sound
import org.junit.Assert.*
import org.junit.Test
class C63FeedbackInputTest {
    @Test fun partialNegativeAndUncertainFeedbackAreValidWithoutPair() {
        assertTrue(C63FeedbackInput.valid("rejected","刺耳，提前停止"))
        assertTrue(C63FeedbackInput.valid("unsure","音量不足，暂不能判断"))
        assertFalse(C63FeedbackInput.valid("accepted"," "))
        assertFalse(C63FeedbackInput.valid("unknown","说明"))
    }
}
