camera_ip = 'http://192.168.1.43:8080/video'    #ip of camera 
robot_ip = "192.168.1.100"                      #ip of robot arm

robotExists = 0                                 #define whether the arm is connected or not to prevent crashes (0 for debug without arm)
debug = 1

time_limit = 1.000                              #max time for stockfish call

rook_height = 25
knight_height = 30
bishop_height = 20
queen_height = 35
king_height = 30

checkboard_coord_start = [100, 150, 20]             #x and y position of arm grabbing the upper left piece, using tallest piece
checkboard_coord_end =  [310, 360, 20]              #x and y position of arm grabbing the lower right piece, using tallest piece
travel_offset = 50                                  #distance from grip point of piece when travelling

home_position = [0.2, -0.2, 0.2, -1.0, -1.57, 0.0]