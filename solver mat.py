import chess
import time
import os
import sys
from collections import defaultdict

# Αυξάνουμε το όριο αναδρομής για βαθιές αναζητήσεις
sys.setrecursionlimit(10000)

fen_file = "fen_list_labeled.txt"

# --- Global counters/structures ---
NODES = 0
ROOT_SIDE = chess.WHITE  

TT = {}  
KILLERS = defaultdict(lambda: set())
HISTORY = defaultdict(int)

# --- FEN File Management ---
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

# --- Move Ordering & Evaluation Heuristics ---
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
# --- Core Recursive Mate Finder ---
def has_forced_mate(board, depth, total_depth, mode, ply):
    global NODES, TT, ROOT_SIDE
    NODES += 1

    if board.is_checkmate():
        return True, {}  

    # Έλεγχος τερματισμού λόγω βάθους ή ισοπαλίας
    if depth <= 0 or board.is_stalemate() or board.is_insufficient_material() or board.can_claim_fifty_moves():
        return False, None

    # Το κλειδί TT περιλαμβάνει το depth και το turn για αποφυγή TT Pollution
    key = (board._transposition_key(), depth, board.turn)
    if key in TT:
        tt_depth, tt_ok, tt_tree, tt_best = TT[key]
        if tt_depth >= depth:
            return tt_ok, tt_tree

    legal = list(board.legal_moves)
    if not legal:
        return False, None

    if mode == "quiet" and ply == 0:
        legal = [m for m in legal if is_quiet(board, m)]
        if not legal:
            return False, None

    # Ανάκτηση της καλύτερης κίνησης UCI από το TT αν υπάρχει
    tt_best_uci = TT[key] if key in TT and len(TT[key]) > 3 else None
    moves = order_moves(board, legal, tt_best_uci, ply)
    is_or_node = (board.turn == ROOT_SIDE)
    side_flag = 1 if board.turn == chess.WHITE else -1

    if is_or_node:  
        # Επιθετικός (OR Node): Ψάχνει τουλάχιστον ΜΙΑ κίνηση που να εξαναγκάζει σε ματ
        for mv in moves:
            board.push(mv)
            # Αφαιρέθηκε το eff_depth inflation που προκαλούσε άπειρη αναδρομή στα σαχ
            ok, sub_tree = has_forced_mate(board, depth - 1, total_depth, mode, ply + 1)
            board.pop()
            if ok:
                best_move_uci = mv.uci()
                KILLERS[ply].add(best_move_uci)
                HISTORY[(side_flag, mv.from_square, mv.to_square)] += 1 + depth
                
                tree = {mv: sub_tree}
                TT[key] = (depth, True, tree, best_move_uci)
                return True, tree
            else:
                HISTORY[(side_flag, mv.from_square, mv.to_square)] -= 1
        TT[key] = (depth, False, None, None)
        return False, None
    else:  
        # Αμυνόμενος (AND Node): ΠΡΕΠΕΙ ΟΛΕΣ οι απαντήσεις του να καταλήγουν σε ματ
        full_tree = {}
        for mv in moves:
            board.push(mv)
            ok, sub_tree = has_forced_mate(board, depth - 1, total_depth, mode, ply + 1)
            board.pop()
            if not ok:
                TT[key] = (depth, False, None, mv.uci())
                return False, None
            else:
                full_tree[mv] = sub_tree
                HISTORY[(side_flag, mv.from_square, mv.to_square)] -= 1
        
        TT[key] = (depth, True, full_tree, None)
        return True, full_tree

def print_tree(board, tree, current_line=""):
    """
    Τυπώνει κάθε εξαναγκασμένη βαριάντα ματ σε μία ενιαία, πεντακάθαρη γραμμή.
    Αν ο αμυνόμενος έχει 3 απαντήσεις, θα τυπωθούν 3 ξεχωριστές, εύκολες στην ανάγνωση γραμμές!
    """
    if not tree:
        print(f" {current_line.strip()} -> Ματ!")
        return

    for move, sub_tree in tree.items():
        san = board.san(move)
        
        # Μορφοποίηση της κίνησης με σωστή αρίθμηση σκακιού
        if board.turn == chess.WHITE:
            move_str = f"{board.fullmove_number}. {san}"
        else:
            # Αν είναι η πρώτη κίνηση της γραμμής και παίζουν τα μαύρα, βάζουμε αποσιωπητικά
            if not current_line:
                move_str = f"{board.fullmove_number}... {san}"
            else:
                move_str = f"{san}"
                
        # Προσθήκη της κίνησης στην τρέχουσα βαριάντα
        next_line = f"{current_line} {move_str}"
        
        board.push(move)
        print_tree(board, sub_tree, next_line)
        board.pop()

# --- Search Orchestration (Iterative Deepening) ---
def find_first_forced_move(fen, depth, mode, focus=None):
    global NODES, TT, KILLERS, HISTORY, ROOT_SIDE
    NODES = 0
    TT.clear()
    KILLERS.clear()
    HISTORY.clear()

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
    # Το βήμα έγινε 1 (αντί για 2) για ακριβή έλεγχο όλων των plies άμυνας/επίθεσης
    for d in range(1, depth + 1):
        print(f"\n--- Αναζήτηση σε βάθος {d} plies ---")
        legal = list(board.legal_moves)
        if mode == "quiet":
            legal = [m for m in legal if is_quiet(board, m)]
            if not legal:
                break

        TT.clear()  
        root_moves = order_moves(board, legal, None, ply=0)

        found_here = None
        for mv in root_moves:
            san = board.san(mv)
            board.push(mv)
            ok, sub_tree = has_forced_mate(board, d - 1, d, mode, 1)
            board.pop()
            if ok:
                print(f"--> Εξετάζω: {san}!  [Βρέθηκε ματ!]")
                found_here = {mv: sub_tree}
                best_tree = found_here
                break
            else:
                print(f"--> Εξετάζω: {san}")
        if found_here:
            return best_tree
    return best_tree

# --- Execution Entry Point ---
def run_solver_on_fen(fen, full_moves_mate):
    global NODES, TT
    board = chess.Board(fen)

    print("\nΤύπος ανάλυσης:")
    print(" Force mate (όλες οι κινήσεις επιτρέπονται)")
    print(" Ήσυχη πρώτη κίνηση μόνο")
    analysis_choice = input("Επιλογή: ").strip()
    mode = "quiet" if analysis_choice == "2" else "force"

    focus = input("Αν θέλεις να εξεταστεί μόνο μία κίνηση (π.χ. Qd7+), γράψε την εδώ (αλλιώς Enter):\n").strip()
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
        print("==========================")
    else:
        print("Δεν βρέθηκε υποχρεωτικό ματ.")
    print(f"\nΧρόνος: {elapsed:.2f} δευτερόλεπτα")
    print(f"Θέσεις που εξετάστηκαν: {NODES}")
    print(f"Ταχύτητα: {nps} θέσεις/δευτερόλεπτο")

# --- Main loop ---
while True:
    print("\n=== Don Zouán Mate Solver v3.5 — Book Print Edition ===")
    print(" Αποθήκευση νέου FEN με περιγραφή")
    print(" Προβολή/Λύση αποθηκευμένου ή νέου FEN")
    print(" Έξοδος")
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
        print("Έγινε έξοδος.")
        break
    else:
        print("Μη έγκυρη επιλογή.")
