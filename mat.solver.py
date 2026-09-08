import chess
import time
import os
import sys

sys.setrecursionlimit(5000)

fen_file = "fen_list_labeled.txt"

nodes = 0
memo = {}


# ============================================================
# ΑΠΟΘΗΚΕΥΣΗ FEN
# ============================================================

def save_fen(fen, description):
    with open(fen_file, "a", encoding="utf-8") as f:
        f.write(f"{description} --- {fen}\n")

    print("Το FEN αποθηκεύτηκε με περιγραφή.")


def list_fens():
    if not os.path.exists(fen_file):
        return []

    with open(fen_file, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if "---" in line
        ]


def show_fens(fens):
    for i, entry in enumerate(fens, 1):
        desc, fen = entry.split(" --- ", 1)
        print(f"{i}. {desc}")


def select_fen_or_new():

    fens = list_fens()

    if not fens:
        print("Δεν υπάρχουν αποθηκευμένα FEN.")

        fen = input("Δώσε νέο FEN:\n").strip()
        desc = input(
            "Δώσε περιγραφή (π.χ. 'Ματ σε 2'): "
        ).strip()

        save_fen(fen, desc)

        return fen, desc

    print("Διαθέσιμες θέσεις:")
    show_fens(fens)

    print("0. Δώσε νέο FEN")

    try:
        choice = int(
            input("Διάλεξε αριθμό FEN: ")
        )

        if choice == 0:

            fen = input(
                "Δώσε νέο FEN:\n"
            ).strip()

            desc = input(
                "Δώσε περιγραφή (π.χ. 'Ματ σε 2'): "
            ).strip()

            save_fen(fen, desc)

            return fen, desc

        elif 1 <= choice <= len(fens):

            desc, fen = fens[choice - 1].split(
                " --- ",
                1
            )

            return fen, desc

    except ValueError:
        pass

    print("Μη έγκυρη επιλογή.")

    return None, None


# ============================================================
# ΗΣΥΧΗ ΚΙΝΗΣΗ
# ============================================================

def is_quiet(board, move):

    return (
        not board.is_capture(move)
        and not board.gives_check(move)
    )


# ============================================================
# MOVE ORDERING
# ============================================================

def order_moves(board):

    def score(move):

        s = 0

        # Checks πρώτα
        if board.gives_check(move):
            s += 1000

        # Captures
        if board.is_capture(move):
            s += 500

        # Promotion
        if move.promotion:
            s += 800

        return -s

    return sorted(
        board.legal_moves,
        key=score
    )


# ============================================================
# FORCED MATE SEARCH
# ============================================================

def is_forced_mate(
    board,
    depth,
    total_depth,
    mode
):

    global nodes
    global memo

    nodes += 1

    # --------------------------------------------------------
    # Αν είναι ματ, επιτυχία
    # --------------------------------------------------------

    if board.is_checkmate():
        return True

    # --------------------------------------------------------
    # Τέλος βάθους
    # --------------------------------------------------------

    if depth <= 0:
        return False

    # --------------------------------------------------------
    # Πατ / άλλες καταστάσεις λήξης
    # --------------------------------------------------------

    if board.is_stalemate():
        return False

    # --------------------------------------------------------
    # Memoization
    # --------------------------------------------------------

    key = (
        board.fen()
        + "_"
        + str(depth)
        + "_"
        + mode
    )

    if key in memo:
        return memo[key]

    # --------------------------------------------------------
    # Ply από την αρχική θέση
    # --------------------------------------------------------

    ply_from_start = (
        total_depth - depth + 1
    )

    # ========================================================
    # ΛΕΥΚΑ
    # ========================================================

    if board.turn == chess.WHITE:

        for move in order_moves(board):

            # ------------------------------------------------
            # Quiet mode:
            # μόνο η ΠΡΩΤΗ κίνηση του λευκού
            # πρέπει να είναι ήσυχη
            # ------------------------------------------------

            if (
                mode == "quiet"
                and ply_from_start == 1
            ):

                if not is_quiet(board, move):
                    continue

            board.push(move)

            result = is_forced_mate(
                board,
                depth - 1,
                total_depth,
                mode
            )

            board.pop()

            # ------------------------------------------------
            # Το λευκό χρειάζεται ΜΙΑ σωστή κίνηση
            # ------------------------------------------------

            if result:

                memo[key] = True

                return True

        # Καμία κίνηση δεν οδηγεί σε forced mate

        memo[key] = False

        return False

    # ========================================================
    # ΜΑΥΡΑ
    # ========================================================

    else:

        for move in order_moves(board):

            board.push(move)

            result = is_forced_mate(
                board,
                depth - 1,
                total_depth,
                mode
            )

            board.pop()

            # ------------------------------------------------
            # Το μαύρο χρειάζεται ΜΙΑ άμυνα
            # που να αποφεύγει το ματ.
            #
            # Άρα αν βρούμε μία τέτοια άμυνα,
            # ΔΕΝ υπάρχει forced mate.
            # ------------------------------------------------

            if not result:

                memo[key] = False

                return False

        # Όλες οι άμυνες οδηγούν σε ματ

        memo[key] = True

        return True


# ============================================================
# ΒΡΕΣ ΤΗΝ ΠΡΩΤΗ ΚΙΝΗΣΗ
# ============================================================

def find_first_forced_move(
    fen,
    depth,
    mode,
    focus=None
):

    board = chess.Board(fen)

    print("\nΣκέφτομαι...", flush=True)

    ply_from_start = 1

    # ========================================================
    # ΕΣΤΙΑΣΗ ΣΕ ΜΙΑ ΣΥΓΚΕΚΡΙΜΕΝΗ ΚΙΝΗΣΗ
    # ========================================================

    if focus:

        try:

            move = board.parse_san(focus)

            print(
                f"--> Εξετάζω: {focus}"
            )

            # Quiet first move
            if (
                mode == "quiet"
                and ply_from_start == 1
                and board.turn == chess.WHITE
            ):

                if not is_quiet(board, move):

                    print(
                        "Η κίνηση δεν είναι ήσυχη, "
                        "παραλείπεται."
                    )

                    return None

            board.push(move)

            result = is_forced_mate(
                board,
                depth - 1,
                depth,
                mode
            )

            board.pop()

            if result:

                print(
                    f"--> Εξετάστηκε: {focus} "
                    f"[Βρέθηκε forced mate!]"
                )

                return move

            print(
                f"--> Εξετάστηκε: {focus} "
                f"[Δεν δίνει forced mate]"
            )

            return None

        except ValueError:

            print(
                "Λάθος μορφή κίνησης."
            )

            return None

    # ========================================================
    # ΕΞΕΤΑΣΗ ΟΛΩΝ ΤΩΝ ΠΡΩΤΩΝ ΚΙΝΗΣΕΩΝ
    # ========================================================

    for move in order_moves(board):

        san = board.san(move)

        # Quiet mode
        if (
            mode == "quiet"
            and ply_from_start == 1
            and board.turn == chess.WHITE
        ):

            if not is_quiet(board, move):
                continue

        print(
            f"--> Εξετάζω: {san}",
            flush=True
        )

        board.push(move)

        result = is_forced_mate(
            board,
            depth - 1,
            depth,
            mode
        )

        board.pop()

        if result:

            print(
                f"--> Εξετάζω: {san}! "
                f"[Βρέθηκε ματ!]"
            )

            return move

    return None


# ============================================================
# SOLVER
# ============================================================

def run_solver_on_fen(fen, depth):

    global nodes
    global memo

    nodes = 0
    memo = {}

    try:

        board = chess.Board(fen)

    except ValueError:

        print(
            "\nΤο FEN δεν είναι έγκυρο."
        )

        return

    print("\nΤύπος ανάλυσης:")

    print(
        "[1] Force mate "
        "(όλες οι κινήσεις επιτρέπονται)"
    )

    print(
        "[2] Ήσυχη πρώτη κίνηση μόνο"
    )

    analysis_choice = input(
        "Επιλογή: "
    ).strip()

    if analysis_choice == "2":
        mode = "quiet"
    else:
        mode = "force"

    focus = input(
        "\nΑν θέλεις να εξεταστεί μόνο "
        "μία κίνηση (π.χ. Qd7+), "
        "γράψε την εδώ.\n"
        "Πάτησε Enter για όλες: "
    ).strip()

    if focus == "":
        focus = None

    print(
        f"\nΒάθος αναζήτησης: {depth} plies"
    )

    start = time.time()

    move = find_first_forced_move(
        fen,
        depth,
        mode,
        focus
    )

    end = time.time()

    elapsed = end - start

    nps = (
        int(nodes / elapsed)
        if elapsed > 0
        else 0
    )

    # ========================================================
    # ΑΠΟΤΕΛΕΣΜΑΤΑ
    # ========================================================

    print("\n" + "=" * 55)
    print("ΑΠΟΤΕΛΕΣΜΑΤΑ")
    print("=" * 55)

    if move:

        print(
            "Πρώτη σωστή κίνηση του λευκού: "
            f"{board.san(move)}"
        )

    else:

        print(
            "Δεν βρέθηκε υποχρεωτικό ματ."
        )

    print(
        f"Χρόνος: {elapsed:.2f} δευτερόλεπτα"
    )

    print(
        f"Θέσεις που εξετάστηκαν: {nodes}"
    )

    print(
        f"Ταχύτητα: {nps} θέσεις/δευτερόλεπτο"
    )

    print(
        f"Memo entries: {len(memo)}"
    )

    print("=" * 55)


# ============================================================
# ΚΥΡΙΟ MENU
# ============================================================

while True:

    print(
        "\n=== Don Zouán Mate Solver v2.0 ==="
    )

    print(
        "=== Force ή Ήσυχη Πρώτη Κίνηση ==="
    )

    print(
        "[1] Αποθήκευση νέου FEN με περιγραφή"
    )

    print(
        "[2] Προβολή/Λύση αποθηκευμένου ή νέου FEN"
    )

    print(
        "[3] Έξοδος"
    )

    επιλογή = input(
        "Επιλογή: "
    ).strip()

    # ========================================================
    # ΑΠΟΘΗΚΕΥΣΗ
    # ========================================================

    if επιλογή == "1":

        fen = input(
            "Δώσε νέο FEN:\n"
        ).strip()

        desc = input(
            "Δώσε περιγραφή "
            "(π.χ. 'Ματ σε 2'): "
        ).strip()

        try:

            chess.Board(fen)

            save_fen(
                fen,
                desc
            )

        except ValueError:

            print(
                "Το FEN δεν είναι έγκυρο. "
                "Δεν αποθηκεύτηκε."
            )

    # ========================================================
    # ΛΥΣΗ
    # ========================================================

    elif επιλογή == "2":

        fen, desc = select_fen_or_new()

        if fen:

            try:

                moves = int(
                    input(
                        f"({desc}) "
                        "Ματ σε πόσες πλήρεις κινήσεις; "
                    )
                )

                if moves <= 0:

                    print(
                        "Το πλήθος κινήσεων "
                        "πρέπει να είναι θετικό."
                    )

                    continue

                # 1 πλήρης κίνηση = 2 plies

                depth = moves * 2

                run_solver_on_fen(
                    fen,
                    depth
                )

            except ValueError:

                print(
                    "Δώσε έναν έγκυρο αριθμό."
                )

    # ========================================================
    # ΕΞΟΔΟΣ
    # ========================================================

    elif επιλογή == "3":

        print(
            "Έγινε έξοδος."
        )

        break

    else:

        print(
            "Μη έγκυρη επιλογή."
        )