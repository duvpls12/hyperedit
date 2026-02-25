import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / 'run_cinematic_training_qa_batch10.py'

spec = importlib.util.spec_from_file_location('batch10', MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestVisionInstanceGuard(unittest.TestCase):
    def test_validate_vision_instance_count_enforces_exactly_one(self):
        self.assertTrue(mod.validate_vision_instance_count(1))
        with self.assertRaises(RuntimeError):
            mod.validate_vision_instance_count(0)
        with self.assertRaises(RuntimeError):
            mod.validate_vision_instance_count(2)

    def test_fallback_order_is_11b_then_8b_then_4b(self):
        self.assertEqual(len(mod.VISION_MODELS), 3)
        self.assertIn('11b', mod.VISION_MODELS[0].lower())
        self.assertIn('8b', mod.VISION_MODELS[1].lower())
        self.assertIn('4b', mod.VISION_MODELS[2].lower())


if __name__ == '__main__':
    unittest.main()
