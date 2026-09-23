"""Map chessboard squares to UR base-frame tool poses."""
from math import isfinite

from arm_methods.getPieceOffset import getPieceOffset


def calculatePosition(
    piece,
    main_checkboard_coord_start,
    main_checkboard_coord_end,
    initial_check,
    target_check,
):
    """Return 6D UR poses for source and destination squares.

    Calibration poses are the centres of a8 and h1 (top-left and bottom-right
    in the camera's canonical board view). Each square step interpolates over
    the seven intervals between those two measured poses.
    """
    start = [float(value) for value in main_checkboard_coord_start]
    end = [float(value) for value in main_checkboard_coord_end]
    if len(start) != 6 or len(end) != 6:
        raise ValueError("UR calibration poses must each contain six values.")
    if not all(isfinite(value) for value in start + end):
        raise ValueError("UR calibration poses must contain finite values.")

    def pose_for(square):
        if len(square) != 2:
            raise ValueError("Chess square coordinates must be [row, column].")
        row, column = (int(square[0]), int(square[1]))
        if not (0 <= row < 8 and 0 <= column < 8):
            raise ValueError(f"Chess square outside board: {square!r}")

        # Board row 0/file a is the calibrated top-left image corner.
        x = start[0] + (end[0] - start[0]) * column / 7.0
        y = start[1] + (end[1] - start[1]) * row / 7.0
        z = start[2] + (end[2] - start[2]) * (row + column) / 14.0
        z -= getPieceOffset(piece)
        return [x, y, z, *start[3:6]]

    return pose_for(initial_check), pose_for(target_check)
