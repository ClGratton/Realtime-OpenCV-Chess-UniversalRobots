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
- Pauses after a refresh or a large viewpoint change and retries a relock every
  five seconds for up to one minute.
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

The robot is disabled by default. The ⚙ panel stores the controller IP and
the camera URL locally. For robot position teaching, switch the pendant from
Remote to Local/Manual, stop the program, hold Freedrive and guide the tool to
the centre of a8. Release Freedrive and press **Acquisisci a8** in the position
dialog. Repeat for h8, a1 and the capture tray, then save and return to Remote
for play. The dashboard reads `actual_TCP_pose` and `actual_TCP_speed` from
RTDE; it captures only a fresh, stationary pose while the controller reports
Local, a stopped program and a normal or reduced safety state. It never sends
Freedrive or jog commands. If hand guiding is inconvenient, use the pendant's
Move tab in Manual to reach the point before pressing Acquisisci.

The four taught points are stored in
`Visual Studio/program/robot_calibration.json`, bound to the controller IP and
serial. Values use metres and radians in the UR base frame. `chess_main.py`
refuses a robot control connection when calibration is missing, implausible or
bound to another controller, and reloads positions at the next turn if changed
during a game. The three measured board centres permit a board rotated in the
robot's XY plane. Check the actual workspace, tool orientation and travel
height before setting CHESS_ROBOT_ENABLED=1. Camera calibration does not
measure robot coordinates, and the board must remain fixed relative to the
robot until robot-to-board tracking is added.

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
board outline, changed squares, legal move candidates, turn, game reset, and
Stockfish analysis for the displayed FEN. Choose the physical a8 corner before
reading moves. The tracker checks the visible grid and corrects accumulated
perspective drift. After alignment, a selectable 1/3/5/7-frame temporal median
suppresses transient video noise, followed by adjustable CLAHE contrast. These
controls change both the displayed image and the image used to recognize moves;
changing either rebuilds the reference to avoid a false move.
In the perspective tab, buttons 1-4 reveal each cumulative stage: geometry,
geometry plus temporal median, geometry plus median and contrast, then the
complete diagnostic overlay. Selecting a stage changes only the presentation;
the backend keeps running its complete analysis on every frame.
Possible square changes remain visible as text for debugging; orange overlays
appear only once the change matches a stable legal move. Changes outside all
legal moves for the current player are excluded from move recognition, while
castling and en passant keep their extra affected squares.
The move and FEN controls update this display's game state; they do not move
the robot. The dashboard queries the UR Dashboard Server for remote mode,
robot mode, safety, program and serial, and checks whether the RTDE and script
ports are reachable. These are read-only checks; the display never sends a
motion, power, unlock or play command. Saved addresses and filter settings are
kept in `Visual Studio/program/dashboard_settings.json`.
Install the pinned official Universal Robots RTDE Python library from
`requirements.txt` to enable live TCP readings and the Acquisisci buttons.
In Manual/Local mode, use the pendant Freedrive control to teach the lowest
permitted gripper-tip position at a8, h8, a1 and the capture tray. Confirm on
the pendant that the active TCP is set at the gripper tip. The dashboard reads
the stopped TCP pose and active TCP offset without jogging the robot, then
saves both with the controller serial. Robot control refuses calibration if
the controller or TCP offset changes. Pick-and-place commands are checked
against the taught minimum TCP height before motion, including the return
home pose; all generated Cartesian waypoints stay above that limit.

During a BOOX full-page refresh, tracking pauses and retries locating the
board every five seconds for up to one minute. A successful relock spends five
seconds rebuilding its visual reference while the screen settles. Broad screen
changes are suppressed instead of highlighted as chess moves. If a broad
change then remains still for two seconds, the display rebuilds its reference
and reminds the operator to verify the FEN. If the board is
still lost after one minute, stabilize the view and click `Riloca scacchiera`.
The browser video reconnects after a temporary dashboard server interruption.
