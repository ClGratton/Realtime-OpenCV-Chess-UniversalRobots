###################################################################################
## Import Libraries
###################################################################################
import os
import shutil
import atexit
from pathlib import Path
import chess
import chess.engine
import cv2
import numpy as np
import time
from urx import Robot

###################################################################################
## Import files
###################################################################################
from image_methods.detect_points import get_points
from image_methods.board_tracker import BoardTracker, BoardTrackingError
from image_methods.find_position_black import infer_human_move, MoveDetectionError
from arm_methods.calculatePosition import calculatePosition
from arm_methods.movePiece import movePiece
from config import camera_ip, robot_ip, robotExists, debug, time_limit, eaten_position, checkboard_coord_start, checkboard_coord_end
from arm_methods.getPieceOffset import getPieceOffset


_camera = None


def close_camera():
    global _camera
    if _camera is not None:
        _camera.release()
        _camera = None


atexit.register(close_camera)


def read_camera_frame(retries=3):
    """Read a live stream continuously; reconnect after dropped frames."""
    global _camera
    for attempt in range(retries):
        if _camera is None or not _camera.isOpened():
            close_camera()
            _camera = cv2.VideoCapture(camera_ip)
        if _camera.isOpened():
            ok, frame = _camera.read()
            if ok and frame is not None:
                return True, frame
        close_camera()
        time.sleep(0.25 * (attempt + 1))
    raise RuntimeError(f"Unable to read a frame from chess camera: {camera_ip}")


###################################################################################
## User defined variables
###################################################################################


###################################################################################
## Define Main Variables
###################################################################################
points = []    # contains chess board corners points
boxes = np.zeros((8,8,4),dtype=int)    # contains top-left and bottom-right point of chessboard boxes
board = chess.Board() # object of chess board
dir_path = os.path.dirname(os.path.realpath(__file__))+"/numpy_saved" # path of current directory
check_lenght = 0
check_height = 0
# device = cv2.VideoCapture(1) # set devidce for read image (1: for tacking input from usb-webcam)
img_resize = (800,800) # set o/p image size
image = []
def find_stockfish():
    configured = os.environ.get("STOCKFISH_PATH")
    candidates = [configured, shutil.which("stockfish"), shutil.which("stockfish.exe")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise FileNotFoundError(
        "Stockfish non trovato. Installa Stockfish e imposta STOCKFISH_PATH "
        "oppure aggiungi stockfish al PATH."
    )


engine = chess.engine.SimpleEngine.popen_uci(find_stockfish())
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
    
    cv2.putText(game_img,"Move not recognized",(830,30),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,0,255),2)
    cv2.putText(game_img,"Press",(830,80),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
    cv2.putText(game_img,"S",(925,80),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)
    cv2.putText(game_img," after restoring board ",(960,80),cv2.FONT_HERSHEY_SIMPLEX,0.8,(255,255,255),2)
    
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
    print("Press 's' after restoring the previous board position")
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
            flag , img = read_camera_frame()
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
## Live chessboard calibration
###################################################################################

tracker = BoardTracker(img_resize)
_, img = read_camera_frame()
img = cv2.resize(img, img_resize)
# Reuse of saved pixel coordinates is unsafe when the phone can move. Detect
# on the current frame; get_points offers manual corners if detection fails.
warp_points = get_points(img, 4)
while True:
    try:
        result = tracker.initialize(img, warp_points)
        break
    except BoardTrackingError as error:
        print(f"Invalid board calibration: {error}")
        _, img = read_camera_frame()
        img = cv2.resize(img, img_resize)
        warp_points = get_points(img, 4)
cv2.imshow("Board live", result)
cv2.waitKey(1)


def get_board_img(frame):
    return tracker.update(cv2.resize(frame, img_resize))


def relock_board():
    """Pause until the operator has restored the physical game and camera."""
    print("Board tracking lost. Do not move a piece or the robot.")
    print("Make the physical board match the displayed game and steady the phone;")
    print("you will identify the a8 corner after relocking,")
    print("then press 'r' in the camera window to find the board again.")
    while True:
        try:
            _, frame = read_camera_frame()
        except RuntimeError as error:
            print(f"Waiting for camera: {error}")
            time.sleep(0.5)
            continue
        frame = cv2.resize(frame, img_resize)
        cv2.imshow("Board live", frame)
        if cv2.waitKey(30) == ord('r'):
            corners = get_points(frame, 4)
            try:
                result = tracker.initialize(frame, corners)
            except BoardTrackingError as error:
                print(f"Board still cannot be locked: {error}")
                continue
            cv2.imshow("Board live", result)
            return result


def safe_board_img(frame):
    try:
        return get_board_img(frame)
    except BoardTrackingError as error:
        print(f"Camera view rejected: {error}")
        return relock_board()


def wait_for_key_tracking(key):
    """Keep locating the board during an operator's physical move."""
    first_failure_at = None
    while True:
        try:
            _, frame = read_camera_frame()
            view = get_board_img(frame)
        except (RuntimeError, BoardTrackingError) as error:
            if first_failure_at is None:
                first_failure_at = time.monotonic()
            if time.monotonic() - first_failure_at >= 1.0:
                print(f"Camera view rejected: {error}")
                relock_board()
                return None
            cv2.waitKey(30)
            continue
        first_failure_at = None
        cv2.imshow("Board live", view)
        if cv2.waitKey(1) == ord(key):
            return view



###################################################################################
## calibrate points for chess corners
###################################################################################
while True:
        print("Calibrate new points for checks?[y/n]:",end=" ")
        ans = str(input())
        if ans == "y" or ans == "Y":
            ret , img = read_camera_frame()
            img =   cv2.resize(img,(800,800))
            img = safe_board_img(img)
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
        ret , img = read_camera_frame()
        img =   cv2.resize(img,(800,800))
        img = safe_board_img(img)
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
            with np.load(dir_path+'/fen_line_board.npz', allow_pickle=False) as saved:
                if 'fen' not in saved.files:
                    raise RuntimeError(
                        "Old save has no full FEN: castling and en passant rights "
                        "cannot be restored safely. Start a new game."
                    )
                board = chess.Board(str(saved['fen'].item()))
                last_move = str(saved['last_move'].item())
            chess_board, player_bool_position = fen2board(board.fen())

            ret,img = read_camera_frame()
            img = cv2.resize(img,(800,800))
            img = safe_board_img(img)
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
            np.savez(
                dir_path+"/fen_line_board.npz",
                chess_board=chess_board,
                player_bool_position=player_bool_position,
                fen=board.fen(),
                last_move="",
            )
            print("Loaded succesfully")
            break
        else:
            print("Enter a valid input")
###################################################################################
## Arm setup
###################################################################################
main_checkboard_coord_start = list(checkboard_coord_start)
main_checkboard_coord_end = list(checkboard_coord_end)
if robotExists:
    # Connect to the robot
    robot = Robot(robot_ip)
    # An all-zero pose means calibration has not been saved. Check each pose
    # independently; sharing the old counter skipped the second calibration.
    if all(float(value) == 0.0 for value in checkboard_coord_start):
        print("Move the arm to the upper left corner while grabbing the highest piece, then press q")
        while True:
            if cv2.waitKey(1) == ord('q'):
                break
        main_checkboard_coord_start = robot.getl()
    else:
        main_checkboard_coord_start = list(checkboard_coord_start)

    if all(float(value) == 0.0 for value in checkboard_coord_end):
        print("Move the arm to the lower right corner while grabbing the highest piece, then press q")
        while True:
            if cv2.waitKey(1) == ord('q'):
                break
        main_checkboard_coord_end = robot.getl()
    else:
        main_checkboard_coord_end = list(checkboard_coord_end)
###################################################################################
## Start Game
###################################################################################

while not board.is_game_over(claim_draw=True):

    ## white turn 
    print("turn:", board.turn)
    if board.turn and board.is_checkmate() == False:
        ret , img = read_camera_frame()
        img =   cv2.resize(img,(800,800))
        img = safe_board_img(img)
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

        is_castling = board.is_castling(result.move)
        capture_square = result.move.to_square
        if board.is_en_passant(result.move):
            capture_square += -8 if board.turn == chess.WHITE else 8
        capture_square_name = chess.square_name(capture_square)
        capture_box_coordinate = map_position[capture_square_name]
        
        if debug:
            print(box_1_coordinate)
            print(box_2_coordinate)
            print(chess_board)

        piece = chess_board[box_1_coordinate[0], box_1_coordinate[1]]
        eaten_piece = chess_board[
            capture_box_coordinate[0], capture_box_coordinate[1]
        ]
        
        if str(eaten_piece) != "1":     # Move the captured piece to the configured tray.
            captured_position, _ = calculatePosition(
                eaten_piece,
                main_checkboard_coord_start,
                main_checkboard_coord_end,
                capture_box_coordinate,
                capture_box_coordinate,
            )
            target_position = [float(value) for value in eaten_position]
            target_position.extend(main_checkboard_coord_start[3:6])

            if robotExists:
                if target_position[:3] == [0.0, 0.0, 0.0]:
                    raise RuntimeError(
                        "Configura eaten_position in config.py prima di giocare "
                        "con il braccio attivo."
                    )
                print('Arm is connected, moving captured piece...')
                movePiece(robot, captured_position, target_position)
            
        print("piece:",piece, "box_1_coordinate:",box_1_coordinate, "box_2_coordinate:",box_2_coordinate)
        initial_position, target_position = calculatePosition(piece, main_checkboard_coord_start, main_checkboard_coord_end, box_1_coordinate, box_2_coordinate)
        print("initial_position:",initial_position, "target_position:",target_position)
        
        if robotExists:
            print('Arm is connected, moving selected piece...')
            movePiece(robot, initial_position, target_position)
            if is_castling:
                # The board state includes both castling pieces, so move the
                # rook physically after the king.
                rank = "1" if result.move.from_square < 8 else "8"
                king_target_file = chess.square_file(result.move.to_square)
                rook_from = ("h" if king_target_file == 6 else "a") + rank
                rook_to = ("f" if king_target_file == 6 else "d") + rank
                rook_piece = chess_board[
                    map_position[rook_from][0], map_position[rook_from][1]
                ]
                rook_start, rook_end = calculatePosition(
                    rook_piece,
                    main_checkboard_coord_start,
                    main_checkboard_coord_end,
                    map_position[rook_from],
                    map_position[rook_to],
                )
                movePiece(robot, rook_start, rook_end)
            if result.move.promotion:
                promoted = chess.piece_symbol(result.move.promotion).upper()
                print(f"Replace the pawn on {position2} with {promoted}, then press 'p'.")
                while cv2.waitKey(1) != ord('p'):
                    pass
        
        if not robotExists:
            print("Press 'w' after moving the piece manually")
            while True:
                if wait_for_key_tracking('w') is not None:
                    break
                print("Restore the position shown in the game, then make the AI move again.")
        # Advance the digital board only after the physical move is complete.
        board.push(result.move)
        last_move = result.move.uci()
        chess_board,player_bool_position = fen2board(board.fen())
        
        np.savez(dir_path+"/fen_line_board.npz",chess_board=chess_board,player_bool_position=player_bool_position,fen=board.fen(),last_move=last_move)

    ## black turn
    if not board.turn and not board.is_game_over(claim_draw=True):
        while not board.turn:
            try:
                _, frame = read_camera_frame()
                img_1 = get_board_img(frame)
            except (RuntimeError, BoardTrackingError) as error:
                print(f"Camera view rejected: {error}")
                relock_board()
                continue
            show_game(img_1, board, last_move)

            print("Black turn: finish the whole move, including the rook in castling.")
            print("Press 'q' only when your hand has left the board.")
            img_2 = wait_for_key_tracking('q')
            if img_2 is None:
                # The before/after pair is no longer trustworthy. The user
                # restored the old position during relock; take a new before.
                continue

            try:
                candidates = infer_human_move(img_1, img_2, boxes, board)
            except MoveDetectionError as error:
                print(f"Move not accepted: {error}")
                print("Restore the previous board position, then press 's'.")
                set_legal_positions(img_2, board, boxes)
                continue

            if len(candidates) == 1:
                move = candidates[0]
            else:
                # The same image results from Q/R/B/N promotion. Ask the player.
                while True:
                    choice = input("Promotion piece on the physical board (q/r/b/n): ").strip().lower()
                    selected = [
                        candidate for candidate in candidates
                        if chess.piece_symbol(candidate.promotion) == choice
                    ]
                    if selected:
                        move = selected[0]
                        break
                    print("Choose q, r, b or n matching the piece on the board.")

            board.push(move)
            last_move = move.uci()
            show_game(img_2, board, last_move)
            chess_board, player_bool_position = fen2board(board.fen())
            np.savez(
                dir_path + "/fen_line_board.npz",
                chess_board=chess_board,
                player_bool_position=player_bool_position,
                fen=board.fen(),
                last_move=last_move,
            )
            print(f"Accepted move: {last_move}")

    if board.is_checkmate():
        print("Checkmate!")
        ret , img = read_camera_frame()
        img_1 =   cv2.resize(img,(800,800))
        game_img = safe_board_img(img_1)
        show_game(game_img,board,last_move)
        cv2.waitKey(0)
        break

print("Exit")
cv2.destroyAllWindows()
