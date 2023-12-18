import os
import chess
import chess.engine
import cv2
import numpy as np
import time
from urx import Robot
from program.image_methods.detect_points import get_points
from program.image_methods.read_warp_img import get_warp_img
from program.image_methods.find_position_black import find_current_past_position
from program.arm_methods.calculatePosition import calculatePosition
from program.arm_methods.movePiece import movePiece

robot_ip = "192.168.1.100"   
robot = Robot(robot_ip)

position1_box = [0, 0]
position2_box = [0, 0]
piece_height = 10

initial_position, target_position = calculatePosition(position1_box, position2_box)
print('arm is connected, moving selected piece')
movePiece(robot, piece_height, initial_position, target_position)