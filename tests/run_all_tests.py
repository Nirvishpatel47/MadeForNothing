"""
Standalone Test Runner for MADE FOR NOTHING.
Usage:
    python tests/run_all_tests.py
    pytest
"""
import sys
import os
import subprocess

# Ensure Website directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def main():
    print("=" * 70)
    print("MADE FOR NOTHING — Automated Verification Suite")
    print("=" * 70)

    try:
        import pytest
        print("Launching pytest runner across all test modules...\n")
        exit_code = pytest.main([
            os.path.join(BASE_DIR, "tests"),
            "-v",
            "--tb=short"
        ])
        sys.exit(exit_code)
    except ImportError:
        print("[!] pytest not found in current environment.")
        print("    Running with python -m unittest discovery fallback...\n")
        import unittest
        loader = unittest.TestLoader()
        suite = loader.discover(start_dir=os.path.join(BASE_DIR, "tests"), pattern="test_*.py")
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
