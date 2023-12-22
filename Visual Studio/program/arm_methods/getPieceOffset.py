from config import rook_offset, knight_offset, bishop_offset, queen_offset, king_offset, pawn_offset

def getPieceOffset(piece):
    if piece == 'r' or piece == 'R':
        piece_offset = rook_offset
    elif piece == 'n' or piece == 'N':
        piece_offset = knight_offset
    elif piece == 'b' or piece == 'B':
        piece_offset = bishop_offset
    elif piece == 'q' or piece == 'Q':
        piece_offset = queen_offset
    elif piece == 'k' or piece == 'K':
        piece_offset = king_offset
    elif piece == 'p' or piece == 'P':
        piece_offset = pawn_offset
    else:
        print('error selecting piece height')
        piece_offset = 0
    return piece_offset