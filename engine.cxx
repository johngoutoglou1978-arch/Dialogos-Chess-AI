 #include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <map>
#include <chrono>
#include <memory>
#include <algorithm>
#include <thread>
#include <atomic>
#include <queue>
#include <mutex>
#include "/storage/emulated/0/chess.hpp" 
#include <atomic> // Σιγουρευτείτε ότι υπάρχει αυτό το include στην κορυφή
#include <random>

std::atomic<bool> ai_interrupt_flag(false);

using namespace chess;
using namespace std;

// --- Δομές Δεδομένων για το Δέντρο Λύσης ---
struct Node {
    Move move;
    std::vector<std::shared_ptr<Node>> children; 
};
using TreePtr = std::shared_ptr<Node>;
using Tree = std::vector<TreePtr>;

// --- Global counters / structures ---
const std::string fen_file = "fen_list_labeled.txt";
uint64_t NODES = 0;
Color ROOT_SIDE = Color::WHITE;

const int INF = 1000000;
const int MATE_VALUE = 900000;

// --- Πίνακες Αξιολόγησης Θέσης (Piece-Square Tables - PST) ---

const int pawn_pst[64] = {
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
};

const int knight_pst[64] = {
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
};

const int bishop_pst[64] = {
    -20,-10,-10,-10,-10,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5, 10, 10,  5,  0,-10,
    -10,  5,  5, 10, 10,  5,  5,-10,
    -10,  0, 10, 10, 10, 10,  0,-10,
    -10, 10, 10, 10, 10, 10, 10,-10,
    -10,  5,  0,  0,  0,  0,  5,-10,
    -20,-10,-10,-10,-10,-10,-10,-20
};

const int rook_pst[64] = {
      0,  0,  0,  0,  0,  0,  0,  0,
      5, 10, 10, 10, 10, 10, 10,  5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
     -5,  0,  0,  0,  0,  0,  0, -5,
      0,  0,  0,  5,  5,  0,  0,  0
};

const int queen_pst[64] = {
    -20,-10,-10, -5, -5,-10,-10,-20,
    -10,  0,  0,  0,  0,  0,  0,-10,
    -10,  0,  5,  5,  5,  5,  0,-10,
     -5,  0,  5,  5,  5,  5,  0, -5,
      0,  0,  5,  5,  5,  5,  0, -5,
    -10,  5,  5,  5,  5,  5,  0,-10,
    -10,  0,  5,  0,  0,  0,  0,-10,
    -20,-10,-10, -5, -5,-10,-10,-20
};

// Πίνακας Βασιλιά για το Μέσον του Παιχνιδιού (Midgame)
const int king_middle_pst[64] = {
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30,
    -20,-30,-30,-40,-40,-30,-30,-20,
    -10,-20,-20,-20,-20,-20,-20,-10,
     20, 20,  0,  0,  0,  0, 20, 20,
     20, 30, 10,  0,  0, 10, 30, 20
};

// Νέος Πίνακας Βασιλιά για το Φινάλε (Endgame) - Ενθαρρύνει την έξοδο στο κέντρο
const int king_endgame_pst[64] = {
    -50,-40,-30,-20,-20,-30,-40,-50,
    -30,-20,-10,  0,  0,-10,-20,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 30, 40, 40, 30,-10,-30,
    -30,-10, 20, 30, 30, 20,-10,-30,
    -30,-30,  0,  0,  0,  0,-30,-30,
    -50,-30,-30,-30,-30,-30,-30,-50
};

// Transposition Table (TT) entry
struct TTEntry {
    int depth;
    bool ok;
    Tree tree;
    string best_move_uci;
    int score;
    int flag; 
};

struct TTKey {
    uint64_t hash;
    int depth;
    Color turn;

    bool operator==(const TTKey& other) const {
        return hash == other.hash && depth == other.depth && turn == other.turn;
    }
};

struct TTKeyHash {
    size_t operator()(const TTKey& k) const {
        return k.hash ^ (k.depth << 1) ^ (static_cast<int>(k.turn) << 2);
    }
};

unordered_map<TTKey, TTEntry, TTKeyHash> TT;
unordered_map<int, unordered_set<string>> KILLERS;
unordered_map<string, int> HISTORY;

// --- FEN File Management ---
void save_fen(const string& fen, const string& description) {
    ofstream f(fen_file, ios::app);
    if (f.is_open()) {
        f << description << " --- " << fen << "\n";
        cout << "Το FEN αποθηκεύτηκε με περιγραφή.\n";
    }
}

vector<string> list_fens() {
    vector<string> fens;
    ifstream f(fen_file);
    string line;
    while (getline(f, line)) {
        if (line.find(" --- ") != string::npos) {
            fens.push_back(line);
        }
    }
    return fens;
}

void show_fens(const vector<string>& fens) {
    for (size_t i = 0; i < fens.size(); ++i) {
        size_t pos = fens[i].find(" --- ");
        string desc = fens[i].substr(0, pos);
        cout << i + 1 << ". " << desc << "\n";
    }
}

pair<string, string> select_fen_or_new() {
    auto fens = list_fens();
    if (fens.empty()) {
        cout << "Δεν υπάρχουν αποθηκευμένα FEN.\n";
        string fen, desc;
        cout << "Δώσε νέο FEN:\n";
        cin.ignore();
        getline(cin, fen);
        cout << "Δώσε περιγραφή (π.χ. 'Ματ σε 2'): ";
        getline(cin, desc);
        save_fen(fen, desc);
        return make_pair(fen, desc);
    } else {
        cout << "Διαθέσιμες θέσεις:\n";
        show_fens(fens);
        cout << "0. Δώσε νέο FEN\n";
        cout << "Διάλεξε αριθμό FEN: ";
        int choice;
        if (!(cin >> choice)) return make_pair("", "");
        cin.ignore();
        if (choice == 0) {
            string fen, desc;
            cout << "Δώσε νέο FEN:\n";
            getline(cin, fen);
            cout << "Δώσε περιγραφή (π.χ. 'Ματ σε 2'): ";
            getline(cin, desc);
            save_fen(fen, desc);
            return make_pair(fen, desc);
        } else if (choice >= 1 && choice <= (int)fens.size()) {
            size_t pos = fens[choice - 1].find(" --- ");
            string desc = fens[choice - 1].substr(0, pos);
            string fen = fens[choice - 1].substr(pos + 5);
            return make_pair(fen, desc);
        }
    }
    return make_pair("", "");
}
// --- Συνάρτηση Αξιολόγησης (Evaluation) ---
// --- Υπολογισμός Φάσης Παιχνιδιού (Game Phase) ---
// Επιστρέφει 24 στην αρχή του παιχνιδιού και μειώνεται όσο χάνονται κομμάτια
int calculate_game_phase(const Board& board) {
    int phase = 0;
    
    for (int sq = 0; sq < 64; ++sq) {
        Piece p = board.at(Square(sq));
        if (p == Piece::NONE) continue;
        
        // Προσθέτουμε βάρος ανάλογα με τα κομμάτια που είναι ζωντανά
        if (p.type() == PieceType::KNIGHT)  phase += 1;
        else if (p.type() == PieceType::BISHOP) phase += 1;
        else if (p.type() == PieceType::ROOK)   phase += 2;
        else if (p.type() == PieceType::QUEEN)  phase += 4;
    }
    
    return phase;
}

// --- Κύρια Συνάρτηση Αξιολόγησης Σκακιέρας (Evaluation) ---
int evaluate_board(const Board& board) {
    int score = 0;
    
    // Φινάλε θεωρείται όταν έχουν μείνει ελάχιστα μεγάλα κομμάτια (phase <= 6)
    // Στην αρχή του παιχνιδιού το phase θα είναι 24, οπότε is_endgame = false
    bool is_endgame = (calculate_game_phase(board) <= 6);
    
    // Πίνακες καταμέτρησης πιονιών ανά στήλη (0-7) για διπλωμένα πιόνια
    int white_pawns_in_file[8] = {0};
    int black_pawns_in_file[8] = {0};
    
    // 1. Υλική αξία και Πίνακες Θέσης (PST)
    for (int sq = 0; sq < 64; ++sq) {
        Piece p = board.at(Square(sq));
        if (p == Piece::NONE) continue;
        
        int p_val = 0;
        const int* pst = nullptr;
        
        // Καταγραφή στηλών για διπλωμένα πιόνια
        if (p.type() == PieceType::PAWN) {
            if (p.color() == Color::WHITE) white_pawns_in_file[sq % 8]++;
            else black_pawns_in_file[sq % 8]++;
        }
        
        // Ορισμός αξιών και επιλογή PST
        if (p.type() == PieceType::PAWN) {
            p_val = 100; pst = pawn_pst;
        } else if (p.type() == PieceType::KNIGHT) {
            p_val = 320; pst = knight_pst;
        } else if (p.type() == PieceType::BISHOP) {
            p_val = 330; pst = bishop_pst;
        } else if (p.type() == PieceType::ROOK) {
            p_val = 500; pst = rook_pst;
        } else if (p.type() == PieceType::QUEEN) {
            p_val = 900; pst = queen_pst;
        } else if (p.type() == PieceType::KING) {
            p_val = 20000; 
            // Τώρα θα επιλέγει σωστά τον king_middle_pst στην αρχή του παιχνιδιού
            pst = is_endgame ? king_endgame_pst : king_middle_pst;
        }
        
        // Διόρθωση δεικτών (καθρεφτισμός)
        int sq_idx = sq ^ 56;
        if (p.color() == Color::BLACK) {
            sq_idx = sq;
        }
        
        int total_piece_val = p_val + ((pst != nullptr) ? pst[sq_idx] : 0);
        
        if (p.color() == Color::WHITE) score += total_piece_val;
        else score -= total_piece_val;
    }
    
    // 2. Ποινές για Διπλωμένα Πιόνια (Doubled Pawns)
    for (int file = 0; file < 8; ++file) {
        if (white_pawns_in_file[file] > 1) {
            score -= (white_pawns_in_file[file] - 1) * 15;
        }
        if (black_pawns_in_file[file] > 1) {
            score += (black_pawns_in_file[file] - 1) * 15;
        }
    }
    
    // 3. Κινητικότητα (Mobility) & Στριμώξιμο
    int white_mobility = 0;
    int black_mobility = 0;
    // white_mobility = board.YOUR_MOVE_GENERATOR_FUNCTION(Color::WHITE).size();
    // black_mobility = board.YOUR_MOVE_GENERATOR_FUNCTION(Color::BLACK).size();
    score += (white_mobility - black_mobility) * 2;
    
    return (board.sideToMove() == Color::WHITE) ? score : -score;
}

// --- Move Ordering & Evaluation Heuristics ---
bool is_quiet(const Board& board, Move move) {
    Board b = board;
    b.makeMove(move);
    return !board.isCapture(move) && !b.inCheck();
}

int order_score(const Board& board, Move move, const string& tt_best_uci, int ply) {
    int score = 0;
    string uci = uci::moveToUci(move);
    if (!tt_best_uci.empty() && uci == tt_best_uci) score += 1000000;
    
    Board b = board; b.makeMove(move);
    if (b.inCheck()) score += 200000;
    if (board.isCapture(move)) score += 100000; 
    if (KILLERS[ply].count(uci)) score += 80000;
    if (HISTORY.count(uci)) score += 2 * HISTORY[uci];
    
    return score;
}

vector<Move> order_moves(const Board& board, Movelist& moves, const string& tt_best_uci, int ply) {
    vector<pair<int, Move> > scored_moves;
    for (size_t i = 0; i < moves.size(); ++i) {
        scored_moves.push_back(make_pair(order_score(board, moves[i], tt_best_uci, ply), moves[i]));
    }
    sort(scored_moves.begin(), scored_moves.end(), [](const pair<int, Move>& a, const pair<int, Move>& b) {
        return a.first > b.first;
    });
    vector<Move> result;
    for (size_t i = 0; i < scored_moves.size(); ++i) result.push_back(scored_moves[i].second);
    return result;
}

// Βοηθητική συνάρτηση για την αξία των κομματιών (χρησιμοποιείται στο MVV-LVA και Delta Pruning)
int get_piece_value(PieceType pt) {
    if (pt == PieceType::PAWN)   return 100;
    if (pt == PieceType::KNIGHT) return 300;
    if (pt == PieceType::BISHOP) return 300;
    if (pt == PieceType::ROOK)   return 500;
    if (pt == PieceType::QUEEN)  return 900;
    return 0;
}

// --- Επαγγελματική Quiescence Search ---
int quiescence(int alpha, int beta, Board& board) {
    NODES++;

    // 1. Stand-Pat: Αν η τρέχουσα θέση (χωρίς να φάμε τίποτα) είναι ήδη αρκετά καλή, σταματάμε
    int stand_pat = evaluate_board(board);
    if (stand_pat >= beta) return beta;
    if (stand_pat > alpha) alpha = stand_pat;

    // Παραγωγή ΜΟΝΟ των captures (φαγωμάτων)
    Movelist moves;
    movegen::legalmoves<movegen::MoveGenType::CAPTURE>(moves, board);

    // 2. MVV-LVA Scoring (Most Valuable Victim - Least Valuable Assault)
    int move_scores[256] = {0};
    for (size_t i = 0; i < moves.size(); i++) {
        Move mv = moves[i];
        PieceType victim = board.at(mv.to()).type();
        PieceType attacker = board.at(mv.from()).type();
        
        // Φόρμουλα MVV-LVA: Προηγείται το θύμα με τη μεγαλύτερη αξία 
        // και ο επιτιθέμενος με τη μικρότερη αξία
        move_scores[i] = get_piece_value(victim) * 10 - get_piece_value(attacker);
    }

    // Loop αναζήτησης
    for (size_t i = 0; i < moves.size(); i++) {
        
        // Incremental Move Selection (Ταξινόμηση στην στοίβα, χωρίς vector)
        int best_index = i;
        for (size_t j = i + 1; j < moves.size(); j++) {
            if (move_scores[j] > move_scores[best_index]) {
                best_index = j;
            }
        }
        std::swap(moves[i], moves[best_index]);
        std::swap(move_scores[i], move_scores[best_index]);

        Move mv = moves[i];
        PieceType victim = board.at(mv.to()).type();

        // 3. DELTA PRUNING
        // Αν το stand_pat + η αξία του κομματιού που πάμε να φάμε + ένα περιθώριο (200 πόντοι για ασφάλεια/προαγωγές)
        // εξακολουθεί να είναι μικρότερο από το alpha, τότε αυτή η κίνηση δεν έχει ελπίδα να μας βοηθήσει.
        if (stand_pat + get_piece_value(victim) + 200 < alpha) {
            continue; // Κλάδεμα αμέσως, προσπερνάμε την κίνηση χωρίς makeMove!
        }

        board.makeMove(mv);
        int score = -quiescence(-beta, -alpha, board);
        board.unmakeMove(mv);

        if (score >= beta) return beta;
        if (score > alpha) alpha = score;
    }

    return alpha;
}


// --- Advanced Alpha-Beta Engine with NMP, PVS & LMR ---
int alphabeta(int alpha, int beta, int depth, Board& board, int ply, Move& best_move) {
    // ⚡ ΑΚΑΡΙΑΙΑ ΔΙΑΚΟΠΗ: Αν πατήθηκε το ENTER, σταματάμε αμέσως την αναζήτηση
    if (ai_interrupt_flag.load()) return alpha;

    // ⚡ ΕΛΕΓΧΟΣ ΤΡΙΠΛΗΣ ΕΠΑΝΑΛΗΨΗΣ / ΙΣΟΠΑΛΙΑΣ ΜΕΣΑ ΣΤΗΝ ΑΝΑΖΗΤΗΣΗ
    // Ο έλεγχος γίνεται για ply > 0 (στις κινήσεις που προβλέπει η AI στο μέλλον)
    if (ply > 0 && board.isRepetition()) {
        // Contempt Factor: Αν η AI έχει ήδη βρει καλή γραμμή (alpha > 50), "μισεί" την ισοπαλία
        // και τη βαθμολογεί ως κακό αποτέλεσμα (-150) για να επιλέξει άλλη κίνηση.
        // Αν η AI χάνει (alpha < -50), η ισοπαλία τη βολεύει, οπότε επιστρέφει 0.
        if (alpha > 50) {
            return -150; 
        }
        return 0; 
    }

    NODES++;
    
    // Έλεγχος αν φτάσαμε στο τελικό βάθος (μετάβαση σε Quiescence Search για τα φαγώματα)
    if (depth <= 0) return quiescence(alpha, beta, board);

    // --- 1. NULL MOVE PRUNING (NMP) ---
    if (depth >= 3 && !board.inCheck() && ply > 0) {
        board.makeNullMove(); // Κάνουμε "πάσο"
        
        int reduction = 2; // Μείωση βάθους για τη null κίνηση
        int null_score = -alphabeta(-beta, -beta + 1, depth - 1 - reduction, board, ply + 1, best_move);
        
        board.unmakeNullMove(); // Αναίρεση του "πάσο"
        
        if (null_score >= beta) {
            return beta; // Κλάδεμα αμέσως αν η θέση είναι πολύ ανώτερη
        }
    }

    // Παραγωγή νόμιμων κινήσεων
    Movelist moves;
    movegen::legalmoves(moves, board);
    
    // Έλεγχος για Ματ ή Πατ
    if (moves.size() == 0) {
        if (board.inCheck()) return -MATE_VALUE + ply;
        return 0;
    }

    // ΔΙΟΡΘΩΣΗ: Ρητός ορισμός στατικού πίνακα 256 θέσεων στην στοίβα (stack)
    int move_scores[256] = {0}; 
    for (size_t i = 0; i < moves.size(); i++) {
        if (board.isCapture(moves[i])) {
            move_scores[i] = 10000; // Προτεραιότητα στα captures
        }
    }

    int score;
    bool search_pv = true; 
    int legal_moves_searched = 0;

    for (size_t i = 0; i < moves.size(); i++) {
        // ⚡ ΕΛΕΓΧΟΣ ΜΕΣΑ ΣΤΟ LOOP: Διακοπή και κατά τη διάρκεια της αναζήτησης των κινήσεων
        if (ai_interrupt_flag.load()) return alpha;

        // --- 2. INCREMENTAL MOVE SELECTION ---
        int best_index = i;
        for (size_t j = i + 1; j < moves.size(); j++) {
            if (move_scores[j] > move_scores[best_index]) {
                best_index = j;
            }
        }
        std::swap(moves[i], moves[best_index]);
        std::swap(move_scores[i], move_scores[best_index]);

        Move mv = moves[i];
        
        bool is_capture = board.isCapture(mv);
        bool is_promotion = (mv.typeOf() == Move::PROMOTION); 

        board.makeMove(mv);
        legal_moves_searched++;

        // --- 3. PRINCIPAL VARIATION SEARCH (PVS) ---
        if (search_pv) {
            score = -alphabeta(-beta, -alpha, depth - 1, board, ply + 1, best_move);
        } else {
            // --- 4. LATE MOVE REDUCTIONS (LMR) ---
            int lmr_reduction = 0;
            if (depth >= 3 && legal_moves_searched > 3 && !board.inCheck() && !is_capture && !is_promotion) {
                lmr_reduction = 1;
            }

            // Αναζήτηση με Null Window
            score = -alphabeta(-(alpha + 1), -alpha, depth - 1 - lmr_reduction, board, ply + 1, best_move);
            
            // Αν η κίνηση αποδειχθεί καλή, την ξαναψάχνουμε χωρίς μείωση βάθους
            if (score > alpha && lmr_reduction > 0) {
                score = -alphabeta(-(alpha + 1), -alpha, depth - 1, board, ply + 1, best_move);
            }
            // Αν εξακολουθεί να είναι καλή, την ψάχνουμε με πλήρες παράθυρο
            if (score > alpha && score < beta) {
                score = -alphabeta(-beta, -alpha, depth - 1, board, ply + 1, best_move);
            }
        }
        
        board.unmakeMove(mv);
        
        // Beta Cutoff (Fail-High)
        if (score >= beta) return beta; 
        
        // Alpha Update (Fail-Low / Exact)
        if (score > alpha) {
            alpha = score;
            search_pv = false; 
            if (ply == 0) best_move = mv;
        }
    }
    
    return alpha;
}




// --- Core Recursive Mate Finder ---
pair<bool, Tree> has_forced_mate(Board& board, int depth, int total_depth, const string& mode, int ply) {
    NODES++;
    Movelist moves;
    movegen::legalmoves(moves, board);
    if (board.inCheck() && moves.size() == 0) return make_pair(true, Tree());
    if (depth <= 0 || (!board.inCheck() && moves.size() == 0)) return make_pair(false, Tree());

    TTKey key = {board.hash(), depth, board.sideToMove()}; 
    if (TT.count(key)) {
        TTEntry& entry = TT[key];
        if (entry.depth >= depth) return make_pair(entry.ok, entry.tree);
    }

    if (mode == "quiet" && ply == 0) {
        Movelist quiet_moves;
        for (size_t i = 0; i < moves.size(); ++i) {
            if (is_quiet(board, moves[i])) quiet_moves.add(moves[i]); 
        }
        moves = quiet_moves;
        if (moves.size() == 0) return make_pair(false, Tree());
    }

    string tt_best_uci = TT.count(key) ? TT[key].best_move_uci : "";
    vector<Move> ordered_moves = order_moves(board, moves, tt_best_uci, ply);
    bool is_or_node = (board.sideToMove() == ROOT_SIDE);

    if (is_or_node) {
        for (size_t i = 0; i < ordered_moves.size(); ++i) {
            Move mv = ordered_moves[i];
            board.makeMove(mv);
            pair<bool, Tree> result = has_forced_mate(board, depth - 1, total_depth, mode, ply + 1);
            board.unmakeMove(mv);

            if (result.first) {
                string best_uci = uci::moveToUci(mv);
                KILLERS[ply].insert(best_uci);
                HISTORY[best_uci] += 1 + depth;
                Tree tree;
                TreePtr node = make_shared<Node>();
                node->move = mv;
                node->children = result.second;
                tree.push_back(node);
                TT[key] = {depth, true, tree, best_uci, 0, 0};
                return make_pair(true, tree);
            } else {
                string best_uci = uci::moveToUci(mv);
                HISTORY[best_uci] -= 1;
            }
        }
        TT[key] = {depth, false, Tree(), "", 0, 0};
        return make_pair(false, Tree());
    } else {
        Tree full_tree;
        for (size_t i = 0; i < ordered_moves.size(); ++i) {
            Move mv = ordered_moves[i];
            board.makeMove(mv);
            pair<bool, Tree> result = has_forced_mate(board, depth - 1, total_depth, mode, ply + 1);
            board.unmakeMove(mv);

            if (!result.first) {
                TT[key] = {depth, false, Tree(), uci::moveToUci(mv), 0, 0};
                return make_pair(false, Tree());
            } else {
                TreePtr node = make_shared<Node>();
                node->move = mv;
                node->children = result.second;
                full_tree.push_back(node);
                string best_uci = uci::moveToUci(mv);
                HISTORY[best_uci] -= 1;
            }
        }
        TT[key] = {depth, true, full_tree, "", 0, 0};
        return make_pair(true, full_tree);
    }
}
// --- Print Solution Tree ---
void print_tree(Board& board, const Tree& tree, string current_line = "") {
    if (tree.empty()) {
        cout << current_line << " -> Ματ!\n";
        return;
    }

    for (size_t i = 0; i < tree.size(); ++i) {
        TreePtr node = tree[i];
        Move move = node->move;
        string san = uci::moveToSan(board, move);
        string move_str;

        if (board.sideToMove() == Color::WHITE) {
            move_str = to_string(board.fullMoveNumber()) + ". " + san;
        } else {
            if (current_line.empty()) {
                move_str = to_string(board.fullMoveNumber()) + "... " + san;
            } else {
                move_str = san;
            }
        }

        string next_line = current_line + " " + move_str;
        board.makeMove(move);
        print_tree(board, node->children, next_line);
        board.unmakeMove(move);
    }
}

// Δομή που αναπαριστά μια εγγραφή (entry) 16-bit στο PolyGlot βιβλίο
struct PolyglotEntry {
    uint64_t key;
    uint16_t move;
    uint16_t weight;
    uint32_t learn;
};

// Συνάρτηση αλλαγής Endianness (το PolyGlot αποθηκεύει σε Big Endian, η C++ θέλει Little Endian)
uint64_t flip_endian_64(uint64_t val) {
    return ((val << 56) & 0xFF00000000000000ULL) | ((val << 40) & 0x00FF000000000000ULL) |
           ((val << 24) & 0x0000FF0000000000ULL) | ((val << 8)  & 0x000000FF00000000ULL) |
           ((val >> 8)  & 0x00000000FF000000ULL) | ((val >> 24) & 0x0000000000FF0000ULL) |
           ((val >> 40) & 0x000000000000FF00ULL) | ((val >> 56) & 0x00000000000000FFULL);
}

uint16_t flip_endian_16(uint16_t val) {
    return (val << 8) | (val >> 8);
}

// Η συνάρτηση που καλείται από την interactive_gameplay
Move get_book_move(Board& board, const std::vector<Move>& game_history) {
    // 1. Άνοιγμα του αρχείου don.bin από το σωστό path
    std::ifstream file("/storage/emulated/0/don.bin", std::ios::binary);
    if (!file.is_open()) return Move::NO_MOVE; // Αν δεν βρει το αρχείο, συνεχίζει κανονικά

    // 2. Παίρνουμε το PolyGlot Hash της τρέχουσας θέσης από την chess.hpp
    uint64_t target_key = board.hash(); 

    // 3. Binary Search στο αρχείο για να βρούμε το key
    file.seekg(0, std::ios::end);
    long long file_size = file.tellg();
    long long num_entries = file_size / 16;

    long long low = 0;
    long long high = num_entries - 1;
    long long found_index = -1;

    while (low <= high) {
        long long mid = low + (high - low) / 2;
        file.seekg(mid * 16, std::ios::beg);

        uint64_t entry_key;
        file.read(reinterpret_cast<char*>(&entry_key), 8);
        entry_key = flip_endian_64(entry_key);

        if (entry_key == target_key) {
            found_index = mid;
            break;
        } else if (entry_key < target_key) {
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }

    if (found_index == -1) return Move::NO_MOVE; // Η θέση δεν υπάρχει στο βιβλίο

    // 4. Πηγαίνουμε στην πρώτη εγγραφή που έχει αυτό το key
    while (found_index > 0) {
        file.seekg((found_index - 1) * 16, std::ios::beg);
        uint64_t entry_key;
        file.read(reinterpret_cast<char*>(&entry_key), 8);
        if (flip_endian_64(entry_key) != target_key) break;
        found_index--;
    }

    // 5. Διαβάζουμε όλες τις διαθέσιμες κινήσεις (entries) για αυτήν τη θέση
    std::vector<PolyglotEntry> book_entries;
    int total_weight = 0;

    file.seekg(found_index * 16, std::ios::beg);
    while (found_index < num_entries) {
        PolyglotEntry raw_entry;
        file.read(reinterpret_cast<char*>(&raw_entry.key), 8);
        file.read(reinterpret_cast<char*>(&raw_entry.move), 2);
        file.read(reinterpret_cast<char*>(&raw_entry.weight), 2);
        file.read(reinterpret_cast<char*>(&raw_entry.learn), 4);

        raw_entry.key = flip_endian_64(raw_entry.key);
        if (raw_entry.key != target_key) break; // Τελείωσαν οι κινήσεις για αυτήν τη θέση

        raw_entry.move = flip_endian_16(raw_entry.move);
        raw_entry.weight = flip_endian_16(raw_entry.weight);

        // Αποκωδικοποίηση της κίνησης από το PolyGlot format στο Move της chess.hpp
        int from_idx = (raw_entry.move >> 6) & 0x3F;
        int to_idx = raw_entry.move & 0x3F;
        int promo_idx = (raw_entry.move >> 12) & 7;

        Square from_sq = Square(from_idx);
        Square to_sq = Square(to_idx);
        
        // ΔΙΟΡΘΩΣΗ: Δημιουργία κίνησης σύμφωνα με το API της chess.hpp
        Move cpp_move;
        if (promo_idx > 0) {
            // Αντιστοίχιση κομματιού προαγωγής: 1=Knight, 2=Bishop, 3=Rook, 4=Queen
            PieceType promo_piece = PieceType::QUEEN;
            if (promo_idx == 1) promo_piece = PieceType::KNIGHT;
            else if (promo_idx == 2) promo_piece = PieceType::BISHOP;
            else if (promo_idx == 3) promo_piece = PieceType::ROOK;
            
            cpp_move = Move::make(from_sq, to_sq, promo_piece);
        } else {
            cpp_move = Move::make(from_sq, to_sq);
        }
        
        // Έλεγχος νομιμότητας
        Movelist legal_moves;
        movegen::legalmoves(legal_moves, board);
        bool is_legal = false;
        for (size_t k = 0; k < legal_moves.size(); k++) {
            if (legal_moves[k] == cpp_move) {
                is_legal = true;
                break;
            }
        }

        if (is_legal) {
            book_entries.push_back(raw_entry);
            total_weight += raw_entry.weight;
        }
        found_index++;
    }

    if (book_entries.empty() || total_weight == 0) return Move::NO_MOVE;

    // 6. ΔΙΟΡΘΩΣΗ: Τυχαία επιλογή κίνησης με χρήση standard μεθόδων που υποστηρίζει το Cxxdroid
    static std::mt19937 rng(std::random_device{}());
    std::uniform_int_distribution<int> dist(0, total_weight - 1);
    int r = dist(rng);
    int upto = 0;

    for (const auto& entry : book_entries) {
        upto += entry.weight;
        if (upto > r) {
            int from_idx = (entry.move >> 6) & 0x3F;
            int to_idx = entry.move & 0x3F;
            int promo_idx = (entry.move >> 12) & 7;

            if (promo_idx > 0) {
                PieceType promo_piece = PieceType::QUEEN;
                if (promo_idx == 1) promo_piece = PieceType::KNIGHT;
                else if (promo_idx == 2) promo_piece = PieceType::BISHOP;
                else if (promo_idx == 3) promo_piece = PieceType::ROOK;
                
                return Move::make(Square(from_idx), Square(to_idx), promo_piece);
            } else {
                return Move::make(Square(from_idx), Square(to_idx));
            }
        }
    }

    return Move::NO_MOVE;
}


bool check_draw(const Board& board) {
    if (board.isRepetition()) return true;
    return false;
}

// Εκτύπωση Σκακιέρας (Fidelity Relief με ANSI Colors)
void print_board_fidelity_relief(const Board& board) {
    const string BG_LIGHT = "\033[48;5;252m"; 
    const string BG_DARK = "\033[48;5;22m";   
    const string BG_LIGHT_WITH_WHITE_PIECE = "\033[48;5;250m";
    const string RESET = "\033[0m";

    const string pieces_unicode[2][6] = {
        {"♙", "♘", "♗", "♖", "♕", "♔"}, // White
        {"♟", "♞", "♝", "♜", "♛", "♚"}  // Black
    };


    const string FG_LIGHT_ON_LIGHT = "\033[38;5;232m";
    const string FG_LIGHT_ON_DARK = "\033[38;5;255m";
    const string FG_DARK = "\033[38;5;232m";

    cout << "\n a b c d e f g h\n";
    cout << " ─────────────────\n";

    for (int rank = 7; rank >= 0; --rank) {
        cout << rank + 1 << " │";
        for (int file = 0; file < 8; ++file) {
            int sq_idx = rank * 8 + file;
            Square sq(sq_idx);
            Piece piece = board.at(sq);
            
            bool is_light = (rank + file + 1) % 2 == 0;
            string bg = is_light ? BG_LIGHT : BG_DARK;
            if (piece != Piece::NONE && piece.color() == Color::WHITE && is_light) {
                bg = BG_LIGHT_WITH_WHITE_PIECE;
            }

            string symbol = " ";
            string fg = "";

            if (piece != Piece::NONE) {
                int c_idx = (piece.color() == Color::WHITE) ? 0 : 1;
                int t_idx = static_cast<int>(piece.type());
                if (t_idx >= 0 && t_idx < 6) {
                    symbol = pieces_unicode[c_idx][t_idx];
                }

                if (piece.color() == Color::WHITE) {
                    fg = !is_light ? FG_LIGHT_ON_DARK : FG_LIGHT_ON_LIGHT;
                } else {
                    fg = FG_DARK;
                }
            }
            cout << bg << fg << symbol << " " << RESET;
        }
        cout << "│ " << rank + 1 << "\n";
    }
    cout << " ─────────────────\n";
    cout << " a b c d e f g h\n\n";
}

void reset_engine() {
    KILLERS.clear();
    HISTORY.clear();
    TT.clear();
    cout << "\033[33m>> Engine reset έγινε.\033[0m\n";
}
// --- Κύρια Ροή Διαδραστικού Παιχνιδιού (Πλήρης & Διορθωμένη για UCI κινήσεις) ---
#include <vector>

void interactive_gameplay() {
    cout << "\033[1;32m=== Don Zouάν Chess AI Interactive ===\033[0m\n";
    cout << "\033[36mΔώσε αρχικό FEN ή άφησέ το κενό για default:\033[0m ";
    string fen_input;
    cin.ignore();
    getline(cin, fen_input);

    Board board = fen_input.empty() ? Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1") : Board(fen_input);
    
    // Δομή για να κρατάμε ιστορικό κινήσεων ώστε να λειτουργεί το UNDO
    std::vector<Move> game_history;

    cout << "\033[36mAI παίζει με ποιο χρώμα; (w=Λευκά, b=Μαύρα):\033[0m ";
    string ai_side_input;
    cin >> ai_side_input;
    Color ai_side = (ai_side_input == "w") ? Color::WHITE : Color::BLACK;

    cout << "\033[36mΔευτερόλεπτα σκέψης (π.χ. 5) [0 για manual]:\033[0m ";
    int time_limit;
    if (!(cin >> time_limit)) {
        time_limit = 5;
        cout << "\033[36m>> Χρήση default χρόνου: 5 δευτερόλεπτα\033[0m\n";
    }
    if (time_limit <= 0) time_limit = 9999; 

    int move_number = board.fullMoveNumber();

    while (true) {
        Movelist moves;
        movegen::legalmoves(moves, board);
        if (moves.size() == 0) break; 

        cout << "\n\033[1;32mΤρέχουσα θέση (Fidelity Relief):\033[0m\n";
        print_board_fidelity_relief(board);
        cout << "\n\033[1;32m----------------------------\033[0m\n";

        if (check_draw(board)) {
            cout << "\033[36m>> Ισοπαλία αναγνωρίστηκε.\033[0m\n";
            break;
        }

        if (board.sideToMove() == ai_side) {
            if (moves.size() == 1) {
                Move only_move = moves[0];
                string san = uci::moveToSan(board, only_move);
                string uci_str = uci::moveToUci(only_move);
                string prefix = (board.sideToMove() == Color::WHITE) ? to_string(move_number) + "." : to_string(move_number) + "...";
                cout << "\033[1;32m" << prefix << " " << san << " (" << uci_str << ") (AI μόνο κίνηση)\033[0m\n";
                
                game_history.push_back(only_move); // Αποθήκευση στο ιστορικό
                board.makeMove(only_move);
                if (board.sideToMove() == Color::WHITE) move_number++;
                continue;
            }

            // Κλήση του βιβλίου ανοιγμάτων don.bin
            Move book_move = get_book_move(board, game_history);

            if (book_move != Move::NO_MOVE) {
                string san = uci::moveToSan(board, book_move);
                string uci_str = uci::moveToUci(book_move);
                string prefix = (board.sideToMove() == Color::WHITE) ? to_string(move_number) + "." : to_string(move_number) + "...";
                cout << "\033[1;32m" << prefix << " " << san << " (" << uci_str << ") (AI από book)\033[0m\n";
                
                game_history.push_back(book_move); // Αποθήκευση στο ιστορικό
                board.makeMove(book_move);
                if (board.sideToMove() == Color::WHITE) move_number++;
                continue;
            }

            cout << "\033[1;32mΣκέψη AI... (Πάτα ENTER για άμεση κίνηση)\033[0m\n" << flush;
            
            // Μηδενισμός του global flag πριν ξεκινήσει η αναζήτηση
            ai_interrupt_flag = false;
            
            cin.clear();
            cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');

            std::thread input_thread([]() {
                string dummy;
                getline(cin, dummy); // Περιμένει ακαριαία το ENTER
                ai_interrupt_flag = true; 
            });

            auto start_time = chrono::high_resolution_clock::now();
            Move best_move_full = Move::NO_MOVE;
            int best_score_full = 0;
            int depth = 1;
            int previous_score = 0;
            int DELTA = 35; 

            while (true) {
                auto current_time = chrono::high_resolution_clock::now();
                chrono::duration<double> elapsed = current_time - start_time;
                
                if (ai_interrupt_flag || elapsed.count() >= time_limit) {
                    break;
                }

                int alpha = -INF;
                int beta = INF;

                if (depth > 1 && abs(previous_score) < 8000) {
                    alpha = previous_score - DELTA;
                    beta = previous_score + DELTA;
                }

                Move current_best = Move::NO_MOVE;
                
                // Κλήση με τα 6 κλασικά ορίσματα (δουλεύει με την global ai_interrupt_flag)
                int score = alphabeta(alpha, beta, depth, board, 0, current_best);

                if (ai_interrupt_flag) {
                    break;
                }

                if (depth > 1 && (score <= alpha || score >= beta)) {
                    score = alphabeta(-INF, INF, depth, board, 0, current_best);
                    if (ai_interrupt_flag) break;
                }

                if (current_best != Move::NO_MOVE) {
                    best_move_full = current_best;
                    best_score_full = score;
                    previous_score = score;
                }

                string move_san = (best_move_full != Move::NO_MOVE) ? uci::moveToSan(board, best_move_full) : "???";
                string move_uci = (best_move_full != Move::NO_MOVE) ? uci::moveToUci(best_move_full) : "???";
                cout << "\r\033[36m[Depth " << depth << "] Best: " << move_san << " (" << move_uci << ")"
                     << " | Eval: " << fixed << (best_score_full / 100.0) 
                     << " | Nodes: " << NODES << "\033[0m" << flush;

                if (abs(score) >= MATE_VALUE - 100) break; 

                depth++;
                if (depth > 20) break; 
            }

            // Κλείσιμο του thread εισόδου
            if (ai_interrupt_flag) {
                if (input_thread.joinable()) {
                    input_thread.join();
                }
            } else {
                cout << "\n\033[33m[AI ολοκλήρωσε τη σκέψη. Πάτα ENTER για να συνεχίσεις...]\033[0m\n";
                if (input_thread.joinable()) {
                    input_thread.join();
                }
            }

            if (best_move_full != Move::NO_MOVE) {
                string san = uci::moveToSan(board, best_move_full);
                string uci_str = uci::moveToUci(best_move_full);
                string prefix = (board.sideToMove() == Color::WHITE) ? to_string(move_number) + "." : to_string(move_number) + "...";
                cout << "\n\033[1;32m" << prefix << " AI παίζει: " << san << " (" << uci_str << ") (" << fixed << (best_score_full / 100.0) << ")\033[0m\n";
                
                game_history.push_back(best_move_full); // Αποθήκευση στο ιστορικό
                board.makeMove(best_move_full);
                if (board.sideToMove() == Color::WHITE) move_number++;
            } else {
                Move fallback = moves[0];
                game_history.push_back(fallback); // Αποθήκευση στο ιστορικό
                board.makeMove(fallback);
                cout << "\n\033[31mAI: Fallback Move\033[0m\n";
            }
        } 
        else {
            size_t tt_count = TT.size();
            size_t max_tt_size = 1000000; 
            double fill_percentage = (double)tt_count / max_tt_size * 100.0;

            string mem_color = (fill_percentage < 70.0) ? "\033[32m🟢" : ((fill_percentage < 85.0) ? "\033[33m⚠️ " : "\033[31m🚨 ΚΙΝΔΥΝΟΣ! ");
            cout << mem_color << "Μνήμη TT: " << tt_count << "/" << max_tt_size << " (" << fixed << fill_percentage << "% γεμάτο)\033[0m\n";

            cout << "\033[1;32m==> Η σειρά σου!\033[0m\n";
            cout << "\033[36mΗ κίνησή σου (e2e4 | undo | clear | reset):\033[0m ";
            string move_str;
            cin >> move_str;

            // --- ΜΗΧΑΝΙΣΜΟΣ UNDO ---
            if (move_str == "undo") {
                if (game_history.size() >= 2) {
                    board.unmakeMove(game_history.back());
                    game_history.pop_back();

                    board.unmakeMove(game_history.back());
                    game_history.pop_back();

                    if (board.sideToMove() == Color::BLACK) move_number--;
                    cout << "\033[33m⏪ Έγινε αναίρεση των 2 τελευταίων κινήσεων!\033[0m\n";
                } else {
                    cout << "\033[31m❌ Δεν υπάρχουν αρκετές κινήσεις για αναίρεση.\033[0m\n";
                }
                continue;
            }

            if (move_str == "clear") {
                TT.clear();
                cout << "\033[1;32m🧹 Το Transposition Table καθαρίστηκε επιτυχώς!\033[0m\n";
                continue;
            }
            if (move_str == "reset") {
                reset_engine();
                cout << "\033[33m>> Έξοδος από το παιχνίδι...\033[0m\n";
                return;
            }

            Move user_move = Move::NO_MOVE;
            bool is_legal = false;

            for (size_t i = 0; i < moves.size(); ++i) {
                if (uci::moveToUci(moves[i]) == move_str) { 
                    user_move = moves[i];
                    is_legal = true;
                    break;
                }
            }

            if (is_legal && user_move != Move::NO_MOVE) {
                game_history.push_back(user_move); // Αποθήκευση στο ιστορικό
                board.makeMove(user_move);
                if (board.sideToMove() == Color::WHITE) move_number++;
            } else {
                cout << "\033[31mΜη νόμιμη κίνηση ή λάθος μορφή (δώσε π.χ. e2e4, e8g8).\033[0m\n";
            }
        }
    }

    print_board_fidelity_relief(board);
    cout << "\n\033[1;32m--- Τελικό Αποτέλεσμα ---\033[0m\n";
    if (board.inCheck()) {
        cout << "\033[1;36m>> ΜΑΤ!\033[0m\n";
    } else {
        cout << "\033[36m>> Το παιχνίδι έληξε (Ισοπαλία/Πατ).\033[0m\n";
    }
}



// --- Search Orchestration (Mate Finder) ---
Tree find_first_forced_move(const string& fen, int depth, const string& mode, const string& focus) {
    NODES = 0;
    TT.clear();
    KILLERS.clear();
    HISTORY.clear();

    Board board(fen);
    ROOT_SIDE = board.sideToMove();

    cout << "\nΣκέφτομαι... (Σειρά έχουν τα: " << ((ROOT_SIDE == Color::WHITE) ? "Λευκά" : "Μαύρα") << ")\n" << flush;

    if (!focus.empty()) {
        Move mv = uci::parseSan(board, focus);
        if (mv != Move::NO_MOVE) {
            if (mode == "quiet" && !is_quiet(board, mv)) {
                cout << "Η κίνηση δεν είναι ήσυχη, παραλείπεται.\n";
            } else {
                board.makeMove(mv);
                pair<bool, Tree> result = has_forced_mate(board, depth - 1, depth, mode, 1);
                board.unmakeMove(mv);
                if (result.first) {
                    cout << "--> Εξετάζω: " << focus << "!  [Βρέθηκε ματ!]\n";
                    Tree single_tree;
                    TreePtr node = make_shared<Node>();
                    node->move = mv;
                    node->children = result.second;
                    single_tree.push_back(node);
                    return single_tree;
                } else {
                    cout << "--> Εξετάζω: " << focus << "  [Δεν οδηγεί σε υποχρεωτικό ματ]\n";
                }
            }
        } else {
            cout << "Λάθος μορφή κίνησης.\n";
        }
    }

    Tree best_tree;
    for (int d = 1; d <= depth; ++d) {
        cout << "\n--- Αναζήτηση σε βάθος " << d << " plies ---\n";
        Movelist moves;
        movegen::legalmoves(moves, board);

        if (mode == "quiet") {
            Movelist quiet_moves;
            for (size_t i = 0; i < moves.size(); ++i) {
                if (is_quiet(board, moves[i])) quiet_moves.add(moves[i]);
            }
            moves = quiet_moves;
            if (moves.size() == 0) break;
        }

        TT.clear();
        vector<Move> root_moves = order_moves(board, moves, "", 0);
        bool found_here = false;

        for (size_t i = 0; i < root_moves.size(); ++i) {
            Move mv = root_moves[i];
            string san = uci::moveToSan(board, mv);
            board.makeMove(mv);
            pair<bool, Tree> result = has_forced_mate(board, d - 1, d, mode, 1);
            board.unmakeMove(mv);

            if (result.first) {
                cout << "--> Εξετάζω: " << san << "!  [Βρέθηκε ματ!]\n";
                best_tree.clear();
                TreePtr node = make_shared<Node>();
                node->move = mv;
                node->children = result.second;
                best_tree.push_back(node);
                found_here = true;
                break;
            } else {
                cout << "--> Εξετάζω: " << san << "\n";
            }
        }
        if (found_here) return best_tree;
    }
    return best_tree;
}

// --- Orchestration για την Καλύτερη Κίνηση (Iterative Deepening Engine) ---
void find_best_general_move(const string& fen, int max_depth) {
    Board board(fen);
    NODES = 0;
    Move overall_best_move = Move::NO_MOVE;
    
    cout << "\n--- Έναρξη Γενικής Ανάλυσης Θέσης (Alpha-Beta) ---\n";
    auto start = chrono::high_resolution_clock::now();
    
    for (int d = 1; d <= max_depth; ++d) {
        Move current_best = Move::NO_MOVE;
        int score = alphabeta(-INF, INF, d, board, 0, current_best);
        
        if (current_best != Move::NO_MOVE) {
            overall_best_move = current_best;
        }
        
        string san = (overall_best_move != Move::NO_MOVE) ? uci::moveToSan(board, overall_best_move) : "None";
        cout << "Βάθος " << d << " plies -> Καλύτερη κίνηση: " << san;
        
        if (score > MATE_VALUE - 100) {
            cout << " (Αναγκαστικό Ματ σε " << (MATE_VALUE - score + 1) / 2 << " κινήσεις)";
        } else if (score < -MATE_VALUE + 100) {
            cout << " (Δεχόμενο Ματ σε " << (MATE_VALUE + score) / 2 << " κινήσεις)";
        } else {
            cout << " (Αξιολόγηση: " << fixed << (score / 100.0) << ")";
        }
        cout << "\n";
    }
    
    auto end = chrono::high_resolution_clock::now();
    chrono::duration<double> elapsed = end - start;
    uint64_t nps = (elapsed.count() > 0) ? static_cast<uint64_t>(NODES / elapsed.count()) : 0;
    
    cout << "\n=== ΤΕΛΙΚΟ ΑΠΟΤΕΛΕΣΜΑ ΑΝΑΛΥΣΗΣ ===\n";
    if (overall_best_move != Move::NO_MOVE) {
        cout << "Προτεινόμενη Κίνηση: " << uci::moveToSan(board, overall_best_move) << "\n";
    } else {
        cout << "Δεν βρέθηκε έγκυρη κίνηση.\n";
    }
    cout << "Χρόνος: " << elapsed.count() << " δευτερόλεπτα\n";
    cout << "Θέσεις που εξετάστηκαν: " << NODES << "\n";
    cout << "Ταχύτητα: " << nps << " θέσεις/δευτερόλεπτο\n";
    cout << "=================================\n";
}

void run_solver_on_fen(const string& fen, int full_moves_mate) {
    Board board(fen);
    cout << "\nΤύπος ανάλυσης:\n1. Force mate (όλες οι κινήσεις επιτρέπονται)\n2. Ήσυχη πρώτη κίνηση μόνο\nΕπιλογή: ";
    string choice;
    cin >> choice;
    string mode = (choice == "2") ? "quiet" : "force";

    cout << "Αν θέλεις να εξεταστεί μόνο μία κίνηση (π.χ. Qd7+), γράψε την εδώ (αλλιώς Enter):\n";
    string focus;
    cin.ignore();
    getline(cin, focus);

    int depth = full_moves_mate * 2;
    auto start = chrono::high_resolution_clock::now();
    Tree mate_tree = find_first_forced_move(fen, depth, mode, focus);
    auto end = chrono::high_resolution_clock::now();

    chrono::duration<double> elapsed = end - start;
    uint64_t nps = (elapsed.count() > 0) ? static_cast<uint64_t>(NODES / elapsed.count()) : 0;

    cout << "\nΑποτελέσματα:\n";
    if (!mate_tree.empty()) {
        cout << "\n=== ΠΛΗΡΕΣ ΔΕΝΤΡΟ ΛΥΣΗΣ ===\n";
        Board temp_board(fen);
        print_tree(temp_board, mate_tree);
        cout << "==========================\n";
    } else {
        cout << "Δεν βρέθηκε υποχρεωτικό ματ.\n";
    }
    cout << "\nΧρόνος: " << fixed << elapsed.count() << " δευτερόλεπτα\n";
    cout << "Θέσεις που εξετάστηκαν: " << NODES << "\n";
    cout << "Ταχύτητα: " << nps << " θέσεις/δευτερόλεπτο\n";
}

// --- Κύρια Συνάρτηση Main με το Νέο Μενού Επιλογών ---
int main() {
    while (true) {
        cout << "\n=== Don Zouάν Mate Solver & AI Game v4.5 (C++) ===\n";
        cout << "1. Αποθήκευση νέου FEN με περιγραφή\n";
        cout << "2. Προβολή/Λύση αποθηκευμένου ή νέου FEN (Εύρεση Ματ)\n";
        cout << "3. Γενική Ανάλυση Θέσης (Εύρεση Καλύτερης Κίνησης)\n";
        cout << "4. Διαδραστικό Παιχνίδι (Interactive Gameplay vs AI) 🎮\n";
        cout << "5. Έξοδος\n";
        cout << "Επιλογή: ";
        string choice;
        cin >> choice;

        if (choice == "1") {
            string fen, desc;
            cout << "Δώσε νέο FEN:\n";
            cin.ignore();
            getline(cin, fen);
            cout << "Δώσε περιγραφή (π.χ. 'Ματ σε 2'): ";
            getline(cin, desc);
            save_fen(fen, desc);
        } else if (choice == "2") {
            pair<string, string> fen_desc = select_fen_or_new();
            if (!fen_desc.first.empty()) {
                cout << "(" << fen_desc.second << ") Ματ σε πόσες πλήρεις κινήσεις; ";
                int moves_count;
                cin >> moves_count;
                run_solver_on_fen(fen_desc.first, moves_count);
            }
        } else if (choice == "3") {
            pair<string, string> fen_desc = select_fen_or_new();
            if (!fen_desc.first.empty()) {
                cout << "Μέγιστο βάθος αναζήτησης σε plies (προτεινόμενο: 6-12): ";
                int max_depth;
                cin >> max_depth;
                find_best_general_move(fen_desc.first, max_depth);
            }
        } else if (choice == "4") {
            interactive_gameplay();
        } else if (choice == "5") {
            cout << "Έγινε έξοδος.\n";
            break;
        } else {
            cout << "Μη έγκυρη επιλογή.\n";
        }
    }
    return 0;
}
