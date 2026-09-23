"""Infer a human move from square changes and python-chess legal moves.

The camera does not classify piece types. It measures which squares changed;
the tracked board supplies legal piece identity and move rules.
"""
import chess
import cv2
import numpy as np


class MoveDetectionError(ValueError):
    """The image does not identify one legal physical move."""


def affected_squares(board, move):
    """Squares whose images should change after a legal standard-chess move."""
    if board.chess960:
        raise MoveDetectionError("Chess960 is not supported by this board mapper.")

    changed = {move.from_square, move.to_square}
    if board.is_en_passant(move):
        captured = move.to_square - 8 if board.turn == chess.WHITE else move.to_square + 8
        changed.add(captured)
    if board.is_castling(move):
        rank = 0 if board.turn == chess.WHITE else 7
        if board.is_kingside_castling(move):
            changed.update((chess.square(7, rank), chess.square(5, rank)))
        else:
            changed.update((chess.square(0, rank), chess.square(3, rank)))
    return frozenset(changed)


def changed_squares_from_images(before, after, boxes):
    """Return changed chess squares in a stable, already warped camera view."""
    if before is None or after is None or before.shape != after.shape:
        raise MoveDetectionError("Camera frames are missing or have different sizes.")
    if np.asarray(boxes).shape != (8, 8, 4):
        raise MoveDetectionError("The chessboard box calibration is invalid.")

    def gray(image):
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    earlier = cv2.GaussianBlur(gray(before), (5, 5), 0)
    later = cv2.GaussianBlur(gray(after), (5, 5), 0)
    difference = cv2.absdiff(earlier, later)
    scores = np.zeros((8, 8), dtype=np.float32)

    for row in range(8):
        for column in range(8):
            left, top, right, bottom = map(int, boxes[row, column])
            width, height = right - left, bottom - top
            if width < 12 or height < 12:
                raise MoveDetectionError("A calibrated square is too small.")
            margin_x, margin_y = max(2, width // 8), max(2, height // 8)
            interior = difference[
                top + margin_y:bottom - margin_y,
                left + margin_x:right - margin_x,
            ]
            if interior.size == 0:
                raise MoveDetectionError("A calibrated square lies outside the image.")
            scores[row, column] = float(np.mean(interior > 18))

    background = float(np.median(scores))
    if background > 0.08:
        raise MoveDetectionError(
            "Most squares changed: steady the phone, lighting and hands, then retry."
        )
    threshold = max(0.035, background + 0.025)
    changed = {
        chess.square(column, 7 - row)
        for row in range(8)
        for column in range(8)
        if scores[row, column] >= threshold
    }
    if not 2 <= len(changed) <= 4:
        names = ", ".join(sorted(chess.square_name(square) for square in changed))
        raise MoveDetectionError(
            f"Expected 2-4 changed squares; observed {len(changed)} ({names})."
        )
    return frozenset(changed)


def infer_human_move(before, after, boxes, board):
    """Return legal move candidates matching exactly the observed changed squares.

    Ordinary moves have one candidate. Promotion choices share the same visual
    signature and must be selected by the player.
    """
    observed = changed_squares_from_images(before, after, boxes)
    matches = [
        move for move in board.legal_moves
        if affected_squares(board, move) == observed
    ]
    if not matches:
        names = ", ".join(sorted(chess.square_name(square) for square in observed))
        raise MoveDetectionError(
            f"Square changes ({names}) do not match a legal move. Restore the board."
        )
    endpoints = {(move.from_square, move.to_square) for move in matches}
    if len(endpoints) != 1:
        raise MoveDetectionError("The image matches multiple legal moves.")
    if len(matches) > 1 and not all(move.promotion for move in matches):
        raise MoveDetectionError("The move is ambiguous in the image.")
    return matches
