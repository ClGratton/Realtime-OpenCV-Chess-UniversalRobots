"""Stored board-to-robot positions. Loading this file never connects to the arm."""

import json
import ipaddress
from math import isfinite
import os
from pathlib import Path
import socket

import numpy as np


CALIBRATION_FILE = Path(os.getenv("CHESS_CALIBRATION_FILE", str(Path(__file__).with_name("robot_calibration.json"))))


def validate_calibration(data):
    poses = {}
    for square in ("a8", "h8", "a1"):
        values = [float(value) for value in data[square]]
        if len(values) != 6 or not all(isfinite(value) for value in values):
            raise ValueError(f"{square}: servono 6 coordinate finite (metri e radianti)")
        poses[square] = values
    tray = [float(value) for value in data["tray"]]
    if len(tray) != 3 or not all(isfinite(value) for value in tray):
        raise ValueError("Vassoio: servono 3 coordinate finite in metri")
    a8, h8, a1 = (np.asarray(poses[square][:3]) for square in ("a8", "h8", "a1"))
    file_axis, rank_axis = h8 - a8, a1 - a8
    if not 0.12 < np.linalg.norm(file_axis) < 0.65 or not 0.12 < np.linalg.norm(rank_axis) < 0.65:
        raise ValueError("I centri a8, h8 e a1 devono essere distinti e plausibili")
    if np.linalg.norm(np.cross(file_axis, rank_axis)) < 0.01:
        raise ValueError("I tre centri sono quasi allineati")
    if max(abs(h8[2] - a8[2]), abs(a1[2] - a8[2])) > 0.08:
        raise ValueError("I tre centri differiscono troppo in altezza")
    if np.linalg.norm(np.asarray(tray) - a8) < 0.05:
        raise ValueError("Il vassoio è troppo vicino ad a8")
    if any(np.linalg.norm(np.asarray(poses[square][3:]) - np.asarray(poses["a8"][3:])) > 0.15
           for square in ("h8", "a1")):
        raise ValueError("L'orientamento della pinza deve essere uguale nei tre punti")
    address = str(ipaddress.ip_address(data["robot_ip"]))
    serial = str(data["serial"]).strip()
    if not serial.isdigit():
        raise ValueError("Manca il seriale verificato del controller")
    tcp_offset = [float(value) for value in data["tcp_offset"]]
    if len(tcp_offset) != 6 or not all(isfinite(value) for value in tcp_offset) or np.linalg.norm(tcp_offset[:3]) < 0.005:
        raise ValueError("TCP della punta della pinza non configurato")
    return {**poses, "tray": tray, "robot_ip": address, "serial": serial,
            "tcp_offset": tcp_offset}


def read_robot_serial(address):
    """Read only the controller serial via the UR Dashboard Server."""
    with socket.create_connection((address, 29999), timeout=1.0) as connection:
        connection.settimeout(1.0)
        connection.recv(512)
        connection.sendall(b"get serial number\n")
        return connection.recv(512).decode("ascii", errors="replace").strip()


def read_robot_tcp_offset(address):
    """Read the controller's active flange-to-TCP transform without commanding motion."""
    import rtde.rtde as ur_rtde
    connection = ur_rtde.RTDE(address, 30004)
    try:
        connection.connect()
        if not connection.send_output_setup(["tcp_offset"], ["VECTOR6D"], frequency=10) or not connection.send_start():
            raise RuntimeError("Il controller non espone il TCP attivo")
        sample = connection.receive()
        if sample is None:
            raise RuntimeError("Lettura del TCP attivo fallita")
        return [float(value) for value in sample.tcp_offset]
    finally:
        connection.disconnect()


def require_calibration_for_robot(address):
    calibration = load_calibration()
    if calibration is None:
        raise RuntimeError("Calibra a8, h8, a1 e vassoio prima di collegare il robot")
    if calibration["robot_ip"] != address:
        raise RuntimeError("La calibrazione appartiene a un altro IP robot")
    if read_robot_serial(address) != calibration["serial"]:
        raise RuntimeError("La calibrazione appartiene a un altro controller")
    if not np.allclose(read_robot_tcp_offset(address), calibration["tcp_offset"], atol=0.002):
        raise RuntimeError("Il TCP attivo è cambiato dalla calibrazione della punta")
    return calibration


def load_calibration(path=CALIBRATION_FILE):
    if not Path(path).is_file():
        return None
    return validate_calibration(json.loads(Path(path).read_text(encoding="utf-8")))


def save_calibration(data, path=CALIBRATION_FILE):
    validated = validate_calibration(data)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(validated, indent=2), encoding="utf-8")
    temporary.replace(target)
    return validated
