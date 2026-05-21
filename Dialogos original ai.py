import importlib
import time
import random
import os
import chess
import chess.polyglot
import queue
import threading
from collections import defaultdict

killer_moves = [[None, None] for _ in range(64)]
history_heuristic = defaultdict(int)
# -------------------------
# Φόρτωση python-chess
# -------------------------
chess_lib = importlib.import_module("chess")

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

# -------------------------
# Piece values
# -------------------------
piece_values = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}
# ==================================================
# KING PIECE-SQUARE TABLES
# ==================================================

KING_MID_TABLE = [
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20, 0, 0, 0, 0, 20, 20,
     20, 30, 10, 0, 0, 10, 30, 20
]

KING_END_TABLE = [
    -50,-40,-30,-20,-20,-30,-40,-50,
    -30,-20,-10, 0, 0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30, 0, 0, 0, 0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50
]

# ==================================================
# KNIGHT & BISHOP PIECE-SQUARE TABLES
# ==================================================

KNIGHT_TABLE = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]

BISHOP_TABLE = [
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
]

def mirror(square):
    return chess.square_mirror(square)

# --- Προ-υπολογισμένες μάσκες για μέγιστη ταχύτητα στην αρχή του αρχείου ---
BB_CENTER = chess.BB_D4 | chess.BB_E4 | chess.BB_D5 | chess.BB_E5
BB_RIM_FILES = chess.BB_FILE_A | chess.BB_FILE_H

def evaluate_board(board):
    # ==================================================
    # Terminal states
    # ==================================================
    if board.is_checkmate():
        return -99999 if board.turn else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0

    # ==================================================
    # Fast Material & Endgame Detection (Bitwise)
    # ==================================================
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

    # Ασφαλής καταμέτρηση bit για παλαιότερες εκδόσεις βιβλιοθήκης
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

    # 1. Υλικό (Material)
    score += w_p_count * piece_values[chess.PAWN] - b_p_count * piece_values[chess.PAWN]
    score += w_n_count * piece_values[chess.KNIGHT] - b_n_count * piece_values[chess.KNIGHT]
    score += w_b_count * piece_values[chess.BISHOP] - b_b_count * piece_values[chess.BISHOP]
    score += w_r_count * piece_values[chess.ROOK] - b_r_count * piece_values[chess.ROOK]
    score += w_q_count * piece_values[chess.QUEEN] - b_q_count * piece_values[chess.QUEEN]

    # 2. Προσδιορισμός Endgame
    w_major_minor = w_n_count + w_b_count + w_r_count
    b_major_minor = b_n_count + b_b_count + b_r_count
    endgame = (w_q_count == 0 or w_major_minor <= 1) and (b_q_count == 0 or b_major_minor <= 1)

    # ==================================================
    # PIECE-SQUARE TABLE BONUSES
    # ==================================================
        # ==================================================
    # PIECE-SQUARE TABLE BONUSES (ΔΙΟΡΘΩΜΕΝΟ ΓΙΑ ΡΟΚΕ)
    # ==================================================
    # 1. Βασιλιάς (King)
    wk = board.king(chess.WHITE)
    bk = board.king(chess.BLACK)

    if wk is not None:
        # Χρησιμοποιούμε το mirror και στον λευκό επειδή οι πίνακες είναι top-down
        score += KING_END_TABLE[chess.square_mirror(wk)] if endgame else KING_MID_TABLE[chess.square_mirror(wk)]

    if bk is not None:
        # Για τον μαύρο, επειδή οι πίνακες είναι ήδη top-down για τα λευκά, 
        # απλά διαβάζουμε απευθείας την αντίστοιχη θέση (χωρίς mirror)
        score -= KING_END_TABLE[bk] if endgame else KING_MID_TABLE[bk]


    # 2. Άλογα (Knights)
    for sq in chess.SquareSet(w_knights):
        score += KNIGHT_TABLE[sq]
    for sq in chess.SquareSet(b_knights):
        score -= KNIGHT_TABLE[chess.square_mirror(sq)]

    # 3. Αξιωματικοί (Bishops)
    for sq in chess.SquareSet(w_bishops):
        score += BISHOP_TABLE[sq]
    for sq in chess.SquareSet(b_bishops):
        score -= BISHOP_TABLE[chess.square_mirror(sq)]

    all_pawns = board.pawns



    # ==================================================
    # ROOK STRATEGY
    # ==================================================
    for r_sq in chess.SquareSet(w_rooks):
        f_idx = chess.square_file(r_sq)
        r_idx = chess.square_rank(r_sq)
        if r_idx == 6: score += 25
        if f_idx in (3, 4): score += 10
        f_mask = chess.BB_FILES[f_idx]
        if not (all_pawns & f_mask): score += 20
        elif not (w_pawns & f_mask): score += 12

    for r_sq in chess.SquareSet(b_rooks):
        f_idx = chess.square_file(r_sq)
        r_idx = chess.square_rank(r_sq)
        if r_idx == 1: score -= 25
        if f_idx in (3, 4): score -= 10
        f_mask = chess.BB_FILES[f_idx]
        if not (all_pawns & f_mask): score -= 20
        elif not (b_pawns & f_mask): score -= 12

    # ==================================================
    # Natural Development (Knights & Bishops)
    # ==================================================
    for sq in chess.SquareSet(w_bishops):
        if chess.square_rank(sq) > 0: score += 15
        score += int(board.attacks(sq)).bit_count() * 2
                
    for sq in chess.SquareSet(b_bishops):
        if chess.square_rank(sq) < 7: score -= 15
        score -= int(board.attacks(sq)).bit_count() * 2

    for sq in chess.SquareSet(w_knights):
        f, r = chess.square_file(sq), chess.square_rank(sq)
        score += int(8 - (abs(f - 3.5) + abs(r - 3.5))) * 4
        if (chess.BB_SQUARES[sq] & BB_RIM_FILES): score -= 15
        if board.fullmove_number <= 12 and sq in (chess.C3, chess.F3): score += 25

    for sq in chess.SquareSet(b_knights):
        f, r = chess.square_file(sq), chess.square_rank(sq)
        score -= int(8 - (abs(f - 3.5) + abs(r - 3.5))) * 4
        if (chess.BB_SQUARES[sq] & BB_RIM_FILES): score += 15
        if board.fullmove_number <= 12 and sq in (chess.C6, chess.F6): score -= 25

    # ==================================================
    # STRATEGIC EXTRAS (Space, Batteries, Pairs)
    # ==================================================
    for sq in (chess.D4, chess.E4, chess.D5, chess.E5):
        if board.is_attacked_by(chess.WHITE, sq): score += 8
        if board.is_attacked_by(chess.BLACK, sq): score -= 8

    if w_r_count >= 2:
        w_r_list = list(chess.SquareSet(w_rooks))
        if chess.square_file(w_r_list[0]) == chess.square_file(w_r_list[1]) or chess.square_rank(w_r_list[0]) == chess.square_rank(w_r_list[1]):
            score += 15
            
    if b_r_count >= 2:
        b_r_list = list(chess.SquareSet(b_rooks))
        if chess.square_file(b_r_list[0]) == chess.square_file(b_r_list[1]) or chess.square_rank(b_r_list[0]) == chess.square_rank(b_r_list[1]):
            score -= 15
                
    if w_b_count >= 2: score += 30
    if b_b_count >= 2: score -= 30

    # ==================================================
    # 9. ENDGAME SPECIFIC LOGIC (The Closer)
    # ==================================================
    if endgame:
        if wk is not None:
            score += (3.5 - abs(chess.square_file(wk) - 3.5)) * 10
            score += (3.5 - abs(chess.square_rank(wk) - 3.5)) * 10
        if bk is not None:
            score -= (3.5 - abs(chess.square_file(bk) - 3.5)) * 10
            score -= (3.5 - abs(chess.square_rank(bk) - 3.5)) * 10

        # Rook Behind Passed Pawns
        for p_sq in chess.SquareSet(w_pawns):
            f = chess.square_file(p_sq)
            r = chess.square_rank(p_sq)
            for r_sq in chess.SquareSet(w_rooks):
                if chess.square_file(r_sq) == f and chess.square_rank(r_sq) < r:
                    score += 25

        for p_sq in chess.SquareSet(b_pawns):
            f = chess.square_file(p_sq)
            r = chess.square_rank(p_sq)
            for r_sq in chess.SquareSet(b_rooks):
                if chess.square_file(r_sq) == f and chess.square_rank(r_sq) > r:
                    score -= 25

    # ==================================================
    # KING SAFETY & DEFENSE
    # ==================================================
    if wk is not None:
        w_penalty = 0
        if board.attackers(chess.BLACK, wk): w_penalty += 20
        w_penalty -= int(board.occupied_co[chess.WHITE] & chess.BB_KING_ATTACKS[wk]).bit_count() * 10
        if not (w_pawns & chess.BB_FILES[chess.square_file(wk)]): w_penalty += 45
        score -= w_penalty

    if bk is not None:
        b_penalty = 0
        if board.attackers(chess.WHITE, bk): b_penalty += 20
        b_penalty -= int(board.occupied_co[chess.BLACK] & chess.BB_KING_ATTACKS[bk]).bit_count() * 10
        if not (b_pawns & chess.BB_FILES[chess.square_file(bk)]): b_penalty += 45
        score += b_penalty

    all_pawns = board.pawns

    # ==================================================
    # ΜΠΟΝΟΥΣ ΟΤΑΝ ΤΑ ΚΕΝΤΡΙΚΑ ΠΙΟΝΙΑ ΕΧΟΥΝ ΠΡΟΧΩΡΗΣΕΙ
    # ==================================================
    
    # 1. ΛΕΥΚΑ ΠΙΟΝΙΑ (d2, e2)
    # Αν το πιόνι ΔΕΝ είναι πια στο d2, σημαίνει ότι πήγε d3 ή d4 -> Δώσε μπόνους!
    if board.piece_at(chess.D2) != chess.Piece(chess.PAWN, chess.WHITE):
        score += 25  

    # Αν το πιόνι ΔΕΝ είναι πια στο e2, σημαίνει ότι πήγε e3 ή e4 -> Δώσε μπόνους!
    if board.piece_at(chess.E2) != chess.Piece(chess.PAWN, chess.WHITE):
        score += 25  


    # 2. ΜΑΥΡΑ ΠΙΟΝΙΑ (d7, e7)
    # Αν το πιόνι ΔΕΝ είναι πια στο d7, σημαίνει ότι πήγε d6 ή d5 -> Δώσε μπόνους στα μαύρα!
    if board.piece_at(chess.D7) != chess.Piece(chess.PAWN, chess.BLACK):
        score -= 25  

    # Αν το πιόνι ΔΕΝ είναι πια στο e7, σημαίνει ότι πήγε e6 ή e5 -> Δώσε μπόνους στα μαύρα!
    if board.piece_at(chess.E7) != chess.Piece(chess.PAWN, chess.BLACK):
        score -= 25  


    # ==================================================
    # ΣΥΣΤΗΜΑ ΠΙΟΝΙΩΝ
    # ==================================================
    w_p_files = [chess.square_file(p) for p in chess.SquareSet(w_pawns)]
    b_p_files = [chess.square_file(p) for p in chess.SquareSet(b_pawns)]

    # White Pawns
    for p in chess.SquareSet(w_pawns):
        rank = chess.square_rank(p)
        file = chess.square_file(p)
        score += rank * 4
        if rank in (5, 6): score += 10
        if rank == 1: score += 5

        enemy_attacked = board.attacks(p) & board.occupied_co[chess.BLACK]
        if enemy_attacked: score += int(enemy_attacked).bit_count() * 8

        if w_p_files.count(file) > 1: score -= 10
        if file > 0 and (file - 1) not in w_p_files and file < 7 and (file + 1) not in w_p_files: score -= 10

        if not endgame and p in (chess.E2, chess.E3, chess.E4, chess.D2, chess.D3, chess.D4):
            score += 30
        if endgame:
            score += rank * 15

    # Black Pawns
    for p in chess.SquareSet(b_pawns):
        rank = chess.square_rank(p)
        file = chess.square_file(p)
        advance = 7 - rank
        score -= advance * 4
        if advance in (5, 6): score -= 10
        if rank == 6: score -= 5

        enemy_attacked = board.attacks(p) & board.occupied_co[chess.WHITE]
        if enemy_attacked: score -= int(enemy_attacked).bit_count() * 8

        if b_p_files.count(file) > 1: score += 10
        if file > 0 and (file - 1) not in b_p_files and file < 7 and (file + 1) not in b_p_files: score += 10

        if not endgame and p in (chess.E7, chess.E6, chess.E5, chess.D7, chess.D6, chess.D5):
            score -= 30
        if endgame:
            score -= advance * 15

    # ==================================================
    # Tempo Bonus
    # ==================================================
    score += (15 if board.turn == chess.WHITE else -15)

    return score / 120.0


# -------------------------
# Quiescence Search
# -------------------------
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
    Βέλτιστη Ultra-fast quiescence με SEE, MVV-LVA και διορθωμένο Alpha-Beta Pruning.
    """
    # --------- Stop conditions ---------
    if time.time() - start_time > time_limit or depth >= max_depth:
        return evaluate_board(board)

    # --------- Stand-pat evaluation ---------
    stand = evaluate_board(board)
    
    if maximizing:
        # FAIL-HIGH: Αν η τρέχουσα θέση είναι ήδη καλύτερη από το beta, ο αντίπαλος δεν θα μας αφήσει να έρθουμε εδώ
        if stand >= beta:
            return beta
        alpha = max(alpha, stand)
        
        # --------- Only captures ---------
        raw_moves = [m for m in board.legal_moves if board.is_capture(m)]
        moves = [m for m in raw_moves if fast_see(board, m) >= 0]
        moves.sort(key=lambda m: mvv_lva(m, board), reverse=True)

        for move in moves:
            board.push(move)
            # Αναδρομή για τον minimizing (False)
            score = quiescence(board, alpha, beta, False, start_time, time_limit, max_depth, depth + 1, ply=ply+1)
            board.pop()

            if score is None: return None
            
            alpha = max(alpha, score)
            if alpha >= beta or time.time() - start_time > time_limit:
                break
        return alpha

    else:
        # FAIL-LOW: Αν η τρέχουσα θέση είναι χειρότερη από το alpha, εμείς δεν θα επιλέξουμε αυτή τη βαριάντα
        if stand <= alpha:
            return alpha
        beta = min(beta, stand)
        
        # --------- Only captures ---------
        raw_moves = [m for m in board.legal_moves if board.is_capture(m)]
        moves = [m for m in raw_moves if fast_see(board, m) >= 0]
        moves.sort(key=lambda m: mvv_lva(m, board), reverse=True)

        for move in moves:
            board.push(move)
            # Αναδρομή για τον maximizing (True)
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
def mvv_lva(move, board):
    """
    Πειραματικό Move Ordering βασισμένο αποκλειστικά σε:
    1) Κοψίματα (Captures) - MVV-LVA
    2) Σαχ (Checks)
    """
    score = 0
    attacker = board.piece_at(move.from_square)

    # 1️⃣ Κοψίματα (Captures)
    if board.is_capture(move):
        # Αν είναι en-passant, το θύμα είναι πιόνι
        if board.is_en_passant(move):
            victim_type = chess.PAWN
        else:
            victim = board.piece_at(move.to_square)
            victim_type = victim.piece_type if victim else chess.PAWN
            
        if attacker:
            # MVV-LVA: (Αξία Θύματος * 10) - Αξία Επιτιθέμενου
            score += 1000 + (piece_values[victim_type] * 10) - piece_values[attacker.piece_type]

    # 2️⃣ Σαχ (Checks) - Απαιτεί push/pop
    board.push(move)
    if board.is_check():
        score += 5000
    board.pop()

    return score

def is_endgame(board):
    """
    Βέλτιστη και υπερ-ταχεία ανίχνευση φινάλε με bitwise πράξεις (100% ίδια στρατηγική λογική).
    """
    # 1. Ακαριαίο μέτρημα βαριών κομματιών με bit_count()
    w_heavy = board.knights | board.bishops | board.rooks | board.queens
    b_heavy = board.knights | board.bishops | board.rooks | board.queens
    
    material_count = int(w_heavy & board.occupied_co[chess.WHITE]).bit_count() + \
                     int(b_heavy & board.occupied_co[chess.BLACK]).bit_count()

    free_pawn_count = 0
    occupied = board.occupied

    # 2. Έλεγχος προωθήσιμων πιόνιων με bitwise μάσκες (χωρίς loops και piece_at)
    w_pawns = board.pawns & board.occupied_co[chess.WHITE]
    b_pawns = board.pawns & board.occupied_co[chess.BLACK]

    # Για τα λευκά πιόνια
    for sq in chess.SquareSet(w_pawns):
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        # Μάσκα για τα τετράγωνα μπροστά από το πιόνι στην ίδια στήλη
        front_squares = chess.BB_FILES[file] & ~chess.BB_RANKS[rank]
        # Κρατάμε μόνο αυτά που είναι πιο πάνω από το πιόνι
        for r in range(rank + 1):
            front_squares &= ~chess.BB_RANKS[r]
            
        # Αν υπάρχει έστω και ένα κενό τετράγωνο μπροστά (δηλαδή τα μπροστινά τετράγωνα δεν είναι πλήρως κατειλημμένα)
        if int(front_squares & ~occupied).bit_count() > 0:
            free_pawn_count += 1

    # Για τα μαύρα πιόνια
    for sq in chess.SquareSet(b_pawns):
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        # Μάσκα για τα τετράγωνα μπροστά από το πιόνι στην ίδια στήλη
        front_squares = chess.BB_FILES[file] & ~chess.BB_RANKS[rank]
        # Κρατάμε μόνο αυτά που είναι πιο κάτω από το πιόνι
        for r in range(rank, 8):
            front_squares &= ~chess.BB_RANKS[r]

        if int(front_squares & ~occupied).bit_count() > 0:
            free_pawn_count += 1

    # Κανόνας φινάλε (Ακριβώς τα ίδια όρια με τη δική σας στρατηγική)
    if material_count <= 4 or free_pawn_count <= 3:
        return True
    return False


def find_best_move(board, depth, nodes, start_time, time_limit):
    # Ξεκινάμε με το "μείον άπειρο" για να μπορεί να βρεθεί οποιοδήποτε σκορ
    best_score = -float('inf')
    best_move = None
    
    # ΑΥΤΟ ΔΙΟΡΘΩΝΕΙ ΤΑ ΜΑΥΡΑ:
    # Αν είναι η σειρά των Λευκών, multiplier = 1 (κρατάμε το σκορ ως έχει).
    # Αν είναι η σειρά των Μαύρων, multiplier = -1 (αντιστρέφουμε το σκορ).
    multiplier = 1 if board.turn == chess.WHITE else -1

    # Move Ordering και στο Root για ταχύτητα
    moves = list(board.legal_moves)
    moves.sort(key=lambda m: score_move(m, board, 0), reverse=True)

    for move in moves:
        if is_hanging_piece_root(board, move):
            continue

        board.push(move)
        # Καλούμε τη minimax. Το 'not board.turn' στέλνει το σωστό maximizing flag
        score, _ = minimax(board, depth - 1, -999999, 999999, not board.turn, nodes, start_time, time_limit, ply=1)
        board.pop()

        if score is None: return None # Διακοπή λόγω χρόνου

        # ΜΕΤΑΤΡΟΠΗ ΣΚΟΡ:
        # Αν τα Μαύρα βρήκαν σκορ -500 (καλό για αυτά), το κάνουμε +500
        # ώστε η σύγκριση (actual_score > best_score) να το επιλέξει!
        actual_score = score * multiplier

        if actual_score > best_score:
            best_score = actual_score
            best_move = move

    return best_move


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
    score = mvv_lva(move, board) # η υπάρχουσα σου συνάρτηση

    # Killer moves
    if move == killer_moves[ply][0]:
        score += 900000
    elif move == killer_moves[ply][1]:
        score += 800000

    # History heuristic
    piece = board.piece_at(move.from_square)
    if piece:
        score += history_heuristic[(piece.piece_type, move.to_square)]

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


import chess.polyglot

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

    # 3. --- TERMINAL / GAME OVER (ΔΙΟΡΘΩΜΕΝΟ ΓΙΑ ΑΠΟΦΥΓΗ ΙΣΟΠΑΛΙΑΣ) ---
    if depth == 0 or board.is_game_over():
        if depth == 0 or board.is_checkmate():
            score = quiescence(board, alpha, beta, maximizing, start_time, time_limit, ply=ply)
            return score, []
        else:
            # Αν το παιχνίδι τελείωσε με Stalemate / 50 κινήσεις και είμαστε κερδισμένοι, δίνουμε ποινή
            current_eval = evaluate_board(board)
            if maximizing:
                return (-300 if current_eval > 1.0 else 0), []
            else:
                return (300 if current_eval < -1.0 else 0), []

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
                # ΔΙΟΡΘΩΜΕΝΟ: Ποινή -300 αν είμαστε στο +3 (πάνω από 1.0) για να αποφύγει την επανάληψη
                score = -300 if score > 1.0 else 0
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
                # ΔΙΟΡΘΩΜΕΝΟ: Αν ο Μαύρος κερδίζει (κάτω από -1.0), δίνουμε +300 για να μην δεχτεί ισοπαλία
                score = 300 if score < -1.0 else 0
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

            while True:
                if not input_queue.empty() or (time.time() - start_time >= time_limit):
                    break

                result = minimax(board, depth, -float('inf'), float('inf'), board.turn,
                                 nodes_counter, start_time, time_limit,
                                 best_move_hint=last_best_move,
                                 interrupt_queue=input_queue)

                if result is not None and result[0] is not None:
                    score, line = result
                    best_score_full = score
                    best_line_full = line
                    last_best_move = line[0] if line else None
                    
                    move_san = board.san(best_line_full[0]) if best_line_full else "???"
                    print(f"\r\033[36m[Depth {depth:2d}] Best: {move_san:5} | Eval: {score:+.2f} | Nodes: {nodes_counter[0]}\033[0m", flush=True)
                    
                    if abs(score) >= 9000:
                        break
                else:
                    break

                depth += 1
                if depth > 25: break

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
            print("\033[1;32m==> Η σειρά σου!\033[0m")
            move_str = input("\033[36mΗ κίνησή σου (e2e4 | undo | reset):\033[0m ").strip().lower()

            if move_str == "undo":
                if len(board.move_stack) >= 2:
                    board.pop(); board.pop()
                    print("\033[1;32m>> Undo έγινε.\033[0m")
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

    print("\n\033[1;32m--- Τελικό Αποτέλεσμα ---\033[0m")
    if board.is_checkmate(): print("\033[1;36m>> ΜΑΤ!\033[0m")
    else: print("\033[36m>> Το παιχνίδι έληξε.\033[0m")


if __name__ == "__main__":
    interactive_gameplay()
