import json
import math
import pathlib
import sys
import tempfile
import unittest

from websockets.sync.client import connect


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "s12" / "acoustic_demo"
PROJECT_ROOT = ROOT.parents[1]
ANDROID_ROOT = PROJECT_ROOT / "android_vehicle_sound_demo"
sys.path.insert(0, str(DEMO_ROOT))


from vehicle_state_protocol import VEHICLE_STATE_SCHEMA_PATH  # noqa: E402
from runtime_server.websocket_server import VehicleRuntimeWebSocketServer  # noqa: E402
from runtime_server.demo import run_android_protocol_demo  # noqa: E402
from vehicle_interface.engine_runtime_api import EngineRuntimeApi  # noqa: E402


def packet_at(timestamp: float, **overrides: float) -> dict[str, float]:
    values = {
        "timestamp": timestamp,
        "speed": 80.0,
        "acceleration": 1.2,
        "rpm": 3200.0,
        "load": 0.6,
        "throttle": 0.6,
    }
    values.update(overrides)
    return values


class VehicleStateProtocolTests(unittest.TestCase):
    def test_schema_covers_all_synthetic_android_protocol_fields(self):
        schema = json.loads(VEHICLE_STATE_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["schema"], "s12.vehicle_state_protocol.v0.8")
        self.assertTrue(schema["synthetic"])
        self.assertEqual(
            set(schema["fields"]),
            {"timestamp", "speed", "acceleration", "rpm", "load", "throttle"},
        )
        for field in schema["fields"].values():
            self.assertEqual(field["type"], "number")
            self.assertIn("unit", field)
            self.assertEqual(len(field["range"]), 2)
            self.assertEqual(field["source_level"], "C")


class RuntimeWebSocketTests(unittest.TestCase):
    def test_two_packets_emit_pcm_through_the_existing_runtime(self):
        api = EngineRuntimeApi()
        with VehicleRuntimeWebSocketServer(api) as server:
            with connect(server.url) as socket:
                socket.send(json.dumps(packet_at(0.00)))
                first = json.loads(socket.recv())
                socket.send(json.dumps(packet_at(0.01)))
                second = json.loads(socket.recv())

        self.assertFalse(first["pcm_available"])
        self.assertTrue(second["pcm_available"])
        self.assertEqual((api.packet_count, api.pcm_frame_count), (2, 1))
        self.assertEqual(api.clipping_count, 0)
        self.assertEqual(api.underrun_count, 0)

    def test_reconnect_continues_the_runtime_state_stream(self):
        api = EngineRuntimeApi()
        with VehicleRuntimeWebSocketServer(api) as server:
            with connect(server.url) as first_socket:
                first_socket.send(json.dumps(packet_at(0.00)))
                first_socket.recv()
                first_socket.send(json.dumps(packet_at(0.01)))
                first_socket.recv()
            with connect(server.url) as second_socket:
                second_socket.send(json.dumps(packet_at(0.02)))
                second_socket.recv()
                second_socket.send(json.dumps(packet_at(0.03)))
                resumed = json.loads(second_socket.recv())

        self.assertTrue(resumed["pcm_available"])
        self.assertFalse(resumed["fallback_applied"])
        self.assertEqual((api.packet_count, api.pcm_frame_count), (4, 2))

    def test_malformed_and_nan_packets_do_not_stop_the_server(self):
        api = EngineRuntimeApi()
        with VehicleRuntimeWebSocketServer(api) as server:
            with connect(server.url) as socket:
                socket.send("{")
                malformed = json.loads(socket.recv())
                socket.send(json.dumps(packet_at(0.00)))
                socket.recv()
                socket.send(json.dumps(packet_at(0.01, rpm=math.nan), allow_nan=True))
                fallback = json.loads(socket.recv())

        self.assertEqual(malformed["error"], "invalid_packet")
        self.assertTrue(fallback["fallback_applied"])
        self.assertEqual(api.clipping_count, 0)
        self.assertEqual(api.underrun_count, 0)

    def test_one_missing_100hz_packet_injects_a_safe_fallback_without_underrun(self):
        api = EngineRuntimeApi()
        with VehicleRuntimeWebSocketServer(api) as server:
            with connect(server.url) as socket:
                socket.send(json.dumps(packet_at(0.00)))
                socket.recv()
                socket.send(json.dumps(packet_at(0.02)))
                gap = json.loads(socket.recv())
                socket.send(json.dumps(packet_at(0.03)))
                resumed = json.loads(socket.recv())

        self.assertTrue(gap["gap_fallback_applied"])
        self.assertTrue(resumed["pcm_available"])
        self.assertGreaterEqual(api.fallback_count, 1)
        self.assertEqual(api.underrun_count, 0)
        self.assertEqual(api.clipping_count, 0)

    def test_long_timestamp_gap_uses_one_bounded_safe_fallback(self):
        api = EngineRuntimeApi()
        with VehicleRuntimeWebSocketServer(api) as server:
            with connect(server.url) as socket:
                socket.send(json.dumps(packet_at(0.00)))
                socket.recv()
                socket.send(json.dumps(packet_at(1.00)))
                recovered = json.loads(socket.recv())

        self.assertTrue(recovered["gap_fallback_applied"])
        self.assertEqual((api.packet_count, api.pcm_frame_count), (3, 1))
        self.assertGreaterEqual(api.fallback_count, 1)
        self.assertEqual(api.underrun_count, 0)
        self.assertEqual(api.clipping_count, 0)


class AndroidProtocolDemoTests(unittest.TestCase):
    def test_paced_protocol_demo_records_all_packets_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as left_root, tempfile.TemporaryDirectory() as right_root:
            left = run_android_protocol_demo(
                pathlib.Path(left_root),
                duration_s=1.0,
                enforce_latency_target=False,
            )
            right = run_android_protocol_demo(
                pathlib.Path(right_root),
                duration_s=1.0,
                enforce_latency_target=False,
            )

            self.assertEqual(left.pcm_sha256, right.pcm_sha256)
            self.assertEqual((left.packet_count, left.pcm_frame_count), (100, 50))
            latency = json.loads(left.latency_report_path.read_text(encoding="utf-8"))
            self.assertEqual(latency["sample_count"], 100)
            self.assertIn("WebSocket", latency["measurement"])
            report = json.loads(left.runtime_report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["transport"], "websocket_v0.8")
            self.assertEqual(report["client_kind"], "synthetic_android_protocol_simulator")
            self.assertEqual(report["reconnect_count"], 1)
            self.assertFalse(list(pathlib.Path(left_root).rglob("*.wav")))
            self.assertFalse(list(pathlib.Path(left_root).rglob("*.pcm")))
            self.assertFalse(list(pathlib.Path(left_root).rglob("*.raw")))


class AndroidDemoContractTests(unittest.TestCase):
    def test_minimal_controller_declares_network_and_required_actions(self):
        manifest_path = ANDROID_ROOT / "app" / "src" / "main" / "AndroidManifest.xml"
        activity_path = ANDROID_ROOT / "app" / "src" / "main" / "java" / "com" / "jovi" / "s12sound" / "MainActivity.java"

        self.assertTrue(manifest_path.is_file())
        self.assertTrue(activity_path.is_file())
        manifest = manifest_path.read_text(encoding="utf-8")
        source = activity_path.read_text(encoding="utf-8")
        self.assertIn("android.permission.INTERNET", manifest)
        for label in ("Start", "Stop", "Send Vehicle State"):
            self.assertIn(label, source)
        self.assertIn("ws://", source)
        self.assertIn("\\\"rpm\\\":3200", source)
        self.assertIn("ScheduledFuture", source)
        self.assertIn("stateTask.cancel", source)
        self.assertIn("lastAcknowledgementMs", source)

    def test_android_transport_has_bounded_reads_and_a_nonblocking_close_path(self):
        activity_path = ANDROID_ROOT / "app" / "src" / "main" / "java" / "com" / "jovi" / "s12sound" / "MainActivity.java"
        source = activity_path.read_text(encoding="utf-8")

        self.assertIn("SOCKET_TIMEOUT_MS", source)
        self.assertIn("setSoTimeout(SOCKET_TIMEOUT_MS)", source)
        self.assertIn("readFully(", source)
        self.assertNotIn("readNBytes(", source)
        self.assertNotIn("synchronized void close()", source)

    def test_api_documentation_declares_synthetic_websocket_boundary(self):
        document_path = DEMO_ROOT / "runtime_server" / "Vehicle_State_API_v08.md"

        self.assertTrue(document_path.is_file())
        document = document_path.read_text(encoding="utf-8")
        self.assertIn("ws://127.0.0.1", document)
        self.assertIn("C/synthetic", document)
        self.assertIn("Android Emulator", document)
        self.assertNotIn("CAN implementation", document)

    def test_android_readme_labels_the_debug_apk_without_claiming_unsigned(self):
        readme = (ANDROID_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("Debug-signed", readme)
        self.assertNotIn("unsigned debug artifact", readme.lower())

if __name__ == "__main__":
    unittest.main()
