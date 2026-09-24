"""Configuration for the chess robot.

Robot poses and offsets use metres and radians, as required by URX.
Set CHESS_ROBOT_ENABLED=1 only when the robot is ready for remote motion.
"""
import os
import json
from pathlib import Path

_dashboard_settings_path = Path(__file__).with_name("dashboard_settings.json")
try:
    _dashboard_settings = json.loads(_dashboard_settings_path.read_text(encoding="utf-8"))
except (FileNotFoundError, ValueError):
    _dashboard_settings = {}

# IP Webcam on the current phone. DHCP may change this address; override it
# with CHESS_CAMERA_URL when the app shows a different URL.
camera_ip = os.getenv("CHESS_CAMERA_URL", _dashboard_settings.get("camera_url", "http://192.168.22.119:8080/video"))
robot_ip = os.getenv("UR_ROBOT_IP", _dashboard_settings.get("robot_ip", "192.168.17.168"))

# Remote robot movement is disabled until explicitly enabled by the operator.
robotExists = int(os.getenv("CHESS_ROBOT_ENABLED", "0"))
debug = int(os.getenv("CHESS_DEBUG", "0"))
time_limit = float(os.getenv("CHESS_ENGINE_TIME_LIMIT", "1.0"))

# Height differences relative to the tallest piece, in metres.
rook_offset = 0.010
knight_offset = 0.010
bishop_offset = 0.010
queen_offset = 0.005
king_offset = 0.0
pawn_offset = 0.020

eaten_position = [0.0, 0.0, 0.0]  # Calibrate tray XYZ in robot base frame (metres).
checkboard_coord_start = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # top-left square pose
checkboard_coord_end = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]    # bottom-right square pose

travel_offset = 0.050
arm_acceleration = 0.1
arm_velocity = 0.07
home_position = [0.2, -0.2, 0.2, -1.0, -1.57, 0.0]
