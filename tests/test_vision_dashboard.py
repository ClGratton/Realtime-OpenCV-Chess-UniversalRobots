"""Regression checks for e-ink refresh recovery in the live display."""
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from image_methods.board_tracker import BoardTrackingError
from image_methods.find_position_black import MoveDetectionError
from vision_dashboard import BoardViewFilter, VisionDashboard


CORNERS = np.float32([[80, 80], [719, 80], [719, 719], [80, 719]])


def patterned_board():
    image = np.full((800, 800, 3), 80, dtype=np.uint8)
    for row in range(8):
        for col in range(8):
            shade = 205 if (row + col) % 2 else 45
            cv2.rectangle(image, (80 + col * 80, 80 + row * 80),
                          (159 + col * 80, 159 + row * 80), (shade,) * 3, -1)
    return image


class VisionDashboardTests(unittest.TestCase):
    def test_display_filter_removes_one_frame_video_noise(self):
        steady = np.full((80, 80, 3), 80, dtype=np.uint8)
        noisy = steady.copy()
        noisy[20:30, 20:30] = 200
        video_filter = BoardViewFilter()
        video_filter.process(steady)
        video_filter.process(noisy)
        filtered = video_filter.process(steady)
        expected = BoardViewFilter().process(steady)
        np.testing.assert_array_equal(filtered, expected)

    def test_display_filter_updates_after_two_changed_frames(self):
        old = np.full((80, 80, 3), 80, dtype=np.uint8)
        new = old.copy()
        new[20:30, 20:30] = 200
        video_filter = BoardViewFilter()
        video_filter.process(old)
        video_filter.process(old)
        video_filter.process(new)
        filtered = video_filter.process(new)
        expected = BoardViewFilter().process(new)
        np.testing.assert_array_equal(filtered, expected)

    @patch("vision_dashboard.detect_board_corners", return_value=CORNERS)
    def test_refresh_recovers_on_next_five_second_attempt(self, detector):
        image = patterned_board()
        dashboard = VisionDashboard("test")
        with dashboard.lock:
            dashboard._process_frame(image, image)
            self.assertTrue(dashboard.snapshot()["tracked"])
            with patch.object(dashboard.tracker, "update", side_effect=BoardTrackingError("refresh")):
                dashboard._process_frame(image, image)
            self.assertTrue(dashboard.snapshot()["recovering"])
            attempts = detector.call_count
            dashboard._process_frame(image, image)
            self.assertEqual(detector.call_count, attempts)
            dashboard.next_recovery_at = time.monotonic() - 0.1
            dashboard._process_frame(image, image)
            self.assertEqual(detector.call_count, attempts + 1)
            self.assertTrue(dashboard.snapshot()["tracked"])

    def test_full_screen_refresh_is_not_shown_as_changed_squares(self):
        dashboard = VisionDashboard("test")
        dashboard.orientation_confirmed = True
        dashboard.baseline = np.zeros((800, 800, 3), dtype=np.uint8)
        dashboard._analyze_move(np.full((800, 800, 3), 255, dtype=np.uint8))
        self.assertEqual(dashboard.changed, [])
        self.assertIsNone(dashboard.candidate)
        self.assertIn("Molte caselle", dashboard.detail)

    def test_unmatched_changes_are_not_painted_as_a_move(self):
        dashboard = VisionDashboard("test")
        dashboard.orientation_confirmed = True
        dashboard.baseline = np.zeros((800, 800, 3), dtype=np.uint8)
        after = dashboard.baseline.copy()
        after[720:780, 620:680] = 200
        after[720:780, 720:780] = 200
        with patch("vision_dashboard.infer_human_move", side_effect=MoveDetectionError("not legal")):
            dashboard._analyze_move(after)
        self.assertEqual(len(dashboard.changed), 2)
        self.assertEqual(dashboard.highlighted, [])

    def test_recovery_stops_after_sixty_seconds(self):
        image = patterned_board()
        dashboard = VisionDashboard("test")
        dashboard.tracker.initialize(image, CORNERS)
        dashboard.tracking_paused = True
        dashboard.recovery_started = time.monotonic() - 61
        dashboard.next_recovery_at = time.monotonic() - 1
        with dashboard.lock:
            dashboard._process_frame(image, image)
        self.assertEqual(dashboard.status, "Rilocca la scacchiera")
        self.assertFalse(dashboard.snapshot()["recovering"])


if __name__ == "__main__":
    unittest.main()
