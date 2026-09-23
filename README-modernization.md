# Realtime OpenCV Chess — recognition and robot motion update

## Changes

- Re-enabled the AI piece-transfer call and fixed the captured-square check:
  fen2board stores empty squares as the string "1".
- Fixed capture position planning and prevent unconfigured tray coordinates
  from being sent to an enabled robot.
- Replaced the hard-coded Stockfish 16 Windows path with STOCKFISH_PATH or a
  stockfish executable found on PATH.
- Corrected UR pose interpolation so it does not mutate calibration arrays,
  uses independent board axes, and preserves all six pose values.
- Uses blocking URX Cartesian movel calls, including for the configured home
  pose, and copies poses before adding travel height. Distances and piece
  offsets are in metres.
- Added automatic image calibration when OpenCV can see all 49 internal
  checkerboard intersections; otherwise manual corner selection remains.
- Tracks the board on each live camera frame using optical flow, with periodic
  fresh chessboard detection to correct drift. Each move's before and after
  images are warped using their own current board positions.
- Pauses and requires an explicit relock when the board leaves view, jumps,
  changes appearance across many squares, or the two locators disagree.
- Infers the human move by matching changed squares against every legal move
  in python-chess. Castling needs all four squares, en passant all three, and
  promotions require the player to choose the piece. The saved game now keeps
  full FEN so special-move rights survive a restart.

## Recognition limits

The camera tracks changed squares, not piece identities. It cannot confirm
that a player physically replaced a pawn with the selected promotion piece,
or detect a wrong piece substituted on a square. The phone may move gradually
while the board remains visible. A sudden viewpoint jump pauses play; after
restoring the physical position shown in the game, press `r` to relock. At
initial lock or relock, choose which numbered corner is the physical `a8`;
this resolves board orientation even if the phone starts from another side.
The pixel and motion thresholds need validation on the actual board, lighting,
phone and chess pieces. An unmarked, symmetric checkerboard cannot determine
absolute orientation after a large camera rotation without that selection.

## Setup and calibration

Install the Python packages with pip install -r requirements.txt, plus the
Robotiq gripper setup appropriate to the controller. Install the official
Stockfish release separately and set STOCKFISH_PATH to its executable, or add
it to PATH.

The robot is disabled by default. Configure UR_ROBOT_IP, both six-value board
calibration poses, the tray XYZ pose, and CHESS_ROBOT_ENABLED=1 only after
checking the coordinate frame and clearances. Image corner detection calibrates
the camera view; it does not infer robot base-frame coordinates. Two taught UR
poses are still required for image-to-robot motion. The chessboard must stay
fixed relative to the robot until board-to-robot tracking is added; live
camera tracking alone does not update robot coordinates.

This update targets the repository's Universal Robots + Robotiq hardware and
uses its existing Python-URX interface. It is not a Dobot driver replacement.
