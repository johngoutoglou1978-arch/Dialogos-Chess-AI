def minimax(board, depth, alpha, beta, maximizing, nodes, start_time, time_limit, ply=0, best_move_hint=None, interrupt_queue=None):

    # 1. --- ΑΚΑΡΙΑΙΟΣ ΕΛΕΓΧΟΣ ΔΙΑΚΟΠΗΣ ---
    if (interrupt_queue is not None and not interrupt_queue.empty()) or (time.time() - start_time >= time_limit):
        return None, None

    # 2. --- COUNT NODES ---
    nodes[0] += 1  

    # ----------------------------------------------------
    # ⭐ ΤΕΧΝΙΚΗ 1: MATE DISTANCE PRUNING (ΑΠΟΛΥΤΩΣ ΑΣΦΑΛΕΣ)
    # ----------------------------------------------------
    # Αν έχουμε ήδη βρει ματ, δεν ψάχνουμε βαθύτερα αν δεν μπορεί να βελτιωθεί ο αριθμός των κινήσεων
    if maximizing:
        alpha = max(alpha, -10000 + ply)
        if alpha >= beta:
            return alpha, []
    else:
        beta = min(beta, 10000 - ply)
        if alpha >= beta:
            return beta, []
    # ----------------------------------------------------

    # 3. --- TERMINAL / GAME OVER ---
    if depth == 0 or board.is_game_over():
        score = quiescence(board, alpha, beta, maximizing, start_time, time_limit, ply=ply)
        return score, []

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

        if tt_entry['depth'] >= depth:
            tt_score = tt_entry['score']
            tt_flag = tt_entry['flag']
            
            # Διόρθωση Mate Scores για το τρέχον Ply
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

    if tt_move and tt_move in moves:
        moves.remove(tt_move)
        moves.insert(0, tt_move)

    if best_move_hint:
        hint = best_move_hint[0] if isinstance(best_move_hint, list) and best_move_hint else best_move_hint
        if hint in moves:
            moves.remove(hint)
            insert_idx = 1 if (tt_move and moves and moves[0] == tt_move) else 0
            moves.insert(insert_idx, hint)

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
        
        for moves_searched, move in enumerate(moves):
            board.push(move)
            
            if board.is_repetition(3):
                score = evaluate_board(board)
                score = score - 3 if score >= 5.0 else 0
                line = []
            else:
                # ----------------------------------------------------
                # ⭐ ΤΕΧΝΙΚΗ 2: PRINCIPAL VARIATION SEARCH (PVS)
                # ----------------------------------------------------
                if moves_searched == 0:
                    # Η πρώτη κίνηση (PV) ψάχνεται πάντα με πλήρες παράθυρο [1]
                    score, line = minimax(board, depth - 1, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                else:
                    # Οι επόμενες κινήσεις ψάχνονται με στενό παράθυρο (Null Window: alpha έως alpha + 1) [1]
                    score, line = minimax(board, depth - 1, alpha, alpha + 1, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                    
                    # Αν το στενό παράθυρο αποτύχει (δηλαδή η κίνηση αποδειχθεί καλύτερη από το alpha) [1]
                    # και δεν έχουμε ξεπεράσει ήδη το beta, τότε κάνουμε πλήρη αναζήτηση (Re-search) [1]
                    if score is not None and score > alpha and score < beta:
                        score, line = minimax(board, depth - 1, alpha, beta, False, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                # ----------------------------------------------------
            
            board.pop()
            if score is None: return None, None

            if score > best:
                best = score
                best_line = [move] + line

            alpha = max(alpha, best)
            if beta <= alpha:
                update_killer_history(move, board, ply, depth)
                break
                
        # --- ΑΠΟΘΗΚΕΥΣΗ ΣΤΟ TT ---
        if best <= original_alpha: flag = TT_ALPHA
        elif best >= original_beta: flag = TT_BETA
        else: flag = TT_EXACT

        # Διόρθωση Mate Score κατά την αποθήκευση στο TT
        stored_score = best
        if stored_score > 8000: stored_score += ply
        elif stored_score < -8000: stored_score -= ply

        if tt_entry is None or depth >= tt_entry['depth']:
            if len(transposition_table) >= MAX_TT_SIZE:
                for k in list(transposition_table.keys())[:20000]: transposition_table.pop(k, None)
            
            transposition_table[zobrist_key] = {
                'score': stored_score,
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
        
        for moves_searched, move in enumerate(moves):
            board.push(move)
            
            if board.is_repetition(3):
                score = evaluate_board(board)
                score = score + 3 if score <= -5.0 else 0
                line = []
            else:
                # ----------------------------------------------------
                # ⭐ ΤΕΧΝΙΚΗ 2: PRINCIPAL VARIATION SEARCH (PVS)
                # ----------------------------------------------------
                if moves_searched == 0:
                    score, line = minimax(board, depth - 1, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                else:
                    # Στενό παράθυρο για τον Minimizing (beta - 1 έως beta) [1]
                    score, line = minimax(board, depth - 1, beta - 1, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                    
                    # Αν η κίνηση "σπάσει" το παράθυρο προς τα κάτω (αποδειχθεί επικίνδυνη για τον Λευκό) [1]
                    if score is not None and score < beta and score > alpha:
                        score, line = minimax(board, depth - 1, alpha, beta, True, nodes, start_time, time_limit, ply=ply+1, interrupt_queue=interrupt_queue)
                # ----------------------------------------------------
            
            board.pop()
            if score is None: return None, None

            if score < best:
                best = score
                best_line = [move] + line

            beta = min(beta, best)
            if beta <= alpha:
                update_killer_history(move, board, ply, depth)
                break
                
        # --- ΑΠΟΘΗΚΕΥΣΗ ΣΤΟ TT ---
        if best <= original_alpha: flag = TT_ALPHA
        elif best >= original_beta: flag = TT_BETA
        else: flag = TT_EXACT

        stored_score = best
        if stored_score > 8000: stored_score += ply
        elif stored_score < -8000: stored_score -= ply

        if tt_entry is None or depth >= tt_entry['depth']:
            if len(transposition_table) >= MAX_TT_SIZE:
                for k in list(transposition_table.keys())[:20000]: transposition_table.pop(k, None)
            
            transposition_table[zobrist_key] = {
                'score': stored_score,
                'depth': depth,
                'flag': flag,
                'best_move': best_line[0].uci() if best_line else None
            }
        return best, best_line