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

def mvv_lva(move, board, tt_move=None, killers=None, is_mate_solver=False):
    """
    Βελτιωμένο Move Ordering.
    Αν is_mate_solver=True, αναποδογυρίζει την προτεραιότητα για καλλιτεχνικά προβλήματα Ματ.
    """
    # Το TT Move παραμένει ΠΡΩΤΟ σε κάθε περίπτωση (αν βρέθηκε κάτι καλό σε προηγούμενο βάθος)
    if tt_move and move == tt_move:
        return 10000000  

    attacker = board.piece_at(move.from_square)
    if not attacker:
        return 0

    is_capture = board.is_capture(move)
    
    # ----------------------------------------------------
    # ⭐ ΛΕΙΤΟΥΡΓΙΑ: MATE SOLVER MODE (Καλλιτεχνικά Προβλήματα)
    # ----------------------------------------------------
    if is_mate_solver:
        # Έλεγχος αν το τετράγωνο που πάμε απειλείται (άρα χάνουμε το κομμάτι)
        enemy_color = not board.turn
        is_square_attacked = board.is_attacked_by(enemy_color, move.to_square)
        
        # 1) ΚΟΜΜΑΤΙ ΠΟΥ ΧΑΝΕΤΑΙ (ΘΥΣΙΑ): Παίζει σε απειλούμενο τετράγωνο ΧΩΡΙΣ να τρώει κάτι μεγαλύτερο
        if is_square_attacked:
            if is_capture:
                victim = board.piece_at(move.to_square)
                victim_type = victim.piece_type if victim else chess.PAWN
                # Αν τρώει κάτι μικρότερης ή ίσης αξίας αλλά χάνει το δικό του, θεωρείται θυσία
                if piece_values[attacker.piece_type] > piece_values[victim_type]:
                    return 9000000  # Κορυφαία προτεραιότητα
            else:
                return 9500000  # Καθαρή θυσία (ήσυχη κίνηση σε απειλούμενο τετράγωνο)

        # 2) ΗΣΥΧΗ ΚΙΝΗΣΗ: Ούτε τρώει, ούτε απειλείται το τετράγωνο
        if not is_capture and not is_square_attacked:
            # Δίνουμε έξτρα bonus αν η ήσυχη κίνηση κάνει Σαχ (πολύ ύποπτο για προβλήματα)
            board.push(move)
            gives_check = board.is_check()
            board.pop()
            
            if gives_check:
                return 8500000
            return 8000000  # Υψηλό σκορ για απλές ήσυχε κινήσεις

        # 3) ΠΡΟΑΓΩΓΗ ΠΙΟΝΙΟΥ
        if move.promotion:
            return 7000000

        # 4) ΚΟΜΜΑΤΙ ΜΕΓΑΛΥΤΕΡΗΣ ΑΞΙΑΣ ΚΟΒΕΙ ΜΙΚΡΟΤΕΡΟ (Bad Capture)
        if is_capture and not is_square_attacked:
            if not board.is_en_passant(move):
                victim = board.piece_at(move.to_square)
                victim_type = victim.piece_type if victim else chess.PAWN
                if piece_values[attacker.piece_type] > piece_values[victim_type]:
                    return 6000000

        # 5) ΚΟΜΜΑΤΙ ΜΙΚΡΟΤΕΡΗΣ ΑΞΙΑΣ ΚΟΒΕΙ ΜΕΓΑΛΥΤΕΡΟ (Κλασικό MVV-LVA)
        if is_capture:
            if board.is_en_passant(move):
                victim_type = chess.PAWN
            else:
                victim = board.piece_at(move.to_square)
                victim_type = victim.piece_type if victim else chess.PAWN
            return 5000000 + (piece_values[victim_type] * 10) - piece_values[attacker.piece_type]

        return 0

    # ----------------------------------------------------
    # ⚙️ ΛΕΙΤΟΥΡΓΙΑ: ΚΑΝΟΝΙΚΟ ΠΑΙΧΝΙΔΙ (Όπως το είχατε)
    # ----------------------------------------------------
    else:
        # 1️⃣ ΚΟΨΙΜΑΤΑ (Captures) - MVV-LVA
        if is_capture:
            if board.is_en_passant(move):
                victim_type = chess.PAWN
            else:
                victim = board.piece_at(move.to_square)
                victim_type = victim.piece_type if victim else chess.PAWN
            return 5000000 + (piece_values[victim_type] * 10) - piece_values[attacker.piece_type]

        # ΣΤΑΔΙΟ 3: KILLER MOVES
        if killers:
            if len(killers) > 0 and move == killers[0]:
                return 4000000
            elif len(killers) > 1 and move == killers[1]:
                return 3000000

        # ΣΤΑΔΙΟ 4: QUIET MOVES (PST)
        score = 0
        from_sq = move.from_square
        to_sq = move.to_square

        if board.turn == chess.WHITE:
            from_sq ^= 56
            to_sq ^= 56

        table = PST_MAP.get(attacker.piece_type)
        if table is not None:
            score += table[to_sq] - table[from_sq]

        if move.promotion:
            score += 2000000

        return score