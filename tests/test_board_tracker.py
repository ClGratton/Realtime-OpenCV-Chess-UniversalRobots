"""Synthetic camera views exercise live registration and fail-safe relock."""
import unittest
from unittest.mock import patch

import cv2
import chess
import numpy as np

from image_methods.board_tracker import BoardTracker, BoardTrackingError
from image_methods.detect_points import orient_corners
from image_methods.find_position_black import infer_human_move


CORNERS = np.float32([[80, 80], [719, 80], [719, 719], [80, 719]])


def board_image():
    image = np.full((800, 800, 3), 110, dtype=np.uint8)
    for row in range(8):
        for column in range(8):
            shade = 220 if (row + column) % 2 else 35
            top = (80 + column * 80, 80 + row * 80)
            bottom = (top[0] + 80, top[1] + 80)
            cv2.rectangle(image, top, bottom, (shade, shade, shade), -1)
            # Sparse distinctive texture imitates stable board markings.
            if (row * 8 + column) % 3 == 0:
                cv2.circle(image, (top[0] + 26, top[1] + 22), 3, (110, 90, 70), -1)
    for column in (0, 1, 2, 3, 4, 5, 6, 7):
        cv2.circle(image, (120 + column * 80, 600), 14, (70, 100, 160), -1)
    return image


def shifted(image, x, y):
    return cv2.warpAffine(image, np.float32([[1, 0, x], [0, 1, y]]), (800, 800))


class BoardTrackerTests(unittest.TestCase):
    def setUp(self):
        self.original = board_image()
        self.tracker = BoardTracker(detection_interval=100)
        self.tracker.initialize(self.original, CORNERS)

    def test_a8_identity_survives_rotated_phone_view(self):
        corners_from_detector = np.roll(CORNERS, 2, axis=0)
        np.testing.assert_array_equal(orient_corners(corners_from_detector, 2), CORNERS)

    @patch("image_methods.board_tracker.detect_board_corners", return_value=None)
    def test_phone_moves_gradually_and_view_stays_registered(self, _):
        reference = self.tracker.warp_current(self.original)
        for x, y in ((10, 7), (20, 13), (30, 19)):
            warped = self.tracker.update(shifted(self.original, x, y))
        self.assertLess(np.median(cv2.absdiff(
            reference, warped,
        )), 20)
        np.testing.assert_allclose(self.tracker.corners, CORNERS + [30, 19], atol=3)

    @patch("image_methods.board_tracker.detect_board_corners", return_value=None)
    def test_phone_rotates_slightly_and_squares_remain_aligned(self, _):
        matrix = cv2.getRotationMatrix2D((400, 400), 5, 1)
        rotated = cv2.warpAffine(self.original, matrix, (800, 800))
        view = self.tracker.update(rotated)
        expected = cv2.transform(CORNERS.reshape(-1, 1, 2), matrix).reshape(4, 2)
        np.testing.assert_allclose(self.tracker.corners, expected, atol=3)
        self.assertEqual(view.shape, self.original.shape)

    @patch("image_methods.board_tracker.detect_board_corners", return_value=None)
    def test_move_is_recognized_while_phone_moves(self, _):
        before_view = self.tracker.warp_current(self.original)
        moved_piece = self.original.copy()
        cv2.rectangle(moved_piece, (401, 561), (479, 639), (35, 35, 35), -1)
        cv2.circle(moved_piece, (440, 440), 14, (70, 100, 160), -1)
        after_view = self.tracker.update(shifted(moved_piece, 10, 6))
        boxes = np.array([
            [[column * 100, row * 100, (column + 1) * 100, (row + 1) * 100]
             for column in range(8)]
            for row in range(8)
        ])
        candidates = infer_human_move(before_view, after_view, boxes, chess.Board())
        self.assertEqual([move.uci() for move in candidates], ["e2e4"])

    @patch("image_methods.board_tracker.detect_board_corners", return_value=None)
    def test_sudden_jump_does_not_change_lock(self, _):
        with self.assertRaises(BoardTrackingError):
            self.tracker.update(shifted(self.original, 180, 0))
        np.testing.assert_array_equal(self.tracker.corners, CORNERS)

    @patch("image_methods.board_tracker.detect_board_corners", return_value=None)
    def test_board_disappears_and_can_be_relocked(self, _):
        with self.assertRaises(BoardTrackingError):
            self.tracker.update(np.full_like(self.original, 90))
        self.tracker.initialize(shifted(self.original, 50, 0), CORNERS + [50, 0])
        np.testing.assert_allclose(self.tracker.corners, CORNERS + [50, 0])

    @patch("image_methods.board_tracker.detect_board_corners")
    def test_detector_disagreement_stops_tracking(self, detector):
        self.tracker.frames_since_detection = 100
        detector.return_value = CORNERS + [100, 0]
        with self.assertRaises(BoardTrackingError):
            self.tracker.update(shifted(self.original, 10, 0))

    @patch("image_methods.board_tracker.detect_board_corners", return_value=CORNERS)
    def test_whole_board_appearance_change_is_rejected(self, _):
        inverted = cv2.bitwise_not(self.original)
        with self.assertRaises(BoardTrackingError):
            self.tracker.update(inverted)
        np.testing.assert_array_equal(self.tracker.corners, CORNERS)


if __name__ == "__main__":
    unittest.main()
