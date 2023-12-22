import time
from urx import Robot
from config import travel_offset, home_position, arm_acceleration, arm_velocity
from robotiq_two_finger_gripper import Robotiq_Two_Finger_Gripper

def movePiece(robot, initial_position, target_position):
    gripper = Robotiq_Two_Finger_Gripper(robot)
    
    # Move to the initial position with travel_offset
    travel_start_position = initial_position
    travel_start_position[2] += travel_offset
    robot.movep(travel_start_position, acc = arm_acceleration, vel = arm_velocity)

    # Open the gripper
        #robot.set_digital_out(0, True)  # Assuming digital output 0 controls gripper open
    gripper.open_gripper()
    # Move the gripper down (adjust as needed)
    robot.movep(initial_position, acc = arm_acceleration, vel = arm_velocity)

    # Close the gripper
        #robot.set_digital_out(0, False)  # Assuming digital output 0 controls gripper close
    gripper.close_gripper()
    # Move the gripper up
    robot.movep(travel_start_position, acc = arm_acceleration, vel = arm_velocity)

    # Move to the target position
    travel_target_position = target_position
    travel_target_position[2] += travel_offset
    robot.movep(travel_target_position, acc = arm_acceleration, vel = arm_velocity)
    
    # Move the gripper down (adjust as needed)
    robot.movep(target_position, acc = arm_acceleration, vel = arm_velocity)

    # Open the gripper
        #robot.set_digital_out(0, True)
    gripper.open_gripper()
    # Move the gripper up (adjust as needed)
        #robot.translate_tool((0, 0, 0.1), acc=0.1, vel=0.02)
    robot.movep(target_position, acc = arm_acceleration, vel = arm_velocity)

    # Move the arm to home
    robot.movej(home_position, acc = arm_acceleration, vel = arm_velocity)

    # Close the connection
        #robot.close()