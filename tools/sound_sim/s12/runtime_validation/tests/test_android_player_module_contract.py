from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[5]
ANDROID = ROOT / "android_vehicle_sound_demo"


class AndroidPlayerModuleContractTests(unittest.TestCase):
    def test_player_is_a_separate_module_and_keeps_the_pc_controller(self):
        settings = (ANDROID / "settings.gradle").read_text(encoding="utf-8")
        self.assertIn('include(":app")', settings)
        self.assertIn('include(":player")', settings)

    def test_oboe_can_be_resolved_from_an_optional_local_maven_mirror(self):
        settings = (ANDROID / "settings.gradle").read_text(encoding="utf-8")
        self.assertIn("app1OboeRepo", settings)
        self.assertIn('includeGroup("com.google.oboe")', settings)
        self.assertIn('includeGroup("com.google.prefab")', settings)

    def test_player_pins_native_dependencies_and_experimental_package_identity(self):
        gradle = (ANDROID / "player" / "build.gradle").read_text(encoding="utf-8")
        self.assertIn('applicationId "com.jovi.s12player"', gradle)
        self.assertIn('ndkVersion "30.0.16248370"', gradle)
        self.assertIn('version "3.22.1"', gradle)
        self.assertIn("com.google.oboe:oboe:1.11.0", gradle)

    def test_manifest_is_foreground_only_and_does_not_request_network_or_background_location(self):
        manifest = (ANDROID / "player" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertIn("android.permission.ACCESS_FINE_LOCATION", manifest)
        self.assertIn("android.permission.ACCESS_COARSE_LOCATION", manifest)
        self.assertIn('android:foregroundServiceType="location|mediaPlayback"', manifest)
        self.assertNotIn("ACCESS_BACKGROUND_LOCATION", manifest)
        self.assertNotIn("android.permission.INTERNET", manifest)

    def test_player_exposes_replay_profile_selection_and_sensor_source(self):
        activity = (ANDROID / "player" / "src" / "main" / "java" / "com" / "jovi" / "s12player" / "PlayerActivity.java").read_text(encoding="utf-8")
        service = (ANDROID / "player" / "src" / "main" / "java" / "com" / "jovi" / "s12player" / "DriveAudioService.java").read_text(encoding="utf-8")
        strings = (ANDROID / "player" / "src" / "main" / "res" / "values" / "strings.xml").read_text(encoding="utf-8")
        self.assertIn("button_start_replay", strings)
        self.assertIn("button_sensors", strings)
        self.assertIn("Experimental V8 Synth", strings)
        self.assertIn("Experimental Rotary Synth", strings)
        self.assertIn("startForegroundService", activity)
        self.assertIn("nativeSubmitMotion", service)
        self.assertIn("startForeground", service)
        self.assertNotIn("onPause()", activity)
        self.assertNotIn("ws://", activity)

    def test_oboe_callback_stays_native_and_uses_the_bounded_core(self):
        native = (ANDROID / "player" / "src" / "main" / "cpp" / "native_player.cpp").read_text(encoding="utf-8")
        self.assertIn("onAudioReady", native)
        self.assertIn("engine_.check_input_freshness", native)
        self.assertIn("engine_.render", native)
        self.assertNotIn("std::mutex", native)
        self.assertNotIn("NewObject", native)
        self.assertNotIn("std::vector", native)


if __name__ == "__main__":
    unittest.main()
