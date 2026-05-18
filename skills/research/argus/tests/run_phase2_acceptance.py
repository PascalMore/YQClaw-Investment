#!/usr/bin/env python3
# skills/research/argus/tests/run_phase2_acceptance.py
"""Run Argus Phase 2 acceptance tests with the standard library."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, '/home/pascal/.openclaw/workspace-yquant')


if __name__ == '__main__':
    test_dir = Path(__file__).parent
    suite = unittest.defaultTestLoader.discover(str(test_dir), pattern='test_argus_phase2_acceptance.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
