"""Map chessboard squares to UR base-frame tool poses."""
from math import isfinite

from arm_methods.getPieceOffset import getPieceOffset


def calculatePosition(
    piece,
    main_checkboard_coord_start,
    main_checkboard_coord_end,
    initial_check,
    target_check,
    main_checkboard_coord_a1=None,
):
    """Return 6D UR poses for source and destination squares.

    With a1 supplied, calibration uses the measured centres of a8, h8 and a1;
    each square step interpolates over seven intervals along both board axes.
    The two-point a8/h1 convention remains for legacy callers.
    """
    start = [float(value) for value in main_checkboard_coord_start]
    end = [float(value) for value in main_checkboard_coord_end]
    side = [float(value) for value in main_checkboard_coord_a1] if main_checkboard_coord_a1 is not None else None
    if len(start) != 6 or len(end) != 6:
        raise ValueError("UR calibration poses must each contain six values.")
    if side is not None and len(side) != 6:
        raise ValueError("The a1 calibration pose must contain six values.")
    if not all(isfinite(value) for value in start + end + (side or [])):
        raise ValueError("UR calibration poses must contain finite values.")

    def pose_for(square):
        if len(square) != 2:
            raise ValueError("Chess square coordinates must be [row, column].")
        row, column = (int(square[0]), int(square[1]))
        if not (0 <= row < 8 and 0 <= column < 8):
            raise ValueError(f"Chess square outside board: {square!r}")

        # Board row 0/file a is the calibrated top-left image corner.
        if side is None:
            # Compatibility with the original axis-aligned two-point setup.
            x = start[0] + (end[0] - start[0]) * column / 7.0
            y = start[1] + (end[1] - start[1]) * row / 7.0
            z = start[2] + (end[2] - start[2]) * (row + column) / 14.0
        else:
            # Three measured square centres also support a rotated board.
            xyz = [start[i] + (end[i] - start[i]) * column / 7.0
                   + (side[i] - start[i]) * row / 7.0 for i in range(3)]
            x, y, z = xyz
        z -= getPieceOffset(piece)
        return [x, y, z, *start[3:6]]

    return pose_for(initial_check), pose_for(target_check)
