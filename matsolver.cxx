#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <map>
#include <algorithm>
#include <chrono>
#include <cctype>

using namespace std;

// ============================================================
// LIGHTWEIGHT CHESS ENGINE CORE
// ============================================================

enum Color { WHITE, BLACK };
enum PieceType { EMPTY, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING };

struct Piece {
    PieceType type = EMPTY;
    Color color = WHITE;
};

struct Move {
    int from_sq = -1;
    int to_sq = -1;
    PieceType promotion = EMPTY;
    bool is_capture = false;
    
    bool operator==(const Move& o) const {
        return from_sq == o.from_sq && to_sq == o.to_sq && promotion == o.promotion;
    }
};

class SimpleBoard {
public:
    Piece board[64];
    Color turn = WHITE;
    int castling = 0; // Not fully parsed for simplicity, but tracking state
    int ep_square = -1;
    int halfmove = 0;
    int fullmove = 1;

    SimpleBoard() { clear(); }

    void clear() {
        for (int i = 0; i < 64; i++) board[i] = Piece();
        turn = WHITE;
        ep_square = -1;
    }

    bool parse_fen(const string& fen) {
        clear();
        stringstream ss(fen);
        string ranks, turn_str, castling_str, ep_str;
        if (!(ss >> ranks >> turn_str)) return false;
        
        int r = 7, f = 0;
        for (char c : ranks) {
            if (c == '/') { r--; f = 0; }
            else if (isdigit(c)) { f += (c - '0'); }
            else {
                int sq = r * 8 + f;
                Color col = isupper(c) ? WHITE : BLACK;
                char tc = tolower(c);
                PieceType pt = EMPTY;
                if (tc == 'p') pt = PAWN;
                else if (tc == 'n') pt = KNIGHT;
                else if (tc == 'b') pt = BISHOP;
                else if (tc == 'r') pt = ROOK;
                else if (tc == 'q') pt = QUEEN;
                else if (tc == 'k') pt = KING;
                board[sq] = {pt, col};
                f++;
            }
        }
        turn = (turn_str == "w") ? WHITE : BLACK;
        return true;
    }

    string to_fen() const {
        string fen = "";
        for (int r = 7; r >= 0; r--) {
            int empty = 0;
            for (int f = 0; f < 8; f++) {
                int sq = r * 8 + f;
                if (board[sq].type == EMPTY) { empty++; }
                else {
                    if (empty > 0) { fen += to_string(empty); empty = 0; }
                    char c = ' ';
                    if (board[sq].type == PAWN) c = 'p';
                    else if (board[sq].type == KNIGHT) c = 'n';
                    else if (board[sq].type == BISHOP) c = 'b';
                    else if (board[sq].type == ROOK) c = 'r';
                    else if (board[sq].type == QUEEN) c = 'q';
                    else if (board[sq].type == KING) c = 'k';
                    if (board[sq].color == WHITE) c = toupper(c);
                    fen += c;
                }
            }
            if (empty > 0) fen += to_string(empty);
            if (r > 0) fen += "/";
        }
        fen += (turn == WHITE) ? " w" : " b";
        return fen;
    }

    bool in_bounds(int r, int f) const { return r >= 0 && r < 8 && f >= 0 && f < 8; }

    int find_king(Color c) const {
        for (int i = 0; i < 64; i++) {
            if (board[i].type == KING && board[i].color == c) return i;
        }
        return -1;
    }

    bool is_square_attacked(int sq, Color attacker_color) const {
        int sr = sq / 8, sf = sq % 8;
        // Knight jumps
        int kr[] = {-2, -2, -1, -1, 1, 1, 2, 2};
        int kf[] = {-1, 1, -2, 2, -2, 2, -1, 1};
        for (int i = 0; i < 8; i++) {
            int nr = sr + kr[i], nf = sf + kf[i];
            if (in_bounds(nr, nf)) {
                int nsq = nr * 8 + nf;
                if (board[nsq].type == KNIGHT && board[nsq].color == attacker_color) return true;
            }
        }
        // Rays: Rook/Queen & Bishop/Queen
        int dr[] = {1, -1, 0, 0, 1, 1, -1, -1};
        int df[] = {0, 0, 1, -1, 1, -1, 1, -1};
        for (int i = 0; i < 8; i++) {
            int nr = sr, nf = sf;
            while (true) {
                nr += dr[i]; nf += df[i];
                if (!in_bounds(nr, nf)) break;
                int nsq = nr * 8 + nf;
                if (board[nsq].type != EMPTY) {
                    if (board[nsq].color == attacker_color) {
                        PieceType pt = board[nsq].type;
                        if (i < 4 && (pt == ROOK || pt == QUEEN)) return true;
                        if (i >= 4 && (pt == BISHOP || pt == QUEEN)) return true;
                        if (pt == KING && abs(sr-nr) <= 1 && abs(sf-nf) <= 1) return true;
                    }
                    break;
                }
            }
        }
        // Pawns
        int pdir = (attacker_color == WHITE) ? -1 : 1;
        int p_att_r = sr + pdir;
        for (int df_p : {-1, 1}) {
            int p_att_f = sf + df_p;
            if (in_bounds(p_att_r, p_att_f)) {
                int nsq = p_att_r * 8 + p_att_f;
                if (board[nsq].type == PAWN && board[nsq].color == attacker_color) return true;
            }
        }
        return false;
    }

    bool is_in_check(Color c) const {
        int ksq = find_king(c);
        if (ksq == -1) return false;
        return is_square_attacked(ksq, c == WHITE ? BLACK : WHITE);
    }

    void generate_pseudo_moves(vector<Move>& moves) const {
        Color us = turn;
        Color them = (us == WHITE) ? BLACK : WHITE;
        int pdir = (us == WHITE) ? 1 : -1;
        int start_p_rank = (us == WHITE) ? 1 : 6;
        int promo_rank = (us == WHITE) ? 7 : 0;

        for (int sq = 0; sq < 64; sq++) {
            if (board[sq].type == EMPTY || board[sq].color != us) continue;
            int r = sq / 8, f = sq % 8;

            if (board[sq].type == PAWN) {
                // Single push
                int nr = r + pdir, nf = f;
                if (in_bounds(nr, nf) && board[nr * 8 + nf].type == EMPTY) {
                    if (nr == promo_rank) {
                        for (PieceType pt : {QUEEN, ROOK, BISHOP, KNIGHT}) moves.push_back({sq, nr * 8 + nf, pt, false});
                    } else {
                        moves.push_back({sq, nr * 8 + nf, EMPTY, false});
                        // Double push
                        if (r == start_p_rank && board[(r + 2 * pdir) * 8 + f].type == EMPTY) {
                            moves.push_back({sq, (r + 2 * pdir) * 8 + f, EMPTY, false});
                        }
                    }
                }
                // Captures
                for (int df : {-1, 1}) {
                    nr = r + pdir; nf = f + df;
                    if (in_bounds(nr, nf)) {
                        int nsq = nr * 8 + nf;
                        if (board[nsq].type != EMPTY && board[nsq].color == them) {
                            if (nr == promo_rank) {
                                for (PieceType pt : {QUEEN, ROOK, BISHOP, KNIGHT}) moves.push_back({sq, nsq, pt, true});
                            } else {
                                moves.push_back({sq, nsq, EMPTY, true});
                            }
                        }
                    }
                }
            }
            else if (board[sq].type == KNIGHT) {
                int kr[] = {-2, -2, -1, -1, 1, 1, 2, 2};
                int kf[] = {-1, 1, -2, 2, -2, 2, -1, 1};
                for (int i = 0; i < 8; i++) {
                    int nr = r + kr[i], nf = f + kf[i];
                    if (in_bounds(nr, nf)) {
                        int nsq = nr * 8 + nf;
                        if (board[nsq].type == EMPTY) moves.push_back({sq, nsq, EMPTY, false});
                        else if (board[nsq].color == them) moves.push_back({sq, nsq, EMPTY, true});
                    }
                }
            }
            else if (board[sq].type == KING) {
                for (int dr = -1; dr <= 1; dr++) {
                    for (int df = -1; df <= 1; df++) {
                        if (dr == 0 && df == 0) continue;
                        int nr = r + dr, nf = f + df;
                        if (in_bounds(nr, nf)) {
                            int nsq = nr * 8 + nf;
                            if (board[nsq].type == EMPTY) moves.push_back({sq, nsq, EMPTY, false});
                            else if (board[nsq].color == them) moves.push_back({sq, nsq, EMPTY, true});
                        }
                    }
                }
            }
            else { // Sliding pieces: BISHOP, ROOK, QUEEN
                int dr[8], df[8], count = 0;
                if (board[sq].type == BISHOP || board[sq].type == QUEEN) {
                    int br[] = {1, 1, -1, -1}, bf[] = {1, -1, 1, -1};
                    for (int i=0; i<4; i++) { dr[count] = br[i]; df[count] = bf[i]; count++; }
                }
                if (board[sq].type == ROOK || board[sq].type == QUEEN) {
                    int rr[] = {1, -1, 0, 0}, rf[] = {0, 0, 1, -1};
                    for (int i=0; i<4; i++) { dr[count] = rr[i]; df[count] = rf[i]; count++; }
                }
                for (int i = 0; i < count; i++) {
                    int nr = r, nf = f;
                    while (true) {
                        nr += dr[i]; nf += df[i];
                        if (!in_bounds(nr, nf)) break;
                        int nsq = nr * 8 + nf;
                        if (board[nsq].type == EMPTY) {
                            moves.push_back({sq, nsq, EMPTY, false});
                        } else {
                            if (board[nsq].color == them) moves.push_back({sq, nsq, EMPTY, true});
                            break;
                        }
                    }
                }
            }
        }
    }

    void generate_legal_moves(vector<Move>& legal) {
        vector<Move> pseudo;
        generate_pseudo_moves(pseudo);
        for (const auto& m : pseudo) {
            SimpleBoard temp = *this;
            temp.push_move(m);
            if (!temp.is_in_check(turn)) { // If our turn just changed, check if 'us' before push is in check
                legal.push_back(m);
            }
        }
    }

    void push_move(const Move& m) {
        board[m.to_sq] = board[m.from_sq];
        if (m.promotion != EMPTY) board[m.to_sq].type = m.promotion;
        board[m.from_sq] = Piece();
        turn = (turn == WHITE) ? BLACK : WHITE;
    }

    bool is_checkmate() {
        if (!is_in_check(turn)) return false;
        vector<Move> legal;
        generate_legal_moves(legal);
        return legal.empty();
    }

    bool is_stalemate() {
        if (is_in_check(turn)) return false;
        vector<Move> legal;
        generate_legal_moves(legal);
        return legal.empty();
    }

    bool gives_check(const Move& m) {
        SimpleBoard temp = *this;
        temp.push_move(m);
        return temp.is_in_check(temp.turn);
    }

    string square_to_str(int sq) const {
        char f = 'a' + (sq % 8);
        char r = '1' + (sq / 8);
        return string(1, f) + string(1, r);
    }

    string move_to_san(const Move& m) {
        if (board[m.from_sq].type == KING && abs(m.from_sq % 8 - m.to_sq % 8) == 2) {
            if (m.to_sq % 8 == 6) return "O-O";
            if (m.to_sq % 8 == 2) return "O-O-O";
        }
        string p_str = "";
        if (board[m.from_sq].type == KNIGHT) p_str = "N";
        else if (board[m.from_sq].type == BISHOP) p_str = "B";
        else if (board[m.from_sq].type == ROOK) p_str = "R";
        else if (board[m.from_sq].type == QUEEN) p_str = "Q";
        else if (board[m.from_sq].type == KING) p_str = "Kin";

        string res = p_str + square_to_str(m.from_sq) + (m.is_capture ? "x" : "-") + square_to_str(m.to_sq);
        if (m.promotion == QUEEN) res += "=Q";
        if (m.promotion == ROOK) res += "=R";
        if (m.promotion == BISHOP) res += "=B";
        if (m.promotion == KNIGHT) res += "=N";
        if (gives_check(m)) res += "+";
        return res;
    }

    Move parse_san(const string& san) {
        vector<Move> legal;
        generate_legal_moves(legal);
        for (const auto& m : legal) {
            string m_san = move_to_san(m);
            if (m_san == san || square_to_str(m.from_sq) + square_to_str(m.to_sq) == san) return m;
        }
        return Move();
    }
};

// Global Solver vars
long long nodes = 0;
map<string, bool> memo;
const string fen_file = "fen_list_labeled.txt";

bool is_quiet(SimpleBoard& board, const Move& m) {
    return !m.is_capture && !board.gives_check(m);
}

vector<Move> order_moves(SimpleBoard& board) {
    vector<Move> moves;
    board.generate_legal_moves(moves);
    
    vector<pair<int, Move>> scored;
    for (const auto& m : moves) {
        int score = 0;
        if (board.gives_check(m)) score += 1000;
        if (m.is_capture) score += 500;
        if (m.promotion != EMPTY) score += 800;
        scored.push_back({score, m});
    }
    sort(scored.begin(), scored.end(), [](const pair<int, Move>& a, const pair<int, Move>& b) {
        return a.first > b.first;
    });
    vector<Move> res;
    for (const auto& p : scored) res.push_back(p.second);
    return res;
}

bool is_forced_mate(SimpleBoard& board, int depth, int total_depth, string mode) {
    nodes++;
    if (board.is_checkmate()) return true;
    if (depth <= 0) return false;
    if (board.is_stalemate()) return false;

    string key = board.to_fen() + "_" + to_string(depth) + "_" + mode;
    if (memo.find(key) != memo.end()) return memo[key];

    int ply_from_start = total_depth - depth + 1;
    vector<Move> moves = order_moves(board);

    if (board.turn == WHITE) {
        for (const auto& m : moves) {
            if (mode == "quiet" && ply_from_start == 1) {
                if (!is_quiet(board, m)) continue;
            }
            SimpleBoard temp = board;
            temp.push_move(m);
            if (is_forced_mate(temp, depth - 1, total_depth, mode)) {
                memo[key] = true;
                return true;
            }
        }
        memo[key] = false;
        return false;
    } else {
        for (const auto& m : moves) {
            SimpleBoard temp = board;
            temp.push_move(m);
            if (!is_forced_mate(temp, depth - 1, total_depth, mode)) {
                memo[key] = false;
                return false;
            }
        }
        memo[key] = true;
        return true;
    }
}

Move find_first_forced_move(string fen, int depth, string mode, string focus) {
    SimpleBoard board;
    board.parse_fen(fen);
    cout << "\nΣκέφτομαι..." << endl;
    
    if (!focus.empty()) {
        Move m = board.parse_san(focus);
        if (m.from_sq == -1) {
            cout << "Λάθος μορφή κίνησης." << endl;
            return Move();
        }
        cout << "--> Εξετάζω: " << focus << endl;
        if (mode == "quiet" && board.turn == WHITE && !is_quiet(board, m)) {
            cout << "Η κίνηση δεν είναι ήσυχη, παραλείπεται." << endl;
            return Move();
        }
        SimpleBoard temp = board;
        temp.push_move(m);
        if (is_forced_mate(temp, depth - 1, depth, mode)) {
            cout << "--> Εξετάστηκε: " << focus << " [Βρέθηκε forced mate!]" << endl;
            return m;
        }
        cout << "--> Εξετάστηκε: " << focus << " [Δεν δίνει forced mate]" << endl;
        return Move();
    }

    vector<Move> moves = order_moves(board);
    for (const auto& m : moves) {
        string san = board.move_to_san(m);
        if (mode == "quiet" && board.turn == WHITE && !is_quiet(board, m)) continue;
        cout << "--> Εξετάζω: " << san << endl;
        SimpleBoard temp = board;
        temp.push_move(m);
        if (is_forced_mate(temp, depth - 1, depth, mode)) {
            cout << "--> Εξετάζω: " << san << "! [Βρέθηκε ματ!]" << endl;
            return m;
        }
    }
    return Move();
}

void save_fen(string fen, string description) {
    ofstream f(fen_file, ios::app);
    if (f.is_open()) {
        f << description << " --- " << fen << "\n";
        cout << "Το FEN αποθηκεύτηκε με περιγραφή." << endl;
    }
}

vector<string> list_fens() {
    vector<string> entries;
    ifstream f(fen_file);
    string line;
    while (getline(f, line)) {
        if (line.find(" --- ") != string::npos) entries.push_back(line);
    }
    return entries;
}

void run_solver_on_fen(string fen, int depth) {
    nodes = 0;
    memo.clear();
    SimpleBoard board;
    if (!board.parse_fen(fen)) {
        cout << "\nΤο FEN δεν είναι έγκυρο." << endl;
        return;
    }
    cout << "\nΤύπος ανάλυσης:\n[1] Force mate (όλες οι κινήσεις επιτρέπονται)\n[2] Ήσυχη πρώτη κίνηση μόνο\nΕπιλογή: ";
    string choice; cin >> choice;
    string mode = (choice == "2") ? "quiet" : "force";
    
    cout << "\nΑν θέλεις να εξεταστεί μόνο μία κίνηση (π.χ. e2-e4), γράψε την εδώ.\nΠάτησε Enter για όλες: ";
    string focus;
    cin.ignore();
    getline(cin, focus);
    
    cout << "\nΒάθος αναζήτησης: " << depth << " plies" << endl;
    auto start = chrono::high_resolution_clock::now();
    Move m = find_first_forced_move(fen, depth, mode, focus);
    auto end = chrono::high_resolution_clock::now();
    
    chrono::duration<double> elapsed = end - start;
    long long nps = elapsed.count() > 0 ? (long long)(nodes / elapsed.count()) : 0;
    
    cout << "\n=======================================================\nΑΠΟΤΕΛΕΣΜΑΤΑ\n=======================================================\n";
    if (m.from_sq != -1) {
        cout << "Πρώτη σωστή κίνηση του λευκού: " << board.move_to_san(m) << endl;
    } else {
        cout << "Δεν βρέθηκε υποχρεωτικό ματ." << endl;
    }
    cout << "Χρόνος: " << elapsed.count() << " δευτερόλεπτα" << endl;
    cout << "Θέσεις που εξετάστηκαν: " << nodes << endl;
    cout << "Ταχύτητα: " << nps << " θέσεις/δευτερόλεπτο" << endl;
    cout << "Memo entries: " << memo.size() << endl;
    cout << "=======================================================\n";
}

int main() {
    while (true) {
        cout << "\n=== Don Zouán Mate Solver v2.0 ===\n=== Force ή Ήσυχη Πρώτη Κίνηση ===\n[1] Αποθήκευση νέου FEN με περιγραφή\n[2] Προβολή/Λύση αποθηκευμένου ή νέου FEN\n[3] Έξοδος\nΕπιλογή: ";
        string choice; cin >> choice;
        if (choice == "1") {
            cout << "Δώσε νέο FEN:\n"; string fen; cin.ignore(); getline(cin, fen);
            cout << "Δώσε περιγραφή (π.χ. 'Ματ σε 2'): "; string desc; getline(cin, desc);
            SimpleBoard b;
            if (b.parse_fen(fen)) save_fen(fen, desc);
            else cout << "Το FEN δεν είναι έγκυρο. Δεν αποθηκεύτηκε." << endl;
        } else if (choice == "2") {
            vector<string> fens = list_fens();
            string fen, desc;
            if (fens.empty()) {
                cout << "Δεν υπάρχουν αποθηκευμένα FEN.\nΔώσε νέο FEN:\n"; cin.ignore(); getline(cin, fen);
                cout << "Δώσε περιγραφή (π.χ. 'Ματ σε 2'): "; getline(cin, desc);
                SimpleBoard b;
                if (b.parse_fen(fen)) save_fen(fen, desc);
                else { cout << "Μη έγκυρο FEN." << endl; continue; }
            } else {
                cout << "Διαθέσιμες θέσεις:\n";
                for (size_t i = 0; i < fens.size(); i++) {
                    size_t pos = fens[i].find(" --- ");
                    cout << i + 1 << ". " << fens[i].substr(0, pos) << endl;
                }
                cout << "0. Δώσε νέο FEN\nΔιάλεξε αριθμό FEN: ";
                int idx; cin >> idx;
                if (idx == 0) {
                    cout << "Δώσε νέο FEN:\n"; cin.ignore(); getline(cin, fen);
                    cout << "Δώσε περιγραφή (π.χ. 'Ματ σε 2'): "; getline(cin, desc);
                    SimpleBoard b;
                    if (b.parse_fen(fen)) save_fen(fen, desc);
                    else { cout << "Μη έγκυρο FEN." << endl; continue; }
                } else if (idx >= 1 && idx <= (int)fens.size()) {
                    size_t pos = fens[idx - 1].find(" --- ");
                    desc = fens[idx - 1].substr(0, pos);
                    fen = fens[idx - 1].substr(pos + 5);
                } else { cout << "Μη έγκυρη επιλογή." << endl; continue; }
            }
            cout << "(" << desc << ") Ματ σε πόσες πλήρεις κινήσεις; ";
            int moves; cin >> moves;
            if (moves <= 0) { cout << "Το πλήθος κινήσεων πρέπει να είναι θετικό." << endl; continue; }
            run_solver_on_fen(fen, moves * 2);
        } else if (choice == "3") {
            cout << "Έγινε έξοδος." << endl; break;
        } else { cout << "Μη έγκυρη επιλογή." << endl; }
    }
    return 0;
}
