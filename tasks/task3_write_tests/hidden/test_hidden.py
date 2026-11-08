"""Hidden grading tests for task 3. Not shown to the agent."""
import os
import sys
import unittest

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, WORK)

import stringutil


class TestSlugifyFunction(unittest.TestCase):
    def test_two_words(self):
        self.assertEqual(stringutil.slugify("Hello World"), "hello-world")

    def test_extra_spaces(self):
        self.assertEqual(stringutil.slugify("  A  B  "), "a-b")

    def test_already_slug(self):
        self.assertEqual(stringutil.slugify("hello"), "hello")


class TestAgentTestsExist(unittest.TestCase):
    def test_agent_test_file_exists(self):
        path = os.path.join(WORK, "tests", "test_stringutil.py")
        self.assertTrue(os.path.exists(path), "tests/test_stringutil.py missing")

    def test_agent_tests_pass_and_cover(self):
        import importlib.util
        path = os.path.join(WORK, "tests", "test_stringutil.py")
        self.assertTrue(os.path.exists(path), "tests/test_stringutil.py missing")
        spec = importlib.util.spec_from_file_location(
            "agent_stringutil_tests", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["agent_stringutil_tests"] = module
        spec.loader.exec_module(module)
        suite = unittest.TestLoader().loadTestsFromModule(module)
        result = unittest.TextTestRunner(verbosity=0).run(suite)
        self.assertGreaterEqual(result.testsRun, 3)
        self.assertEqual(len(result.failures), 0)
        self.assertEqual(len(result.errors), 0)


if __name__ == "__main__":
    unittest.main()
