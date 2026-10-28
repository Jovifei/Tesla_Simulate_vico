"""Tests for fixed-frame external texture input."""

from pathlib import Path
import tempfile
import unittest

from tools.sound_sim.s12.playground_v12.common.s12_v12_texture_frame_source import (
    FRAME_SAMPLES,
    frame_at,
    read_f32le,
    source_receipt,
)


class TextureFrameSourceTest(unittest.TestCase):
    def test_frame_is_fixed_960_samples_and_wraps_without_state_inference(self) -> None:
        values = [index / 2000.0 for index in range(FRAME_SAMPLES + 5)]
        first = frame_at(values, 0)
        second = frame_at(values, 1)
        self.assertEqual(len(first), FRAME_SAMPLES)
        self.assertEqual(len(second), FRAME_SAMPLES)
        self.assertEqual(first[0], values[0])
        self.assertEqual(second[0], values[FRAME_SAMPLES])

    def test_receipt_binds_source_sha_and_unknown_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "texture.f32le"
            path.write_bytes(b"\x00\x00\x00\x00" * FRAME_SAMPLES)
            values, digest = read_f32le(path)
            receipt = source_receipt(path, 10)
            self.assertEqual(len(values), FRAME_SAMPLES)
            self.assertEqual(receipt["source_sha256"], digest)
            self.assertEqual(receipt["state"], "UNKNOWN")
            self.assertEqual(receipt["purpose"], "RESEARCH_ONLY_NOT_PRODUCT_AUDIO")

    def test_invalid_length_and_bounds_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            odd = Path(temp) / "odd.f32le"
            odd.write_bytes(b"x")
            with self.assertRaises(ValueError):
                read_f32le(odd)
        with self.assertRaises(ValueError):
            frame_at([0.0] * (FRAME_SAMPLES - 1), 0)
        with self.assertRaises(ValueError):
            frame_at([0.0] * FRAME_SAMPLES, -1)


if __name__ == "__main__":
    unittest.main()
