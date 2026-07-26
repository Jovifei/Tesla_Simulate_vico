import http.client
import json
import math
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO_ROOT = ROOT / "s12" / "acoustic_demo"
sys.path.insert(0, str(DEMO_ROOT))


from vehicle_interface.engine_runtime_api import EngineRuntimeApi  # noqa: E402
from vehicle_interface.localhost_api import LocalhostVehicleStateServer  # noqa: E402
from vehicle_interface.packet import VEHICLE_STATE_PACKET_SCHEMA_PATH, VehicleStatePacket  # noqa: E402
from vehicle_interface.vehicle_state_stream import SyntheticVehicleStateStream  # noqa: E402


def packet_at(timestamp: float, **overrides: float) -> VehicleStatePacket:
    values = {
        "timestamp": timestamp,
        "rpm": 2200.0,
        "speed": 60.0,
        "acceleration": 0.0,
        "load": 0.30,
        "throttle": 0.30,
    }
    values.update(overrides)
    return VehicleStatePacket.from_mapping(values)


def post_json(url: str, payload: object, path: str = "/vehicle_state") -> tuple[int, dict]:
    host_port = url.removeprefix("http://")
    connection = http.client.HTTPConnection(host_port, timeout=5.0)
    body = json.dumps(payload, allow_nan=True, separators=(",", ":"))
    connection.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    response = connection.getresponse()
    decoded = json.loads(response.read().decode("utf-8"))
    connection.close()
    return response.status, decoded


class VehiclePacketContractTests(unittest.TestCase):
    def test_schema_covers_every_synthetic_packet_field(self):
        schema = json.loads(VEHICLE_STATE_PACKET_SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["schema"], "s12.vehicle_state_packet.v0.1")
        self.assertTrue(schema["synthetic"])
        self.assertEqual(set(schema["fields"]), {"timestamp", "rpm", "speed", "acceleration", "load", "throttle"})
        for field in schema["fields"].values():
            self.assertEqual(field["type"], "number")
            self.assertEqual(field["source_level"], "C")
            self.assertIn("unit", field)
            self.assertEqual(len(field["range"]), 2)

    def test_packet_converts_documented_kmh_to_runtime_mps_without_clamping(self):
        packet = VehicleStatePacket.from_mapping(
            {"timestamp": 0.0, "rpm": 7000.0, "speed": 80.0, "acceleration": 1.2, "load": 0.6, "throttle": 0.5}
        )
        state = packet.to_runtime_state()

        self.assertEqual(state.rpm, 7000.0)
        self.assertAlmostEqual(state.speed_mps, 80.0 / 3.6)

    def test_stream_is_exactly_100hz_continuous_and_contains_requested_regions(self):
        packets = list(SyntheticVehicleStateStream(duration_s=10.0).iter_packets())

        self.assertEqual(len(packets), 1000)
        self.assertTrue(all(right.timestamp_s > left.timestamp_s for left, right in zip(packets, packets[1:])))
        self.assertTrue(all(
            math.isfinite(value)
            for packet in packets
            for value in (packet.rpm, packet.speed_kmh, packet.acceleration_mps2, packet.load, packet.throttle)
        ))
        self.assertTrue(any(abs(packet.rpm - 800.0) < 1.0e-9 and packet.speed_kmh == 0.0 for packet in packets))
        self.assertTrue(any(abs(packet.rpm - 2200.0) < 1.0e-9 and abs(packet.speed_kmh - 60.0) < 1.0e-9 for packet in packets))
        self.assertGreaterEqual(max(packet.rpm for packet in packets), 6000.0)
        self.assertLess(max(abs(right.rpm - left.rpm) for left, right in zip(packets, packets[1:])), 100.0)


class RuntimeApiTests(unittest.TestCase):
    def test_two_100hz_packets_produce_one_v06_pcm_frame(self):
        api = EngineRuntimeApi()

        first = api.process_state(packet_at(0.00))
        second = api.process_state(packet_at(0.01))

        self.assertIsNone(first.pcm_frame)
        self.assertIsNotNone(second.pcm_frame)
        self.assertEqual(len(second.pcm_frame.normalized_samples), 960)
        self.assertEqual(len(second.pcm_frame.pcm_s24le_stereo), 960 * 2 * 3)
        self.assertEqual(api.packet_count, 2)
        self.assertEqual(api.pcm_frame_count, 1)

    def test_invalid_packets_fall_back_without_poisoning_next_100hz_pair(self):
        api = EngineRuntimeApi()
        api.process_state(packet_at(0.00))
        invalid = api.process_state(packet_at(0.00, rpm=-1.0))
        api.process_state(packet_at(0.02))
        recovered = api.process_state(packet_at(0.03))

        self.assertTrue(invalid.fallback_applied)
        self.assertFalse(recovered.fallback_applied)
        self.assertEqual(api.fallback_count, 1)
        self.assertEqual(api.clipping_count, 0)
        self.assertEqual(api.underrun_count, 0)

    def test_other_unsafe_numeric_inputs_use_runtime_fallback(self):
        cases = (
            {"rpm": math.nan},
            {"rpm": 10001.0},
            {"acceleration": 100.0},
            {"timestamp_s": -1.0},
        )
        for values in cases:
            with self.subTest(values=values):
                api = EngineRuntimeApi()
                api.process_state(packet_at(0.00))
                timestamp = values.pop("timestamp_s", 0.01)
                result = api.process_state(packet_at(timestamp, **values))
                self.assertTrue(result.fallback_applied)
                self.assertEqual(api.clipping_count, 0)
                self.assertEqual(api.underrun_count, 0)


class LocalhostApiTests(unittest.TestCase):
    def test_localhost_post_routes_packets_and_preserves_fallback(self):
        with LocalhostVehicleStateServer(EngineRuntimeApi()) as server:
            status_a, body_a = post_json(server.url, packet_at(0.00).as_mapping())
            status_b, body_b = post_json(server.url, packet_at(0.01, rpm=math.nan).as_mapping())
            missing_status, missing_body = post_json(server.url, {}, path="/missing")

        self.assertEqual(status_a, 200)
        self.assertFalse(body_a["pcm_available"])
        self.assertEqual(status_b, 200)
        self.assertTrue(body_b["pcm_available"])
        self.assertTrue(body_b["fallback_applied"])
        self.assertEqual(missing_status, 404)
        self.assertEqual(missing_body["error"], "not_found")

    def test_malformed_or_nonnumeric_packet_is_rejected_without_stopping_server(self):
        with LocalhostVehicleStateServer(EngineRuntimeApi()) as server:
            host_port = server.url.removeprefix("http://")
            connection = http.client.HTTPConnection(host_port, timeout=5.0)
            connection.request("POST", "/vehicle_state", body="{", headers={"Content-Type": "application/json"})
            malformed = connection.getresponse()
            malformed.read()
            connection.close()
            status, body = post_json(server.url, {**packet_at(0.00).as_mapping(), "rpm": "fast"})

        self.assertEqual(malformed.status, 400)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "invalid_packet")


class VehicleInterfaceDemoTests(unittest.TestCase):
    def test_demo_is_deterministic_records_latency_and_writes_no_wav(self):
        from vehicle_interface.demo import run_vehicle_interface_demo

        with tempfile.TemporaryDirectory() as left_root, tempfile.TemporaryDirectory() as right_root:
            left = run_vehicle_interface_demo(pathlib.Path(left_root), duration_s=1.0)
            right = run_vehicle_interface_demo(pathlib.Path(right_root), duration_s=1.0)

            self.assertEqual(left.pcm_sha256, right.pcm_sha256)
            self.assertEqual((left.packet_count, left.pcm_frame_count), (100, 50))
            self.assertTrue(left.runtime_report_path.is_file())
            self.assertTrue(left.latency_report_path.is_file())
            self.assertFalse(list(pathlib.Path(left_root).rglob("*.wav")))
            latency = json.loads(left.latency_report_path.read_text(encoding="utf-8"))
            self.assertEqual(latency["sample_count"], 50)
            self.assertLess(latency["p99_ms"], 20.0)
            report = json.loads(left.runtime_report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["transport"], "localhost_http_v0.1")
            self.assertTrue(report["synthetic"])
            self.assertFalse(report["realtime_qualified"])


if __name__ == "__main__":
    unittest.main()
