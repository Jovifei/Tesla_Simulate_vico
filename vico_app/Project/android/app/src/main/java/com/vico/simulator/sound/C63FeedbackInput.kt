package com.vico.simulator.sound
internal object C63FeedbackInput {
    fun valid(assessment:String,notes:String)=assessment in setOf("rejected","unsure","improved") && notes.isNotBlank()
}
