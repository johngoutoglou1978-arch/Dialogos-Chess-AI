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
#include "/storage/emulated/0/chess.hpp" 

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

// Transposition Table (TT) entry
struct TTEntry {
    int depth;
    bool ok;
    Tree tree;
    string best_move_uci;
};

// Custom Hash για το κλειδί του TT: {Zobrist_Hash, depth, turn}
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

// Killer Moves & History Heuristic (Απλοποιημένα με string για αποφυγή σφαλμάτων compiler)
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
// --- Core Recursive Mate Finder ---
pair<bool, Tree> has_forced_mate(Board& board, int depth, int total_depth, const string& mode, int ply) {
    NODES++;

    Movelist moves;
    movegen::legalmoves(moves, board);
    if (board.inCheck() && moves.size() == 0) {
        return make_pair(true, Tree());
    }

    if (depth <= 0 || (!board.inCheck() && moves.size() == 0)) {
        return make_pair(false, Tree());
    }

    TTKey key = {board.hash(), depth, board.sideToMove()}; 
    if (TT.count(key)) {
        TTEntry& entry = TT[key];
        if (entry.depth >= depth) {
            return make_pair(entry.ok, entry.tree);
        }
    }

    if (mode == "quiet" && ply == 0) {
        Movelist quiet_moves;
        for (size_t i = 0; i < moves.size(); ++i) {
            if (is_quiet(board, moves[i])) {
                quiet_moves.add(moves[i]); 
            }
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

                TT[key] = {depth, true, tree, best_uci};
                return make_pair(true, tree);
            } else {
                string best_uci = uci::moveToUci(mv);
                HISTORY[best_uci] -= 1;
            }
        }
        TT[key] = {depth, false, Tree(), ""};
        return make_pair(false, Tree());
    } else {
        Tree full_tree;
        for (size_t i = 0; i < ordered_moves.size(); ++i) {
            Move mv = ordered_moves[i];
            board.makeMove(mv);
            pair<bool, Tree> result = has_forced_mate(board, depth - 1, total_depth, mode, ply + 1);
            board.unmakeMove(mv);

            if (!result.first) {
                TT[key] = {depth, false, Tree(), uci::moveToUci(mv)};
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
        TT[key] = {depth, true, full_tree, ""};
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
        string san = uci::moveToSan(board, move); // ΔΙΟΡΘΩΘΗΚΕ ΕΔΩ
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

// --- Search Orchestration ---
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
            string san = uci::moveToSan(board, mv); // ΔΙΟΡΘΩΘΗΚΕ ΕΔΩ
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
    chrono::high_resolution_clock::time_point start = chrono::high_resolution_clock::now();
    Tree mate_tree = find_first_forced_move(fen, depth, mode, focus);
    chrono::high_resolution_clock::time_point end = chrono::high_resolution_clock::now();

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

int main() {
    while (true) {
        cout << "\n=== Don Zouάν Mate Solver v3.5 — Book Print Edition (C++) ===\n";
        cout << "1. Αποθήκευση νέου FEN με περιγραφή\n";
        cout << "2. Προβολή/Λύση αποθηκευμένου ή νέου FEN\n";
        cout << "3. Έξοδος\n";
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
            cout << "Έγινε έξοδος.\n";
            break;
        } else {
            cout << "Μη έγκυρη επιλογή.\n";
        }
    }
    return 0;
}
