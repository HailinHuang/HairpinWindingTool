"""Short regression form of the non-rendering stability soak."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from stability_soak import run_soak


class StabilitySoakTests(unittest.TestCase):
    def test_repeated_calculation_publication_and_shutdown(self):
        result = run_soak(10)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["unique_published_states"], 10)
        self.assertEqual(result["active_threads_after_close"], 0)


if __name__ == "__main__":
    unittest.main()
