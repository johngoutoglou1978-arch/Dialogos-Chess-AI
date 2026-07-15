import importlib
import time
import random
import os
import chess
import chess.polyglot
import queue
import threading
from collections import defaultdict
import math

killer_moves = [[None, None] for _ in range(64)]
history_heuristic = defaultdict(int)
# -------------------------
# Φόρτωση python-chess
# -------------------------
chess_lib = importlib.import_module("chess")

# -------------------------
# Polyglot Book
# -------------------------
# -------------------------
# Polyglot Book
# -------------------------
def get_book_move(board):
    paths = [
        "/content/drive/MyDrive/don.bin",
        "/storage/emulated/0/don.bin",
        "/storage/emulated/0/Pydroid3/don.bin",
        "/storage/emulated/0/Download/don.bin",
        "./don.bin"
    ]

    for path in paths:
        if os.path.exists(path):
            try:
                with chess.polyglot.open_reader(path) as reader:
                    entries = list(reader.find_all(board))
                    if not entries:
                        return None

                    total_weight = sum(entry.weight for entry in entries)
                    r = random.uniform(0, total_weight)
                    upto = 0

                    for entry in entries:
                        upto += entry.weight
                        if upto >= r:
                            return entry.move
            except:
                pass

    return None

# =============================================================================
# SUNFISH PIECE VALUES & PIECE-SQUARE TABLES (64 SQUARES - TOP DOWN)
# =============================================================================
# ΣΤΑΘΕΡΕΣ ΚΑΙ ΠΙΝΑΚΕΣ ΑΞΙΟΛΟΓΗΣΗΣ
# =============================================================================

piece_values = {
    chess.PAWN: 100,
    chess.KNIGHT: 280, 
    chess.BISHOP: 320, 
    chess.ROOK: 479, 
    chess.QUEEN: 929, 
    chess.KING: 60000 
}

PAWN_TABLE = [
     0,   0,   0,   0,   0,   0,   0,   0,
    78,  83,  86,  73, 102,  82,  85,  90,
     7,  29,  21,  44,  40,  31,  44,   7,
   -17,  16,  -2,  15,  14,   0,  15, -13,
   -26,   3,  10,   9,   6,   1,   0, -23,
   -22,   9,   5, -11, -10,  -2,   3, -19,
   -31,   8,  -7, -37, -36, -14,   3, -31,
     0,   0,   0,   0,   0,   0,   0,   0
]

KNIGHT_TABLE = [
   -66, -53, -75, -75, -10, -55, -58, -70,
    -3,  -6, 100, -36,   4,  62,  -4, -14,
    10,  67,   1,  74,  73,  27,  62,  -2,
    24,  24,  45,  37,  33,  41,  25,  17,
    -1,   5,  31,  21,  22,  35,   2,   0,
   -18,  10,  13,  22,  18,  15,  11, -14,
   -23, -15,   2,   0,   2,   0, -23, -20,
   -74, -23, -26, -24, -19, -35, -22, -69
]

BISHOP_TABLE = [
   -59, -78, -82, -76, -23,-107, -37, -50,
   -11,  20,  35, -42, -39,  31,   2, -22,
    -9,  39, -32,  41,  52, -10,  28, -14,
    25,  17,  20,  34,  26,  25,  15,  10,
    13,  10,  17,  23,  17,  16,   0,   7,
    14,  25,  24,  15,   8,  25,  20,  15,
    19,  20,  11,   6,   7,   6,  20,  16,
    -7,   2, -15, -12, -14, -15, -10, -10
]

ROOK_TABLE = [
    35,  29,  33,   4,  37,  33,  56,  50,
    55,  29,  56,  67,  55,  62,  34,  60,
    19,  35,  28,  33,  45,  27,  25,  15,
     0,   5,  16,  13,  18,  -4,  -9,  -6,
   -28, -35, -16, -21, -13, -29, -46, -30,
   -42, -28, -42, -25, -25, -35, -26, -46,
   -53, -38, -31, -26, -29, -43, -44, -53,
   -30, -24, -18,   5,  -2, -18, -31, -32
]

QUEEN_TABLE = [
     6,   1,  -8,-104,  69,  24,  88,  26,
    14,  32,  60, -10,  20,  76,  57,  24,
    -2,  43,  32,  60,  72,  63,  43,   2,
     1, -16,  22,  17,  25,  20, -13,  -6,
   -14, -15,  -2,  -5,  -1, -10, -20, -22,
   -30,  -6, -13, -11, -16, -11, -16, -27,
   -36, -18,   0, -19, -15, -15, -21, -38,
   -39, -30, -31, -13, -31, -36, -34, -42
]

KING_TABLE = [
     4,  54,  47, -99, -99,  60,  83, -62,
   -32,  10,  55,  56,  56,  55,  10,   3,
   -62,  12, -57,  44, -67,  28,  37, -31,
   -55,  50,  11,  -4, -19,  13,   0, -49,
   -55, -43, -52, -28, -51, -47,  -8, -50,
   -47, -42, -43, -79, -64, -32, -29, -32,
    -4,   3, -14, -50, -57, -18,  13,   4,
    17,  30,  -3, -14,   6,  -1,  40,  18
]

# --- ΠΙΝΑΚΕΣ ΦΙΝΑΛΕ (ENDGAME TABLES) ---

PAWN_ENDGAME_TABLE = [
     0,   0,   0,   0,   0,   0,   0,   0,
    70,  70,  70,  70,  70,  70,  70,  70,
    35,  35,  35,  40,  40,  35,  35,  35,
    20,  20,  20,  25,  25,  20,  20,  20,
    10,  10,  10,  15,  15,  10,  10,  10,
     5,   5,   5,  10,  10,   5,   5,   5,
     0,   0,   0,   0,   0,   0,   0,   0,
     0,   0,   0,   0,   0,   0,   0,   0
]

KNIGHT_ENDGAME_TABLE = [
   -58, -38, -30, -28, -28, -30, -38, -58,
   -38, -22, -13, -11, -11, -13, -22, -38,
   -30, -13,  -4,  -1,  -1,  -4, -13, -30,
   -28, -11,  -1,   3,   3,  -1, -11, -28,
   -28, -11,  -1,   3,   3,  -1, -11, -28,
   -30, -13,  -4,  -1,  -1,  -4, -13, -30,
   -38, -22, -13, -11, -11, -13, -22, -38,
   -58, -38, -30, -28, -28, -30, -38, -58
]

BISHOP_ENDGAME_TABLE = [
   -34, -20, -15, -12, -12, -15, -20, -34,
   -20, -10,  -5,  -2,  -2,  -5, -10, -20,
   -15,  -5,   2,   5,   5,   2,  -5, -15,
   -12,  -2,   5,  10,  10,   5,  -2, -12,
   -12,  -2,   5,  10,  10,   5,  -2, -12,
   -15,  -5,   2,   5,   5,   2,  -5, -15,
   -20, -10,  -5,  -2,  -2,  -5, -10, -20,
   -34, -20, -15, -12, -12, -15, -20, -34
]

ROOK_ENDGAME_TABLE = [
    12,  15,  18,  20,  20,  18,  15,  12,
    15,  18,  20,  22,  22,  20,  18,  15,
     8,  10,  12,  15,  15,  12,  10,   8,
     0,   2,   5,   7,   7,   5,   2,   0,
    -5,  -2,   0,   2,   2,   0,  -2,  -5,
   -10,  -7,  -5,  -2,  -2,  -5,  -7, -10,
   -15, -12, -10,  -7,  -7, -10, -12, -15,
   -20, -15, -12, -10, -10, -12, -15, -20
]

QUEEN_ENDGAME_TABLE = [
   -15, -10,  -5,   0,   0,  -5, -10, -15,
   -10,  -2,   2,   5,   5,   2,  -2, -10,
    -5,   2,   5,   8,   8,   5,   2,  -5,
     0,   5,   8,  12,  12,   8,   5,   0,
     0,   5,   8,  12,  12,   8,   5,   0,
    -5,   2,   5,   8,   8,   5,   2,  -5,
   -10,  -2,   2,   5,   5,   2,  -2, -10,
   -15, -10,  -5,   0,   0,  -5, -10, -15
]

KING_ENDGAME_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -30, -20, -10,   0,   0, -10, -20, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  30,  40,  40,  30, -10, -30,
    -30, -10,  20,  30,  30,  20, -10, -30,
    -30, -30,   0,   0,   0,   0, -30, -30,
    -50, -30, -30, -30, -30, -30, -30, -50
]


# Ο επίσημος πίνακας ασφάλειας Stockfish / Glaurung
STOCKFISH_SAFETY_TABLE = [
    0,  0,   1,   2,   3,   5,   7,   9,  12,  15,
  18,  22,  26,  30,  35,  39,  44,  50,  56,  62,
  68,  75,  82,  85,  89,  97, 105, 113, 122, 131,
  140, 150, 169, 180, 191, 202, 213, 225, 237, 248,
  260, 272, 283, 295, 307, 319, 330, 342, 354, 366,
  377, 389, 401, 412, 424, 436, 448, 459, 471, 483,
  494, 500, 500, 500, 500, 500, 500, 500, 500, 500,
  500, 500, 500, 500, 500, 500, 500, 500, 500, 500,
  500, 500, 500, 500, 500, 500, 500, 500, 500, 500,
  500, 500, 500, 500, 500, 500, 500, 500, 500, 500
]

# =============================================================================
# ΣΥΝΑΡΤΗΣΗ ΥΠΟΛΟΓΙΣΜΟΥ ΑΣΦΑΛΕΙΑΣ ΒΑΣΙΛΙΑ (STOCKFISH ATTACK UNITS)
# =============================================================================

def calculate_king_safety(board, king_color):
    king_square = board.king(king_color)
    if king_square is None:
        return 0
        
    enemy_color = not king_color
    king_zone = set()
    king_rank = chess.square_rank(king_square)
    king_file = chess.square_file(king_square)
    
    # 1. Καθαρός γεωμετρικός υπολογισμός: 8 γειτονικά + ο ίδιος ο βασιλιάς
    for f_offset in [-1, 0, 1]:
        for r_offset in [-1, 0, 1]:
            target_file = king_file + f_offset
            target_rank = king_rank + r_offset
            if 0 <= target_file <= 7 and 0 <= target_rank <= 7:
                king_zone.add(chess.square(target_file, target_rank))
                
    # 2. Προσθήκη των έξτρα επιπέδων μπροστά (Facing Enemy Position)
    direction = 1 if king_color == chess.WHITE else -1
    
    for f_offset in [-1, 0, 1]:
        target_file = king_file + f_offset
        
        # ✅ ΑΛΛΑΓΗ ΔΟΜΗΣ: Χρήση range για αποφυγή του bug εμφάνισης
        for depth in range(1, 3):
            target_rank = king_rank + (depth * direction)
            if 0 <= target_file <= 7 and 0 <= target_rank <= 7:
                king_zone.add(chess.square(target_file, target_rank))

    attack_units = 0
    attacking_pieces_count = 0
    
    # 3. Έλεγχος εχθρικών επιθέσεων στη ζώνη
    for piece_type in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        pieces = board.pieces(piece_type, enemy_color)
        
        for piece_square in pieces:
            piece_attacks = board.attacks(piece_square)
            
            # Αν το κομμάτι στοχεύει έστω και ένα τετράγωνο της ζώνης
            if king_zone.intersection(piece_attacks):
                attacking_pieces_count += 1
                
                # Μονάδες επίθεσης
                if piece_type in [chess.KNIGHT, chess.BISHOP]:
                    attack_units += 15
                elif piece_type == chess.ROOK:
                    attack_units += 30
                elif piece_type == chess.QUEEN:
                    attack_units += 90

    # Αν επιτίθενται λιγότερα από 2 κομμάτια, δεν υπάρχει στρατηγικός κίνδυνος
    if attacking_pieces_count < 2:
        return 0
        
    # Διαίρεση διά 8 για σωστή αντιστοίχιση στον πίνακα 0-99
    safety_index = min(attack_units // 8, 99)
    return STOCKFISH_SAFETY_TABLE[safety_index]


# =============================================================================
# EVALUATE BOARD FUNCTION (UPDATED WITH KING SAFETY)
# =============================================================================

def evaluate_board(board):
    # 1. Terminal states
    if board.is_checkmate():
        return -99999 if board.turn else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0

    # 2. Fast Material Detection using Bitmasks
    w_pawns = board.pawns & board.occupied_co[chess.WHITE]
    b_pawns = board.pawns & board.occupied_co[chess.BLACK]
    w_knights = board.knights & board.occupied_co[chess.WHITE]
    b_knights = board.knights & board.occupied_co[chess.BLACK]
    w_bishops = board.bishops & board.occupied_co[chess.WHITE]
    b_bishops = board.bishops & board.occupied_co[chess.BLACK]
    w_rooks = board.rooks & board.occupied_co[chess.WHITE]
    b_rooks = board.rooks & board.occupied_co[chess.BLACK]
    w_queens = board.queens & board.occupied_co[chess.WHITE]
    b_queens = board.queens & board.occupied_co[chess.BLACK]

    w_p_count = int(w_pawns).bit_count()
    b_p_count = int(b_pawns).bit_count()
    w_n_count = int(w_knights).bit_count()
    b_n_count = int(b_knights).bit_count()
    w_b_count = int(w_bishops).bit_count()
    b_b_count = int(b_bishops).bit_count()
    w_r_count = int(w_rooks).bit_count()
    b_r_count = int(b_rooks).bit_count()
    w_q_count = int(w_queens).bit_count()
    b_q_count = int(b_queens).bit_count()

    # --- ΥΠΟΛΟΓΙΣΜΟΣ ΦΑΣΗΣ ΠΑΙΧΝΙΔΙΟΥ (ENDGAME DETECTION) ---
    major_pieces_count = w_n_count + b_n_count + w_b_count + b_b_count + w_r_count + b_r_count + w_q_count + b_q_count
    
    if major_pieces_count <= 4:
        endgame_weight = 1.0
    elif major_pieces_count >= 12:
        endgame_weight = 0.0
    else:
        endgame_weight = (12 - major_pieces_count) / 8.0

    # Δυναμική αξία πιονιού
    pawn_current_value = piece_values[chess.PAWN] + int(endgame_weight * 40)

    # Προσθήκη Υλικού (Material)
    score += w_p_count * pawn_current_value - b_p_count * pawn_current_value
    score += w_n_count * piece_values[chess.KNIGHT] - b_n_count * piece_values[chess.KNIGHT]
    score += w_b_count * piece_values[chess.BISHOP] - b_b_count * piece_values[chess.BISHOP]
    score += w_r_count * piece_values[chess.ROOK] - b_r_count * piece_values[chess.ROOK]
    score += w_q_count * piece_values[chess.QUEEN] - b_q_count * piece_values[chess.QUEEN]

    # --- ΑΞΙΟΛΟΓΗΣΗ ΔΙΠΛΩΜΕΝΩΝ ΠΙΟΝΙΩΝ (DOUBLED PAWNS) ---
    DOUBLED_PAWN_PENALTY = 60  # Ποινή σε centipawns
    
    for file_mask in chess.BB_FILES:
        # Λευκά διπλωμένα πιόνια στην τρέχουσα στήλη
        w_pawns_in_file = int(w_pawns & file_mask).bit_count()
        if w_pawns_in_file > 1:
            score -= (w_pawns_in_file - 1) * DOUBLED_PAWN_PENALTY

        # Μαύρα διπλωμένα πιόνια στην τρέχουσα στήλη
        b_pawns_in_file = int(b_pawns & file_mask).bit_count()
        if b_pawns_in_file > 1:
            score += (b_pawns_in_file - 1) * DOUBLED_PAWN_PENALTY

    # 3. Piece-Square Table Positioning (Middlegame vs Endgame Tapered Interpolation)
    
    # ΠΙΟΝΙΑ
    for sq in chess.SquareSet(w_pawns): 
        score += int((1 - endgame_weight) * PAWN_TABLE[sq ^ 56] + endgame_weight * PAWN_ENDGAME_TABLE[sq ^ 56])
    for sq in chess.SquareSet(b_pawns): 
        score -= int((1 - endgame_weight) * PAWN_TABLE[sq] + endgame_weight * PAWN_ENDGAME_TABLE[sq])

    # ΙΠΠΟΙ
    for sq in chess.SquareSet(w_knights): 
        score += int((1 - endgame_weight) * KNIGHT_TABLE[sq ^ 56] + endgame_weight * KNIGHT_ENDGAME_TABLE[sq ^ 56])
    for sq in chess.SquareSet(b_knights): 
        score -= int((1 - endgame_weight) * KNIGHT_TABLE[sq] + endgame_weight * KNIGHT_ENDGAME_TABLE[sq])

    # ΑΞΙΩΜΑΤΙΚΟΙ
    for sq in chess.SquareSet(w_bishops): 
        score += int((1 - endgame_weight) * BISHOP_TABLE[sq ^ 56] + endgame_weight * BISHOP_ENDGAME_TABLE[sq ^ 56])
    for sq in chess.SquareSet(b_bishops): 
        score -= int((1 - endgame_weight) * BISHOP_TABLE[sq] + endgame_weight * BISHOP_ENDGAME_TABLE[sq])

    # ΠΥΡΓΟΙ
    for sq in chess.SquareSet(w_rooks): 
        score += int((1 - endgame_weight) * ROOK_TABLE[sq ^ 56] + endgame_weight * ROOK_ENDGAME_TABLE[sq ^ 56])
    for sq in chess.SquareSet(b_rooks): 
        score -= int((1 - endgame_weight) * ROOK_TABLE[sq] + endgame_weight * ROOK_ENDGAME_TABLE[sq])

    # ΒΑΣΙΛΙΣΣΕΣ
    for sq in chess.SquareSet(w_queens): 
        score += int((1 - endgame_weight) * QUEEN_TABLE[sq ^ 56] + endgame_weight * QUEEN_ENDGAME_TABLE[sq ^ 56])
    for sq in chess.SquareSet(b_queens): 
        score -= int((1 - endgame_weight) * QUEEN_TABLE[sq] + endgame_weight * QUEEN_ENDGAME_TABLE[sq])

    # 6. Βασιλιάς - Δυναμική εναλλαγή
    wk = board.king(chess.WHITE)
    bk = board.king(chess.BLACK)

    if wk is not None:
        mg_king_score = KING_TABLE[wk ^ 56]
        eg_king_score = KING_ENDGAME_TABLE[wk ^ 56]
        score += int((1 - endgame_weight) * mg_king_score + endgame_weight * eg_king_score)
        
    if bk is not None:
        mg_king_score = KING_TABLE[bk]
        eg_king_score = KING_ENDGAME_TABLE[bk]
        score -= int((1 - endgame_weight) * mg_king_score + endgame_weight * eg_king_score)

    # --- ΠΡΟΣΘΗΚΗ: KING SAFETY (STOCKFISH ATTACK UNITS) ---
    if endgame_weight < 1.0:
        white_king_danger = calculate_king_safety(board, chess.WHITE)
        dark_king_danger = calculate_king_safety(board, chess.BLACK)
        
        # Μειώνουμε την ποινή όσο πλησιάζουμε στο φινάλε (tapered scaling)
        scaled_white_danger = int(white_king_danger * (1 - endgame_weight))
        scaled_dark_danger = int(dark_king_danger * (1 - endgame_weight))
        
        # Αφαιρούμε πόντους από τον Λευκό αν κινδυνεύει, προσθέτουμε αν κινδυνεύει ο Μαύρος
        score -= scaled_white_danger
        score += scaled_dark_danger

    # 4. Tempo Bonus
    score += (15 if board.turn == chess.WHITE else -15)

    # Η ΜΕΓΑΛΗ ΓΝΩΣΗ: ΣΤΡΑΓΓΑΛΙΣΜΟΣ & ΠΕΡΙΟΡΙΣΜΟΣ ΚΙΝΗΤΙΚΟΤΗΤΑΣ ΑΝΤΙΠΑΛΟΥ
    w_mobility = 0
    for sq in chess.SquareSet(w_knights):
        w_mobility += int(board.attacks(sq) & ~board.occupied_co[chess.WHITE]).bit_count()
    for sq in chess.SquareSet(w_bishops):
        w_mobility += int(board.attacks(sq) & ~board.occupied_co[chess.WHITE]).bit_count()
    for sq in chess.SquareSet(w_rooks):
        w_mobility += int(board.attacks(sq) & ~board.occupied_co[chess.WHITE]).bit_count()
    for sq in chess.SquareSet(w_queens):
        w_mobility += int(board.attacks(sq) & ~board.occupied_co[chess.WHITE]).bit_count()

    b_mobility = 0
    for sq in chess.SquareSet(b_knights):
        b_mobility += int(board.attacks(sq) & ~board.occupied_co[chess.BLACK]).bit_count()
    for sq in chess.SquareSet(b_bishops):
        b_mobility += int(board.attacks(sq) & ~board.occupied_co[chess.BLACK]).bit_count()
    for sq in chess.SquareSet(b_rooks):
        b_mobility += int(board.attacks(sq) & ~board.occupied_co[chess.BLACK]).bit_count()
    for sq in chess.SquareSet(b_queens):
        b_mobility += int(board.attacks(sq) & ~board.occupied_co[chess.BLACK]).bit_count()

    MOBILITY_WEIGHT = 2
    score += (w_mobility - b_mobility) * MOBILITY_WEIGHT

    # =============================================================================
    # ΕΝΣΩΜΑΤΩΣΗ ΝΕΑΣ ΓΝΩΣΗΣ: ΚΛΕΙΣΤΟ ΚΕΝΤΡΟ, ΚΑΚΟΙ ΑΞΙΩΜΑΤΙΚΟΙ & PAWN BREAKS
    # =============================================================================
    if endgame_weight < 1.0:
        # --- ΑΝΙΧΝΕΥΣΗ ΚΛΕΙΣΤΟΥ ΚΕΝΤΡΟΥ (d4-d5 ή e4-e5) ---
        d4_p, d5_p = board.piece_at(chess.D4), board.piece_at(chess.D5)
        e4_p, e5_p = board.piece_at(chess.E4), board.piece_at(chess.E5)
        
        center_is_closed = (
            (d4_p and d5_p and d4_p.piece_type == chess.PAWN and d4_p.color == chess.WHITE and d5_p.piece_type == chess.PAWN and d5_p.color == chess.BLACK) or
            (e4_p and e5_p and e4_p.piece_type == chess.PAWN and e4_p.color == chess.WHITE and e5_p.piece_type == chess.PAWN and e5_p.color == chess.BLACK)
        )

        strategy_score = 0

        # 1. ΥΠΟΛΟΓΙΣΜΟΣ ΠΟΙΝΗΣ "ΚΑΚΟΥ ΑΞΙΩΜΑΤΙΚΟΥ" (BAD BISHOP PENALTY)
        BAD_BISHOP_UNIT = 25  # Ποινή ανά πιόνι-εμπόδιο στο κέντρο
        
        # Κεντρικά τετράγωνα ελέγχου
        WHITE_LIGHT_CENTER = [chess.C4, chess.D3, chess.E4, chess.F3]
        WHITE_DARK_CENTER  = [chess.C3, chess.D4, chess.E3, chess.F4]
        BLACK_LIGHT_CENTER = [chess.C5, chess.D6, chess.E5, chess.F6]
        BLACK_DARK_CENTER  = [chess.C6, chess.D5, chess.E6, chess.F5]

        # Έλεγχος για Λευκούς Αξιωματικούς
        for sq in chess.SquareSet(w_bishops):
            # Έλεγχος αν το τετράγωνο είναι λευκό (light square)
            if (chess.square_file(sq) + chess.square_rank(sq)) % 2 != 0:
                blocked = sum(1 for p_sq in WHITE_LIGHT_CENTER if board.piece_at(p_sq) and board.piece_at(p_sq).piece_type == chess.PAWN and board.piece_at(p_sq).color == chess.WHITE)
                strategy_score -= blocked * BAD_BISHOP_UNIT
            else:  # Μαύρο τετράγωνο
                blocked = sum(1 for p_sq in WHITE_DARK_CENTER if board.piece_at(p_sq) and board.piece_at(p_sq).piece_type == chess.PAWN and board.piece_at(p_sq).color == chess.WHITE)
                strategy_score -= blocked * BAD_BISHOP_UNIT

        # Έλεγχος για Μαύρους Αξιωματικούς
        for sq in chess.SquareSet(b_bishops):
            # Έλεγχος αν το τετράγωνο είναι λευκό (light square)
            if (chess.square_file(sq) + chess.square_rank(sq)) % 2 != 0:
                blocked = sum(1 for p_sq in BLACK_LIGHT_CENTER if board.piece_at(p_sq) and board.piece_at(p_sq).piece_type == chess.PAWN and board.piece_at(p_sq).color == chess.BLACK)
                strategy_score += blocked * BAD_BISHOP_UNIT
            else:  # Μαύρο τετράγωνο
                blocked = sum(1 for p_sq in BLACK_DARK_CENTER if board.piece_at(p_sq) and board.piece_at(p_sq).piece_type == chess.PAWN and board.piece_at(p_sq).color == chess.BLACK)
                strategy_score += blocked * BAD_BISHOP_UNIT

        # 2. ΥΠΟΛΟΓΙΣΜΟΣ ΜΠΟΝΟΥΣ ΓΙΑ ΣΠΑΣΙΜΑΤΑ ΣΤΑ ΦΤΕΡΑ (PAWN BREAKS)
        if center_is_closed:
            BREAK_BONUS = 30  # Μπόνους για προώθηση σε στήλες c και f
            
            # Έλεγχος Λευκών πιονιών στα φτερά
            for sq in [chess.C4, chess.C5, chess.F4, chess.F5]:
                p = board.piece_at(sq)
                if p and p.piece_type == chess.PAWN and p.color == chess.WHITE:
                    strategy_score += BREAK_BONUS
                    
            # Έλεγχος Μαύρων πιονιών στα φτερά
            for sq in [chess.C5, chess.C4, chess.F5, chess.F4]:
                p = board.piece_at(sq)
                if p and p.piece_type == chess.PAWN and p.color == chess.BLACK:
                    strategy_score -= BREAK_BONUS

        # Εφαρμογή Tapered Scaling (μαλακώνει στο endgame) και προσθήκη στο συνολικό score
        score += int(strategy_score * (1.0 - endgame_weight))
    # =============================================================================


    return score / 120.0


def fast_see(board, move):
    """
    Υπολογίζει αν μια ανταλλαγή συμφέρει χωρίς push/pop.
    Απαραίτητο για να μην χάνει χρόνο η Quiescence σε κακά captures.
    """
    to_sq = move.to_square
    victim = board.piece_at(to_sq)
    if not victim: return 0 
    
    attacker_type = board.piece_at(move.from_square).piece_type
    gain = piece_values[victim.piece_type]
    
    # Αν ο επιτιθέμενος είναι φθηνότερος ή ίσης αξίας, η κίνηση είναι καλή
    if piece_values[attacker_type] <= gain:
        return gain
        
    # Αν ο επιτιθέμενος είναι ακριβότερος (π.χ. Βασίλισσα παίρνει Πιόνι),
    # δες αν το τετράγωνο προστατεύεται από τον αντίπαλο.
    if board.attackers(not board.turn, to_sq):
        return gain - piece_values[attacker_type]
    
    return gain

def quiescence(board, alpha, beta, maximizing, start_time, time_limit, max_depth=2, depth=0, ply=0):
    """
    Αναβαθμισμένη Quiescence με Delta Pruning (Sunfish style), SEE και MVV-LVA.
    """
    # --------- Stop conditions ---------
    if time.time() - start_time > time_limit or depth >= max_depth:
        return evaluate_board(board)

    # --------- Stand-pat evaluation ---------
    stand = evaluate_board(board)
    
    if maximizing:
        if stand >= beta:
            return beta
        alpha = max(alpha, stand)
        
        # --------- Delta Pruning (Sunfish Strategy) ---------
        # Αν η τρέχουσα θέση + η αξία μιας βασίλισσας (το μέγιστο capture) 
        # είναι ακόμα μικρότερη από το alpha, τότε αυτός ο κλάδος είναι απελπιστικός.
        # Διαιρούμε με 120.0 επειδή η evaluate_board επιστρέφει normalized score.
        QUEEN_VALUE_NORMALIZED = 929 / 120.0 
        if stand + QUEEN_VALUE_NORMALIZED < alpha:
            return alpha

        # --------- Only captures ---------
        raw_moves = [m for m in board.legal_moves if board.is_capture(m)]
        moves = [m for m in raw_moves if fast_see(board, m) >= 0]
        moves.sort(key=lambda m: mvv_lva(m, board), reverse=True)

        for move in moves:
            # Δυναμικό Delta Pruning ανά κίνηση:
            # Αν φάμε ένα κομμάτι και το σκορ μας + η αξία του θύματος + περιθώριο (π.χ. 200/120)
            # δεν φτάνει το alpha, προσπερνάμε την κίνηση χωρίς push/pop!
            victim = board.piece_at(move.to_square)
            victim_val = piece_values[victim.piece_type] / 120.0 if victim else 100 / 120.0 # fallback για en passant
            if stand + victim_val + (200 / 120.0) < alpha:
                continue

            board.push(move)
            score = quiescence(board, alpha, beta, False, start_time, time_limit, max_depth, depth + 1, ply=ply+1)
            board.pop()

            if score is None: return None
            
            alpha = max(alpha, score)
            if alpha >= beta or time.time() - start_time > time_limit:
                break
        return alpha

    else:
        if stand <= alpha:
            return alpha
        beta = min(beta, stand)
        
        # --------- Delta Pruning για τα Μαύρα ---------
        QUEEN_VALUE_NORMALIZED = 929 / 120.0
        if stand - QUEEN_VALUE_NORMALIZED > beta:
            return beta

        # --------- Only captures ---------
        raw_moves = [m for m in board.legal_moves if board.is_capture(m)]
        moves = [m for m in raw_moves if fast_see(board, m) >= 0]
        moves.sort(key=lambda m: mvv_lva(m, board), reverse=True)

        for move in moves:
            # Δυναμικό Delta Pruning για Minimizing
            victim = board.piece_at(move.to_square)
            victim_val = piece_values[victim.piece_type] / 120.0 if victim else 100 / 120.0
            if stand - victim_val - (200 / 120.0) > beta:
                continue

            board.push(move)
            score = quiescence(board, alpha, beta, True, start_time, time_limit, max_depth, depth + 1, ply=ply+1)
            board.pop()

            if score is None: return None
            
            beta = min(beta, score)
            if alpha >= beta or time.time() - start_time > time_limit:
                break
        return beta



# -------------------------
# Move Ordering
# -------------------------
# 🌟 Λεξικό για ακαριαία αντιστοίχιση των PST πινάκων (Λογική Stockfish για Quiet Moves)
PST_MAP = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE
}

def mvv_lva(move, board, tt_move=None, killers=None):
    """
    Βελτιωμένο Move Ordering με τη λογική σταδίων του Stockfish:
    1) TT Move (Απόλυτη προτεραιότητα)
    2) Good Captures (MVV-LVA)
    3) Killer Moves
    4) Quiet Moves (Sunfish PST Positioning)
    """
    # ΣΤΑΔΙΟ 1: MAIN_TT (Η κίνηση από το Transposition Table πάει ΠΡΩΤΗ)
    if tt_move and move == tt_move:
        return 10000000  # Μέγιστο σκορ

    # 1️⃣ ΚΟΨΙΜΑΤΑ (Captures) - MVV-LVA
    if board.is_capture(move):
        attacker = board.piece_at(move.from_square)
        if not attacker:
            return 0
            
        if board.is_en_passant(move):
            victim_type = chess.PAWN
        else:
            victim = board.piece_at(move.to_square)
            victim_type = victim.piece_type if victim else chess.PAWN
            
        # MVV-LVA: (Αξία Θύματος * 10) - Αξία Επιτιθέμενου + Base Score για Captures
        return 5000000 + (piece_values[victim_type] * 10) - piece_values[attacker.piece_type]

    # ΣΤΑΔΙΟ 3: KILLER MOVES (Έπονται των captures)
    if killers:
        if len(killers) > 0 and move == killers[0]:
            return 4000000
        elif len(killers) > 1 and move == killers[1]:
            return 3000000

    # ΣΤΑΔΙΟ 4: QUIET MOVES (Ήσυχες κινήσεις με βάση το PST του Sunfish)
    score = 0
    attacker = board.piece_at(move.from_square)
    if not attacker:
        return 0

    from_sq = move.from_square
    to_sq = move.to_square

    # Αν παίζουν τα λευκά, XOR 56
    if board.turn == chess.WHITE:
        from_sq ^= 56
        to_sq ^= 56

    # Ακαριαίο bonus θέσης από το λεξικό
    table = PST_MAP.get(attacker.piece_type)
    if table is not None:
        score += table[to_sq] - table[from_sq]

    # Προαγωγή πιονιού (Quiet Promotion)
    if move.promotion:
        score += 2000000

    return score


def is_endgame(board):
    """
    Υπερ-ταχεία ανίχνευση φινάλε (0% loops, 100% bitwise σε επίπεδο C).
    """
    # 1. Μέτρημα βαριών κομματιών με bit_count() - Διορθώθηκε το b_heavy να κοιτάει τα μαύρα
    w_heavy = board.knights | board.bishops | board.rooks | board.queens
    material_count = int(w_heavy).bit_count() # Συνολικά μεγάλα κομμάτια και των δύο

    # Αν έχουμε 4 ή λιγότερα μεγάλα κομμάτια, είμαστε 100% σε φινάλε
    if material_count <= 4:
        return True

    # 2. Έλεγχος προωθήσιμων πιόνιων ΧΩΡΙΣ LOOPS
    # Παίρνουμε όλα τα τετράγωνα που είναι κατειλημμένα (occupied)
    occupied = board.occupied
    
    # Μετατοπίζουμε τα bitmasks των πιονιών κατά 8 θέσεις (μία γραμμή μπροστά)
    # Αν το τετράγωνο μπροστά τους είναι άδειο (~occupied), τότε το πιόνι είναι προωθήσιμο!
    w_pawns_forward = (board.pawns & board.occupied_co[chess.WHITE]) << 8
    b_pawns_forward = (board.pawns & board.occupied_co[chess.BLACK]) >> 8
    
    # Μετράμε πόσα πιόνια έχουν ελεύθερο το τετράγωνο ακριβώς μπροστά τους
    free_pawns_w = int(w_pawns_forward & ~occupied).bit_count()
    free_pawns_b = int(b_pawns_forward & ~occupied).bit_count()
    
    free_pawn_count = free_pawns_w + free_pawns_b

    # Κανόνας φινάλε
    if free_pawn_count <= 3:
        return True
        
    return False


# ==============================
# Killer Moves & History Heuristic
# ==============================


MAX_PLY = 64 # μέγιστο βάθος (ply) που θα υποστηρίζουμε
killer_moves = [[None, None] for _ in range(MAX_PLY)] # 2 killer moves ανά ply
history_heuristic = defaultdict(int) # (piece_type, to_square) -> score

# ----------------------------
# Move scoring wrapper
# ----------------------------
def score_move(move, board, ply):
    """
    Δίνει score σε μια κίνηση για move ordering
    χρησιμοποιώντας: MVV-LVA + Killer + History
    """
    score = 0

    # Παίρνουμε το επιτιθέμενο κομμάτι μία φορά στην αρχή για εξοικονόμηση χρόνου
    attacker = board.piece_at(move.from_square)

    # 1. MVV-LVA (Γρήγορος έλεγχος για captures)
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        if victim and attacker:
            # Formula: (Αξία θύματος * 100) - Αξία επιτιθέμενου
            score = (victim.piece_type * 100) - attacker.piece_type + 1000000
        else:
            # Περίπτωση En Passant (το victim τετράγωνο είναι άδειο)
            score = 1000100 

    # 2. Killer moves (🌟 ΔΙΟΡΘΩΘΗΚΕ: Έλεγχος με δείκτες [0] και)
    if ply < len(killer_moves):
        killers = killer_moves[ply]
        if killers:  # Έλεγχος αν η λίστα/πλειάδα δεν είναι άδεια
            if len(killers) > 0 and move == killers[0]:
                score += 900000
            elif len(killers) > 1 and move == killers[1]:
                score += 800000

    # 3. History heuristic
    if attacker:
        # Χρήση της .get() με default τιμή 0 για να μην κρασάρει ποτέ
        score += history_heuristic.get((attacker.piece_type, move.to_square), 0)

    return score


# ----------------------------
# Για χρήση όταν γίνεται beta-cutoff
# ----------------------------
def update_killer_history(move, board, ply, depth):
    """
    Καταγράφει killer και history όταν γίνεται beta-cutoff
    depth: βάθος που προκάλεσε cutoff
    """
    # 1. Killer table
    if not board.is_capture(move):
        # Εξασφαλίζουμε ότι η λίστα killer_moves[ply] έχει πάντα 2 στοιχεία
        while len(killer_moves[ply]) < 2:
            killer_moves[ply].append(None)
            
        # Shift προηγούμενο killer (Η 1η κίνηση γίνεται 2η, και η νέα γίνεται 1η)
        if move != killer_moves[ply][0]:
            killer_moves[ply][1] = killer_moves[ply][0]
            killer_moves[ply][0] = move

        # 2. History heuristic
        piece = board.piece_at(move.from_square)
        if piece:
            history_heuristic[(piece.piece_type, move.to_square)] = history_heuristic.get(
                (piece.piece_type, move.to_square), 0
            ) + (depth * depth)


def has_major_pieces(board, turn):
    """
    Ελέγχει ακαριαία αν υπάρχουν κομμάτια πέρα από βασιλιά και πιόνια
    για την αποφυγή παγίδων Zugzwang κατά το Null Move Pruning.
    """
    # Φιλτράρουμε τους ίππους, αξιωματικούς, πύργους και βασίλισσες του παίκτη που έχει σειρά
    major_pieces = (board.knights | board.bishops | board.rooks | board.queens) & board.occupied_co[turn]
    return int(major_pieces).bit_count() > 0

# Τύποι εγγραφών (Bounds)
TT_EXACT = 0  # Ακριβές σκορ
TT_ALPHA = 1  # Upper bound (score <= alpha)
TT_BETA  = 2  # Lower bound (score >= beta)

# Το λεξικό του TT και το μέγιστο μέγεθος για τη RAM του Android
transposition_table = {}
MAX_TT_SIZE = 250000  

def minimax(board, depth, alpha, beta, maximizing, nodes, start_time, time_limit, ply=0, best_move_hint=None, interrupt_queue=None):

    # 1. --- ΑΚΑΡΙΑΙΟΣ ΕΛΕΓΧΟΣ ΔΙΑΚΟΠΗΣ ---
    if (interrupt_queue is not None and not interrupt_queue.empty()) or (time.time() - start_time >= time_limit):
        return None, None

    # 2. --- COUNT NODES ---
    nodes[0] += 1  

    # 3. --- TERMINAL / GAME OVER ---
    if depth == 0 or board.is_game_over():
        if depth == 0 or board.is_checkmate():
            score = quiescence(board, alpha, beta, maximizing, start_time, time_limit, ply=ply)
            return score, []
        else:
            current_eval = evaluate_board(board)
            if maximizing:
                return (-300 if current_eval > 1.0 else 0), []
            else:
                return (300 if current_eval < -1.0 else 0), []

    original_alpha = alpha
    original_beta = beta

    # 4. --- ΑΝΑΓΝΩΣΗ ΑΠΟ ΤΟ TRANSPOSITION TABLE ---
    zobrist_key = chess.polyglot.zobrist_hash(board)
    tt_entry = transposition_table.get(zobrist_key)
    tt_move = None

    if tt_entry is not None and not board.is_repetition(2):
        tt_move_uci = tt_entry.get('best_move')
        if tt_move_uci:
            try: tt_move = chess.Move.from_uci(tt_move_uci)
            except: tt_move = None

        if tt_entry['depth'] >= depth:
            tt_score = tt_entry['score']
            tt_flag = tt_entry['flag']
            
            if tt_score > 8000: tt_score -= ply
            elif tt_score < -8000: tt_score += ply

            if tt_flag == TT_EXACT:
                return tt_score, [tt_move] if tt_move and tt_move in board.legal_moves else []
            elif tt_flag == TT_ALPHA and tt_score <= alpha:
                return alpha, [tt_move] if tt_move and tt_move in board.legal_moves else []
            elif tt_flag == TT_BETA and tt_score >= beta:
                return beta, [tt_move] if tt_move and tt_move in board.legal_moves else []

    # 5. --- MOVE ORDERING (ΔΙΟΡΘΩΜΕΝΟ) ---
    scored_moves = []
    for move in board.legal_moves:
        score_val = score_move(move, board, ply)
        scored_moves.append((score_val, move))
    
    scored_moves.sort(key=lambda x: x[0], reverse=True)
    moves = [item[1] for item in scored_moves]

    if tt_move and tt_move in moves:
        moves.remove(tt_move)
        moves.insert(0, tt_move)

    if best_move_hint:
        hint = best_move_hint[0] if isinstance(best_move_hint, list) and best_move_hint else best_move_hint
        if hint in moves:
            moves.remove(hint)
            insert_idx = 1 if (tt_move and moves and moves[0] == tt_move) else 0
            moves.insert(insert_idx, hint)

    # 6. --- ΣΤΑΤΙΚΗ ΑΞΙΟΛΟΓΗΣΗ ΓΙΑ FUTILITY PRUNING ---
    static_eval = evaluate_board(board)
    in_check = board.is_check()

    R = 1 if depth < 5 else 2 

    is_prev_move_null = False
    if board.move_stack:
        is_prev_move_null = (board.move_stack[-1] == chess.Move.null())

    # --- MAXIMIZING PLAYER (Λευκά) ---
    if maximizing:
        if not is_prev_move_null and depth >= 3 and not in_check:
            if has_major_pieces(board, board.turn):
                board.push(chess.Move.null())
                null_score, _ = minimax(board, depth - 1 - R, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                board.pop()
                
                if null_score is None: return None, None
                if null_score >= beta: return beta, [] 

        best = -float("inf")
        best_line = []
        
        for moves_searched, move in enumerate(moves):
            is_capture = board.is_capture(move)
            is_promo = (move.promotion is not None)
            
            # --- FUTILITY PRUNING ---
            if depth <= 3 and not in_check and not is_capture and not is_promo:
                futility_margin = depth * 150
                if static_eval + futility_margin <= alpha:
                    continue

            board.push(move)
            
            if board.is_repetition(3):
                score = evaluate_board(board)
                score = 0 if score > 1.0 else 0
                line = []
            else:
                # --- CHECK EXTENSION ---
                # Αν η κίνηση που κάναμε έδωσε σαχ, αυξάνουμε το βάθος κατά 1 (αν δεν έχουμε πάει πολύ βαθιά)
                extension = 1 if board.is_check() and ply < 30 else 0

                # --- AGGRESSIVE LMR ---
                # Αν η κίνηση δίνει σαχ (extension == 1), ΔΕΝ κάνουμε μείωση LMR για να μην χάσουμε την τακτική
                if moves_searched >= 1 and depth >= 2 and not in_check and not is_capture and not is_promo and extension == 0:
                    reduction = int(0.5 + math.log(depth) * math.log(moves_searched + 1) / 2.0)
                    reduction = max(1, min(reduction, depth - 1))
                    
                    score, line = minimax(board, depth - 1 - reduction, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                    
                    if score is not None and score > alpha:
                        score, line = minimax(board, depth - 1 + extension, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                else:
                    score, line = minimax(board, depth - 1 + extension, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
            
            board.pop()

            if score is None: return None, None

            if score > best:
                best = score
                best_line = [move] + line

            alpha = max(alpha, best)
            if beta <= alpha:
                update_killer_history(move, board, ply, depth)
                break
                
        if best <= original_alpha: flag = TT_ALPHA
        elif best >= original_beta: flag = TT_BETA
        else: flag = TT_EXACT

        if tt_entry is None or depth >= tt_entry['depth']:
            if len(transposition_table) >= MAX_TT_SIZE:
                for k in list(transposition_table.keys())[:20000]: transposition_table.pop(k, None)
            
            transposition_table[zobrist_key] = {
                'score': best, 'depth': depth, 'flag': flag,
                'best_move': best_line[0].uci() if best_line else None
            }

        return best, best_line


    # --- MINIMIZING PLAYER (Μαύρα) ---
    else:
        if not is_prev_move_null and depth >= 3 and not in_check:
            if has_major_pieces(board, board.turn):
                board.push(chess.Move.null())
                null_score, _ = minimax(board, depth - 1 - R, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                board.pop()
                
                if null_score is None: return None, None
                if null_score <= alpha: return alpha, [] 

        best = float("inf")
        best_line = []
        
        for moves_searched, move in enumerate(moves):
            is_capture = board.is_capture(move)
            is_promo = (move.promotion is not None)
            
            # --- FUTILITY PRUNING ---
            if depth <= 3 and not in_check and not is_capture and not is_promo:
                futility_margin = depth * 150
                if static_eval - futility_margin >= beta:
                    continue

            board.push(move)
            
            if board.is_repetition(3):
                score = evaluate_board(board)
                score = 0 if score < -1.0 else 0
                line = []
            else:
                # --- CHECK EXTENSION ---
                # Αν η κίνηση των μαύρων έδωσε σαχ, αυξάνουμε το βάθος κατά 1
                extension = 1 if board.is_check() and ply < 30 else 0

                # --- AGGRESSIVE LMR ---
                # Αν η κίνηση δίνει σαχ (extension == 1), ΔΕΝ κάνουμε μείωση LMR
                if moves_searched >= 1 and depth >= 2 and not in_check and not is_capture and not is_promo and extension == 0:
                    reduction = int(0.5 + math.log(depth) * math.log(moves_searched + 1) / 2.0)
                    reduction = max(1, min(reduction, depth - 1))
                    
                    score, line = minimax(board, depth - 1 - reduction, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                    
                    if score is not None and score < beta:
                        score, line = minimax(board, depth - 1 + extension, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                else:
                    score, line = minimax(board, depth - 1 + extension, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
            
            board.pop()

            if score is None: return None, None

            if score < best:
                best = score
                best_line = [move] + line

            beta = min(beta, best)
            if beta <= alpha:
                update_killer_history(move, board, ply, depth)
                break
                
        if best >= original_beta: flag = TT_ALPHA
        elif best <= original_alpha: flag = TT_BETA
        else: flag = TT_EXACT

        if tt_entry is None or depth >= tt_entry['depth']:
            if len(transposition_table) >= MAX_TT_SIZE:
                for k in list(transposition_table.keys())[:20000]: transposition_table.pop(k, None)
            
            transposition_table[zobrist_key] = {
                'score': best, 'depth': depth, 'flag': flag,
                'best_move': best_line[0].uci() if best_line else None
            }

        return best, best_line

def check_draw(board):
    """
    Επιστρέφει True αν η θέση είναι αντικειμενικά ισοπαλία σύμφωνα με τους κανόνες.
    """
    if board.is_stalemate() or board.is_insufficient_material() \
       or board.is_repetition(3) or board.can_claim_fifty_moves():
        return True
    return False


def print_board_fidelity_relief(board):
    BG_LIGHT = "\033[48;5;252m" # off-white
    BG_DARK = "\033[48;5;22m" # dark green (σκούρο)
    BG_LIGHT_WITH_WHITE_PIECE = "\033[48;5;250m"
    RESET = "\033[0m"

    pieces_unicode = {  
        'P': '♙', 'N': '♘', 'B': '♗', 'R': '♖', 'Q': '♕', 'K': '♔',  
        'p': '♟', 'n': '♞', 'b': '♝', 'r': '♜', 'q': '♛', 'k': '♚'  
    }  

    FG_LIGHT_ON_LIGHT = "\033[38;5;232m"  
    FG_LIGHT_ON_DARK = "\033[38;5;255m"  
    FG_DARK = "\033[38;5;232m"  

    print("\n a b c d e f g h")  
    print(" ─────────────────")  

    for rank in range(7, -1, -1):  
        print(f"{rank+1} │", end="")  
        for file in range(8):  
            square = rank * 8 + file  
            piece = board.piece_at(square)  
            # Ά1 = σκούρο
            is_light = (rank + file + 1) % 2 == 0  

            bg = BG_LIGHT if is_light else BG_DARK  
            if piece and piece.color == chess_lib.WHITE and is_light:  
                bg = BG_LIGHT_WITH_WHITE_PIECE  

            symbol = " "  
            fg = ""
            if piece:  
                symbol = pieces_unicode[piece.symbol()]  
                if piece.color == chess_lib.WHITE:  
                    fg = FG_LIGHT_ON_DARK if not is_light else FG_LIGHT_ON_LIGHT  
                else:  
                    fg = FG_DARK  

            print(f"{bg}{fg}{symbol} {RESET}", end="")  
        print(f"│ {rank+1}")  

    print(" ─────────────────")  
    print(" a b c d e f g h\n")
def reset_engine():
    global killer_moves, history_heuristic, transposition_table

    killer_moves = [[None, None] for _ in range(100)]
    history_heuristic = {}
    transposition_table = {}

    print("\033[33m>> Engine reset έγινε.\033[0m")

def interactive_gameplay():
    print("\033[1;32m=== Don Zouán Chess AI Interactive ===\033[0m")
    fen = input("\033[36mΔώσε αρχικό FEN ή άφησέ το κενό για default:\033[0m ")
    board = chess_lib.Board(fen) if fen.strip() else chess_lib.Board()
    ai_side_input = input("\033[36mAI παίζει με ποιο χρώμα; (w=Λευκά, b=Μαύρα):\033[0m ").lower()
    ai_side = chess_lib.WHITE if ai_side_input == "w" else chess_lib.BLACK
    move_number = 1
    
    try:
        time_limit_input = input("\033[36mΔευτερόλεπτα σκέψης (π.χ. 5) [Enter για manual]:\033[0m ")
        time_limit = int(time_limit_input) if time_limit_input.strip() else 999
    except:
        time_limit = 5
        print("\033[36m>> Χρήση default χρόνου: 5 δευτερόλεπτα\033[0m")

    while not board.is_game_over():
        print("\n\033[1;32mΤρέχουσα θέση (Fidelity Relief):\033[0m\n")
        print_board_fidelity_relief(board)
        print("\n\033[1;32m----------------------------\033[0m\n")

        if check_draw(board):
            print("\033[36m>> Ισοπαλία αναγνωρίστηκε.\033[0m")
            break

        if board.turn == ai_side:
            legal_moves = list(board.legal_moves)
            if len(legal_moves) == 1:
                only_move = legal_moves[0]
                san = board.san(only_move)
                prefix = f"{move_number}." if board.turn == chess_lib.WHITE else f"{move_number}..."
                print(f"\033[1;32m{prefix} {san} (AI μόνο κίνηση)\033[0m")
                board.push(only_move)
                if board.turn == chess_lib.WHITE: move_number += 1
                continue

            book_move = get_book_move(board)
            if book_move and book_move in board.legal_moves:
                san = board.san(book_move)
                prefix = f"{move_number}." if board.turn == chess_lib.WHITE else f"{move_number}..."
                print(f"\033[1;32m{prefix} {san} (AI από book)\033[0m")
                board.push(book_move)
                if board.turn == chess_lib.WHITE: move_number += 1
                continue

            print(f"\033[1;32mΣκέψη AI... (Πάτα ENTER για άμεση κίνηση)\033[0m")
            nodes_counter = [0]
            start_time = time.time()
            best_score_full = 0
            best_line_full = []
            last_best_move = None 
            depth = 1

            input_queue = queue.Queue()
            def input_thread(q):
                try:
                    input() 
                    q.put(True)
                except EOFError:
                    pass
            threading.Thread(target=input_thread, args=(input_queue,), daemon=True).start()

            stop_timer = False
            def live_timer():
                seconds = 1
                while not stop_timer:
                    time.sleep(1)
                    if not stop_timer and seconds % 5 == 0:
                         print(f"\r\033[33mΣκέψη: {seconds}s...\033[0m", end="", flush=True)
                    seconds += 1
            timer_thread = threading.Thread(target=live_timer, daemon=True)
            timer_thread.start()

            # --- ASPIRATION WINDOW ΡΥΘΜΙΣΗ ---
            # Αν η minimax επιστρέφει float (π.χ. 1.25), βάλτε DELTA = 0.35
            # Αν επιστρέφει ακέραιο (π.χ. 125), βάλτε DELTA = 35
            DELTA = 35 
            previous_score = 0

            while True:
                if not input_queue.empty() or (time.time() - start_time >= time_limit):
                    break

                # Καθορισμός στενού παραθύρου από το Depth 2 και μετά
                if depth > 1 and abs(previous_score) < 8000:
                    alpha = previous_score - DELTA
                    beta = previous_score + DELTA
                else:
                    alpha = -float('inf')
                    beta = float('inf')

                # Πρώτη αναζήτηση με το στενό παράθυρο
                result = minimax(board, depth, alpha, beta, board.turn,
                                 nodes_counter, start_time, time_limit,
                                 best_move_hint=last_best_move,
                                 interrupt_queue=input_queue)

                if result is None or result[0] is None:
                    break

                score, line = result

                # FAIL-LOW: Το σκορ έπεσε κάτω από το alpha. Ξαναψάχνουμε με ανοιχτό Alpha.
                if depth > 1 and score <= alpha:
                    alpha = -float('inf')
                    result = minimax(board, depth, alpha, beta, board.turn,
                                     nodes_counter, start_time, time_limit,
                                     best_move_hint=last_best_move,
                                     interrupt_queue=input_queue)
                    if result is None or result[0] is None: 
                        break
                    score, line = result

                # FAIL-HIGH: Το σκορ ξεπέρασε το beta. Ξαναψάχνουμε με ανοιχτό Beta.
                elif depth > 1 and score >= beta:
                    beta = float('inf')
                    result = minimax(board, depth, alpha, beta, board.turn,
                                     nodes_counter, start_time, time_limit,
                                     best_move_hint=last_best_move,
                                     interrupt_queue=input_queue)
                    if result is None or result[0] is None: 
                        break
                    score, line = result

                # Αποθήκευση αποτελεσμάτων έγκυρου βάθους
                best_score_full = score
                best_line_full = line
                last_best_move = line[0] if line else None
                previous_score = score
                
                move_san = board.san(best_line_full[0]) if best_line_full else "???"
                print(f"\r\033[36m[Depth {depth:2d}] Best: {move_san:5} | Eval: {score:+.2f} | Nodes: {nodes_counter[0]}\033[0m", flush=True)
                
                if abs(score) >= 9000:
                    break

                depth += 1
                if depth > 100: 
                    break

            stop_timer = True
            print() 

            if best_line_full:
                selected_move = best_line_full[0]
                san = board.san(selected_move)
                prefix = f"{move_number}." if board.turn == chess_lib.WHITE else f"{move_number}..."
                print(f"\033[1;32m{prefix} AI παίζει: {san} ({best_score_full:+.2f})\033[0m")
                board.push(selected_move)
                if board.turn == chess_lib.WHITE: move_number += 1
            else:
                fallback = list(board.legal_moves)[0]
                board.push(fallback)
                print("\033[31mAI: Random Move (διακόπηκε πολύ νωρίς)\033[0m")

        else:
            tt_count = len(transposition_table)
            fill_percentage = (tt_count / MAX_TT_SIZE) * 100

            if fill_percentage < 70:
                mem_color = "\033[32m🟢"
            elif fill_percentage < 85:
                mem_color = "\033[33m⚠️ "
            else:
                mem_color = "\033[31m🚨 ΚΙΝΔΥΝΟΣ! "

            print(f"{mem_color}Μνήμη TT: {tt_count}/{MAX_TT_SIZE} ({fill_percentage:.1f}% γεμάτο)\033[0m")
            if fill_percentage >= 85:
                print("\033[1;31m[ΠΡΟΕΙΔΟΠΟΙΗΣΗ]: Η μνήμη είναι σχεδόν γεμάτη! Γράψε 'clear' για να την αδειάσεις ακαριαία.\033[0m")

            print("\033[1;32m==> Η σειρά σου!\033[0m")
            move_str = input("\033[36mΗ κίνησή σου (e2e4 | undo | clear | reset):\033[0m ").strip().lower()

            if move_str == "undo":
                if len(board.move_stack) >= 2:
                    board.pop(); board.pop()
                    print("\033[1;32m>> Undo έγινε.\033[0m")
                continue

            if move_str == "clear":
                transposition_table.clear()
                print("\033[1;32m🧹 Το Transposition Table καθαρίστηκε επιτυχώς! Η μνήμη είναι 0.0%.\033[0m")
                continue

            if move_str == "reset":
                reset_engine()
                print("\033[33m>> Έξοδος από το παιχνίδι...\033[0m")
                return

            try:
                move = chess_lib.Move.from_uci(move_str)
                if move in board.legal_moves:
                    board.push(move)
                    if board.turn == chess_lib.WHITE: move_number += 1
                else:
                    print("\033[31mΜη νόμιμη κίνηση.\033[0m")
            except:
                print("\033[31mΛάθος μορφή (uci).\033[0m")

    print_board_fidelity_relief(board)
    print("\n\033[1;32m--- Τελικό Αποτέλεσμα ---\033[0m")
    if board.is_checkmate(): 
        print("\033[1;36m>> ΜΑΤ!\033[0m")
    else: 
        print("\033[36m>> Το παιχνίδι έληξε.\033[0m")


if __name__ == "__main__":
    interactive_gameplay()