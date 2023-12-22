camera_ip = 'http://192.168.1.43:8080/video'    #ip of camera 
robot_ip = "192.168.1.100"                      #ip of robot arm

robotExists = 0                                 #define whether the arm is connected or not to prevent crashes (0 for debug without arm)
debug = 0

time_limit = 1.000                              #max time for stockfish call

rook_offset = 10
knight_offset = 10
bishop_offset = 10
queen_offset = 5
king_offset = 0
pawn_offset = 20

highest_piece = king_offset
eaten_position = [0,0,0]

checkboard_coord_start = [0, 0, 0, 0, 0, 0]             #x and y position of arm grabbing the upper left piece, using tallest piece
checkboard_coord_end =  [0, 0, 0, 0, 0, 0]              #x and y position of arm grabbing the lower right piece, using tallest piece
travel_offset = 50                                  #distance from grip point of piece when travelling

arm_acceleration = 0.1
arm_velocity = 0.07

home_position = [0.2, -0.2, 0.2, -1.0, -1.57, 0.0]