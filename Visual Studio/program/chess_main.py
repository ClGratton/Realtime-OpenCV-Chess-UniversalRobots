###################################################################################
## Import Libraries
###################################################################################
import os
import chess
import chess.engine
import cv2
import numpy as np
import time
from urx import Robot

usb_camera_index = 0
cap = cv2.VideoCapture(usb_camera_index)
###################################################################################
## Import files
###################################################################################
from image_methods.detect_points import get_points
from image_methods.read_warp_img import get_warp_img
from image_methods.find_position_black import find_current_past_position
from arm_methods.calculatePosition import calculatePosition
from arm_methods.movePiece import movePiece
from config import camera_ip, robot_ip, robotExists, debug, time_limit, highest_piece, eaten_position, checkboard_coord_start, checkboard_coord_end
from program.arm_methods.getPieceOffset import getPieceHeight
###################################################################################
## User defined variables
###################################################################################


###################################################################################
## Define Main Variables
###################################################################################
points = []    # contains chess board corners points
boxes = np.zeros((8,8,4),dtype=int)    # contains top-left and bottom-right point of chessboard boxes
fen_line = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR' # fen line of chess board
board = chess.Board(fen=fen_line) # object of chess board
dir_path = os.path.dirname(os.path.realpath(__file__))+"/numpy_saved" # path of current directory
check_lenght = 0
check_height = 0
# device = cv2.VideoCapture(1) # set devidce for read image (1: for tacking input from usb-webcam)
img_resize = (800,800) # set o/p image size
image = []
engine = chess.engine.SimpleEngine.popen_uci("C:\stockfish_16\stockfish-windows-x86-64-avx2.exe") # stockfish engine
chess_board = []   # it will store chess board matrix
player_bool_position =[]
bool_position = np.zeros((8,8),dtype=int)
number_to_position_map = []
last_move = ""
game_img = ""
move_was_castling = 0
###################################################################################
## Code For Run Program
###################################################################################

print("Enter Configuration Name: ")
code = str(input())
dir_path += "/"+code
if not os.path.exists(dir_path):
    os.makedirs(dir_path)


###################################################################################
## Define Functions
###################################################################################

## map function for map values for (0,0)-> (8,a) , (0,1)-> (8,b).... so on 
def map_function():
    map_position = {}
    x,y=0,0
    for i in "87654321":
        for j in "abcdefgh":
            map_position[j+i] = [x,y]
            y = (y+1)%8
        x = (x+1)%8
    np.savez(dir_path+"/map_position.npz",**map_position)
map_function()
map_position =np.load(dir_path+"/map_position.npz")   # map move values for (0,0)-> (8,a) , (0,1)-> (8,b).... so on


def fen2board(fen_line):
    # Convert a FEN string to a list of board rows
    rows = fen_line.split(' ')[0].split('/')

    # Convert each FEN row to a board row
    chess_board = [list(cell) if cell.isalpha() else ['1'] * int(cell) for row in rows for cell in row]

    # Flatten the lists to ensure consistent lengths
    flattened_chess_board = [cell for sublist in chess_board for cell in sublist]
    current_player_bool_position = [1 if cell != '1' else 0 for sublist in chess_board for cell in sublist]

    return np.array(flattened_chess_board).reshape(8, 8), np.array(current_player_bool_position).reshape(8, 8)

 
def board2fen(chess_board):
    board_array = chess_board
    fen_line = ''
    count = 0
    for i in range(8):
        empty = 0
        for j in range(8):
            if board_array[i][j].isnumeric():
                empty+=1
            else:
                if empty != 0:
                    fen_line+= str(empty)+ str(board_array[i][j])
                    empty = 0
                else:
                    fen_line += str(board_array[i][j])
        if empty != 0:
            fen_line += str(empty)
        if count != 7:
            fen_line += str('/')
            count +=1
    fen_line += " w KQkq - 0 1"
    return fen_line


def map_function_for_number_2_position():
    str1 = "87654321"
    str2 = "abcdefgh"
    for i in range(8):
        temp=[]
        for j in range(8):
            temp.append(str(str2[j]+str1[i]))
        number_to_position_map.append(temp)
map_function_for_number_2_position()            


def rectContains(rect,mid_point):
    logic = rect[0]<mid_point[0]<rect[2] and rect[1]<mid_point[1]<rect[3]
    return logic


def nothing(X):
    pass



def thresold_calibration(img):
    cv2.namedWindow("thresold_calibration")
    cv2.createTrackbar("thresold", "thresold_calibration", 0, 255, nothing)
    while True:
        t =  cv2.getTrackbarPos("thresold", "thresold_calibration")
        matrix,thresold = cv2.threshold(img,t,255,cv2.THRESH_BINARY_INV)
        cv2.imshow("thresold",thresold)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            return t

def fen2board_2(fen_line):
    chess_board = [] 
    for row in fen_line.split(' ')[0].split('/'):
        chess_row = []
        for cell in list(row):
            if cell.isnumeric():
                for i in range(int(cell)):
                    chess_row.append(str(' '))
            else:
                chess_row.append(cell)
        chess_board.append(chess_row)
    chess_board = np.array(chess_board)
    return chess_board

def map_move_to_number(move):
    map_num = 0
    for i in "12345678":
        for j in "abcdefgh":
            if move == str(j)+str(i):
                return map_num
            else:
                map_num += 1

def show_game(game_img,board,player_move):
    side_img = np.zeros((800,800,3),dtype=np.uint8)
    game_img = np.concatenate((game_img, side_img), axis=1)
    overlay = game_img.copy()
    cv2.putText(game_img,"Player Turn : ",(830,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
    if board.turn == 1:
        cv2.putText(game_img,"White ",(1050,30),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        cv2.putText(game_img,"Press",(830,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        cv2.putText(game_img,"'W'",(925,80),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
        cv2.putText(game_img," when player moved ",(960,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    else:
        cv2.putText(game_img,"black ",(1050,30),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        cv2.putText(game_img,"Press",(830,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        cv2.putText(game_img,"'Q'",(925,80),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
        cv2.putText(game_img," when player moved ",(960,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    
    chess_board = fen2board_2(str(board.fen()))
    padding_col = 0
    for i in chess_board:  
        padding_row = 0
        for j in i:
            if str(j).isupper():
                cv2.putText(game_img,"{}".format(j),(padding_row+850,padding_col+140),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
            else:
                cv2.putText(game_img,"{}".format(j),(padding_row+850,padding_col+140),cv2.FONT_HERSHEY_SIMPLEX,1,(255,0,0),2)
            padding_row += 40
        padding_col += 40
    player_move = str(player_move)
    if not (len(player_move) == 0):
        cv2.putText(game_img,"Opponent's last move : ",(830,480),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        cv2.putText(game_img,"{}".format(player_move),(1210,480),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)

        if board.turn == 1:
            cv2.putText(game_img,"{}".format(board.piece_at(map_move_to_number(player_move[2:4]))),(830,530),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        else:
            cv2.putText(game_img,"{}".format(board.piece_at(map_move_to_number(player_move[2:4]))),(830,530),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
        cv2.putText(game_img," Moved from ",(850,530),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        cv2.putText(game_img,"{}".format(player_move[0:2]),(1070,530),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,255),2)
        cv2.putText(game_img," to ",(1100,530),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        cv2.putText(game_img,"{}".format(player_move[2:4]),(1155,530),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,255),2)

        position1 = player_move[0:2]
        position2 = player_move[2:4]

        box_1_coordinate = map_position[position1]
        box_2_coordinate = map_position[position2]
        
        position1_box = boxes[box_1_coordinate[0]][box_1_coordinate[1]]
        position2_box = boxes[box_2_coordinate[0]][box_2_coordinate[1]]

        draw_img = img.copy()
        cv2.rectangle(overlay,(position1_box[0],position1_box[1]),(position1_box[2],position1_box[3]),(0,0,255),-1)
        cv2.rectangle(overlay,(position2_box[0],position2_box[1]),(position2_box[2],position2_box[3]),(0,255,255),-1)
        cv2.addWeighted(overlay,0.3,game_img,0.7,0,game_img)

    cv2.putText(game_img,"is_check : ",(830,580),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    cv2.putText(game_img,"{}".format(board.is_check()),(1000,580),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)

    cv2.putText(game_img,"is_check mate : ",(830,620),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    cv2.putText(game_img,"{}".format(board.is_checkmate()),(1090,620),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)

    cv2.imshow("Game",game_img)
    

def set_legal_positions(game_image,board,boxes):
    side_img = np.zeros((800,800,3),dtype=np.uint8)
    game_img = np.concatenate((game_image, side_img), axis=1)
    chess_board,_ = fen2board(str(board.fen()))
    for i in range(8):
        for j in range(8):
            if not chess_board[i][j] == str(1):
                box1 = boxes[i,j]
                cv2.rectangle(game_img, (int(box1[0]), int(box1[1])), (int(box1[2]), int(box1[3])), (255,0,0), 2)
                cv2.putText(game_img," {}".format(chess_board[i][j]),(int(box1[2])-70, int(box1[3])-50),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,255),2)
    
    cv2.putText(game_img,"illegal move ",(830,30),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
    cv2.putText(game_img,"White ",(1050,30),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    cv2.putText(game_img,"Press",(830,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    cv2.putText(game_img,"S",(925,80),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
    cv2.putText(game_img," when All player Set ",(960,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    
    chess_board = fen2board_2(str(board.fen()))
    padding_col = 0
    for i in chess_board:  
        padding_row = 0
        for j in i:
            if str(j).isupper():
                cv2.putText(game_img,"{}".format(j),(padding_row+850,padding_col+140),cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)
            else:
                cv2.putText(game_img,"{}".format(j),(padding_row+850,padding_col+140),cv2.FONT_HERSHEY_SIMPLEX,1,(255,0,0),2)
            padding_row += 40
        padding_col += 40

    cv2.imshow("Game",game_img)
    print("Press 's' after your move")
    while True:
        if cv2.waitKey(1) == ord('s'):
            break
    

###################################################################################
## camara position calibration
###################################################################################

while True:
    print("Set camera position?[y/n] : ",end=" ")
    answer = str(input())
    if answer == "y" or answer == "Y":
        print("Press q to exit : ")
        while True:
            ## show frame from camera and set positon by moving camera
            flag , img = cv2.VideoCapture(camera_ip).read()
            img = cv2.resize(img,img_resize)
            if flag:
                cv2.imshow("Set camera position",img)
                k = cv2.waitKey(1)
                if k == ord('q'):
                    cv2.destroyAllWindows()
                    break
        break
    elif answer == "n" or answer == "N":
        break
    else:
        print("Invalid Input ")



###################################################################################
## Image warp_prespective
###################################################################################

while True:
    print("Warp perspective of the image?[y/n]:", end=" ")
    answer = str(input())
    ret, img = cv2.VideoCapture(camera_ip).read()
    img = cv2.resize(img, (800, 800))
    width, height = 800, 800

    if answer.lower() == "y":
        #print("Image Shape:", img.shape)
        warp_points = get_points(img, 4)
        #print("Warp Points:", warp_points)

        pts1 = np.float32([[warp_points[0][0], warp_points[0][1]],
                           [warp_points[1][0], warp_points[1][1]],
                           [warp_points[3][0], warp_points[3][1]],
                           [warp_points[2][0], warp_points[2][1]]])

        pts2 = np.float32([[0, 0], [width, 0], [0, height], [width, height]])
        #print("pts1:", pts1)
        #print("pts2:", pts2)

        np.savez(dir_path + "/chess_board_warp_prespective.npz", pts1=pts1, pts2=pts2)
        result = get_warp_img(img, dir_path, img_resize)
        cv2.imshow("result", result)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        break
    elif answer.lower() == "n":
        result = get_warp_img(img, dir_path, img_resize)
        break
    else:
        print("Enter valid input")



###################################################################################
## calibrate points for chess corners
###################################################################################
while True:
        print("Calibrate new points for checks?[y/n]:",end=" ")
        ans = str(input())
        if ans == "y" or ans == "Y":
            ret , img = cv2.VideoCapture(camera_ip).read()
            img =   cv2.resize(img,(800,800))
            img = get_warp_img(img,dir_path,img_resize)
            # Chessboard square size
            square_size = 100

            # Initialize points list
            points = []

            # Iterate over rows
            for i in range(9):
                # Initialize row points list
                row_points = []
                
                # Iterate over columns
                for j in range(9):
                    # Add points based on chessboard square size
                    row_points.append([j * square_size, i * square_size])
                
                # Add row points to the main points list
                points.append(row_points)

            # Print the generated points
            #print("Generated Points:", points)
            np.savez(dir_path+"/chess_board_points.npz",points=points)
            break
        elif ans == "n" or ans == "N":
            # do some work
            points = np.load(dir_path+'/chess_board_points.npz')['points']
            print("Points loaded succesfully")
            break
        else:
            print("Enter a valid input")


###################################################################################
## Define Boxes
###################################################################################
for i in range(8):
    for j in range(8):
        boxes[i][j][0] = points[i][j][0]
        boxes[i][j][1] = points[i][j][1]
        boxes[i][j][2] = points[i+1][j+1][0]
        boxes[i][j][3] = points[i+1][j+1][1]

np.savez(dir_path+"/chess_board_Box.npz",boxes=boxes)

###################################################################################
## View Boxes
###################################################################################
while True:
    print("Debug boxes on Chess board?[y/n]:",end=" ")
    ans = str(input())
    if ans == 'y' or ans == "Y":
        # show boxes
        ret , img = cv2.VideoCapture(camera_ip).read()
        img =   cv2.resize(img,(800,800))
        img = get_warp_img(img,dir_path,img_resize)
        img_box = img.copy()
        for i in range(8):
            for j in range(8):
                box1 = boxes[i,j]
                cv2.rectangle(img_box, (int(box1[0]), int(box1[1])), (int(box1[2]), int(box1[3])), (255,0,0), 2)
                cv2.putText(img_box,"({},{})".format(i,j),(int(box1[2])-70, int(box1[3])-50),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,255),2)
                cv2.imshow("img",img_box)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        break
    elif ans == 'N' or ans == "n":
        break
    else:
        print("Enter valid input")


###################################################################################
## Load Past Game
###################################################################################
while True:
        print("Load Past Game?[y/n]:",end=" ")
        ans = str(input())
        if ans == "y" or ans == "Y":
            chess_board = np.load(dir_path+'/fen_line_board.npz')['chess_board']
            player_bool_position = np.load(dir_path+'/fen_line_board.npz')['player_bool_position']
            white_turn = np.load(dir_path+'/fen_line_board.npz')['white_turn']
            last_move = np.load(dir_path+'/fen_line_board.npz')['last_move']
            fen_line = board2fen(chess_board)
            board = chess.Board(fen=fen_line)
            
            if white_turn == 1:
                board.turn = True
            else:
                board.turn = False

            ret,img = cv2.VideoCapture(camera_ip).read()
            img = cv2.resize(img,(800,800))
            img = get_warp_img(img,dir_path,img_resize)
            img_box = img.copy()
            for i in range(8):
                for j in range(8):
                    if not chess_board[i][j] == str(1):
                        box1 = boxes[i,j]
                        cv2.rectangle(img_box, (int(box1[0]), int(box1[1])), (int(box1[2]), int(box1[3])), (255,0,0), 2)
                        cv2.putText(img_box," {}".format(chess_board[i][j]),(int(box1[2])-70, int(box1[3])-50),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,0,255),2)
            cv2.imshow("Game",img_box)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            print(last_move)
            show_game(img,board,last_move)
            break
        elif ans == "n" or ans == "N":
            chess_board,player_bool_position = fen2board(board.fen())
            np.savez(dir_path+"/fen_line_board.npz",chess_board=chess_board,player_bool_position=player_bool_position)
            print("Loaded succesfully")
            break
        else:
            print("Enter a valid input")
###################################################################################
## Arm setup
###################################################################################
if robotExists:
    # Connect to the robot
    robot = Robot(robot_ip)
    count=0
    
    #check if the upper left coordinate in config.py is null. If it is, setup is initiated
    for x in checkboard_coord_start:
        if x == 0:
            count += 1
    
    if count == len(checkboard_coord_start):
        print("Move the arm to the upper left corner while grabbing the highest piece, then press q")
        while True:
            if cv2.waitKey(1) == ord('q'):
                break
        main_checkboard_coord_start = robot.getl()
    else:
        main_checkboard_coord_start = checkboard_coord_start

    #check if the bottom left coordinate in config.py is null. If it is, setup is initiated
    for x in checkboard_coord_end:
        if x == 0:
            count += 1
    
    if count == len(checkboard_coord_end):
        print("Move the arm to the bottom left corner while grabbing the highest piece, then press q")
        while True:
            if cv2.waitKey(1) == ord('q'):
                break
        main_checkboard_coord_end = robot.getl()
    else:
        main_checkboard_coord_end = checkboard_coord_end
###################################################################################
## Start Game
###################################################################################

while 1:

    ## white turn 
    print("turn:", board.turn)
    if board.turn and board.is_checkmate() == False:
        ret , img = cv2.VideoCapture(camera_ip).read()
        img =   cv2.resize(img,(800,800))
        img = get_warp_img(img,dir_path,img_resize)
        chess_board,player_bool_position = fen2board(board.fen())
        result = engine.play(board, chess.engine.Limit(time_limit)) 

        position1 = str(result.move)[0:2]
        position2 = str(result.move)[2:4]
        
        box_1_coordinate = map_position[position1]  #starting position in format [0 7]
        box_2_coordinate = map_position[position2]  #end position in format [0 7]

        position1_box = boxes[box_1_coordinate[0]][box_1_coordinate[1]]
        position2_box = boxes[box_2_coordinate[0]][box_2_coordinate[1]]

        draw_img = img.copy()
        cv2.rectangle(draw_img,(position1_box[0],position1_box[1]),(position1_box[2],position1_box[3]),(0,0,255),3)
        cv2.rectangle(draw_img,(position2_box[0],position2_box[1]),(position2_box[2],position2_box[3]),(0,255,0),3)
        
        show_game(draw_img,board,last_move)

        board.push(result.move)
        last_move = str(result.move)
        
        if debug:
            print(box_1_coordinate)
            print(box_2_coordinate)
            print(chess_board)

        piece = chess_board[box_1_coordinate[0], box_1_coordinate[1]]
        eaten_piece = chess_board[box_2_coordinate[0],box_2_coordinate[1]]
        
        if eaten_piece !=1:     #get rid of eaten piece
            
            initial_position, target_position = calculatePosition(eaten_piece, box_1_coordinate, box_2_coordinate)
            initial_position = target_position
            eaten_piece_height = getPieceHeight(eaten_piece)
            eaten_position[2] = eaten_position[2] - (highest_piece - eaten_piece_height)
            target_position = eaten_position

            print("initial_position:",initial_position, "target_position:",target_position)
        
            if robotExists:
                print('Arm is connected, moving selected piece...')
                # movePiece(robot, initial_position, target_position)
            
        print("piece:",piece, "box_1_coordinate:",box_1_coordinate, "box_2_coordinate:",box_2_coordinate)
        initial_position, target_position = calculatePosition(piece, main_checkboard_coord_start, main_checkboard_coord_end, box_1_coordinate, box_2_coordinate)
        print("initial_position:",initial_position, "target_position:",target_position)
        
        if robotExists:
            print('Arm is connected, moving selected piece...')
            movePiece(robot, initial_position, target_position)
        
        print("Press 'w' when you moved")
        while True:
            if cv2.waitKey(1) == ord('w'):
                break
        chess_board,player_bool_position = fen2board(board.fen())
        
        np.savez(dir_path+"/fen_line_board.npz",chess_board=chess_board,player_bool_position=player_bool_position,white_turn=0,last_move=last_move)

    ## black turn
    flag = 0
    print("turn:", board.turn)
    if board.turn == False and board.is_checkmate() == False:
        chess_board,bool_position = fen2board(board.fen())

        ##show chessboard image
        ret , img_1 = cv2.VideoCapture(camera_ip).read()
        img_1 =   cv2.resize(img_1,(800,800))
        img_1 = get_warp_img(img_1,dir_path,img_resize)
        show_game(img_1,board,last_move)

        print("Player's turn : ")
        print("Press 'q' when you moved ")
        
        #capture chessboard with new black move
        while True:
            if cv2.waitKey(1) == ord('q'):
                break
        try:
            ret , img_2 = cv2.VideoCapture(camera_ip).read()
            img_2 =   cv2.resize(img_2,(800,800))
            img_2 = get_warp_img(img_2,dir_path,img_resize)
        except:
            print("Connection to camera failed, retying...")
            while True:
                if cv2.VideoCapture(camera_ip).read() != 0:
                    ret , img_2 = cv2.VideoCapture(camera_ip).read()
                    img_2 =   cv2.resize(img_2,(800,800))
                    img_2 = get_warp_img(img_2,dir_path,img_resize)
                    break
        
        #find what move has been executed by black
        try:
            move_word,game_img,flag = find_current_past_position(img_1,img_2,boxes,bool_position,board.fen(),chess_board,number_to_position_map,map_position)
        except:
            # no new move has been detected
            print('no new move has been detected')
            set_legal_positions(img_2,board,boxes)
        
        if flag:
            move = chess.Move.from_uci(str(move_word))
            print("move:", move)
            print("board:\n", board)
            if move in board.legal_moves:      
                board.push(move)
                last_move = str(move_word)
                show_game(game_img,board,last_move)
                print("Done")
                chess_board,player_bool_position = fen2board(board.fen())
                np.savez(dir_path+"/fen_line_board.npz",chess_board=chess_board,player_bool_position=player_bool_position,white_turn=1,last_move=last_move)
            else:
                # not a legal move
                print('Not a legal move')
                
                #reset to make castling work on next turn (unsure why)
                chess_board = np.load(dir_path+'/fen_line_board.npz')['chess_board']
                player_bool_position = np.load(dir_path+'/fen_line_board.npz')['player_bool_position']
                white_turn = np.load(dir_path+'/fen_line_board.npz')['white_turn']
                last_move = np.load(dir_path+'/fen_line_board.npz')['last_move']
                fen_line = board2fen(chess_board)
                board = chess.Board(fen=fen_line)
                board.turn = False
                set_legal_positions(img_2,board,boxes)
                
                #turn: False
                #Player's turn : 
                #Press 'q' when you moved
                #move: e8g8
                #board:
                # r n b q k . . r
                #p p p p b p p p
                #. . . . p . . B
                #. . . . . . . .
                #. . . P P . . .
                #. . . . . N . .
                #P P P . . P P P
                #R N . Q K B . R
                #Not a legal move
                #Press 's' after your move
                #
                #turn: False
                #turn: False
                #Player's turn : 
                #Press 'q' when you moved
                #move: e8g8
                #board:
                # r n b q k . . r
                #p p p p b p p p
                #. . . . p . . B
                #. . . . . . . .
                #. . . P P . . .
                #. . . . . N . .
                #P P P . . P P P
                #R N . Q K B . R
                #Done
                #press q after castling...
                
        else:
            try:
                show_game(game_img,board,last_move)
            except:
                #turn is 0
                print('zero-dimensional arrays cannot be concatenated')
        try:
            if move_word=='e8c8' or move_word=='e8g8':
                move_was_castling += 1
                if move_was_castling == 2:
                    move_was_castling = 0
                    print('press q after castling...')
                    
                    #acts as debounce
                    while True:                         
                        key = cv2.waitKey(1) & 0xFF     
                        if  key != ord("q"):         
                                break
                    #wait for castle to be executed
                    while True:
                        if cv2.waitKey(1) == ord('q'):
                            break
        except:
            #move_word is not defined
            print('move word not defined')
   
    if board.is_checkmate():
        print("Checkmate!")
        ret , img = cv2.VideoCapture(camera_ip).read()
        img_1 =   cv2.resize(img,(800,800))
        game_img = get_warp_img(img_1,dir_path,img_resize)
        show_game(game_img,board,last_move)
        cv2.waitKey(0)
        break

print("Exit")
cv2.destroyAllWindows()