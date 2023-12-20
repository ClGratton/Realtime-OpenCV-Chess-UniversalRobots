from config import rook_height, knight_height, bishop_height, queen_height, king_height, pawn_height

def getPieceHeight(piece):
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
    elif piece == 'p' or piece == 'P':
        piece_height = pawn_height
    else:
        print('error selecting piece height')
    return piece_height