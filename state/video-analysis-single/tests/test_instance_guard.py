import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'run_cinematic_training_qa_batch10.py'

spec = importlib.util.spec_from_file_location('batch10', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestVisionInstanceGuard(unittest.TestCase):
    def test_validate_qwen_instance_count_enforces_exactly_one(self):
        self.assertTrue(mod.validate_qwen_instance_count(1))
        with self.assertRaises(RuntimeError):
            mod.validate_qwen_instance_count(0)
        with self.assertRaises(RuntimeError):
            mod.validate_qwen_instance_count(2)


if __name__ == '__main__':
    unittest.main()
