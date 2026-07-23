"""Bounded, deterministic PTR transport over the accepted radiation package."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from s12_acoustic_audition import PressureTrace


QUALIFICATION_COMMIT = "4afe65a67ed21822422f1eb6dbf43fdd627072d3"
DEFAULT_PACKAGE_PATH = (
    Path(__file__).resolve().parents[1]
    / "benchmark"
    / "baselines"
    / "sprint-4d-b"
    / "radiation-boundary-package.json"
)


@dataclass(frozen=True)
class RadiationPackage:
    path: Path
    sha256: str
    source_commit: str
    reference_plane: str
    a: tuple[tuple[float, float], tuple[float, float]]
    b: tuple[float, float]
    c: tuple[float, float]
    d: float
    initial_state: tuple[float, float]


@dataclass(frozen=True)
class PtrNetworkConfig:
    package_path: Path = DEFAULT_PACKAGE_PATH
    upstream_delay_frames: int = 8
    downstream_delay_frames: int = 12
    upstream_loss: float = 0.98
    downstream_loss: float = 0.97

    def __post_init__(self) -> None:
        if (
            isinstance(self.upstream_delay_frames, bool)
            or isinstance(self.downstream_delay_frames, bool)
            or not isinstance(self.upstream_delay_frames, int)
            or not isinstance(self.downstream_delay_frames, int)
            or self.upstream_delay_frames < 0
            or self.downstream_delay_frames < 0
        ):
            raise ValueError("PTR delays must be nonnegative integers")
        if not all(
            math.isfinite(loss) and 0.0 < loss <= 1.0
            for loss in (self.upstream_loss, self.downstream_loss)
        ):
            raise ValueError("PTR losses must be finite values in (0, 1]")


def _finite_pair(value: object, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must have length two")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} must be finite")
    return result  # type: ignore[return-value]


def load_radiation_package(path: Path = DEFAULT_PACKAGE_PATH) -> RadiationPackage:
    """Read and validate the immutable accepted radiation-boundary package."""
    raw = Path(path).read_bytes()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("radiation package must be valid JSON") from error
    if data.get("schema") != "radiation_boundary_package.v1":
        raise ValueError("unsupported radiation package schema")
    if data.get("source_commit") != QUALIFICATION_COMMIT:
        raise ValueError("radiation package source commit is not accepted")
    a_rows = data.get("state_space_A")
    if not isinstance(a_rows, list) or len(a_rows) != 2:
        raise ValueError("state_space_A must be 2x2")
    a = tuple(_finite_pair(row, "state_space_A row") for row in a_rows)
    b = _finite_pair(data.get("state_space_B"), "state_space_B")
    c = _finite_pair(data.get("state_space_C"), "state_space_C")
    initial_state = _finite_pair(data.get("initial_state"), "initial_state")
    d = float(data.get("state_space_D"))
    if not math.isfinite(d):
        raise ValueError("state_space_D must be finite")
    reference_plane = data.get("reference_plane")
    if not isinstance(reference_plane, str) or not reference_plane:
        raise ValueError("radiation package reference plane is required")
    return RadiationPackage(
        Path(path), hashlib.sha256(raw).hexdigest(), QUALIFICATION_COMMIT,
        reference_plane, a, b, c, d, initial_state,
    )


def _delay_loss(samples: list[float], delay: int, loss: float) -> list[float]:
    return [0.0] * delay + [loss * sample for sample in samples[:-delay or None]]


def _tustin_response(samples: list[float], sample_rate_hz: int,
                     package: RadiationPackage) -> list[float]:
    if sample_rate_hz <= 0:
        raise ValueError("PTR trace must have a positive sample rate")
    dt = 1.0 / sample_rate_hz
    (a00, a01), (a10, a11) = package.a
    determinant = (1.0 - dt * a00 / 2.0) * (1.0 - dt * a11 / 2.0) - (dt * a01 / 2.0) * (dt * a10 / 2.0)
    if not math.isfinite(determinant) or abs(determinant) < 1e-15:
        raise ValueError("PTR Tustin update is singular")
    x0, x1 = package.initial_state
    output: list[float] = []
    for sample in samples:
        rhs0 = (1.0 + dt * a00 / 2.0) * x0 + dt * a01 * x1 / 2.0 + dt * package.b[0] * sample
        rhs1 = dt * a10 * x0 / 2.0 + (1.0 + dt * a11 / 2.0) * x1 + dt * package.b[1] * sample
        x0, x1 = (
            ((1.0 - dt * a11 / 2.0) * rhs0 + dt * a01 * rhs1 / 2.0) / determinant,
            (dt * a10 * rhs0 / 2.0 + (1.0 - dt * a00 / 2.0) * rhs1) / determinant,
        )
        output.append(package.c[0] * x0 + package.c[1] * x1 + package.d * sample)
    return output


def run_ptr_network(trace: PressureTrace, config: PtrNetworkConfig = PtrNetworkConfig()) -> PressureTrace:
    """Apply two causal transport sections and a two-state radiation reflection."""
    if trace.sample_rate_hz is None:
        raise ValueError("PTR trace requires a uniform sample rate")
    package = load_radiation_package(config.package_path)
    outgoing = _delay_loss(trace.pressure_pa, config.upstream_delay_frames, config.upstream_loss)
    outgoing = _delay_loss(outgoing, config.downstream_delay_frames, config.downstream_loss)
    reflected = _tustin_response(outgoing, trace.sample_rate_hz, package)
    total = [forward + backward for forward, backward in zip(outgoing, reflected)]
    if not all(math.isfinite(sample) for sample in total):
        raise ValueError("PTR output became nonfinite")
    return PressureTrace.uniform(
        "ptr_network.v1:" + trace.case_id,
        total,
        trace.sample_rate_hz,
        trace.firing_frequency_hz,
        package.reference_plane,
        trace.provenance + ("ptr_network.v1", "radiation_package_sha256=" + package.sha256),
    )
