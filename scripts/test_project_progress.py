import copy
import json
import unittest
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('progress', Path(__file__).with_name('update-project-progress.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ROOT, percentage, render, validate = module.ROOT, module.percentage, module.render, module.validate


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'docs/project-ledger.json').read_text(encoding='utf-8'))

    def test_valid(self):
        validate(self.data)
        self.assertEqual(2, len(render(self.data)))

    def test_no_evidence(self):
        self.data['phases'][0]['milestones'][0]['evidence'] = []
        with self.assertRaises(AssertionError):
            validate(self.data)

    def test_weights(self):
        self.data['phases'][0]['weight'] += 1
        with self.assertRaises(AssertionError):
            validate(self.data)

    def test_missing_evidence(self):
        self.data['phases'][0]['milestones'][0]['evidence'] = ['not-existing-proof.md']
        with self.assertRaises(AssertionError):
            validate(self.data)

    def test_partial_not_done_and_regression(self):
        phase = copy.deepcopy(self.data['phases'][0])
        for m in phase['milestones']:
            m['status'] = 'PARTIAL'
        self.assertEqual(0, percentage(phase))
        phase['milestones'][0]['status'] = 'DONE'
        self.assertEqual(50, percentage(phase))
        phase['milestones'][0]['status'] = 'FAILED'
        self.assertEqual(0, percentage(phase))

    def test_cycle(self):
        self.data['phases'][0]['dependencies'] = ['P2']
        with self.assertRaises(AssertionError):
            validate(self.data)


if __name__ == '__main__':
    unittest.main()
