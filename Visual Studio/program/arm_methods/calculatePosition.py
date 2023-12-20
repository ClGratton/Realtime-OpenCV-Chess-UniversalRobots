import time
from urx import Robot
from config import checkboard_coord_start, checkboard_coord_end, rook_height, knight_height, bishop_height, queen_height, king_height, travel_offset

check_lenght = abs(checkboard_coord_start[0]-checkboard_coord_end[0])/7    #since coord start and end where the piece lies, the center of the check, the lenght between them is effectively deminished by 2 half checks, so one check less which means deviding by 7 instead of 8
check_height = abs(checkboard_coord_start[1]-checkboard_coord_end[1])/7

def calculatePosition(piece, initial_check, target_check):
    if piece == 'r' or piece == 'R':
        piece_height = rook_height
    elif piece == 'n' or piece == 'N':
        piece_height = knight_height
    elif piece == 'b' or piece == 'B':
        piece_height = bishop_height
    elif piece == 'q' or piece == 'Q':
        piece_height = queen_height
    elif piece == 'k' or piece == 'K':
        piece_height = king_height
    else:
        print('error selecting piece height')

    initial_check_x = initial_check[1]
    initial_check_y = initial_check[0]
    target_check_x = target_check[1]
    target_check_y = target_check[0]
    
    print(initial_check_x,initial_check_y,target_check_x,target_check_y,checkboard_coord_start[0],checkboard_coord_start[1])
    #calculate xi,yi,zi 

    xi= int(checkboard_coord_start[0] + (7 - initial_check_x)*check_lenght)
    yi= int(checkboard_coord_start[1] + (7 - initial_check_y)*check_lenght)
    zi= checkboard_coord_start[2]-piece_height
    initial_position = [xi, yi, zi]
    
    #calculate xt,yt,zt 
    xt= int(checkboard_coord_start[0] + (7 - target_check_x)*check_lenght)
    yt= int(checkboard_coord_start[1] + (7 - target_check_y)*check_lenght)
    zt= checkboard_coord_end[2]-piece_height

    target_position = [xt, yt, zt]

    return initial_position, target_position