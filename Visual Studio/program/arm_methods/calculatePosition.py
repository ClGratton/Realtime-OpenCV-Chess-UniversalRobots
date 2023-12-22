import time
from urx import Robot
from arm_methods.getPieceOffset import getPieceOffset

def calculatePosition(piece, main_checkboard_coord_start, main_checkboard_coord_end, initial_check, target_check):

    check_lenght = abs(main_checkboard_coord_start[0] - main_checkboard_coord_end[0])/7    #since coordinates start and end where the piece lies, the center of the check, the lenght between them is effectively deminished by 2 half checks, one check less, which means deviding by 7 instead of 8
    check_height = abs(main_checkboard_coord_start[1] - main_checkboard_coord_end[1])/7

    piece_offset = getPieceOffset(piece)

    initial_check_x = initial_check[1]
    initial_check_y = initial_check[0]
    target_check_x = target_check[1]
    target_check_y = target_check[0]
    
    #print(initial_check_x,initial_check_y,target_check_x,target_check_y,checkboard_coord_start[0],checkboard_coord_start[1])

    #calculate xi,yi,zi 
    xi = main_checkboard_coord_start[0] + (7 - initial_check_x)*check_lenght
    yi = main_checkboard_coord_start[1] + (7 - initial_check_y)*check_lenght
    zi = main_checkboard_coord_start[2] - piece_offset
    
    initial_position = main_checkboard_coord_start[0] 
    initial_position[0] = xi
    initial_position[1] = yi
    initial_position[2] = zi

    #calculate xt,yt,zt 
    xt = main_checkboard_coord_start[0] + (7 - target_check_x)*check_lenght
    yt = main_checkboard_coord_start[1] + (7 - target_check_y)*check_lenght
    zt = main_checkboard_coord_end[2] - piece_offset

    target_position = main_checkboard_coord_start[0] 
    target_position[0] = xt
    target_position[1] = yt
    target_position[2] = zt

    return initial_position, target_position