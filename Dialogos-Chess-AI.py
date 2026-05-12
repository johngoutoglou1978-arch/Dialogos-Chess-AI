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

def mirror(square):
    return chess.square_mirror(square)

# -------------------------
# Board Evaluation
# -------------------------
def evaluate_board(board):

    # ==================================================
    # Terminal states
    # ==================================================
    if board.is_checkmate():
        return -99999 if board.turn else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    endgame = is_endgame(board) 

    wk = board.king(chess.WHITE)
    bk = board.king(chess.BLACK)

    # ==================================================
    # KING PIECE-SQUARE TABLE BONUS
    # ==================================================
    if wk is not None:
        if endgame:
            score += KING_END_TABLE[wk]
        else:
            score += KING_MID_TABLE[wk]

    if bk is not None:
        mirrored = mirror(bk)
        if endgame:
            score -= KING_END_TABLE[mirrored]
        else:
            score -= KING_MID_TABLE[mirrored]

    # ==================================================
    # Material
    # ==================================================
    for p in piece_values: 
        score += len(board.pieces(p, chess.WHITE)) * piece_values[p]
        score -= len(board.pieces(p, chess.BLACK)) * piece_values[p]

    # ==================================================
    # ROOK STRATEGY
    # ==================================================
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else -1
        for r_sq in board.pieces(chess.ROOK, color):
            f_idx = chess.square_file(r_sq)
            r_idx = chess.square_rank(r_sq)
            
            if (color == chess.WHITE and r_idx == 6) or (color == chess.BLACK and r_idx == 1):
                score += 25 * sign
            
            f_mask = chess.BB_FILES[f_idx]
            w_pawns = board.pieces(chess.PAWN, chess.WHITE) & f_mask
            b_pawns = board.pieces(chess.PAWN, chess.BLACK) & f_mask
            
            if not w_pawns and not b_pawns:
                score += 20 * sign
            elif (color == chess.WHITE and not w_pawns) or (color == chess.BLACK and not b_pawns):
                score += 12 * sign
            
            if f_idx in [3, 4]:
                score += 10 * sign

    # ==================================================
    # Natural Development (Knights & Bishops)
    # ==================================================
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else -1
        
        for sq in board.pieces(chess.BISHOP, color):
            rank = chess.square_rank(sq)
            if (color == chess.WHITE and rank > 0) or (color == chess.BLACK and rank < 7):
                score += 15 * sign
            score += len(board.attacks(sq)) * 2 * sign
                
        for sq in board.pieces(chess.KNIGHT, color):
            f, r = chess.square_file(sq), chess.square_rank(sq)
            dist_to_center = abs(f - 3.5) + abs(r - 3.5)
            score += (8 - dist_to_center) * 4 * sign

            if board.fullmove_number <= 12:
                if color == chess.WHITE:
                    if sq in [chess.C3, chess.F3]:
                        score += 25
                else:
                    if sq in [chess.C6, chess.F6]:
                        score -= 25

    # STRATEGIC EXTRAS (Space, Trapped Pieces, Batteries)
    # ==================================================
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else -1
        
        # 1. Control of the Big Center (d4, e4, d5, e5)
        center_squares = [chess.D4, chess.E4, chess.D5, chess.E5]
        for sq in center_squares:
            if board.is_attacked_by(color, sq):
                score += 8 * sign
        
        # 2. Knight on the Rim Penalty (a/h files)
        for sq in board.pieces(chess.KNIGHT, color):
            if chess.square_file(sq) in [0, 7]:
                score -= 15 * sign

        # 3. Rook/Queen Batteries (Aligned on same file/rank)
        rooks = list(board.pieces(chess.ROOK, color))
        if len(rooks) >= 2:
            if chess.square_file(rooks[0]) == chess.square_file(rooks[1]) or \
               chess.square_rank(rooks[0]) == chess.square_rank(rooks[1]):
                score += 15 * sign
                
        # 4. Bishop Pair (Αν δεν το έχεις ήδη)
        if len(board.pieces(chess.BISHOP, color)) >= 2:
            score += 30 * sign
    # ==================================================
    # 9. ENDGAME SPECIFIC LOGIC (The Closer)
    # ==================================================
    if endgame:
        # --- King Centralization ---
        # Ο Βασιλιάς πρέπει να βγει από την κρυψώνα του
        wk_f, wk_r = chess.square_file(wk), chess.square_rank(wk)
        bk_f, bk_r = chess.square_file(bk), chess.square_rank(bk)
        
        # Λευκός Βασιλιάς στο κέντρο
        score += (3.5 - abs(wk_f - 3.5)) * 10
        score += (3.5 - abs(wk_r - 3.5)) * 10
        # Μαύρος Βασιλιάς στο κέντρο
        score -= (3.5 - abs(bk_f - 3.5)) * 10
        score -= (3.5 - abs(bk_r - 3.5)) * 10

        # --- Rook Behind Passed Pawns ---
        for color in [chess.WHITE, chess.BLACK]:
            sign = 1 if color == chess.WHITE else -1
            r_mask = board.pieces(chess.ROOK, color)
            p_mask = board.pieces(chess.PAWN, color)
            
            for p_sq in p_mask:
                # Αν είναι passed pawn
                f = chess.square_file(p_sq)
                r = chess.square_rank(p_sq)
                # Έλεγχος αν υπάρχει πύργος από πίσω στην ίδια στήλη
                for r_sq in r_mask:
                    if chess.square_file(r_sq) == f:
                        if (color == chess.WHITE and chess.square_rank(r_sq) < r) or \
                           (color == chess.BLACK and chess.square_rank(r_sq) > r):
                            score += 25 * sign
                            
                                # --- KING SAFETY & CHECK AVERSION KNOWLEDGE ---
    for color in [chess.WHITE, chess.BLACK]:
        side_penalty = 0
        king_sq = board.king(color)
        
        # 1. Ποινή αν ο αντίπαλος έχει ΕΤΟΙΜΟ σαχ (Πρόληψη)
        # Ελέγχουμε αν ο βασιλιάς δέχεται επίθεση από οποιοδήποτε εχθρικό κομμάτι
        if board.attackers(not color, king_sq):
            side_penalty += 50 

        # 2. King Proximity (Αμυντική ζώνη)
        # Επιβράβευση αν δικά μας κομμάτια είναι στα 8 τετράγωνα γύρω από τον βασιλιά
        adj_squares = chess.BB_KING_ATTACKS[king_sq]
        defenders = board.occupied_co[color] & adj_squares
        side_penalty -= bin(defenders).count("1") * 10

        # 3. Ανοιχτές στήλες (Shield)
        # Ποινή αν δεν υπάρχει δικό μας πιόνι στην ίδια στήλη με τον βασιλιά
        file_mask = chess.BB_FILES[chess.square_file(king_sq)]
        if not (board.pieces(chess.PAWN, color) & file_mask):
            side_penalty += 45

        # Ενημέρωση του συνολικού score (Αφαιρούμε για λευκά, προσθέτουμε για μαύρα)
        if color == chess.WHITE:
            score -= side_penalty
        else:
            score += side_penalty

    # --- ΣΥΣΤΗΜΑ ΠΙΟΝΙΩΝ ---
    for color in [chess.WHITE, chess.BLACK]:
        sign = 1 if color == chess.WHITE else -1
        pawns = list(board.pieces(chess.PAWN, color))
        files = [chess.square_file(p) for p in pawns]

        for p in pawns:
            rank = chess.square_rank(p)
            file = chess.square_file(p)
            advance = rank if color == chess.WHITE else 7 - rank

            # 1. Μπόνους προώθησης
            score += advance * 4 * sign
            if advance == 5:
                score += 10 * sign
            elif advance == 6:
                score += 10 * sign

            # 2. Αρχική θέση
            if (color == chess.WHITE and rank == 1) or (color == chess.BLACK and rank == 6):
                score += 5 * sign

            # 3. Επίθεση σε κομμάτια
            for t in board.attacks(p):
                piece = board.piece_at(t)
                if piece and piece.color != color:
                    score += 8 * sign

            # 4. Δομή (Διπλά και Μονωμένα πιόνια)
            if files.count(file) > 1:
                score -= 10 * sign
            if file > 0 and file - 1 not in files and file < 7 and file + 1 not in files:
                score -= 10 * sign

            # 5. Πιόνια κέντρου (d/e)
            if not endgame:
                if color == chess.WHITE:
                    if p in (chess.E2, chess.E3, chess.E4, chess.D2, chess.D3, chess.D4):
                        score += 30
                else:
                    if p in (chess.E7, chess.E6, chess.E5, chess.D7, chess.D6, chess.D5):
                        score -= 30

            # 6. Ελεύθερα πιόνια στο φινάλε (Passed Pawns)
            if endgame:
                distance = (7 - rank) if color == chess.WHITE else rank
                score += (7 - distance) * 15 * sign
    # --- ΤΕΛΟΣ ΣΥΣΤΗΜΑΤΟΣ ΠΙΟΝΙΩΝ ---

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

def quiescence(board, alpha, beta, maximizing, start_time, time_limit, max_depth=0, depth=0, ply=0):
    """
    Η δική σου Ultra-fast quiescence ενισχυμένη με SEE:
    - Μόνο captures που "βγάζουν νόημα"
    - Δεν παίζει captures στο πρώτο ply (ply==0)
    """
    # --------- Stop conditions ---------
    if time.time() - start_time > time_limit or depth >= max_depth:
        return evaluate_board(board)

    # --------- Stand-pat evaluation ---------
    stand = evaluate_board(board)
    if maximizing:
        alpha = max(alpha, stand)
    else:
        beta = min(beta, stand)
    
    if alpha >= beta:
        return stand

    # --------- Αν είμαστε στο πρώτο ply, μην κάνεις captures ---------
    if ply == 0:
        return stand

    # --------- Only captures ---------
    # Φιλτράρισμα με SEE για να πετάμε τις "αυτοκτονικές" κινήσεις
    raw_moves = [m for m in board.legal_moves if board.is_capture(m)]
    moves = [m for m in raw_moves if fast_see(board, m) >= 0]
    
    # Διατήρηση του δικού σου sorting με mvv_lva
    moves.sort(key=lambda m: mvv_lva(m, board), reverse=True)

    for move in moves:
        board.push(move)
        score = quiescence(board, alpha, beta, not maximizing, start_time, time_limit, max_depth, depth + 1, ply=ply+1)
        board.pop()

        if maximizing:
            alpha = max(alpha, score)
        else:
            beta = min(beta, score)

        if alpha >= beta or time.time() - start_time > time_limit:
            break

    return alpha if maximizing else beta

# -------------------------
# Move Ordering
# -------------------------
def mvv_lva(move, board):
    """
    Custom MVV-LVA / Move Ordering βάση των προτεραιοτήτων σου:
    1) Ροκέ
    2) Άμυνα: μικρότερο πιόνι απειλεί μεγαλύτερο
    3) Σαχ
    4) Απειλή σε κομμάτι αντιπάλου
    5) Κοψίματα (captures)
    6) Υπόλοιπες κινήσεις
    """
    score = 0

    # 1️⃣ Ροκέ
    if board.is_castling(move):
        return 100000

    attacker = board.piece_at(move.from_square)

    # Προυπολογίζουμε attacks για reuse
    attacks_to = list(board.attacks(move.to_square)) if attacker else []

    # 2️⃣ Άμυνα / μικρό απειλεί μεγάλο
    for sq in attacks_to:
        victim = board.piece_at(sq)
        if victim and victim.color != attacker.color:
            if piece_values[attacker.piece_type] < piece_values[victim.piece_type]:
                score += 9000

    # 5️⃣ Κοψίματα
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        if victim and attacker:
            score += 2000 + (
                piece_values[victim.piece_type] - piece_values[attacker.piece_type]
            )

    # Χρησιμοποιούμε push/pop μόνο για check και threat
    board.push(move)

    # 3️⃣ Σαχ
    if board.is_check():
        score += 7000

    # 4️⃣ Απειλή κομματιού
    for sq in attacks_to:
        victim = board.piece_at(sq)
        if victim and victim.color != board.turn:
            score += 3000

    board.pop()

    # 6️⃣ Υπόλοιπες κινήσεις
    return score

def is_endgame(board):
    """
    Ανιχνεύει αν είμαστε σε φινάλε:
    - Λίγα βαριά κομμάτια (βασίλισσα, πύργος, ίππος, αξιωματικός)
    - Λίγα πιόνια που μπορούν να προχωρήσουν (με τουλάχιστον ένα κενό μπροστά τους μέχρι τη βάση)
    Επιστρέφει True αν θεωρείται φινάλε, False αλλιώς.
    """
    heavy_pieces = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
    material_count = 0
    free_pawn_count = 0

    # Μέτρημα βαριών κομματιών
    for p in heavy_pieces:
        material_count += len(board.pieces(p, chess.WHITE))
        material_count += len(board.pieces(p, chess.BLACK))

    # Μέτρημα “προωθήσιμων” πιόνιων
    for color in [chess.WHITE, chess.BLACK]:
        for sq in board.pieces(chess.PAWN, color):
            rank = chess.square_rank(sq)
            file = chess.square_file(sq)

            if color == chess.WHITE:
                for r in range(rank + 1, 8):
                    if board.piece_at(chess.square(file, r)) is None:
                        free_pawn_count += 1
                        break
            else:
                for r in range(rank - 1, -1, -1):
                    if board.piece_at(chess.square(file, r)) is None:
                        free_pawn_count += 1
                        break

    # Κανόνας φινάλε: λίγα βαριά κομμάτια ή πολύ λίγα “ελεύθερα” πιόνια
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

def minimax(board, depth, alpha, beta, maximizing, nodes, start_time, time_limit, ply=0, allow_null=True, best_move_hint=None, interrupt_queue=None):

    # 1. --- ΑΚΑΡΙΑΙΟΣ ΕΛΕΓΧΟΣ ΔΙΑΚΟΠΗΣ (Enter ή Time) ---
    if (interrupt_queue is not None and not interrupt_queue.empty()) or (time.time() - start_time >= time_limit):
        return None, None # Επιστρέφουμε None για να ακυρωθεί το ημιτελές βάθος

    # 2. --- COUNT NODES ---
    nodes[0] += 1

    # 3. --- TERMINAL / GAME OVER ---
    if depth == 0 or board.is_game_over():
        # Σημείωση: Αν θέλεις απόλυτα instant διακοπή, πέρασε το interrupt_queue και στην quiescence
        score = quiescence(board, alpha, beta, maximizing, start_time, time_limit, ply=ply)
        return score, []

    # 4. --- MOVE ORDERING ---
    moves = list(board.legal_moves)
    moves.sort(key=lambda m: score_move(m, board, ply), reverse=True)

    if best_move_hint:
        hint = best_move_hint[0] if isinstance(best_move_hint, list) and best_move_hint else best_move_hint
        if hint in moves:
            moves.remove(hint)
            moves.insert(0, hint)

    if maximizing:
        best = -float("inf")
        for move in moves:
            board.push(move)
            
            # --- Awareness τριπλής επανάληψης ---
            if board.is_repetition(3):
                score = evaluate_board(board)
                score = score - 3 if score >= 5.0 else 0
                line = []
            else:
                # Προσθήκη του interrupt_queue στην αναδρομή
                score, line = minimax(board, depth - 1, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
            
            board.pop()

            if score is None: return None, None # Επιστροφή None για ακαριαία διακοπή

            if score > best:
                best = score
                best_line = [move] + line

            alpha = max(alpha, best)
            if beta <= alpha:
                update_killer_history(move, board, ply, depth)
                break
        return best, best_line

    else:
        best = float("inf")
        for move in moves:
            board.push(move)
            
            # --- Awareness τριπλής επανάληψης ---
            if board.is_repetition(3):
                score = evaluate_board(board)
                score = score + 3 if score <= -5.0 else 0
                line = []
            else:
                # Προσθήκη του interrupt_queue στην αναδρομή
                score, line = minimax(board, depth - 1, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
            
            board.pop()

            if score is None: return None, None # Επιστροφή None για ακαριαία διακοπή

            if score < best:
                best = score
                best_line = [move] + line

            beta = min(beta, best)
            if beta <= alpha:
                update_killer_history(move, board, ply, depth)
                break
        return best, best_line


def check_draw(board):
    score = evaluate_board(board)

    # Τριπλή επανάληψη ανεξαρτήτως claim
    if board.is_stalemate() or board.is_insufficient_material() \
       or board.is_repetition(3) or board.can_claim_fifty_moves():
        # Αν υπάρχει ξεκάθαρο πλεονέκτημα για οποιαδήποτε πλευρά, ΜΗΝ δεχτείς ισοπαλία
        if abs(score) >= 5.0: # Αν το score είναι ±10 για μεγάλο πλεονέκτημα
            return False
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
