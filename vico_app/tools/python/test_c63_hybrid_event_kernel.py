import unittest

import numpy as np

from c63_hybrid_event_kernel import event_bases


LEVELS_DB = np.array([-4.0, -2.0, 1.0, 3.0, 2.0, 0.0, -3.0, -6.0])


class HybridEventKernelTest(unittest.TestCase):
    def test_rejects_invalid_inputs(self):
        invalid_cases = (
            (np.nan, 35.0, LEVELS_DB, 1),
            (0.9, 35.0, LEVELS_DB, 1),
            (100.1, 35.0, LEVELS_DB, 1),
            (35.0, np.inf, LEVELS_DB, 1),
            (35.0, 4.9, LEVELS_DB, 1),
            (35.0, 120.1, LEVELS_DB, 1),
            (35.0, 35.0, LEVELS_DB[:-1], 1),
            (35.0, 35.0, np.array([0.0, 1.0, 2.0, 3.0, np.nan, 5.0, 6.0, 7.0]), 1),
            (35.0, 35.0, LEVELS_DB, 0),
            (35.0, 35.0, LEVELS_DB, 1.5),
            (35.0, 35.0, LEVELS_DB, True),
        )
        for case in invalid_cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    event_bases(*case)

    def test_returns_fixed_finite_dc_free_orthonormal_bases(self):
        bases = event_bases(35.0, 55.0, LEVELS_DB, seed=5900023)

        self.assertEqual(len(bases), 3)
        for basis in bases:
            self.assertEqual(basis.dtype, np.float64)
            self.assertEqual(basis.shape, (12288,))
            self.assertTrue(np.all(np.isfinite(basis)))
            self.assertLess(abs(float(np.sum(basis))), 1e-8)
            self.assertAlmostEqual(float(np.dot(basis, basis)), 1.0, delta=1e-6)
            self.assertEqual(float(basis[-1]), 0.0)
        self.assertEqual(float(bases[0][0]), 0.0)
        for left in range(3):
            for right in range(left + 1, 3):
                self.assertLess(abs(float(np.dot(bases[left], bases[right]))), 1e-6)

    def test_seed_reproduces_bases_and_only_changes_noise_basis(self):
        first = event_bases(35.0, 55.0, LEVELS_DB, seed=1234)
        repeat = event_bases(35.0, 55.0, LEVELS_DB, seed=1234)
        other = event_bases(35.0, 55.0, LEVELS_DB, seed=1235)

        for actual, expected in zip(first, repeat):
            np.testing.assert_array_equal(actual, expected)
        np.testing.assert_array_equal(first[0], other[0])
        self.assertFalse(np.array_equal(first[1], other[1]))
        self.assertFalse(np.array_equal(first[2], other[2]))

    def test_mixed_response_energy_is_invariant_over_angles_and_ratios(self):
        pressure, noise_a, noise_b = event_bases(35.0, 55.0, LEVELS_DB)
        for ratio in (0.0, 0.25, 0.5):
            for theta in np.linspace(0.0, 2.0 * np.pi, 10, endpoint=False):
                mixed = (
                    np.sqrt(1.0 - ratio) * pressure
                    + np.sqrt(ratio)
                    * (np.cos(theta) * noise_a + np.sin(theta) * noise_b)
                )
                self.assertAlmostEqual(float(np.dot(mixed, mixed)), 1.0, delta=1e-6)

    def test_extreme_supported_timing_has_finite_fixed_support_endpoints(self):
        for attack_ms, tail_ms in ((1.0, 5.0), (100.0, 120.0)):
            with self.subTest(attack_ms=attack_ms, tail_ms=tail_ms):
                bases = event_bases(attack_ms, tail_ms, LEVELS_DB)
                for basis in bases:
                    self.assertEqual(basis.shape, (12288,))
                    self.assertTrue(np.all(np.isfinite(basis)))
                    self.assertEqual(float(basis[0]), 0.0)
                    self.assertEqual(float(basis[-1]), 0.0)


if __name__ == "__main__":
    unittest.main()
