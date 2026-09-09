import chess
import time
import os
import sys
from collections import defaultdict

sys.setrecursionlimit(10000)

fen_file = "fen_list_labeled.txt"

# --- Global counters/structures ---
NODES = 0
ROOT_SIDE = chess.WHITE  

TT = {}  
KILLERS = defaultdict(lambda: set())
HISTORY = defaultdict(int)

def save_fen(fen, description):
    with open(fen_file, "a", encoding="utf-8") as f:
        f.write(f"{description} --- {fen}\n")
    print("Το FEN αποθηκεύτηκε με περιγραφή.")

def list_fens():
    if not os.path.exists(fen_file):
        return []
    with open(fen_file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if "---" in line]

def show_fens(fens):
    for i, entry in enumerate(fens, 1):
        desc, fen = entry.split(" --- ")
        print(f"{i}. {desc}")

def select_fen_or_new():
    fens = list_fens()
    if not fens:
        print("Δεν υπάρχουν αποθηκευμένα FEN.")
        fen = input("Δώσε νέο FEN:\n").strip()
        desc = input("Δώσε περιγραφή (π.χ. 'Ματ σε 2'): ").strip()
        save_fen(fen, desc)
        return fen, desc
    else:
        print("Διαθέσιμες θέσεις:")
        show_fens(fens)
        print("0. Δώσε νέο FEN")
        try:
            choice = int(input("Διάλεξε αριθμό FEN: "))
            if choice == 0:
                fen = input("Δώσε νέο FEN:\n").strip()
                desc = input("Δώσε περιγραφή (π.χ. 'Ματ σε 2'): ").strip()
                save_fen(fen, desc)
                return fen, desc
            elif 1 <= choice <= len(fens):
                desc, fen = fens[choice - 1].split(" --- ")
                return fen, desc
        except:
            print("Μη έγκυρη επιλογή.")
    return None, None

PIECE_VALUE = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000
}

def mvv_lva(board, move):
    if board.is_capture(move):
        victim = board.piece_type_at(move.to_square)
        attacker = board.piece_type_at(move.from_square)
        if victim is None:  
            victim = chess.PAWN
        return PIECE_VALUE.get(victim, 0) * 100 - PIECE_VALUE.get(attacker, 0)
    return -999999

def is_quiet(board, move):
    return (not board.is_capture(move)) and (not board.gives_check(move)) and (not move.promotion)

def see_gain(board, move):
    try:
        return board.see(move)
    except:
        return 0

def order_moves(board, moves, tt_best_uci, ply):
    ordered = []
    for move in moves:
        score = 0
        uci = move.uci()
        if tt_best_uci and uci == tt_best_uci:
            score += 1_000_000
        if move.promotion:
            score += 120_000
        if board.gives_check(move):
            score += 200_000
        if board.is_capture(move):
            score += 100_000 + 50 * see_gain(board, move) + mvv_lva(board, move)
        if uci in KILLERS[ply]:
            score += 80_000
        side = 1 if board.turn == chess.WHITE else -1
        score += 2 * HISTORY[(side, move.from_square, move.to_square)]
        score += 1 if move.from_square ^ move.to_square else 0
        ordered.append((score, move))
    ordered.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in ordered]

def has_forced_mate(board, depth, total_depth, mode, ply):
    global NODES, TT
    NODES += 1

    if board.is_checkmate():
        return True, {}  # Άδειο λεξικό σημαίνει ότι φτάσαμε στο ματ

    if depth <= 0 or board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves():
        return False, None

    key = (board._transposition_key(), depth)
    tt_hit = TT.get(key)
    if tt_hit and tt_hit[0] >= depth:
        return tt_hit[1], tt_hit[2]

    in_check = board.is_check()
    eff_depth = depth + 1 if in_check and depth > 0 else depth

    legal = list(board.legal_moves)
    if not legal:
        return False, None

    if mode == "quiet" and ply == 0:
        legal = [m for m in legal if is_quiet(board, m)]
        if not legal:
            return False, None

    tt_best_uci = tt_hit[3] if tt_hit else None
    moves = order_moves(board, legal, tt_best_uci, ply)
    is_or_node = (board.turn == ROOT_SIDE)
    side_flag = 1 if board.turn == chess.WHITE else -1

    if is_or_node:  
        # Επιθετικός: Ψάχνει έστω και ΜΙΑ κίνηση που να οδηγεί σε ματ
        for mv in moves:
            board.push(mv)
            ok, sub_tree = has_forced_mate(board, eff_depth - 1, total_depth, mode, ply + 1)
            board.pop()
            if ok:
                best_move_uci = mv.uci()
                KILLERS[ply].add(best_move_uci)
                HISTORY[(side_flag, mv.from_square, mv.to_square)] += 1 + eff_depth
                
                # Αποθηκεύουμε τη βαριάντα σε λεξικό
                tree = {mv: sub_tree}
                TT[key] = (depth, True, tree, best_move_uci)
                return True, tree
            else:
                HISTORY[(side_flag, mv.from_square, mv.to_square)] -= 1
        TT[key] = (depth, False, None, None)
        return False, None
    else:  
        # Αμυνόμενος: ΠΡΕΠΕΙ ΟΛΕΣ οι απαντήσεις του να οδηγούν σε ματ
        full_tree = {}
        for mv in moves:
            board.push(mv)
            ok, sub_tree = has_forced_mate(board, eff_depth - 1, total_depth, mode, ply + 1)
            board.pop()
            if not ok:
                # Αν έστω και μία απάντηση ξεφεύγει, δεν είναι αναγκαστικό ματ
                TT[key] = (depth, False, None, mv.uci())
                return False, None
            else:
                # Καταγράφουμε κάθε δυνατή διαφυγή/κίνηση του αντιπάλου
                full_tree[mv] = sub_tree
                HISTORY[(side_flag, mv.from_square, mv.to_square)] -= 1
        
        TT[key] = (depth, True, full_tree, None)
        return True, full_tree
def print_tree(board, tree, indent=0):
    """Συνάρτηση που τυπώνει αναδρομικά όλες τις βαριάντες με σωστή αρίθμηση σκακιού."""
    if not tree:
        print(" -> Ματ!")
        return

    for move, sub_tree in tree.items():
        # Δημιουργούμε το SAN της κίνησης πριν την παίξουμε
        san = board.san(move)
        
        # Μορφοποίηση κίνησης (π.χ. 1. e4 ή 1... e5)
        if board.turn == chess.WHITE:
            move_str = f"{board.fullmove_number}. {san}"
        else:
            move_str = f"{board.fullmove_number}... {san}"
            
        # Εκτύπωση με κενά ανάλογα το βάθος
        if indent == 0:
            print(f"\n{move_str}", end="")
        else:
            print(f"\n{'   ' * indent}└── {move_str}", end="")
            
        board.push(move)
        print_tree(board, sub_tree, indent + 1)
        board.pop()

def find_first_forced_move(fen, depth, mode, focus=None):
    global NODES, TT, KILLERS, HISTORY, ROOT_SIDE
    NODES = 0
    TT.clear(); KILLERS.clear(); HISTORY.clear()

    board = chess.Board(fen)
    ROOT_SIDE = board.turn  
    
    side_str = "Λευκά" if ROOT_SIDE == chess.WHITE else "Μαύρα"
    print(f"\nΣκέφτομαι... (Σειρά έχουν τα: {side_str})", flush=True)

    if focus:
        try:
            mv = board.parse_san(focus)
        except:
            print("Λάθος μορφή κίνησης.")
            mv = None

        if mv:
            if mode == "quiet" and not is_quiet(board, mv):
                print("Η κίνηση δεν είναι ήσυχη, παραλείπεται.")
            else:
                board.push(mv)
                ok, sub_tree = has_forced_mate(board, depth - 1, depth, mode, 1)
                board.pop()
                if ok:
                    print(f"--> Εξετάζω: {focus}!  [Βρέθηκε ματ!]")
                    return {mv: sub_tree}
                else:
                    print(f"--> Εξετάζω: {focus}  [Δεν οδηγεί σε υποχρεωτικό ματ]")

    best_tree = None
    for d in range(2, depth + 1, 2):
        print(f"\n--- Αναζήτηση σε βάθος {d} plies (Ματ σε {d//2} κινήσεις) ---")
        legal = list(board.legal_moves)
        if mode == "quiet":
            legal = [m for m in legal if is_quiet(board, m)]
            if not legal:
                break

        key_root = (board._transposition_key(), d)
        tt_data = TT.get(key_root)
        tt_move_uci = tt_data if tt_data else None
        root_moves = order_moves(board, legal, tt_move_uci, ply=0)

        found_here = None
        for mv in root_moves:
            san = board.san(mv)
            print(f"--> Εξετάζω: {san}")
            board.push(mv)
            ok, sub_tree = has_forced_mate(board, d - 1, depth, mode, 1)
            board.pop()
            if ok:
                print(f"--> Εξετάζω: {san}!  [Βρέθηκε ματ!]")
                found_here = {mv: sub_tree}
                best_tree = found_here
                break
        if found_here:
            return best_tree
    return best_tree

def run_solver_on_fen(fen, full_moves_mate):
    global NODES, TT
    NODES = 0
    TT.clear()
    board = chess.Board(fen)

    print("\nΤύπος ανάλυσης:")
    print("[1] Force mate (όλες οι κινήσεις επιτρέπονται)")
    print("[2] Ήσυχη πρώτη κίνηση μόνο")
    analysis_choice = input("Επιλογή: ").strip()
    mode = "quiet" if analysis_choice == "2" else "force"

    focus = input("Αν θέλεις να εξεταστεί μόνο μία κίνηση (π.χ. κοίτα Qd7+), γράψε την εδώ:\n").strip()
    if focus == "":
        focus = None

    depth = full_moves_mate * 2
    start = time.time()
    mate_tree = find_first_forced_move(fen, depth, mode, focus)
    end = time.time()
    elapsed = end - start
    nps = int(NODES / elapsed) if elapsed > 0 else 0

    print("\nΑποτελέσματα:")
    if mate_tree:
        print("\n=== ΠΛΗΡΕΣ ΔΕΝΤΡΟ ΛΥΣΗΣ ===")
        temp_board = chess.Board(fen)
        print_tree(temp_board, mate_tree)
        print("\n==========================")
    else:
        print("Δεν βρέθηκε υποχρεωτικό ματ.")
    print(f"\nΧρόνος: {elapsed:.2f} δευτερόλεπτα")
    print(f"Θέσεις που εξετάστηκαν: {NODES}")
    print(f"Ταχύτητα: {nps} θέσεις/δευτερόλεπτο")

# --- Main loop ---
while True:
    print("\n=== Don Zouán Mate Solver v3.3 — Full Tree Edition ===")
    print("[1] Αποθήκευση νέου FEN με περιγραφή")
    print("[2] Προβολή/Λύση αποθηκευμένου ή νέου FEN")
    print("[3] Έξοδος")
    επιλογή = input("Επιλογή: ")

    if επιλογή == "1":
        fen = input("Δώσε νέο FEN:\n").strip()
        desc = input("Δώσε περιγραφή (π.χ. 'Ματ σε 2'): ").strip()
        save_fen(fen, desc)
    elif επιλογή == "2":
        fen, desc = select_fen_or_new()
        if fen:
            κινήσεις = int(input(f"({desc}) Ματ σε πόσες πλήρεις κινήσεις; "))
            run_solver_on_fen(fen, κινήσεις)
    elif επιλογή == "3":
        print("Έγinez έξοδος.")
        break
    else:
        print("Μη έγκυρη επιλογή.")
