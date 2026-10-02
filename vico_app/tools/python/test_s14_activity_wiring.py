"""Source wiring contracts complement coordinator JVM and real-device scenarios."""
from pathlib import Path
import os

ROOT=Path(os.environ.get('S14_TEST_SOURCE_ROOT',Path(__file__).resolve().parents[2]))
MAIN=ROOT/'Project/android/app/src/main/java/com/vico/simulator/MainActivity.kt'
ENGINE=ROOT/'Project/android/app/src/main/java/com/vico/simulator/sound/AudioEngine.kt'

def test_actual_preview_callback_checks_generation_owner():
    source=MAIN.read_text(encoding='utf-8')
    preview=source.split('fun previewVehicle(key: String)',1)[1]
    assert 'playbackEpoch.owns(previewOwner)' in preview
    stop=source.split('fun stopAudio(',1)[1].split('fun startS14Reference',1)[0]
    assert 'cancelPreviewCallbacks()' in stop

def test_actual_reference_loader_uses_background_and_ticket_owner():
    source=MAIN.read_text(encoding='utf-8')
    start=source.split('fun startS14Reference',1)[1].split('fun startS13Review',1)[0]
    assert 'Thread({' in start and 'file.length() == 5_760_000L' in start
    assert 's14.owns(owner)' in start and 's14.state != S14TrialCoordinator.State.LOADING' in start
    assert 'startS14Reference(session, owner)' in start

def test_actual_completion_exports_captured_objects_not_next_engine_session():
    source=ENGINE.read_text(encoding='utf-8')
    assert 'S14CompletedCapture(result, reviewCore, capture)' in source
    main=MAIN.read_text(encoding='utf-8')
    finish=main.split('private fun finishS14Reference',1)[1].split('fun startS13Review',1)[0]
    assert 'capture::exportCore' in finish and 'capture::exportAccepted' in finish
