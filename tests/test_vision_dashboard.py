"""Regression checks for e-ink refresh recovery in the live display."""
import time
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import cv2
import chess
import numpy as np

from image_methods.board_tracker import BoardTrackingError
from image_methods.find_position_black import MoveDetectionError
from arm_methods.calculatePosition import calculatePosition
from robot_calibration import validate_calibration, require_calibration_for_robot
from vision_dashboard import BoardViewFilter, GRID_TARGET, VisionDashboard, detect_visible_grid, legal_move_squares


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
    def test_freedrive_teaching_captures_stopped_tcp_without_jog_command(self):
        dashboard = VisionDashboard("test")
        dashboard.robot_diagnostics = {
            "connection":"Controller raggiungibile", "checked_at":time.monotonic(),
            "remote":"true", "robot_mode":"Robotmode: RUNNING",
            "safety":"Safetystatus: REDUCED", "program":"STOPPED demo.urp",
            "serial":"20235300765",
        }
        dashboard.robot_speed = [0.0] * 6
        dashboard.tcp_offset = [0.02, 0, 0.22, 0, 0, 0]
        dashboard.robot_pose_at = time.monotonic()
        dashboard.pose_stationary_since = time.monotonic() - 1
        dashboard.robot_pose = [0.2, -0.3, 0.15, 0, 3.14, 0]
        with self.assertRaisesRegex(ValueError, "Locale/Manuale"):
            dashboard.command({"action":"capture_pose", "slot":"a8", "tip_confirmed":True})
        dashboard.robot_diagnostics["remote"] = "false"
        with self.assertRaisesRegex(ValueError, "Conferma"):
            dashboard.command({"action":"capture_pose", "slot":"a8"})
        for slot, pose in (
            ("a8", [0.2, -0.3, 0.15, 0, 3.14, 0]),
            ("h8", [0.2, 0.0, 0.15, 0, 3.14, 0]),
            ("a1", [0.5, -0.3, 0.15, 0, 3.14, 0]),
            ("tray", [0.35, 0.2, 0.2, 0, 3.14, 0]),
        ):
            dashboard.robot_pose = pose
            dashboard.robot_pose_at = time.monotonic()
            dashboard.command({"action":"capture_pose", "slot":slot, "tip_confirmed":True})
        with patch("vision_dashboard.save_calibration", side_effect=validate_calibration) as save:
            dashboard.command({"action":"calibration"})
        saved = save.call_args.args[0]
        self.assertEqual(saved["serial"], "20235300765")
        self.assertEqual(saved["robot_ip"], dashboard.robot_ip)
        self.assertEqual(saved["tray"], [0.35, 0.2, 0.2])
        self.assertEqual(saved["tcp_offset"], [0.02, 0, 0.22, 0, 0, 0])
        self.assertFalse(dashboard.draft_dirty)

    def test_calibration_refuses_a_different_robot_serial(self):
        saved = {"robot_ip":"192.168.17.168", "serial":"20235300765"}
        with patch("robot_calibration.load_calibration", return_value=saved), \
             patch("robot_calibration.read_robot_serial", return_value="other"):
            with self.assertRaisesRegex(RuntimeError, "altro controller"):
                require_calibration_for_robot("192.168.17.168")

    def test_calibration_refuses_changed_tcp(self):
        saved = {"robot_ip":"192.168.17.168", "serial":"20235300765",
                 "tcp_offset":[0.02, 0, 0.22, 0, 0, 0]}
        with patch("robot_calibration.load_calibration", return_value=saved), \
             patch("robot_calibration.read_robot_serial", return_value="20235300765"), \
             patch("robot_calibration.read_robot_tcp_offset", return_value=[0, 0, 0, 0, 0, 0]):
            with self.assertRaisesRegex(RuntimeError, "TCP attivo"):
                require_calibration_for_robot("192.168.17.168")

    def test_live_filter_settings_survive_dashboard_restart(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch("vision_dashboard.SETTINGS_FILE", Path(directory) / "settings.json"):
            dashboard = VisionDashboard("test")
            dashboard.command({"action":"view_settings", "window":5, "contrast":60})
            dashboard.orientation = 3
            dashboard.orientation_confirmed = True
            dashboard._save_settings()
            restarted = VisionDashboard("test")
        self.assertEqual(restarted.snapshot()["view_window"], 5)
        self.assertEqual(restarted.snapshot()["view_contrast"], 60)
        self.assertTrue(restarted.snapshot()["orientation_confirmed"])

    def test_filter_settings_change_images_used_by_move_detection(self):
        dashboard = VisionDashboard("test")
        dashboard.tracker.corners = GRID_TARGET.copy()
        board = patterned_board()
        dashboard.view_filter.configure(1, 0)
        with patch.object(dashboard.tracker, "update", return_value=board), \
             patch.object(dashboard, "_correct_warp", return_value=board), \
             patch.object(dashboard, "_analyze_move") as analyze:
            with dashboard.lock:
                dashboard._process_frame(board, board)
            np.testing.assert_array_equal(analyze.call_args.args[0], board)
            dashboard.view_filter.configure(1, 100)
            with dashboard.lock:
                dashboard._process_frame(board, board)
            np.testing.assert_array_equal(analyze.call_args.args[0], dashboard.latest_board_view)
            self.assertGreater(float(np.mean(cv2.absdiff(dashboard.latest_board_view, board))), 1)

    def test_three_point_calibration_maps_a_rotated_board(self):
        a8 = [0.2, -0.3, 0.15, 0, 3.14, 0]
        h8 = [0.2, 0.0, 0.15, 0, 3.14, 0]
        a1 = [0.5, -0.3, 0.15, 0, 3.14, 0]
        source, target = calculatePosition("K", a8, h8, [0, 0], [7, 7], a1)
        self.assertAlmostEqual(source[0], a8[0])
        self.assertAlmostEqual(source[1], a8[1])
        self.assertAlmostEqual(target[0], 0.5)
        self.assertAlmostEqual(target[1], 0.0)

    def test_unmeasured_robot_positions_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_calibration({"a8":[0]*6, "h8":[0]*6, "a1":[0]*6, "tray":[0]*3})
        dashboard = VisionDashboard("test")
        dashboard.calibration = None
        with self.assertRaisesRegex(ValueError, "non calibrate"):
            dashboard.command({"action":"connect_robot"})

    def test_grid_feedback_corrects_a_skewed_warp(self):
        misplaced = np.float32([[22, 8], [775, 48], [765, 775], [24, 745]])
        transform = cv2.getPerspectiveTransform(CORNERS, misplaced)
        camera = cv2.warpPerspective(patterned_board(), transform, (800, 800))
        dashboard = VisionDashboard("test")
        dashboard.frame_number = 1
        raw_warp = dashboard.tracker.initialize(camera, GRID_TARGET)
        corrected = dashboard._correct_warp(camera, raw_warp)
        found = detect_visible_grid(corrected)
        self.assertIsNotNone(found)
        self.assertGreater(dashboard.grid_error_px, 20)
        self.assertLess(float(np.max(np.linalg.norm(found - GRID_TARGET, axis=1))), 3)

    def test_display_filter_removes_one_frame_video_noise(self):
        steady = np.full((80, 80, 3), 80, dtype=np.uint8)
        noisy = steady.copy()
        noisy[20:30, 20:30] = 200
        video_filter = BoardViewFilter()
        video_filter.process(steady)
        video_filter.process(noisy)
        median, filtered = video_filter.process(steady)
        expected_median, expected = BoardViewFilter().process(steady)
        np.testing.assert_array_equal(median, expected_median)
        np.testing.assert_array_equal(filtered, expected)

    def test_display_filter_updates_after_two_changed_frames(self):
        old = np.full((80, 80, 3), 80, dtype=np.uint8)
        new = old.copy()
        new[20:30, 20:30] = 200
        video_filter = BoardViewFilter()
        video_filter.process(old)
        video_filter.process(old)
        video_filter.process(new)
        median, filtered = video_filter.process(new)
        expected_median, expected = BoardViewFilter().process(new)
        np.testing.assert_array_equal(median, expected_median)
        np.testing.assert_array_equal(filtered, expected)

    @patch("vision_dashboard.detect_visible_grid", return_value=None)
    @patch("vision_dashboard.detect_board_corners", return_value=CORNERS)
    def test_refresh_recovers_on_next_five_second_attempt(self, detector, _grid):
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

    def test_stable_full_screen_change_rebuilds_visual_reference(self):
        dashboard = VisionDashboard("test")
        dashboard.orientation_confirmed = True
        dashboard.baseline = np.zeros((800, 800, 3), dtype=np.uint8)
        changed = np.full((800, 800, 3), 200, dtype=np.uint8)
        with patch("vision_dashboard.time.monotonic", side_effect=[100.0, 103.0]):
            dashboard._analyze_move(changed)
            self.assertFalse(dashboard.reference_warning)
            dashboard._analyze_move(changed)
        np.testing.assert_array_equal(dashboard.baseline, changed)
        self.assertTrue(dashboard.reference_warning)
        self.assertEqual(dashboard.changed, [])

    def test_unstable_full_screen_change_does_not_rebuild_reference(self):
        dashboard = VisionDashboard("test")
        dashboard.orientation_confirmed = True
        dashboard.baseline = np.zeros((800, 800, 3), dtype=np.uint8)
        with patch("vision_dashboard.time.monotonic", side_effect=[100.0, 103.0]):
            dashboard._analyze_move(np.full((800, 800, 3), 120, dtype=np.uint8))
            dashboard._analyze_move(np.full((800, 800, 3), 255, dtype=np.uint8))
        self.assertFalse(dashboard.reference_warning)
        self.assertEqual(int(dashboard.baseline.max()), 0)

    def test_unmatched_changes_are_not_painted_as_a_move(self):
        dashboard = VisionDashboard("test")
        dashboard.orientation_confirmed = True
        dashboard.board.turn = chess.BLACK
        dashboard.baseline = np.zeros((800, 800, 3), dtype=np.uint8)
        after = dashboard.baseline.copy()
        after[120:180, 20:80] = 200
        after[120:180, 120:180] = 200
        with patch("vision_dashboard.infer_human_move", side_effect=MoveDetectionError("not legal")):
            dashboard._analyze_move(after)
        self.assertEqual(len(dashboard.changed), 2)
        self.assertEqual(dashboard.highlighted, [])

    def test_irrelevant_ghost_square_does_not_block_a_legal_move(self):
        dashboard = VisionDashboard("test")
        dashboard.orientation_confirmed = True
        dashboard.board.turn = chess.BLACK
        dashboard.baseline = np.zeros((800, 800, 3), dtype=np.uint8)
        after = dashboard.baseline.copy()
        after[120:180, 420:480] = 200  # e7
        after[320:380, 420:480] = 200  # e5
        after[720:780, 720:780] = 200  # h1 ghost, illegal for Black
        with patch("vision_dashboard.infer_human_move", return_value=[chess.Move.from_uci("e7e5")]) as infer:
            for _ in range(5):
                dashboard._analyze_move(after)
        self.assertEqual([chess.square_name(s) for s in dashboard.changed], ["e7", "e5"])
        self.assertEqual(dashboard.candidate.uci(), "e7e5")
        self.assertEqual(int(infer.call_args.args[1][750, 750, 0]), 0)

    def test_castling_rook_squares_remain_relevant(self):
        board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
        squares = legal_move_squares(board)
        self.assertTrue({chess.H1, chess.F1, chess.A1, chess.D1}.issubset(squares))

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
