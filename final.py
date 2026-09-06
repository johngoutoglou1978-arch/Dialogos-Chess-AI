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

piece_values = {
    chess.PAWN: 100,
    chess.KNIGHT: 280, 
    chess.BISHOP: 320, 
    chess.ROOK: 479, 
    chess.QUEEN: 929, 
    chess.KING: 60000 
}

PAWN_TABLE = [
     0, 0, 0, 0, 0, 0, 0, 0,
    78, 83, 86, 73, 102, 82, 85, 90,
     7, 29, 21, 44, 40, 31, 44, 7,
   -17, 16, -2, 15, 14, 0, 15, -13,
   -26, 3, 10, 9, 6, 1, 0, -23,
   -22, 9, 5, -11, -10, -2, 3, -19,
   -31, 8, -7, -37, -36, -14, 3, -31,
     0, 0, 0, 0, 0, 0, 0, 0
]

KNIGHT_TABLE = [
   -66, -53, -75, -75, -10, -55, -58, -70,
    -3, -6, 100, -36, 4, 62, -4, -14,
    10, 67, 1, 74, 73, 27, 62, -2,
    24, 24, 45, 37, 33, 41, 25, 17,
    -1, 5, 31, 21, 22, 35, 2, 0,
   -18, 10, 13, 22, 18, 15, 11, -14,
   -23, -15, 2, 0, 2, 0, -23, -20,
   -74, -23, -26, -24, -19, -35, -22, -69
]

BISHOP_TABLE = [
   -59, -78, -82, -76, -23,-107, -37, -50,
   -11, 20, 35, -42, -39, 31, 2, -22,
    -9, 39, -32, 41, 52, -10, 28, -14,
    25, 17, 20, 34, 26, 25, 15, 10,
    13, 10, 17, 23, 17, 16, 0, 7,
    14, 25, 24, 15, 8, 25, 20, 15,
    19, 20, 11, 6, 7, 6, 20, 16,
    -7, 2, -15, -12, -14, -15, -10, -10
]

ROOK_TABLE = [
    35, 29, 33, 4, 37, 33, 56, 50,
    55, 29, 56, 67, 55, 62, 34, 60,
    19, 35, 28, 33, 45, 27, 25, 15,
     0, 5, 16, 13, 18, -4, -9, -6,
   -28, -35, -16, -21, -13, -29, -46, -30,
   -42, -28, -42, -25, -25, -35, -26, -46,
   -53, -38, -31, -26, -29, -43, -44, -53,
   -30, -24, -18, 5, -2, -18, -31, -32
]

QUEEN_TABLE = [
     6, 1, -8,-104, 69, 24, 88, 26,
    14, 32, 60, -10, 20, 76, 57, 24,
    -2, 43, 32, 60, 72, 63, 43, 2,
     1, -16, 22, 17, 25, 20, -13, -6,
   -14, -15, -2, -5, -1, -10, -20, -22,
   -30, -6, -13, -11, -16, -11, -16, -27,
   -36, -18, 0, -19, -15, -15, -21, -38,
   -39, -30, -31, -13, -31, -36, -34, -42
]

# Middlegame King Table (Ο βασιλιάς κρύβεται στις γωνίες)
KING_TABLE = [
     4, 54, 47, -99, -99, 60, 83, -62,
   -32, 10, 55, 56, 56, 55, 10, 3,
   -62, 12, -57, 44, -67, 28, 37, -31,
   -55, 50, 11, -4, -19, 13, 0, -49,
   -55, -43, -52, -28, -51, -47, -8, -50,
   -47, -42, -43, -79, -64, -32, -29, -32,
    -4, 3, -14, -50, -57, -18, 13, 4,
    17, 30, -3, -14, 6, -1, 40, 18
]

# ΝΕΟΣ ΠΙΝΑΚΑΣ: King Endgame Table (Ο βασιλιάς ελκύεται στο κέντρο)
KING_ENDGAME_TABLE = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50
]

# =============================================================================
# EVALUATE BOARD FUNCTION (UPDATED WITH ENDGAME TRANSITION)
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
    # Μετράμε τα μεγάλα κομμάτια (εκτός από πιόνια και βασιλιάδες)
    major_pieces_count = w_n_count + b_n_count + w_b_count + b_b_count + w_r_count + b_r_count + w_q_count + b_q_count
    
    # Αν έχουν μείνει 4 ή λιγότερα κομμάτια στο ταμπλό, είμαστε σε πλήρες φινάλε (is_endgame = 1.0)
    # Αν είμαστε στην αρχή, is_endgame = 0.0. Ενδιάμεσα έχουμε ομαλή μετάβαση.
    if major_pieces_count <= 4:
        endgame_weight = 1.0
    elif major_pieces_count >= 12:
        endgame_weight = 0.0
    else:
        endgame_weight = (12 - major_pieces_count) / 8.0

    # Δυναμική αξία πιονιού: Από 100 (Middlegame) ανεβαίνει στα 140 (Endgame) για να κυνηγάει την προαγωγή
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

    # 3. Sunfish Piece-Square Table Positioning
    # 1. Πιόνια (Pawns)
    for sq in chess.SquareSet(w_pawns):
        score += PAWN_TABLE[sq ^ 56]
    for sq in chess.SquareSet(b_pawns):
        score -= PAWN_TABLE[sq]

    # 2. Ίπποι (Knights)
    for sq in chess.SquareSet(w_knights):
        score += KNIGHT_TABLE[sq ^ 56]
    for sq in chess.SquareSet(b_knights):
        score -= KNIGHT_TABLE[sq]

    # 3. Αξιωματικοί (Bishops)
    for sq in chess.SquareSet(w_bishops):
        score += BISHOP_TABLE[sq ^ 56]
    for sq in chess.SquareSet(b_bishops):
        score -= BISHOP_TABLE[sq]

    # 4. Πύργοι (Rooks)
    for sq in chess.SquareSet(w_rooks):
        score += ROOK_TABLE[sq ^ 56]
    for sq in chess.SquareSet(b_rooks):
        score -= ROOK_TABLE[sq]

    # 5. Βασίλισσες (Queens)
    for sq in chess.SquareSet(w_queens):
        score += QUEEN_TABLE[sq ^ 56]
    for sq in chess.SquareSet(b_queens):
        score -= QUEEN_TABLE[sq]

    # 6. Βασιλιάς (King) - Δυναμική εναλλαγή μεταξύ Middlegame και Endgame
    wk = board.king(chess.WHITE)
    bk = board.king(chess.BLACK)

    if wk is not None:
        mg_king_score = KING_TABLE[wk ^ 56]
        eg_king_score = KING_ENDGAME_TABLE[wk ^ 56]
        # Γραμμική ανάμειξη των δύο πινάκων ανάλογα με τη φάση
        score += int((1 - endgame_weight) * mg_king_score + endgame_weight * eg_king_score)
        
    if bk is not None:
        mg_king_score = KING_TABLE[bk]
        eg_king_score = KING_ENDGAME_TABLE[bk]
        score -= int((1 - endgame_weight) * mg_king_score + endgame_weight * eg_king_score)

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
    # Killer table
    if not board.is_capture(move):
        # Shift προηγούμενο killer
        killer_moves[ply][1] = killer_moves[ply][0]
        killer_moves[ply][0] = move

        # History heuristic
        piece = board.piece_at(move.from_square)
        if piece:
            history_heuristic[(piece.piece_type, move.to_square)] += depth * depth

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
        score = quiescence(board, alpha, beta, maximizing, start_time, time_limit, ply=ply)
        return score, []

    # Κρατάμε τις αρχικές τιμές των alpha/beta για τον καθορισμό του TT flag στο τέλος
    original_alpha = alpha
    original_beta = beta

    # 4. --- ΑΝΑΓΝΩΣΗ ΑΠΟ ΤΟ TRANSPOSITION TABLE ---
    zobrist_key = chess.polyglot.zobrist_hash(board)
    tt_entry = transposition_table.get(zobrist_key)
    tt_move = None

    if tt_entry is not None:
        tt_move_uci = tt_entry.get('best_move')
        if tt_move_uci:
            try:
                tt_move = chess.Move.from_uci(tt_move_uci)
            except:
                tt_move = None

        # Χρησιμοποιούμε την τιμή του TT μόνο αν προέρχεται από ίσο ή μεγαλύτερο βάθος
        if tt_entry['depth'] >= depth:
            tt_score = tt_entry['score']
            tt_flag = tt_entry['flag']
            
            # Διόρθωση Mate Scores για το τρέχον Ply (προαιρετικό αλλά σωστό)
            if tt_score > 8000: tt_score -= ply
            elif tt_score < -8000: tt_score += ply

            if tt_flag == TT_EXACT:
                return tt_score, [tt_move] if tt_move and tt_move in board.legal_moves else []
            elif tt_flag == TT_ALPHA and tt_score <= alpha:
                return alpha, [tt_move] if tt_move and tt_move in board.legal_moves else []
            elif tt_flag == TT_BETA and tt_score >= beta:
                return beta, [tt_move] if tt_move and tt_move in board.legal_moves else []

    # 5. --- MOVE ORDERING ---
    scored_moves = []
    for move in board.legal_moves:
        score_val = score_move(move, board, ply)
        scored_moves.append((score_val, move))
    
    scored_moves.sort(key=lambda x: x[0], reverse=True)
    moves = [item[1] for item in scored_moves]

    # Προτεραιότητα 1η: Η κίνηση από το Transposition Table
    if tt_move and tt_move in moves:
        moves.remove(tt_move)
        moves.insert(0, tt_move)

    # Προτεραιότητα 2η: Το εξωτερικό best_move_hint (από το προηγούμενο Depth)
    if best_move_hint:
        hint = best_move_hint[0] if isinstance(best_move_hint, list) and best_move_hint else best_move_hint
        if hint in moves:
            moves.remove(hint)
            # Αν υπάρχει ήδη η tt_move στην αρχή, τη βάζουμε στη θέση 1 αντί για τη 0
            insert_idx = 1 if (tt_move and moves and moves[0] == tt_move) else 0
            moves.insert(insert_idx, hint)

    # Παράμετρος μείωσης βάθους για NMP
    R = 1 if depth < 5 else 2 

    is_prev_move_null = False
    if board.move_stack:
        is_prev_move_null = (board.move_stack[-1] == chess.Move.null())

    # --- MAXIMIZING PLAYER ---
    if maximizing:
        # --- NULL MOVE PRUNING ---
        if not is_prev_move_null and depth >= 3 and not board.is_check():
            if has_major_pieces(board, board.turn):
                board.push(chess.Move.null())
                null_score, _ = minimax(board, depth - 1 - R, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                board.pop()
                
                if null_score is None: return None, None
                if null_score >= beta:
                    return beta, [] 

        best = -float("inf")
        best_line = []
        
        # Λούπα κινήσεων με μετρητή (index) για το LMR
        for moves_searched, move in enumerate(moves):
            board.push(move)
            
            if board.is_repetition(3):
                score = evaluate_board(board)
                score = score - 3 if score >= 5.0 else 0
                line = []
            else:
                # --- LATE MOVE REDUCTIONS (LMR) ---
                # Προϋποθέσεις: μετά την 3η κίνηση, βάθος >= 3, όχι σαχ, όχι φάγωμα/προαγωγή
                if (moves_searched >= 3 and depth >= 3 
                        and not board.is_check() 
                        and not board.is_capture(move) 
                        and move.promotion is None):
                    
                    reduction = 1  # Μειώνουμε το βάθος κατά 1 βήμα
                    score, line = minimax(board, depth - 1 - reduction, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                    
                    # Αν η κίνηση αποδειχθεί καλή (score > alpha), κάνουμε Re-search σε πλήρες βάθος
                    if score is not None and score > alpha:
                        score, line = minimax(board, depth - 1, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                else:
                    # Κανονική αναζήτηση
                    score, line = minimax(board, depth - 1, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
            
            board.pop()

            if score is None: return None, None

            if score > best:
                best = score
                best_line = [move] + line

            alpha = max(alpha, best)
            if beta <= alpha:
                update_killer_history(move, board, ply, depth)
                break
                
        # --- ΑΠΟΘΗΚΕΥΣΗ ΣΤΟ TT (Maximizing) ---
        if best <= original_alpha:
            flag = TT_ALPHA
        elif best >= original_beta:
            flag = TT_BETA
        else:
            flag = TT_EXACT

        if tt_entry is None or depth >= tt_entry['depth']:
            if len(transposition_table) >= MAX_TT_SIZE:
                # Καθαρισμός των πρώτων 20.000 εγγραφών αν γεμίσει η RAM του Android
                for k in list(transposition_table.keys())[:20000]:
                    transposition_table.pop(k, None)
            
            transposition_table[zobrist_key] = {
                'score': best,
                'depth': depth,
                'flag': flag,
                'best_move': best_line[0].uci() if best_line else None
            }

        return best, best_line

    # --- MINIMIZING PLAYER ---
    else:
        # --- NULL MOVE PRUNING ---
        if not is_prev_move_null and depth >= 3 and not board.is_check():
            if has_major_pieces(board, board.turn):
                board.push(chess.Move.null())
                null_score, _ = minimax(board, depth - 1 - R, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                board.pop()
                
                if null_score is None: return None, None
                if null_score <= alpha:
                    return alpha, [] 

        best = float("inf")
        best_line = []
        
        # Λούπα κινήσεων με μετρητή (index) για το LMR
        for moves_searched, move in enumerate(moves):
            board.push(move)
            
            if board.is_repetition(3):
                score = evaluate_board(board)
                score = score + 3 if score <= -5.0 else 0
                line = []
            else:
                # --- LATE MOVE REDUCTIONS (LMR) ---
                if (moves_searched >= 3 and depth >= 3 
                        and not board.is_check() 
                        and not board.is_capture(move) 
                        and move.promotion is None):
                    
                    reduction = 1
                    score, line = minimax(board, depth - 1 - reduction, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                    
                    # Αν η κίνηση αποδειχθεί "επικίνδυνη" για τον Λευκό (score < beta), Re-search σε πλήρες βάθος
                    if score is not None and score < beta:
                        score, line = minimax(board, depth - 1, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                else:
                    score, line = minimax(board, depth - 1, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
            
            board.pop()

            if score is None: return None, None

            if score < best:
                best = score
                best_line = [move] + line

            beta = min(beta, best)
            if beta <= alpha:
                update_killer_history(move, board, ply, depth)
                break
                
        # --- ΑΠΟΘΗΚΕΥΣΗ ΣΤΟ TT (Minimizing) ---
        if best <= original_alpha:
            flag = TT_ALPHA
        elif best >= original_beta:
            flag = TT_BETA
        else:
            flag = TT_EXACT

        if tt_entry is None or depth >= tt_entry['depth']:
            if len(transposition_table) >= MAX_TT_SIZE:
                for k in list(transposition_table.keys())[:20000]:
                    transposition_table.pop(k, None)
            
            transposition_table[zobrist_key] = {
                'score': best,
                'depth': depth,
                'flag': flag,
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