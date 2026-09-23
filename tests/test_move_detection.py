"""End-to-end checks from changed camera squares to legal chess moves."""
import unittest

import chess
import cv2
import numpy as np

from image_methods.find_position_black import (
    MoveDetectionError,
    affected_squares,
    infer_human_move,
)


def board_boxes():
    return np.array(
        [
            [[column * 100, row * 100, (column + 1) * 100, (row + 1) * 100]
             for column in range(8)]
            for row in range(8)
        ],
        dtype=np.int32,
    )


def frames_with_changes(squares):
    before = np.zeros((800, 800, 3), dtype=np.uint8)
    after = before.copy()
    for square in squares:
        column = chess.square_file(square)
        row = 7 - chess.square_rank(square)
        center = (column * 100 + 50, row * 100 + 50)
        cv2.circle(after, center, 20, (200, 200, 200), -1)
    return before, after


class MoveDetectionTests(unittest.TestCase):
    def assert_detected(self, board, uci):
        original_fen = board.fen()
        move = chess.Move.from_uci(uci)
        self.assertIn(move, board.legal_moves)
        before, after = frames_with_changes(affected_squares(board, move))
        detected = infer_human_move(before, after, board_boxes(), board)
        self.assertIn(move, detected)
        self.assertEqual(board.fen(), original_fen)
        return detected

    def test_ordinary_move(self):
        self.assertEqual(len(self.assert_detected(chess.Board(), "e2e4")), 1)

    def test_capture(self):
        board = chess.Board("4k3/8/8/8/8/8/4p3/4K3 w - - 0 1")
        self.assertEqual(len(self.assert_detected(board, "e1e2")), 1)

    def test_castling_both_sides(self):
        board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1")
        self.assertEqual(len(self.assert_detected(board, "e8g8")), 1)
        self.assertEqual(len(self.assert_detected(board, "e8c8")), 1)

    def test_incomplete_castling_is_rejected(self):
        board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1")
        before, after = frames_with_changes({chess.E8, chess.G8})
        with self.assertRaises(MoveDetectionError):
            infer_human_move(before, after, board_boxes(), board)

    def test_en_passant(self):
        board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
        self.assertEqual(len(self.assert_detected(board, "e5d6")), 1)

    def test_promotion_requires_piece_selection(self):
        board = chess.Board("4k3/6P1/8/8/8/8/8/4K3 w - - 0 1")
        candidates = self.assert_detected(board, "g7g8q")
        self.assertEqual(
            {move.promotion for move in candidates},
            {chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT},
        )

    def test_extra_change_is_rejected(self):
        board = chess.Board()
        move = chess.Move.from_uci("e2e4")
        changed = set(affected_squares(board, move))
        changed.add(chess.H7)
        before, after = frames_with_changes(changed)
        with self.assertRaises(MoveDetectionError):
            infer_human_move(before, after, board_boxes(), board)

    def test_camera_movement_is_rejected(self):
        before = np.zeros((800, 800, 3), dtype=np.uint8)
        after = np.full_like(before, 100)
        with self.assertRaises(MoveDetectionError):
            infer_human_move(before, after, board_boxes(), chess.Board())


if __name__ == "__main__":
    unittest.main()
