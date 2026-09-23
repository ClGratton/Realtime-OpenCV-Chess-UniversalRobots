"""Blocking URX motion sequence for picking and placing one chess piece."""
from math import isfinite

from config import travel_offset, home_position, arm_acceleration, arm_velocity
from arm_methods.robotiq_two_finger_gripper import Robotiq_Two_Finger_Gripper


def _pose(values, name):
    pose = [float(value) for value in values]
    if len(pose) != 6 or not all(isfinite(value) for value in pose):
        raise ValueError(f"{name} must be a finite six-value UR pose.")
    return pose


def _approach(pose):
    approach = list(pose)
    approach[2] += travel_offset
    return approach


def _movel(robot, pose):
    # URX movel accepts a base-frame [x, y, z, rx, ry, rz] pose.
    # wait=True prevents the next gripper action from racing the motion.
    robot.movel(list(pose), acc=arm_acceleration, vel=arm_velocity, wait=True)


def movePiece(robot, initial_position, target_position):
    """Pick a piece, transfer it above the board, and place it.

    Inputs are copied so calibrated positions are never mutated by a move.
    """
    source = _pose(initial_position, "initial_position")
    target = _pose(target_position, "target_position")
    home = _pose(home_position, "home_position")
    if travel_offset <= 0:
        raise ValueError("travel_offset must be a positive distance in metres.")

    source_approach = _approach(source)
    target_approach = _approach(target)
    gripper = Robotiq_Two_Finger_Gripper(robot)

    _movel(robot, source_approach)
    gripper.open_gripper()
    _movel(robot, source)
    gripper.close_gripper()
    _movel(robot, source_approach)
    _movel(robot, target_approach)
    _movel(robot, target)
    gripper.open_gripper()
    _movel(robot, target_approach)
    _movel(robot, home)
