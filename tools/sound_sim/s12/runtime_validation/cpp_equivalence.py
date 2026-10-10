"""Build and compare the APP-1 portable C++ runtime with Python goldens."""

from __future__ import annotations

import ctypes
import json
import math
from pathlib import Path
import struct
import subprocess
from typing import Any

from golden_export import COMPARISON_TOLERANCES, FRAMES_PER_UPDATE, export_golden_bundle
from profiles import load_builtin_profiles


class COrder(ctypes.Structure):
    _fields_ = [("order", ctypes.c_double), ("amplitude", ctypes.c_double), ("phase_rad", ctypes.c_double)]


class CProfile(ctypes.Structure):
    _fields_ = [
        ("profile_id", ctypes.c_char * 48),
        ("idle_rpm", ctypes.c_double),
        ("max_rpm", ctypes.c_double),
        ("rpm_per_mps_by_gear", ctypes.c_double * 8),
        ("gear_count", ctypes.c_uint32),
        ("acceleration_rpm_per_mps2", ctypes.c_double),
        ("upshift_rpm", ctypes.c_double),
        ("downshift_rpm", ctypes.c_double),
        ("shift_rpm_drop", ctypes.c_double),
        ("idle_load", ctypes.c_double),
        ("positive_acceleration_load_per_mps2", ctypes.c_double),
        ("negative_acceleration_load_per_mps2", ctypes.c_double),
        ("orders", COrder * 8),
        ("order_count", ctypes.c_uint32),
        ("transient_gain", ctypes.c_double),
        ("acceleration_reference_mps2", ctypes.c_double),
        ("attack_s", ctypes.c_double),
        ("release_s", ctypes.c_double),
        ("shift_impulse", ctypes.c_double),
        ("carrier_order", ctypes.c_double),
        ("sample_rate_hz", ctypes.c_uint32),
        ("output_gain", ctypes.c_double),
        ("peak_limit", ctypes.c_double),
    ]


class CMotionSample(ctypes.Structure):
    _fields_ = [
        ("sequence", ctypes.c_uint64),
        ("measurement_time_ns", ctypes.c_uint64),
        ("received_time_ns", ctypes.c_uint64),
        ("speed_mps", ctypes.c_double),
        ("acceleration_mps2", ctypes.c_double),
        ("direction", ctypes.c_uint8),
        ("valid", ctypes.c_bool),
    ]


class CVirtualState(ctypes.Structure):
    _fields_ = [
        ("virtual_rpm", ctypes.c_double),
        ("load", ctypes.c_double),
        ("gear", ctypes.c_uint32),
        ("event", ctypes.c_uint8),
        ("shift_events", ctypes.c_uint64),
        ("sample_index", ctypes.c_uint64),
        ("fallback", ctypes.c_bool),
    ]


def _c_profile(value: dict[str, Any]) -> CProfile:
    profile = CProfile()
    profile.profile_id = value["profile_id"].encode("ascii")
    for key in (
        "idle_rpm", "max_rpm", "upshift_rpm",
        "downshift_rpm", "shift_rpm_drop", "idle_load",
        "positive_acceleration_load_per_mps2", "negative_acceleration_load_per_mps2",
    ):
        setattr(profile, key, value["state_mapping"][key])
    profile.acceleration_rpm_per_mps2 = value["state_mapping"]["acceleration_rpm_per_mps2"]
    mapping = value["state_mapping"]
    profile.rpm_per_mps_by_gear = (ctypes.c_double * 8)(*(mapping["rpm_per_mps_by_gear"] + [0.0] * (8 - len(mapping["rpm_per_mps_by_gear"]))))
    profile.gear_count = len(mapping["rpm_per_mps_by_gear"])
    profile.orders = (COrder * 8)(*(
        [COrder(item["order"], item["amplitude"], item["phase_rad"]) for item in value["orders"]]
        + [COrder()] * (8 - len(value["orders"]))
    ))
    profile.order_count = len(value["orders"])
    for field, key in (
        ("transient_gain", "gain"),
        ("acceleration_reference_mps2", "acceleration_reference_mps2"),
        ("attack_s", "attack_s"),
        ("release_s", "release_s"),
        ("shift_impulse", "shift_impulse"),
        ("carrier_order", "carrier_order"),
    ):
        setattr(profile, field, value["transient"][key])
    profile.sample_rate_hz = value["output_policy"]["sample_rate_hz"]
    profile.output_gain = value["output_policy"]["gain"]
    profile.peak_limit = value["output_policy"]["peak_limit"]
    return profile


def _configure_api(library):
    library.app1_sizeof_profile.restype = ctypes.c_size_t
    library.app1_sizeof_motion_sample.restype = ctypes.c_size_t
    library.app1_sizeof_virtual_state.restype = ctypes.c_size_t
    library.app1_engine_create.argtypes = [ctypes.POINTER(CProfile), ctypes.c_uint32]
    library.app1_engine_create.restype = ctypes.c_void_p
    library.app1_engine_destroy.argtypes = [ctypes.c_void_p]
    library.app1_engine_update_motion.argtypes = [ctypes.c_void_p, ctypes.POINTER(CMotionSample), ctypes.c_uint64]
    library.app1_engine_update_motion.restype = ctypes.c_bool
    library.app1_engine_render.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_size_t]
    library.app1_engine_render.restype = ctypes.c_bool
    library.app1_engine_get_state.argtypes = [ctypes.c_void_p, ctypes.POINTER(CVirtualState)]
    library.app1_engine_get_state.restype = ctypes.c_bool
    library.app1_builtin_profile.argtypes = [ctypes.c_uint32, ctypes.POINTER(CProfile)]
    library.app1_builtin_profile.restype = ctypes.c_bool
    return library


def _profile_mismatch_count(native: CProfile, expected: dict[str, Any]) -> int:
    mapping = expected["state_mapping"]
    transient = expected["transient"]
    output = expected["output_policy"]
    scalar_pairs = (
        (native.idle_rpm, mapping["idle_rpm"]),
        (native.max_rpm, mapping["max_rpm"]),
        (native.acceleration_rpm_per_mps2, mapping["acceleration_rpm_per_mps2"]),
        (native.upshift_rpm, mapping["upshift_rpm"]),
        (native.downshift_rpm, mapping["downshift_rpm"]),
        (native.shift_rpm_drop, mapping["shift_rpm_drop"]),
        (native.idle_load, mapping["idle_load"]),
        (native.positive_acceleration_load_per_mps2, mapping["positive_acceleration_load_per_mps2"]),
        (native.negative_acceleration_load_per_mps2, mapping["negative_acceleration_load_per_mps2"]),
        (native.transient_gain, transient["gain"]),
        (native.acceleration_reference_mps2, transient["acceleration_reference_mps2"]),
        (native.attack_s, transient["attack_s"]),
        (native.release_s, transient["release_s"]),
        (native.shift_impulse, transient["shift_impulse"]),
        (native.carrier_order, transient["carrier_order"]),
        (native.output_gain, output["gain"]),
        (native.peak_limit, output["peak_limit"]),
    )
    mismatches = sum(abs(actual - wanted) > 1.0e-12 for actual, wanted in scalar_pairs)
    mismatches += native.profile_id.split(b"\0", 1)[0].decode("ascii") != expected["profile_id"]
    mismatches += native.gear_count != len(mapping["rpm_per_mps_by_gear"])
    mismatches += native.order_count != len(expected["orders"])
    mismatches += native.sample_rate_hz != output["sample_rate_hz"]
    rates = mapping["rpm_per_mps_by_gear"]
    for index in range(8):
        wanted = rates[index] if index < len(rates) else 0.0
        mismatches += abs(native.rpm_per_mps_by_gear[index] - wanted) > 1.0e-12
        if index < len(expected["orders"]):
            order = expected["orders"][index]
            actual = native.orders[index]
            mismatches += abs(actual.order - order["order"]) > 1.0e-12
            mismatches += abs(actual.amplitude - order["amplitude"]) > 1.0e-12
            mismatches += abs(actual.phase_rad - order["phase_rad"]) > 1.0e-12
    return int(mismatches)


def run_cpp_equivalence(
    output_dir: Path,
    *,
    zig_path: Path,
    source_revision: str,
    seed: int,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parents[4]
    core_root = repo_root / "runtime" / "s12_core"
    library_path = Path(zig_path).resolve().parent / "app1-s12-core.dll"
    command = [
        str(zig_path), "c++", "-std=c++17", "-O2", "-shared",
        "-Wno-nullability-completeness", "-I", str(core_root / "include"),
        str(core_root / "src" / "engine.cpp"),
        str(core_root / "src" / "c_api.cpp"),
        "-o", str(library_path),
    ]
    build = subprocess.run(command, capture_output=True, text=True, check=False)
    if build.returncode != 0:
        raise RuntimeError("C++ host build failed:\n" + (build.stderr or build.stdout)[-4000:])

    library = _configure_api(ctypes.CDLL(str(library_path)))
    layout_sizes = (ctypes.sizeof(CProfile), ctypes.sizeof(CMotionSample), ctypes.sizeof(CVirtualState))
    native_sizes = (
        library.app1_sizeof_profile(),
        library.app1_sizeof_motion_sample(),
        library.app1_sizeof_virtual_state(),
    )
    if native_sizes != layout_sizes:
        raise RuntimeError(f"C ABI size mismatch: native={native_sizes}, Python={layout_sizes}")

    golden_root = output_dir / "python-golden"
    manifest = export_golden_bundle(golden_root, source_revision=source_revision, seed=seed)
    builtin_profiles = load_builtin_profiles()
    profiles = {profile["profile_id"]: profile for profile in builtin_profiles}
    native_profile_mismatches = 0
    for index, profile in enumerate(builtin_profiles):
        native_profile = CProfile()
        if not library.app1_builtin_profile(index, ctypes.byref(native_profile)):
            raise RuntimeError(f"native built-in profile {index} was unavailable")
        native_profile_mismatches += _profile_mismatch_count(native_profile, profile)
    event_values = {"none": 0, "shift_up": 1, "shift_down": 2}
    direction_values = {"forward": 0, "reverse": 1, "stationary": 2, "unknown": 3}
    max_rpm_error = 0.0
    max_load_error = 0.0
    max_pcm_error = 0.0
    squared_pcm_error = 0.0
    pcm_value_count = 0
    event_mismatches = 0
    state_sample_count = 0

    for case in manifest["cases"]:
        profile = profiles[case["profile_id"]]
        native_profile = _c_profile(profile)
        engine = library.app1_engine_create(ctypes.byref(native_profile), seed)
        if not engine:
            raise RuntimeError(f"native engine creation failed for {case['profile_id']}")
        prefix = golden_root / case["profile_id"] / case["scenario_id"]
        motions = [json.loads(line) for line in prefix.with_suffix(".motion.jsonl").read_text(encoding="utf-8").splitlines()]
        states = [json.loads(line) for line in prefix.with_suffix(".state.jsonl").read_text(encoding="utf-8").splitlines()]
        expected_pcm = prefix.with_suffix(".pcm.f32le").read_bytes()
        output = (ctypes.c_float * (FRAMES_PER_UPDATE * 2))()
        state = CVirtualState()
        try:
            for sample_index, sample in enumerate(motions):
                native_sample = CMotionSample(
                    sample["sequence"],
                    sample["measurement_time_ns"],
                    sample["received_time_ns"],
                    sample["speed_mps"],
                    sample["longitudinal_acceleration_mps2"],
                    direction_values[sample["direction"]],
                    sample["valid"],
                )
                accepted = library.app1_engine_update_motion(engine, ctypes.byref(native_sample), sample["received_time_ns"])
                if not accepted or not library.app1_engine_get_state(engine, ctypes.byref(state)):
                    raise RuntimeError(f"native motion update rejected at {case['profile_id']}/{case['scenario_id']}/{sample_index}")
                expected_state = states[sample_index]
                max_rpm_error = max(max_rpm_error, abs(state.virtual_rpm - expected_state["virtual_rpm"]))
                max_load_error = max(max_load_error, abs(state.load - expected_state["load"]))
                if (
                    state.gear != expected_state["gear"]
                    or state.event != event_values[expected_state["event"]]
                    or state.shift_events != expected_state["shift_event_count"]
                    or state.fallback
                ):
                    event_mismatches += 1
                if not library.app1_engine_render(engine, output, FRAMES_PER_UPDATE):
                    raise RuntimeError(f"native render failed at {case['profile_id']}/{case['scenario_id']}/{sample_index}")
                pcm_offset = sample_index * FRAMES_PER_UPDATE * 8
                for frame in range(FRAMES_PER_UPDATE):
                    expected_left, expected_right = struct.unpack_from("<ff", expected_pcm, pcm_offset + frame * 8)
                    for channel, expected_value in ((0, expected_left), (1, expected_right)):
                        error = abs(float(output[frame * 2 + channel]) - expected_value)
                        max_pcm_error = max(max_pcm_error, error)
                        squared_pcm_error += error * error
                        pcm_value_count += 1
                state_sample_count += 1
        finally:
            library.app1_engine_destroy(engine)

    rms_error = math.sqrt(squared_pcm_error / max(1, pcm_value_count))
    tolerances = COMPARISON_TOLERANCES
    passed = (
        max_rpm_error <= tolerances["virtual_rpm_abs"]
        and max_load_error <= tolerances["load_abs"]
        and native_profile_mismatches == 0
        and event_mismatches == 0
        and max_pcm_error <= tolerances["pcm_sample_abs"]
        and rms_error <= tolerances["pcm_rms_abs"]
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "profile_count": len(profiles),
        "case_count": len(manifest["cases"]),
        "state_samples": state_sample_count,
        "native_profile_mismatches": native_profile_mismatches,
        "max_virtual_rpm_abs_error": max_rpm_error,
        "max_load_abs_error": max_load_error,
        "event_mismatches": event_mismatches,
        "max_pcm_sample_abs_error": max_pcm_error,
        "max_pcm_rms_abs_error": rms_error,
        "native_abi_sizes": native_sizes,
        "python_abi_sizes": layout_sizes,
    }
