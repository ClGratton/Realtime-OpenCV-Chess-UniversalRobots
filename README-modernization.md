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

## Live camera display

On the PC, run `pwsh -ExecutionPolicy Bypass -File .\start_vision_dashboard.ps1`
from the repository directory and open `http://127.0.0.1:8765/`. Start the IP
Webcam server on the phone first. The current default stream is
`http://192.168.22.119:8080/video`; pass `-CameraUrl 'http://PHONE_IP:8080/video'`
if DHCP gives the phone another address. Install `requirements.txt` in Python
if those packages are not already present. Set `STOCKFISH_PATH` to an installed
Stockfish executable to display its suggested move.

The display offers original camera and perspective-corrected views, a live
board outline, changed squares, legal move candidates, and Stockfish analysis
for the displayed FEN. Choose the physical a8 corner before reading moves.
The perspective view is aligned by the board tracker, uses a rolling three
frame median to suppress isolated video noise, and gently enhances luminance
with CLAHE. Move detection still uses the unfiltered warped frames so the
visual treatment does not alter its decision thresholds.
In the perspective tab, buttons 1-4 reveal each cumulative stage: geometry,
geometry plus temporal median, geometry plus median and contrast, then the
complete diagnostic overlay. Selecting a stage changes only the presentation;
the backend keeps running its complete analysis on every frame.
Possible square changes remain visible as text for debugging; orange overlays
appear only once the change matches a stable legal move.
The move and FEN controls update this display's game state; they do not move
the robot. The dashboard never connects to the robot.

During a BOOX full-page refresh, tracking pauses and retries locating the
board every five seconds for up to one minute. A successful relock spends five
seconds rebuilding its visual reference while the screen settles. Broad screen
changes are suppressed instead of highlighted as chess moves. If a broad
change then remains still for two seconds, the display rebuilds its reference
and reminds the operator to verify the FEN. If the board is
still lost after one minute, stabilize the view and click `Riloca scacchiera`.
The browser video reconnects after a temporary dashboard server interruption.
