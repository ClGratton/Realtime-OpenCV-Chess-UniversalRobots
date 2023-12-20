import time
from urx import Robot
from config import travel_offset, home_position

def movePiece(robot, initial_position, target_position):

    # Move to the initial position with travel_offset
    travel_start_position = initial_position
    travel_start_position[2] += travel_offset
    robot.movel(travel_start_position, acc=0.5, vel=0.1)

    # Open the gripper
    robot.set_digital_out(0, True)  # Assuming digital output 0 controls gripper open

    # Move the gripper down (adjust as needed)
    #robot.translate_tool((0, 0, -0.1), acc=0.1, vel=0.02)
    robot.movel(initial_position, acc=0.5, vel=0.1)

    # Close the gripper
    robot.set_digital_out(0, False)  # Assuming digital output 0 controls gripper close
   
    # Move the gripper up
    robot.movel(travel_start_position, acc=0.5, vel=0.1)

    # Move to the target position
    travel_target_position = target_position
    travel_target_position[2] += travel_offset
    robot.movel(travel_target_position, acc=0.5, vel=0.1)
    # Move the gripper down (adjust as needed)
    robot.movel(target_position, acc=0.5, vel=0.1)

    # Open the gripper
    robot.set_digital_out(0, True)

    # Move the gripper up (adjust as needed)
    #robot.translate_tool((0, 0, 0.1), acc=0.1, vel=0.02)
    robot.movel(target_position, acc=0.5, vel=0.1)

    # Move the arm to home
    robot.movej(home_position, acc=0.5, vel=0.1)

    # Close the connection
    #robot.close()