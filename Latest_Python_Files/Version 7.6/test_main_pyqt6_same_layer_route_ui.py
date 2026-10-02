import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from main_pyqt6 import WindingApp


class SameLayerRouteUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = WindingApp()

    def tearDown(self):
        self.window.close()

    def test_route_selector_is_wide_enough_for_both_choices(self):
        self.assertGreaterEqual(self.window.input_fields["same_layer_route_style"].minimumWidth(), 220)

    def test_radii_gap_has_a_clear_default(self):
        self.assertEqual(self.window.input_fields["radii_gap"].text(), "0.20")

    def test_plot_view_preserves_expanded_route_radius(self):
        self.window.Fig_Para = SimpleNamespace(
            outer_radius=12.0,
            plot_margin=1.6,
            plot_zoom=1.0,
            plot_padding=0.01,
        )
        self.window.ax.set_xlim(-18.0, 18.0)
        self.window.ax.set_ylim(-18.0, 18.0)

        self.window.apply_plot_view()

        self.assertGreaterEqual(self.window.ax.get_xlim()[1], 18.0)
        self.assertGreaterEqual(self.window.ax.get_ylim()[1], 18.0)


if __name__ == "__main__":
    unittest.main()
