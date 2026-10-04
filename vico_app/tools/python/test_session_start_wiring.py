"""Static Android-call-site contract; complements real JVM lifecycle tests, not Android compilation."""
from pathlib import Path
import unittest

class SessionStartWiringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (Path(__file__).resolve().parents[2] / 'Project/android/app/src/main/java/com/vico/simulator/MainActivity.kt').read_text()
    def method(self, name):
        start = self.text.index('fun ' + name + '(')
        begin = self.text.index('{', start); level = 1; end = begin + 1
        while level:
            level += (self.text[end] == '{') - (self.text[end] == '}'); end += 1
        return self.text[begin:end]
    def test_success_precedes_start_request_and_failed_start_never_requests(self):
        body = self.method('startAudio')
        self.assertLess(body.index('if (!audioEngine.start())'), body.index('requestTestLogStartWhenReady()'))
        self.assertLess(body.index('audioRunning = true'), body.index('requestTestLogStartWhenReady()'))
        self.assertNotIn('requestTestLogStartWhenReady()', body[body.index('if (!audioEngine.start())'):body.index('audioRunning = true')])
    def test_start_guard_and_stop_cancellation_use_current_generation(self):
        guard = self.method('requestTestLogStartWhenReady')
        for token in ('activityDestroyed', '!testLog.requested', 'stoppingTestLog', '!audioRunning'):
            self.assertIn(token, guard)
        self.assertIn('requestSessionStart(testLogGeneration,', guard)
        stop = self.method('requestStopTestLog')
        self.assertLess(stop.index('cancelSessionStart(testLogGeneration)'), stop.index('finishTestLogWhenReady()'))
    def test_ready_callback_is_generation_guarded_and_collector_retries(self):
        callback = self.text[self.text.index('testLogOwner = SessionRecordingCoordinator'):self.text.index('testLog = SessionLogAdapter')]
        self.assertLess(callback.index('snapshot().generation == update.generation'), callback.index('requestTestLogStartWhenReady()'))
        collector = self.text[self.text.index('private val audioLogCollector'):self.text.index('private fun collectAudioLogRows')]
        self.assertIn('requestTestLogStartWhenReady()', collector)
        self.assertIn('handler.postDelayed(this, 100L)', collector)
        for token in ('Thread.sleep', 'awaitClosed', 'FileOutputStream'):
            self.assertNotIn(token, self.method('requestTestLogStartWhenReady'))

if __name__ == '__main__': unittest.main()
