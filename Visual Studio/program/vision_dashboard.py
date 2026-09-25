"""Browser-based live chess camera diagnostics. Never connects to the robot.

Run with ``python vision_dashboard.py`` and open http://127.0.0.1:8765/.
The camera and board views come from the same captured frame. The suggested
move is Stockfish analysis of the displayed FEN, not a robot command.
"""

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
os.environ.setdefault("OPENCV_FFMPEG_LOGLEVEL", "16")
from pathlib import Path
import shutil
import socket
import threading
import time
from urllib.parse import urlsplit

import chess
import chess.engine
import cv2
import numpy as np
try:
    import rtde.rtde as ur_rtde
except ImportError:
    ur_rtde = None

from config import camera_ip, robot_ip
from image_methods.board_tracker import BoardTracker, BoardTrackingError
from image_methods.detect_points import _ordered_corners, detect_board_corners, orient_corners
from image_methods.find_position_black import MoveDetectionError, infer_human_move
from robot_calibration import load_calibration, save_calibration


ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = ROOT / "dashboard_settings.json"
SIZE = 800
GRID_TARGET = np.float32([[0, 0], [SIZE - 1, 0], [SIZE - 1, SIZE - 1], [0, SIZE - 1]])
CENTRAL_GRID = np.float32(
    [[column * 100, row * 100] for row in (3, 4, 5) for column in (3, 4, 5)]
)
BOXES = np.array(
    [[[col * 100, row * 100, (col + 1) * 100, (row + 1) * 100]
      for col in range(8)] for row in range(8)], dtype=np.int32,
)


def stockfish_path():
    choices = (
        os.getenv("STOCKFISH_PATH"),
        shutil.which("stockfish"),
        shutil.which("stockfish.exe"),
        str(ROOT.parents[2] / ".deps" / "bin" / "stockfish.exe"),
    )
    return next((str(path) for path in choices if path and Path(path).is_file()), None)


def changed_square_scores(before, after):
    """The same central-square threshold used by move detection, for display."""
    gray_before = cv2.GaussianBlur(cv2.cvtColor(before, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    gray_after = cv2.GaussianBlur(cv2.cvtColor(after, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    delta = cv2.absdiff(gray_before, gray_after)
    scores = np.zeros((8, 8), dtype=np.float32)
    for row in range(8):
        for col in range(8):
            tile = delta[row * 100 + 12:(row + 1) * 100 - 12,
                         col * 100 + 12:(col + 1) * 100 - 12]
            scores[row, col] = float(np.mean(tile > 18))
    background = float(np.median(scores))
    threshold = max(0.035, background + 0.025)
    changed = [chess.square(col, 7 - row) for row in range(8)
               for col in range(8) if scores[row, col] >= threshold]
    return scores, background, changed


def legal_move_squares(board):
    """Squares that can legitimately change on this turn, including special moves."""
    squares = set()
    for move in board.legal_moves:
        squares.update((move.from_square, move.to_square))
        if board.is_castling(move):
            rank = chess.square_rank(move.from_square)
            if chess.square_file(move.to_square) == 6:
                squares.update((chess.square(7, rank), chess.square(5, rank)))
            else:
                squares.update((chess.square(0, rank), chess.square(3, rank)))
        if board.is_en_passant(move):
            squares.add(move.to_square - 8 if board.turn else move.to_square + 8)
    return squares


def draw_arrow(image, move, color):
    if not move:
        return
    a = (chess.square_file(move.from_square) * 100 + 50,
         (7 - chess.square_rank(move.from_square)) * 100 + 50)
    b = (chess.square_file(move.to_square) * 100 + 50,
         (7 - chess.square_rank(move.to_square)) * 100 + 50)
    cv2.arrowedLine(image, a, b, color, 7, cv2.LINE_AA, tipLength=0.2)


def detect_visible_grid(warped):
    """Find the outer board from all 49 corners, or the empty central 3x3."""
    outer = detect_board_corners(warped)
    if outer is not None:
        return outer
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    offset = 210
    crop = gray[offset:590, offset:590]
    detector = getattr(cv2, "findChessboardCornersSB", None)
    if detector is None:
        return None
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(crop)
    for candidate in (crop, enhanced):
        found, points = detector(
            candidate, (3, 3),
            flags=cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY,
        )
        if not found:
            continue
        points = points.reshape(3, 3, 2) + offset
        if abs(points[0, 2, 0] - points[0, 0, 0]) < abs(points[2, 0, 0] - points[0, 0, 0]):
            points = points.transpose(1, 0, 2)
        if points[0, 2, 0] < points[0, 0, 0]:
            points = points[:, ::-1]
        if points[2, 0, 1] < points[0, 0, 1]:
            points = points[::-1]
        if np.max(np.linalg.norm(points.reshape(-1, 2) - CENTRAL_GRID, axis=1)) > 65:
            continue
        homography, _ = cv2.findHomography(CENTRAL_GRID, points.reshape(-1, 2), 0)
        if homography is None:
            continue
        projected = cv2.perspectiveTransform(CENTRAL_GRID.reshape(-1, 1, 2), homography)
        if np.max(np.linalg.norm(projected.reshape(-1, 2) - points.reshape(-1, 2), axis=1)) > 5:
            continue
        return cv2.perspectiveTransform(GRID_TARGET.reshape(-1, 1, 2), homography).reshape(4, 2)
    return None


class BoardViewFilter:
    """Temporal median and moderate CLAHE after geometric stabilization."""

    def __init__(self):
        self.window = 3
        self.contrast = 45
        self.frames = deque(maxlen=self.window)
        self.clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))

    def configure(self, window, contrast):
        window = int(window)
        contrast = int(contrast)
        if window not in (1, 3, 5, 7):
            raise ValueError("La mediana richiede 1, 3, 5 o 7 fotogrammi")
        if not 0 <= contrast <= 100:
            raise ValueError("Il contrasto deve essere tra 0 e 100")
        if window != self.window:
            self.frames = deque(maxlen=window)
            self.window = window
        self.contrast = contrast

    def reset(self):
        self.frames.clear()

    def process(self, warped):
        # The BOOX board is monochrome. Filter one luminance channel to keep
        # the 5/7-frame controls responsive on the live camera.
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        self.frames.append(gray)
        if len(self.frames) == 3:
            a, b, c = self.frames
            # Median of three rejects isolated JPEG noise without the long
            # trails of a four-frame arithmetic average.
            stable = np.maximum(np.minimum(a, b), np.minimum(np.maximum(a, b), c))
        elif len(self.frames) == self.window and self.window > 3:
            stable = np.partition(np.stack(self.frames), self.window // 2, axis=0)[self.window // 2]
        else:
            stable = gray
        stable_bgr = cv2.cvtColor(stable, cv2.COLOR_GRAY2BGR)
        if self.contrast == 0:
            return stable_bgr, stable_bgr.copy()
        improved = self.clahe.apply(stable)
        strength = self.contrast / 100.0
        enhanced = cv2.addWeighted(stable, 1 - strength, improved, strength, 0)
        return stable_bgr, cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


class VisionDashboard:
    def __init__(self, url):
        settings = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.is_file() else {}
        self.url = url
        self.robot_ip = robot_ip
        self.robot_diagnostics = {"connection": "Verifica in corso"}
        try:
            self.calibration = load_calibration()
            self.calibration_error = None
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            self.calibration = None
            self.calibration_error = str(error)
        self.calibration_draft = {slot: self.calibration[slot].copy() for slot in ("a8", "h8", "a1", "tray")} if self.calibration and self.calibration["robot_ip"] == self.robot_ip else {}
        self.draft_serial = self.calibration["serial"] if self.calibration_draft else None
        self.draft_tcp_offset = self.calibration["tcp_offset"].copy() if self.calibration_draft else None
        self.draft_dirty = False
        self.robot_pose = None
        self.tcp_offset = None
        self.robot_speed = None
        self.robot_pose_at = None
        self.pose_stationary_since = None
        self.robot_pose_error = "Lettura RTDE in avvio"
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.commands = deque()
        # Optical flow follows every frame. A normalized grid check below
        # replaces the raw-image periodic detector, which can drift on e-ink.
        self.tracker = BoardTracker((SIZE, SIZE), periodic_detection=False)
        self.orientation = int(settings.get("orientation_corner", 4)) - 1
        self.orientation_confirmed = bool(settings.get("orientation_confirmed", False))
        self.tracking_paused = False
        self.recovery_started = None
        self.next_recovery_at = None
        self.settle_until = 0.0
        self.broad_change_since = None
        self.broad_last_view = None
        self.reference_warning = False
        self.baseline = None
        self.latest_warp = None
        self.grid_last_check = -1000
        self.grid_error_px = None
        self.latest_median_view = None
        self.latest_board_view = None
        self.view_filter = BoardViewFilter()
        self.view_filter.configure(settings.get("view_window", 3), settings.get("view_contrast", 45))
        self.board = chess.Board()
        self.candidate = None
        self.candidate_seen = 0
        self.last_candidate = None
        self.planned_move = None
        self.engine_name = "Avvio..."
        self.engine_error = None
        self.frame_number = 0
        self.raw_jpeg = None
        self.board_jpeg = None
        self.last_frame_at = 0.0
        self.last_frame_interval = None
        self.status = "Avvio camera"
        self.detail = "In attesa del primo fotogramma"
        self.changed = []
        self.highlighted = []
        self.change_scores = np.zeros((8, 8), dtype=np.float32)
        self.background = 0.0
        self.last_move = None
        self.engine_event = threading.Event()
        self.stop_event = threading.Event()
        self.engine_event.set()

    def start(self):
        threading.Thread(target=self._camera_loop, name="camera", daemon=True).start()
        threading.Thread(target=self._engine_loop, name="stockfish", daemon=True).start()
        threading.Thread(target=self._robot_status_loop, name="robot-readonly", daemon=True).start()
        threading.Thread(target=self._robot_pose_loop, name="tcp-pose-readonly", daemon=True).start()

    def _teach_gate(self):
        diagnostics = self.robot_diagnostics
        if time.monotonic() - diagnostics.get("checked_at", 0) > 8:
            return "Stato controller non aggiornato"
        if diagnostics.get("connection") != "Controller raggiungibile":
            return "Controller non raggiungibile"
        if diagnostics.get("remote") != "false":
            return "Passa a Locale/Manuale sul pendant: Freedrive è disabilitato in Remoto"
        if diagnostics.get("robot_mode") != "Robotmode: RUNNING":
            return "Il robot deve essere acceso con freni rilasciati"
        if diagnostics.get("safety") not in ("Safetystatus: NORMAL", "Safetystatus: REDUCED"):
            return "Stato di sicurezza non idoneo all'insegnamento"
        if not str(diagnostics.get("program", "")).upper().startswith("STOPPED"):
            return "Ferma il programma prima di insegnare posizioni"
        if not str(diagnostics.get("serial", "")).isdigit():
            return "Seriale controller non disponibile"
        if self.robot_pose is None or self.robot_speed is None or self.robot_pose_at is None or time.monotonic() - self.robot_pose_at > 1:
            return "Posa TCP non disponibile o non aggiornata"
        if self.tcp_offset is None or np.linalg.norm(self.tcp_offset[:3]) < 0.005:
            return "Configura sul pendant il TCP sulla punta della pinza"
        if self.pose_stationary_since is None or time.monotonic() - self.pose_stationary_since < 0.4:
            return "Rilascia Freedrive e attendi che il braccio sia fermo"
        return None

    def _save_settings(self):
        SETTINGS_FILE.write_text(json.dumps({
            "camera_url": self.url, "robot_ip": self.robot_ip,
            "view_window": self.view_filter.window, "view_contrast": self.view_filter.contrast,
            "orientation_corner": self.orientation + 1,
            "orientation_confirmed": self.orientation_confirmed,
        }, indent=2), encoding="utf-8")

    def command(self, payload):
        with self.lock:
            kind = payload.get("action")
            if kind == "settings":
                camera = str(payload["camera_url"]).strip()
                parsed = urlsplit(camera)
                if parsed.scheme not in ("http", "https") or not parsed.hostname or not parsed.path:
                    raise ValueError("URL camera non valido: usa l'indirizzo completo del video")
                address = str(ipaddress.ip_address(payload["robot_ip"]))
                if self.url != camera:
                    self.url = camera
                    self.orientation_confirmed = False
                    self.tracker = BoardTracker((SIZE, SIZE), periodic_detection=False)
                    self.view_filter.reset()
                    self.latest_warp = None
                    self.latest_median_view = None
                    self.latest_board_view = None
                    self.baseline = None
                    self._clear_candidate()
                if self.robot_ip != address:
                    self.robot_pose = None
                    self.tcp_offset = None
                    self.robot_pose_at = None
                    self.pose_stationary_since = None
                    self.calibration_draft = {}
                    self.draft_serial = None
                    self.draft_tcp_offset = None
                    self.draft_dirty = False
                self.robot_ip = address
                self.robot_diagnostics = {"connection": "Verifica in corso"}
                self._save_settings()
                return {"ok": True}
            if kind == "view_settings":
                self.view_filter.configure(payload["window"], payload["contrast"])
                self._save_settings()
                self.baseline = None
                self._clear_candidate()
                self.settle_until = time.monotonic() + 1.0
                self.detail = "Filtri di visione aggiornati; riferimento in ricostruzione"
                return {"ok": True}
            if kind == "calibration":
                if not self.draft_dirty:
                    raise ValueError("Acquisisci almeno una posa dal braccio prima di salvare")
                if not all(slot in self.calibration_draft for slot in ("a8", "h8", "a1", "tray")):
                    raise ValueError("Acquisisci a8, h8, a1 e vassoio")
                if self.draft_serial != self.robot_diagnostics.get("serial"):
                    raise ValueError("Il seriale del controller è cambiato")
                if self.draft_tcp_offset is None or self.tcp_offset is None or not np.allclose(self.draft_tcp_offset, self.tcp_offset, atol=0.002):
                    raise ValueError("Il TCP è cambiato durante la calibrazione")
                self.calibration = save_calibration({**self.calibration_draft,
                    "robot_ip": self.robot_ip, "serial": self.draft_serial,
                    "tcp_offset": self.draft_tcp_offset})
                self.calibration_error = None
                self.draft_dirty = False
                return {"ok": True}
            if kind == "capture_pose":
                if payload.get("tip_confirmed") is not True:
                    raise ValueError("Conferma che il TCP attivo è sulla punta della pinza")
                slot = payload.get("slot")
                if slot not in ("a8", "h8", "a1", "tray"):
                    raise ValueError("Punto di calibrazione sconosciuto")
                reason = self._teach_gate()
                if reason:
                    raise ValueError(reason)
                serial = self.robot_diagnostics["serial"]
                if self.draft_serial != serial or self.draft_tcp_offset is None or not np.allclose(self.draft_tcp_offset, self.tcp_offset, atol=0.002):
                    self.calibration_draft = {}
                self.draft_serial = serial
                self.draft_tcp_offset = self.tcp_offset.copy()
                count = 3 if slot == "tray" else 6
                self.calibration_draft[slot] = [round(float(value), 6) for value in self.robot_pose[:count]]
                self.draft_dirty = True
                return {"ok": True, "slot": slot, "pose": self.calibration_draft[slot]}
            if kind == "connect_robot":
                if self.calibration is None or self.calibration["robot_ip"] != self.robot_ip:
                    raise ValueError("Collegamento rifiutato: posizioni del robot non calibrate")
                raise ValueError("Il pannello visione non invia comandi al robot")
            self.commands.append(payload)
        return {"ok": True}

    def snapshot(self):
        with self.lock:
            board = self.board.copy()
            proposed = self.planned_move
            candidate = self.candidate
            age = round(time.monotonic() - self.last_frame_at, 1) if self.last_frame_at else None
            teach_reason = self._teach_gate()
            return {
                "camera_url": self.url,
                "status": self.status,
                "detail": self.detail,
                "frame": self.frame_number,
                "age_seconds": age,
                "fps": round(1 / self.last_frame_interval, 1) if self.last_frame_interval else 0,
                "tracked": self.tracker.corners is not None and not self.tracking_paused,
                "recovering": self.tracking_paused and self.recovery_started is not None
                              and time.monotonic() - self.recovery_started < 60,
                "orientation": self.orientation + 1,
                "orientation_confirmed": self.orientation_confirmed,
                "reference_ready": self.baseline is not None,
                "reference_warning": self.reference_warning,
                "grid_error_px": self.grid_error_px,
                "changed_squares": [chess.square_name(sq) for sq in self.changed],
                "change_scores": {
                    f"{chr(97 + col)}{8 - row}": round(float(self.change_scores[row, col]), 3)
                    for row in range(8) for col in range(8)
                    if self.change_scores[row, col] >= 0.01
                },
                "background_change": round(self.background, 3),
                "candidate_uci": candidate.uci() if candidate else None,
                "candidate_san": board.san(candidate) if candidate and candidate in board.legal_moves else None,
                "planned_uci": proposed.uci() if proposed else None,
                "planned_san": board.san(proposed) if proposed and proposed in board.legal_moves else None,
                "engine_name": self.engine_name,
                "engine_error": self.engine_error,
                "fen": board.fen(),
                "turn": "Bianco" if board.turn else "Nero",
                "turn_role": "Braccio" if board.turn else "Persona",
                "game_over": board.is_game_over(claim_draw=True),
                "last_move": self.last_move,
                "robot": "Disabilitato: sola visione",
                "robot_ip": self.robot_ip,
                "robot_diagnostics": self.robot_diagnostics.copy(),
                "robot_pose": self.robot_pose.copy() if self.robot_pose is not None else None,
                "tcp_offset": self.tcp_offset.copy() if self.tcp_offset is not None else None,
                "robot_pose_age": round(time.monotonic() - self.robot_pose_at, 2) if self.robot_pose_at else None,
                "robot_pose_error": self.robot_pose_error,
                "teach_ready": teach_reason is None,
                "teach_reason": teach_reason,
                "calibration_ready": self.calibration is not None and self.calibration["robot_ip"] == self.robot_ip and self.calibration["serial"] == self.robot_diagnostics.get("serial") and self.tcp_offset is not None and np.allclose(self.calibration["tcp_offset"], self.tcp_offset, atol=0.002),
                "calibration": self.calibration,
                "calibration_error": self.calibration_error,
                "calibration_draft": self.calibration_draft.copy(),
                "calibration_draft_dirty": self.draft_dirty,
                "view_window": self.view_filter.window,
                "view_contrast": self.view_filter.contrast,
            }

    def _apply_commands(self, image):
        with self.lock:
            commands = list(self.commands)
            self.commands.clear()
        for payload in commands:
            kind = payload.get("action")
            try:
                if kind == "orientation":
                    index = int(payload["corner"]) - 1
                    if index not in range(4):
                        raise ValueError("L'angolo a8 deve essere 1, 2, 3 o 4")
                    self.orientation = index
                    self._relock(image)
                    self.orientation_confirmed = True
                    self._save_settings()
                elif kind == "relock":
                    self._relock(image)
                elif kind == "reference":
                    if self.latest_warp is None or self.tracking_paused:
                        raise ValueError("Scacchiera non agganciata")
                    self.baseline = self.latest_board_view.copy() if self.latest_board_view is not None else self.latest_warp.copy()
                    self._clear_candidate()
                    self.reference_warning = False
                    self.detail = "Nuovo fotogramma di riferimento acquisito"
                elif kind == "new_game":
                    self.board = chess.Board()
                    self.last_move = None
                    self.baseline = self.latest_board_view.copy() if self.latest_board_view is not None else None
                    self._clear_candidate()
                    self.reference_warning = False
                    self._invalidate_engine()
                elif kind == "fen":
                    board = chess.Board(str(payload["fen"]).strip())
                    if not board.is_valid():
                        raise ValueError("Posizione FEN non valida")
                    self.board = board
                    self.last_move = None
                    self.baseline = self.latest_board_view.copy() if self.latest_board_view is not None else None
                    self._clear_candidate()
                    self.reference_warning = False
                    self._invalidate_engine()
                elif kind == "confirm_candidate":
                    if self.board.turn:
                        raise ValueError("Ora è il turno del braccio")
                    if self.candidate is None or self.candidate not in self.board.legal_moves:
                        raise ValueError("Non c'è una mossa riconosciuta da confermare")
                    self._push_move(self.candidate)
                elif kind == "confirm_engine":
                    if not self.board.turn:
                        raise ValueError("Ora è il turno della persona")
                    if self.planned_move is None or self.planned_move not in self.board.legal_moves:
                        raise ValueError("Non c'è una mossa Stockfish da confermare")
                    self._push_move(self.planned_move)
                else:
                    raise ValueError("Azione sconosciuta")
            except (ValueError, BoardTrackingError) as error:
                self.detail = f"Azione rifiutata: {error}"

    def _push_move(self, move):
        self.last_move = self.board.san(move)
        self.board.push(move)
        self.baseline = self.latest_board_view.copy() if self.latest_board_view is not None else None
        self._clear_candidate()
        self._invalidate_engine()
        self.detail = f"Mossa confermata: {self.last_move}"

    def _invalidate_engine(self):
        with self.lock:
            self.planned_move = None
        self.engine_event.set()

    def _clear_candidate(self):
        self.candidate = None
        self.last_candidate = None
        self.candidate_seen = 0
        self.changed = []
        self.highlighted = []
        self.change_scores.fill(0)
        self.background = 0.0

    def _relock(self, image):
        corners = detect_board_corners(image)
        if corners is None:
            raise ValueError("I 49 incroci della scacchiera non sono visibili")
        oriented = orient_corners(corners, self.orientation)
        raw_warp = self.tracker.initialize(image, oriented)
        self.grid_last_check = -1000
        self.grid_error_px = None
        self.latest_warp = self._correct_warp(image, raw_warp)
        self.view_filter.reset()
        self.latest_median_view = None
        self.latest_board_view = None
        self.tracking_paused = False
        self.recovery_started = None
        self.next_recovery_at = None
        # E-ink refresh can leave a partially drawn board for a moment. Keep
        # updating the reference during this short settling period.
        self.settle_until = time.monotonic() + 5.0
        self.baseline = None
        self.broad_change_since = None
        self.broad_last_view = None
        self._clear_candidate()
        self.status = "Scacchiera agganciata"
        self.detail = "Angoli rilevati automaticamente; riferimento aggiornato"

    def _correct_warp(self, image, raw_warp):
        """Use visible grid intersections to correct accumulated corner drift."""
        if self.frame_number - self.grid_last_check >= 18:
            self.grid_last_check = self.frame_number
            found = detect_visible_grid(raw_warp)
            if found is not None:
                residuals = np.linalg.norm(found - GRID_TARGET, axis=1)
                if float(np.max(residuals)) <= 160.0:
                    self.grid_error_px = round(float(np.mean(residuals)), 1)
                    if float(np.max(residuals)) > 6.0:
                        warp_to_camera = cv2.getPerspectiveTransform(
                            GRID_TARGET, np.asarray(self.tracker.corners, dtype=np.float32)
                        )
                        physical = cv2.perspectiveTransform(
                            found.reshape(4, 1, 2), warp_to_camera
                        ).reshape(4, 2)
                        try:
                            corrected = self.tracker.initialize(image, physical)
                        except BoardTrackingError:
                            raise BoardTrackingError(
                                "La scacchiera non è interamente visibile dopo il riallineamento"
                            )
                        if self.baseline is None:
                            self.view_filter.reset()
                        return corrected
        return raw_warp

    def _engine_loop(self):
        path = stockfish_path()
        if path is None:
            with self.lock:
                self.engine_name = "Stockfish assente"
                self.engine_error = "Imposta STOCKFISH_PATH per vedere la mossa del motore"
            return
        try:
            with chess.engine.SimpleEngine.popen_uci(path) as engine:
                with self.lock:
                    self.engine_name = engine.id.get("name", "Stockfish")
                    self.engine_error = None
                while not self.stop_event.is_set():
                    self.engine_event.wait(0.5)
                    if not self.engine_event.is_set():
                        continue
                    self.engine_event.clear()
                    with self.lock:
                        fen = self.board.fen()
                    board = chess.Board(fen)
                    if board.is_game_over(claim_draw=True):
                        continue
                    info = engine.analyse(board, chess.engine.Limit(time=0.25))
                    move = info["pv"][0]
                    with self.lock:
                        if self.board.fen() == fen:
                            self.planned_move = move
        except Exception as error:
            with self.lock:
                self.engine_error = str(error)
                self.engine_name = "Stockfish non disponibile"

    def _camera_loop(self):
        while not self.stop_event.is_set():
            camera_url = self.url
            camera = cv2.VideoCapture(camera_url)
            if not camera.isOpened():
                with self.lock:
                    self.status = "Camera scollegata"
                    self.detail = "Tentativo di riconnessione..."
                camera.release()
                time.sleep(1)
                continue
            camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            try:
                while not self.stop_event.is_set():
                    if self.url != camera_url:
                        break
                    ok, raw = camera.read()
                    if not ok or raw is None:
                        raise RuntimeError("Il flusso video si è interrotto")
                    image = cv2.resize(raw, (SIZE, SIZE))
                    with self.lock:
                        self._apply_commands(image)
                        self._process_frame(raw, image)
            except Exception as error:
                with self.lock:
                    self.status = "Camera da riconnettere"
                    self.detail = str(error)
                time.sleep(0.5)
            finally:
                camera.release()

    def _robot_status_loop(self):
        while not self.stop_event.is_set():
            with self.lock:
                address = self.robot_ip
            diagnostics = {"connection": "Non raggiungibile", "dashboard_port": False,
                           "rtde_port": False, "script_port": False}
            try:
                with socket.create_connection((address, 29999), timeout=0.7) as connection:
                    connection.settimeout(0.7)
                    connection.recv(512)  # Dashboard greeting.
                    diagnostics["dashboard_port"] = True
                    diagnostics["connection"] = "Controller raggiungibile"
                    for name, command in (("remote", "is in remote control"),
                                          ("operation_mode", "get operational mode"),
                                          ("robot_mode", "robotmode"),
                                          ("safety", "safetystatus"),
                                          ("program", "programState"),
                                          ("serial", "get serial number")):
                        try:
                            connection.sendall((command + "\n").encode("ascii"))
                            diagnostics[name] = connection.recv(512).decode("utf-8", errors="replace").strip()
                        except (OSError, TimeoutError):
                            diagnostics[name] = "Non disponibile"
                            break
                for name, port in (("rtde_port", 30004), ("script_port", 30002)):
                    try:
                        with socket.create_connection((address, port), timeout=0.5):
                            diagnostics[name] = True
                    except OSError:
                        pass
            except OSError as error:
                diagnostics["detail"] = str(error)
            with self.lock:
                if self.robot_ip == address:
                    diagnostics["checked_at"] = time.monotonic()
                    self.robot_diagnostics = diagnostics
            self.stop_event.wait(5)

    def _robot_pose_loop(self):
        if ur_rtde is None:
            with self.lock:
                self.robot_pose_error = "Installa la libreria RTDE ufficiale (requirements.txt)"
            return
        while not self.stop_event.is_set():
            with self.lock:
                address = self.robot_ip
            connection = None
            try:
                connection = ur_rtde.RTDE(address, 30004)
                connection.connect()
                if not connection.send_output_setup(
                    ["timestamp", "actual_TCP_pose", "actual_TCP_speed", "tcp_offset"],
                    ["DOUBLE", "VECTOR6D", "VECTOR6D", "VECTOR6D"], frequency=10
                ) or not connection.send_start():
                    raise RuntimeError("Ricetta RTDE TCP rifiutata dal controller")
                while not self.stop_event.is_set() and self.robot_ip == address:
                    sample = connection.receive()
                    if sample is None:
                        raise RuntimeError("Flusso RTDE interrotto")
                    with self.lock:
                        self.robot_pose = [float(value) for value in sample.actual_TCP_pose]
                        self.tcp_offset = [float(value) for value in sample.tcp_offset]
                        self.robot_speed = [float(value) for value in sample.actual_TCP_speed]
                        now = time.monotonic()
                        self.robot_pose_at = now
                        stationary = (np.linalg.norm(self.robot_speed[:3]) <= 0.005
                                      and np.linalg.norm(self.robot_speed[3:]) <= 0.05)
                        if stationary:
                            self.pose_stationary_since = self.pose_stationary_since or now
                        else:
                            self.pose_stationary_since = None
                        self.robot_pose_error = None
            except Exception as error:
                with self.lock:
                    if self.robot_ip == address:
                        self.robot_pose = None
                        self.tcp_offset = None
                        self.robot_pose_at = None
                        self.pose_stationary_since = None
                        self.robot_pose_error = str(error)
            finally:
                if connection is not None:
                    try:
                        connection.disconnect()
                    except OSError:
                        pass
            self.stop_event.wait(1)

    def _process_frame(self, raw, image):
        now = time.monotonic()
        if self.last_frame_at:
            elapsed = now - self.last_frame_at
            self.last_frame_interval = elapsed if self.last_frame_interval is None else (0.8 * self.last_frame_interval + 0.2 * elapsed)
        self.last_frame_at = now
        self.frame_number += 1

        if self.tracker.corners is None:
            try:
                self._relock(image)
            except (ValueError, BoardTrackingError) as error:
                self.status = "Scacchiera non trovata"
                self.detail = str(error)
        elif self.tracking_paused:
            if self.recovery_started is not None and now - self.recovery_started < 60:
                if now >= self.next_recovery_at:
                    self.next_recovery_at = now + 5.0
                    try:
                        self._relock(image)
                        self.detail = "Scacchiera ritrovata; attendo che il BOOX finisca il refresh"
                    except (ValueError, BoardTrackingError) as error:
                        self.status = "Recupero automatico"
                        self.detail = f"Scacchiera ancora instabile ({error}); nuovo tentativo tra 5 s"
                else:
                    wait = max(0, round(self.next_recovery_at - now))
                    self.status = "Recupero automatico"
                    self.detail = f"Refresh o cambio pagina: riprovo tra {wait} s, fino a 60 s"
            else:
                self.status = "Rilocca la scacchiera"
                self.detail = "60 s di tentativi conclusi; stabilizza il BOOX e premi Riloca"
        else:
            try:
                raw_warp = self.tracker.update(image)
                self.latest_warp = self._correct_warp(image, raw_warp)
                self.status = "Scacchiera agganciata"
            except BoardTrackingError as error:
                self.tracking_paused = True
                self.recovery_started = now
                self.next_recovery_at = now + 5.0
                self._clear_candidate()
                self.status = "Recupero automatico"
                self.detail = f"{error} Attendo il refresh; primo tentativo tra 5 s"

        if self.latest_warp is not None and not self.tracking_paused:
            self.latest_median_view, self.latest_board_view = self.view_filter.process(self.latest_warp)
            self._analyze_move(self.latest_board_view)

        raw_display = self._draw_raw(raw)
        board_display = self._draw_board()
        self.raw_jpeg = cv2.imencode(".jpg", raw_display, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
        self.board_jpeg = cv2.imencode(".jpg", board_display, [cv2.IMWRITE_JPEG_QUALITY, 86])[1].tobytes()
        self.condition.notify_all()

    def _analyze_move(self, warped):
        now = time.monotonic()
        if now < self.settle_until:
            self.baseline = warped.copy()
            self._clear_candidate()
            self.broad_change_since = None
            self.broad_last_view = None
            self.background = 0.0
            self.detail = "Il BOOX si sta stabilizzando; il riferimento viene aggiornato"
            return
        if self.baseline is None:
            self.baseline = warped.copy()
            return
        scores, background, changed = changed_square_scores(self.baseline, warped)
        self.change_scores = scores
        self.background = background
        # A single legal move changes 2-4 squares. E-ink full-page updates can
        # alter many occupied squares at once; never paint those as a move.
        self.changed = changed if background <= 0.08 and len(changed) <= 4 else []
        self.highlighted = []
        if background > 0.08 or len(changed) > 4:
            if self.broad_change_since is None:
                self.broad_change_since = now
            elif self.broad_last_view is not None:
                frame_delta = cv2.absdiff(
                    cv2.cvtColor(self.broad_last_view, cv2.COLOR_BGR2GRAY),
                    cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY),
                )
                if float(np.mean(frame_delta > 12)) > 0.05:
                    self.broad_change_since = now
                elif now - self.broad_change_since >= 2.0:
                    self.baseline = warped.copy()
                    self._clear_candidate()
                    self.broad_change_since = None
                    self.broad_last_view = None
                    self.reference_warning = True
                    self.detail = "Riferimento aggiornato dopo il refresh; verifica la posizione FEN"
                    return
            self.broad_last_view = warped.copy()
        else:
            self.broad_change_since = None
            self.broad_last_view = None
        if not self.orientation_confirmed:
            self.detail = "Conferma quale angolo della camera è a8 per leggere le mosse"
            self._clear_candidate()
            return
        if background > 0.08:
            self.detail = "Molte caselle sono cambiate: attendi il refresh dello schermo"
            self.candidate = None
            self.last_candidate = None
            self.candidate_seen = 0
            return
        if self.board.turn:
            # Robot moves are confirmed explicitly, so keep the reference fresh
            # while waiting; transient e-ink artefacts are not player moves.
            self.baseline = warped.copy()
            self.changed = []
            self.change_scores.fill(0)
            self.detail = "Turno del braccio: in attesa della mossa Stockfish"
            self.candidate = None
            self.last_candidate = None
            self.candidate_seen = 0
            return
        relevant = legal_move_squares(self.board)
        ignored = [square for square in changed if square not in relevant]
        if ignored:
            checked = warped.copy()
            for square in ignored:
                col = chess.square_file(square)
                row = 7 - chess.square_rank(square)
                checked[row*100:(row+1)*100, col*100:(col+1)*100] = self.baseline[row*100:(row+1)*100, col*100:(col+1)*100]
            changed = [square for square in changed if square in relevant]
            self.changed = changed
        else:
            checked = warped
        if not 2 <= len(changed) <= 4:
            self.detail = "In attesa di una mossa completa" if len(changed) < 2 else "Aggiornamento esteso: caselle non evidenziate; usa Nuovo riferimento se la posizione è corretta"
            self.candidate = None
            self.last_candidate = None
            self.candidate_seen = 0
            return
        try:
            options = infer_human_move(self.baseline, checked, BOXES, self.board)
            if len(options) != 1:
                raise MoveDetectionError("Promozione: scegli il pezzo prima di confermare")
            move = options[0]
            self.candidate_seen = self.candidate_seen + 1 if move == self.last_candidate else 1
            self.last_candidate = move
            self.candidate = move if self.candidate_seen >= 5 else None
            self.highlighted = changed if self.candidate else []
            self.detail = "Mossa legale da confermare" if self.candidate else "Verifica stabilità della mossa..."
        except MoveDetectionError as error:
            self.candidate = None
            self.last_candidate = None
            self.candidate_seen = 0
            self.detail = str(error)

    def _draw_raw(self, raw):
        height, width = raw.shape[:2]
        scale = min(1.0, 1280 / width)
        display = cv2.resize(raw, (round(width * scale), round(height * scale)))
        if self.tracker.corners is not None:
            corners = _ordered_corners(self.tracker.corners)
            x_factor = display.shape[1] / SIZE
            y_factor = display.shape[0] / SIZE
            points = np.array([[x * x_factor, y * y_factor] for x, y in corners], dtype=np.int32)
            cv2.polylines(display, [points], True, (42, 210, 122) if not self.tracking_paused else (0, 80, 245), 3)
            for index, (x, y) in enumerate(points):
                active = index == self.orientation
                cv2.circle(display, (int(x), int(y)), 13, (15, 215, 245) if active else (255, 255, 255), -1)
                cv2.putText(display, str(index + 1), (int(x) - 6, int(y) + 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 25, 35), 2)
        label = "CAMERA LIVE" if not self.tracking_paused else "ANALISI IN PAUSA"
        cv2.rectangle(display, (12, 12), (380, 64), (22, 29, 45), -1)
        cv2.putText(display, label, (27, 49), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (255, 255, 255), 2, cv2.LINE_AA)
        return display

    def _draw_board(self):
        if self.latest_warp is None:
            image = np.full((SIZE, SIZE, 3), (26, 33, 46), dtype=np.uint8)
            cv2.putText(image, "ATTESA SCACCHIERA", (100, 400),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return image
        image = self.latest_board_view.copy() if self.latest_board_view is not None else self.latest_warp.copy()
        overlay = image.copy()
        for sq in self.highlighted:
            col = chess.square_file(sq)
            row = 7 - chess.square_rank(sq)
            cv2.rectangle(overlay, (col * 100, row * 100), ((col + 1) * 100, (row + 1) * 100),
                          (30, 170, 255), -1)
        image = cv2.addWeighted(overlay, 0.25, image, 0.75, 0)
        for i in range(9):
            cv2.line(image, (i * 100, 0), (i * 100, 799), (42, 215, 135), 2)
            cv2.line(image, (0, i * 100), (799, i * 100), (42, 215, 135), 2)
        if self.orientation_confirmed:
            for row in range(8):
                for col in range(8):
                    cv2.putText(image, f"{chr(97 + col)}{8 - row}",
                                (col * 100 + 8, row * 100 + 22),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (10, 135, 70), 2)
            draw_arrow(image, self.planned_move, (245, 190, 30))
            draw_arrow(image, self.candidate, (60, 225, 95))
        if self.tracking_paused:
            cv2.rectangle(image, (0, 0), (799, 80), (20, 28, 190), -1)
            cv2.putText(image, "TRACKING IN PAUSA", (105, 52),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
        return image


def make_handler(dashboard):
    html = (ROOT / "vision_dashboard.html").read_bytes()
    stage_views = {
        "geometry": "latest_warp",
        "median": "latest_median_view",
        "contrast": "latest_board_view",
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format_string, *args):
            if not self.path.startswith(("/stream/", "/api/state", "/frame/")):
                super().log_message(format_string, *args)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, "text/html; charset=utf-8", html)
            elif path == "/api/state":
                self._send(200, "application/json", json.dumps(dashboard.snapshot()).encode())
            elif path in ("/frame/raw.jpg", "/frame/board.jpg"):
                with dashboard.lock:
                    data = dashboard.raw_jpeg if "raw" in path else dashboard.board_jpeg
                if data is None:
                    self._send(503, "text/plain", b"Waiting for camera")
                else:
                    self._send(200, "image/jpeg", data)
            elif path.startswith("/frame/board/") and path.endswith(".jpg"):
                stage = path.removeprefix("/frame/board/").removesuffix(".jpg")
                if stage not in stage_views:
                    self._send(404, "text/plain", b"Unknown stage")
                    return
                with dashboard.lock:
                    image = getattr(dashboard, stage_views[stage])
                if image is None:
                    self._send(503, "text/plain", b"Waiting for board")
                else:
                    self._send(200, "image/jpeg", self._encode(image))
            elif path in ("/stream/raw", "/stream/board"):
                self._stream("raw" if path.endswith("raw") else "board")
            elif path.startswith("/stream/board/") and path.removeprefix("/stream/board/") in stage_views:
                self._stream(path.removeprefix("/stream/board/"))
            else:
                self._send(404, "text/plain", b"Not found")

        def do_POST(self):
            if self.path != "/api/action":
                self._send(404, "text/plain", b"Not found")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length < 4096:
                    raise ValueError("Invalid body length")
                payload = json.loads(self.rfile.read(length))
                self._send(200, "application/json", json.dumps(dashboard.command(payload)).encode())
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                self._send(400, "text/plain", str(error).encode())

        def _send(self, status, content_type, body):
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        @staticmethod
        def _encode(image):
            return cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 86])[1].tobytes()

        def _stream(self, which):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            seen = -1
            try:
                while not dashboard.stop_event.is_set():
                    with dashboard.condition:
                        dashboard.condition.wait_for(
                            lambda: dashboard.frame_number != seen or dashboard.stop_event.is_set(), 5
                        )
                        seen = dashboard.frame_number
                        data = dashboard.raw_jpeg if which == "raw" else dashboard.board_jpeg if which == "board" else None
                        image = getattr(dashboard, stage_views[which]) if which in stage_views else None
                    if image is not None:
                        data = self._encode(image)
                    if data is None:
                        continue
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(data)).encode() + b"\r\n\r\n" + data + b"\r\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", default=camera_ip)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    dashboard = VisionDashboard(args.camera)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(dashboard))
    dashboard.start()
    print(f"Vision dashboard: http://127.0.0.1:{args.port}/", flush=True)
    print("Robot control: disabled", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        dashboard.stop_event.set()
        server.server_close()


if __name__ == "__main__":
    main()
