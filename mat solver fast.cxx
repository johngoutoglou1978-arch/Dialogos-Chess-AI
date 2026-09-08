#include <iostream>
#include <string>
#include <vector>
#include <sstream>
#include <fstream>
#include <algorithm>
#include <unordered_map>
#include <chrono>
#include <cctype>
#include <random>

using namespace std;

// ============================================================
// ΔΟΜΕΣ ΚΑΙ ΣΤΑΘΕΡΕΣ ΣΚΑΚΙΟΥ
// ============================================================
enum Piece { EMPTY = 0, P = 1, N = 2, B = 3, R = 4, Q = 5, K = 6 };
enum Color { WHITE_S = 0, BLACK_S = 1 };

struct Move {
    int from;
    int to;
    int promotion;
    Move() : from(-1), to(-1), promotion(0) {}
    Move(int f, int t, int p = 0) : from(f), to(t), promotion(p) {}
    bool operator==(const Move& o) const { return from == o.from && to == o.to && promotion == o.promotion; }
};

// ============================================================
// ZOBRIST HASHING GLOBAL TABLES
// ============================================================
uint64_t zobrist_pieces[2][7][64]; // [Color][Piece][Square]
uint64_t zobrist_turn;

void init_zobrist() {
    mt19937_64 rng(123456789ULL); // Σταθερό seed
    for(int c=0; c<2; c++) {
        for(int p=1; p<=6; p++) {
            for(int sq=0; sq<64; sq++) {
                zobrist_pieces[c][p][sq] = rng();
            }
        }
    }
    zobrist_turn = rng();
}

// ============================================================
// Η ΣΚΑΚΙΕΡΑ (LIGHTWEIGHT ENGINE)
// ============================================================
struct Board {
    int pieces[64];
    int colors[64];
    int turn;
    uint64_t hash_key;

    Board() { clear(); }

    void clear() {
        for(int i=0; i<64; i++) { pieces[i] = EMPTY; colors[i] = WHITE_S; }
        turn = WHITE_S;
        hash_key = 0;
    }

    void compute_hash() {
        hash_key = 0;
        for(int sq=0; sq<64; sq++) {
            if(pieces[sq] != EMPTY) {
                hash_key ^= zobrist_pieces[colors[sq]][pieces[sq]][sq];
            }
        }
        if(turn == BLACK_S) hash_key ^= zobrist_turn;
    }

    void load_fen(const string& fen) {
        clear();
        int rank = 7, file = 0;
        size_t i = 0;
        for (; i < fen.length(); i++) {
            char c = fen[i];
            if (c == ' ') break;
            if (c == '/') { rank--; file = 0; }
            else if (isdigit(c)) { file += (c - '0'); }
            else {
                int color = isupper(c) ? WHITE_S : BLACK_S;
                char uc = toupper(c);
                int piece = EMPTY;
                if (uc == 'P') piece = P;
                else if (uc == 'N') piece = N;
                else if (uc == 'B') piece = B;
                else if (uc == 'R') piece = R;
                else if (uc == 'Q') piece = Q;
                else if (uc == 'K') piece = K;
                int sq = rank * 8 + file;
                pieces[sq] = piece;
                colors[sq] = color;
                file++;
            }
        }
        while(i < fen.length() && fen[i] == ' ') i++;
        if (i < fen.length()) {
            turn = (fen[i] == 'w') ? WHITE_S : BLACK_S;
        }
        compute_hash();
    }

    string to_fen() const {
        string f = "";
        for(int r=7; r>=0; r--) {
            int empty = 0;
            for(int file=0; file<8; file++) {
                int sq = r * 8 + file;
                if(pieces[sq] == EMPTY) empty++;
                else {
                    if(empty > 0) { f += to_string(empty); empty = 0; }
                    char p = ' ';
                    if(pieces[sq] == P) p = 'p';
                    else if(pieces[sq] == N) p = 'n';
                    else if(pieces[sq] == B) p = 'b';
                    else if(pieces[sq] == R) p = 'r';
                    else if(pieces[sq] == Q) p = 'q';
                    else if(pieces[sq] == K) p = 'k';
                    if(colors[sq] == WHITE_S) p = toupper(p);
                    f += p;
                }
            }
            if(empty > 0) f += to_string(empty);
            if(r > 0) f += "/";
        }
        f += (turn == WHITE_S) ? " w" : " b";
        return f;
    }

    bool is_square_attacked(int target_sq, int attacker_color) const {
        for(int sq=0; sq<64; sq++) {
            if(pieces[sq] != EMPTY && colors[sq] == attacker_color) {
                int p = pieces[sq];
                int f_r = sq / 8, f_f = sq % 8;
                int t_r = target_sq / 8, t_f = target_sq % 8;
                int dr = t_r - f_r, df = t_f - f_f;

                if(p == P) {
                    if(attacker_color == WHITE_S) {
                        if(dr == 1 && abs(df) == 1) return true;
                    } else {
                        if(dr == -1 && abs(df) == 1) return true;
                    }
                }
                else if(p == N) {
                    if((abs(dr)==2 && abs(df)==1) || (abs(dr)==1 && abs(df)==2)) return true;
                }
                else if(p == K) {
                    if(abs(dr)<=1 && abs(df)<=1) return true;
                }
                else if(p == B || p == Q || p == R) {
                    bool diagonal = (abs(dr) == abs(df));
                    bool straight = (dr == 0 || df == 0);
                    if((p == B && !diagonal) || (p == R && !straight) || (p == Q && !diagonal && !straight)) continue;
                    int step_r = (dr == 0) ? 0 : (dr > 0 ? 1 : -1);
                    int step_f = (df == 0) ? 0 : (df > 0 ? 1 : -1);
                    int curr_r = f_r + step_r, curr_f = f_f + step_f;
                    bool blocked = false;
                    while(curr_r != t_r || curr_f != t_f) {
                        if(pieces[curr_r * 8 + curr_f] != EMPTY) { blocked = true; break; }
                        curr_r += step_r; curr_f += step_f;
                    }
                    if(!blocked) return true;
                }
            }
        }
        return false;
    }

    bool in_check(int color) const {
        int king_sq = -1;
        for(int i=0; i<64; i++) {
            if(pieces[i] == K && colors[i] == color) { king_sq = i; break; }
        }
        if(king_sq == -1) return false;
        return is_square_attacked(king_sq, 1 - color);
    }

    void pseudo_moves(vector<Move>& list) const {
        int us = turn, enemy = 1 - turn;
        for(int sq=0; sq<64; sq++) {
            if(pieces[sq] == EMPTY || colors[sq] != us) continue;
            int p = pieces[sq];
            int r = sq / 8, f = sq % 8;

            if(p == P) {
                int dir = (us == WHITE_S) ? 1 : -1;
                int next = sq + dir * 8;
                if(next >=0 && next < 64 && pieces[next] == EMPTY) {
                    if((us == WHITE_S && next / 8 == 7) || (us == BLACK_S && next / 8 == 0)) {
                        list.push_back(Move(sq, next, Q));
                    } else {
                        list.push_back(Move(sq, next));
                        if((us == WHITE_S && r == 1) || (us == BLACK_S && r == 6)) {
                            int double_next = sq + dir * 16;
                            if(pieces[double_next] == EMPTY) list.push_back(Move(sq, double_next));
                        }
                    }
                }
                int attacks[2] = {sq + dir * 8 - 1, sq + dir * 8 + 1};
                for(int atk : attacks) {
                    if(atk >= 0 && atk < 64 && abs(atk % 8 - f) == 1) {
                        if(pieces[atk] != EMPTY && colors[atk] == enemy) {
                            if((us == WHITE_S && atk / 8 == 7) || (us == BLACK_S && atk / 8 == 0)) {
                                list.push_back(Move(sq, atk, Q));
                            } else {
                                list.push_back(Move(sq, atk));
                            }
                        }
                    }
                }
            }
            else if(p == N) {
                int dr[] = {-2, -2, -1, -1, 1, 1, 2, 2};
                int df[] = {-1, 1, -2, 2, -2, 2, -1, 1};
                for(int i=0; i<8; i++) {
                    int tr = r + dr[i], tf = f + df[i];
                    if(tr>=0 && tr<8 && tf>=0 && tf<8) {
                        int tsq = tr * 8 + tf;
                        if(pieces[tsq] == EMPTY || colors[tsq] == enemy) list.push_back(Move(sq, tsq));
                    }
                }
            }
            else if(p == K) {
                int dr[] = {-1, -1, -1, 0, 0, 1, 1, 1};
                int df[] = {-1, 0, 1, -1, 1, -1, 0, 1};
                for(int i=0; i<8; i++) {
                    int tr = r + dr[i], tf = f + df[i];
                    if(tr>=0 && tr<8 && tf>=0 && tf<8) {
                        int tsq = tr * 8 + tf;
                        if(pieces[tsq] == EMPTY || colors[tsq] == enemy) list.push_back(Move(sq, tsq));
                    }
                }
            }
            else if(p == B || p == R || p == Q) {
                int dr[8], df[8], dirs = 0;
                if(p == B || p == Q) { dr[dirs]=-1; df[dirs]=-1; dirs++; dr[dirs]=-1; df[dirs]=1; dirs++; dr[dirs]=1; df[dirs]=-1; dirs++; dr[dirs]=1; df[dirs]=1; dirs++; }
                if(p == R || p == Q) { dr[dirs]=-1; df[dirs]=0; dirs++; dr[dirs]=1; df[dirs]=0; dirs++; dr[dirs]=0; df[dirs]=-1; dirs++; dr[dirs]=0; df[dirs]=1; dirs++; }
                for(int d=0; d<dirs; d++) {
                    int tr = r + dr[d], tf = f + df[d];
                    while(tr>=0 && tr<8 && tf>=0 && tf<8) {
                        int tsq = tr * 8 + tf;
                        if(pieces[tsq] == EMPTY) { list.push_back(Move(sq, tsq)); }
                        else {
                            if(colors[tsq] == enemy) list.push_back(Move(sq, tsq));
                            break;
                        }
                        tr += dr[d]; tf += df[d];
                    }
                }
            }
        }
    }

    void push(const Move& m) {
        int f = m.from, t = m.to;
        
        // Αφαίρεση παλιών hashes
        hash_key ^= zobrist_pieces[colors[f]][pieces[f]][f];
        if(pieces[t] != EMPTY) hash_key ^= zobrist_pieces[colors[t]][pieces[t]][t];

        // Εκτέλεση κίνησης
        pieces[t] = pieces[f];
        colors[t] = colors[f];
        if(m.promotion) pieces[t] = m.promotion;
        pieces[f] = EMPTY;

        // Προσθήκη νέου hash κομματιού
        hash_key ^= zobrist_pieces[colors[t]][pieces[t]][t];

        // Αλλαγή σειράς και hash σειράς
        turn = 1 - turn;
        hash_key ^= zobrist_turn;
    }

    void pop(const Move& m, int prev_target_piece, int prev_target_color) {
        int f = m.from, t = m.to;

        // Αφαίρεση τωρινών hashes
        hash_key ^= zobrist_pieces[colors[t]][pieces[t]][t];

        // Επαναφορά σειράς
        turn = 1 - turn;
        hash_key ^= zobrist_turn;

        // Επαναφορά κίνησης
        pieces[f] = pieces[t];
        colors[f] = turn;
        if(m.promotion) pieces[f] = P;
        
        pieces[t] = prev_target_piece;
        colors[t] = prev_target_color;

        // Επαναφορά hashes
        hash_key ^= zobrist_pieces[colors[f]][pieces[f]][f];
        if(pieces[t] != EMPTY) hash_key ^= zobrist_pieces[colors[t]][pieces[t]][t];
    }

    bool is_capture(const Move& m) const { return pieces[m.to] != EMPTY; }

    bool gives_check(const Move& m) {
        int pt = pieces[m.to], ct = colors[m.to];
        push(m);
        bool res = in_check(turn);
        pop(m, pt, ct);
        return res;
    }

    string move_to_san(const Move& m) {
        string s = "";
        if(pieces[m.from] == N) s += "N";
        else if(pieces[m.from] == B) s += "B";
        else if(pieces[m.from] == R) s += "R";
        else if(pieces[m.from] == Q) s += "Q";
        else if(pieces[m.from] == K) s += "K";
        s += (char)('a' + m.from % 8) + to_string(m.from / 8 + 1);
        s += (pieces[m.to] != EMPTY) ? "x" : "-";
        s += (char)('a' + m.to % 8) + to_string(m.to / 8 + 1);
        if(m.promotion == Q) s += "=Q";
        return s;
    }
};

// ============================================================
// GLOBAL ΜΕΤΑΒΛΗΤΕΣ & CACHE
// ============================================================
long long nodes = 0;

// Δημιουργία κλειδιού για το Transposition Table με bitwise λειτουργία 
struct HashKey {
    uint64_t board_hash;
    int depth;
    bool is_quiet_mode;

    bool operator==(const HashKey& o) const {
        return board_hash == o.board_hash && depth == o.depth && is_quiet_mode == o.is_quiet_mode;
    }
};

struct KeyHasher {
    size_t operator()(const HashKey& k) const {
        return k.board_hash ^ (k.depth << 5) ^ (k.is_quiet_mode ? 0xFF : 0x00);
    }
};

unordered_map<HashKey, bool, KeyHasher> memo;
const string fen_file = "fen_list_labeled.txt";

// ============================================================
// MOVE ORDERING
// ============================================================
vector<Move> order_moves(Board& board) {
    vector<Move> raw;
    board.pseudo_moves(raw);
    vector<Move> legal;

    vector<pair<int, Move>> scored;
    for(auto& m : raw) {
        int pt = board.pieces[m.to], ct = board.colors[m.to];
        board.push(m);
        if(board.in_check(1 - board.turn)) {
            board.pop(m, pt, ct);
            continue; // Παράνομη κίνηση
        }
        board.pop(m, pt, ct);

        int score = 0;
        if(board.gives_check(m)) score += 1000;
        if(board.is_capture(m)) score += 500;
        if(m.promotion) score += 800;
        scored.push_back({score, m});
    }

    sort(scored.begin(), scored.end(), [](const pair<int, Move>& a, const pair<int, Move>& b){
        return a.first > b.first;
    });

    for(auto& p : scored) legal.push_back(p.second);
    return legal;
}

bool is_quiet(Board& board, const Move& m) {
    return !board.is_capture(m) && !board.gives_check(m);
}

// ============================================================
// RECURSIVE FORCED MATE SEARCH
// ============================================================
bool is_forced_mate(Board& board, int depth, int total_depth, bool quiet_mode) {
    nodes++;

    vector<Move> moves = order_moves(board);

    // Έλεγχος Ματ / Πατ
    if(moves.empty()) {
        if(board.in_check(board.turn)) return true; // Ο προηγούμενος έκανε Ματ
        return false; // Πατ
    }

    if(depth <= 0) return false;

    // Ζητάμε το Cache ακαριαία με το Zobrist Hash
    HashKey key = { board.hash_key, depth, quiet_mode };
    if(memo.find(key) != memo.end()) return memo[key];

    int ply_from_start = total_depth - depth + 1;

    if(board.turn == WHITE_S) {
        for(auto& m : moves) {
            if(quiet_mode && ply_from_start == 1) {
                if(!is_quiet(board, m)) continue;
            }
            int pt = board.pieces[m.to], ct = board.colors[m.to];
            board.push(m);
            bool result = is_forced_mate(board, depth - 1, total_depth, quiet_mode);
            board.pop(m, pt, ct);

            if(result) {
                memo[key] = true;
                return true;
            }
        }
        memo[key] = false;
        return false;
    } else {
        for(auto& m : moves) {
            int pt = board.pieces[m.to], ct = board.colors[m.to];
            board.push(m);
            bool result = is_forced_mate(board, depth - 1, total_depth, quiet_mode);
            board.pop(m, pt, ct);

            if(!result) {
                memo[key] = false;
                return false; // Το μαύρο βρήκε άμυνα
            }
        }
        memo[key] = true;
        return true; // Όλες οι απαντήσεις του μαύρου καταλήγουν σε ματ
    }
}

// ============================================================
// ΕΥΡΕΣΗ ΠΡΩΤΗΣ ΚΙΝΗΣΗΣ
// ============================================================
Move find_first_forced_move(const string& fen, int depth, bool quiet_mode, string focus) {
    Board board;
    board.load_fen(fen);
    cout << "\nΣκέφτομαι (Zobrist Engine)..." << endl;

    vector<Move> moves = order_moves(board);

    for(auto& m : moves) {
        string san = board.move_to_san(m);
        if(!focus.empty() && san != focus) continue;

        if(quiet_mode && board.turn == WHITE_S) {
            if(!is_quiet(board, m)) continue;
        }

        cout << "--> Εξετάζω: " << san << "..." << endl;

        int pt = board.pieces[m.to], ct = board.colors[m.to];
        board.push(m);
        bool result = is_forced_mate(board, depth - 1, depth, quiet_mode);
        board.pop(m, pt, ct);

        if(result) {
            cout << "--> Εξετάστηκε: " << san << "! [Βρέθηκε ματ!]" << endl;
            return m;
        }
    }
    return Move(-1, -1);
}

// ============================================================
// ΔΙΑΧΕΙΡΙΣΗ ΑΡΧΕΙΩΝ FEN
// ============================================================
void save_fen(const string& fen, const string& desc) {
    ofstream f(fen_file, ios::app);
    if(f.is_open()) {
        f << desc << " --- " << fen << "\n";
        cout << "Το FEN αποθηκεύτηκε.\n";
    }
}

vector<string> list_fens() {
    vector<string> list;
    ifstream f(fen_file);
    string line;
    while(getline(f, line)) {
        if(line.find(" --- ") != string::npos) list.push_back(line);
    }
    return list;
}

pair<string, string> select_fen_or_new() {
    vector<string> fens = list_fens();
    if(fens.empty()) {
        cout << "Δεν υπάρχουν αποθηκευμένα FEN.\nΔώσε νέο FEN:\n";
        string fen, desc;
        cin.ignore();
        getline(cin, fen);
        cout << "Δώσε περιγραφή: ";
        getline(cin, desc);
        save_fen(fen, desc);
        return {fen, desc};
    }
    cout << "Διαθέσιμες θέσεις:\n";
    for(size_t i=0; i<fens.size(); i++) {
        size_t idx = fens[i].find(" --- ");
        cout << i+1 << ". " << fens[i].substr(0, idx) << "\n";
    }
    cout << "0. Δώσε νέο FEN\nΕπιλογή: ";
    int choice;
    cin >> choice;
    if(choice == 0) {
        string fen, desc;
        cin.ignore();
        cout << "Δώσε νέο FEN:\n";
        getline(cin, fen);
        cout << "Δώσε περιγραφή: ";
        getline(cin, desc);
        save_fen(fen, desc);
        return {fen, desc};
    } else if (choice >= 1 && choice <= (int)fens.size()) {
        size_t idx = fens[choice-1].find(" --- ");
        return {fens[choice-1].substr(idx + 5), fens[choice-1].substr(0, idx)};
    }
    return {"", ""};
}

// ============================================================
// MAIN LOOP
// ============================================================
int main() {
    init_zobrist();
    while(true) {
        cout << "\n=== Don Zouán Mate Solver v3.0 (Zobrist Speed) ===\n";
        cout << " Αποθήκευση νέου FEN με περιγραφή\n";
        cout << " Προβολή/Λύση αποθηκευμένου ή νέου FEN\n";
        cout << " Έξοδος\nΕπιλογή: ";
        string choice;
        cin >> choice;

        if(choice == "1") {
            string fen, desc;
            cin.ignore();
            cout << "Δώσε FEN:\n"; getline(cin, fen);
            cout << "Δώσε περιγραφή: "; getline(cin, desc);
            save_fen(fen, desc);
        }
        else if(choice == "2") {
            auto p = select_fen_or_new();
            if(p.first.empty()) continue;
            cout << "(" << p.second << ") Ματ σε πόσες πλήρεις κινήσεις; ";
            int moves;
            cin >> moves;
            int depth = moves * 2;

            cout << "\n Force mate\n Ήσυχη πρώτη κίνηση μόνο\nΕπιλογή: ";
            string mode_c; cin >> mode_c;
            bool quiet = (mode_c == "2");

            cout << "\nΕστίαση σε μία κίνηση (π.χ. e2-e4) ή Enter για όλες: ";
            string focus; cin.ignore(); getline(cin, focus);

            nodes = 0;
            memo.clear();

            auto start = chrono::high_resolution_clock::now();
            Move best = find_first_forced_move(p.first, depth, quiet, focus);
            auto end = chrono::high_resolution_clock::now();

            chrono::duration<double> elapsed = end - start;
            long long nps = elapsed.count() > 0 ? (long long)(nodes / elapsed.count()) : 0;

            cout << "\n" << string(55, '=') << "\nΑΠΟΤΕΛΕΣΜΑΤΑ\n" << string(55, '=') << "\n";
            if(best.from != -1) {
                Board b; b.load_fen(p.first);
                cout << "Πρώτη σωστή κίνηση: " << b.move_to_san(best) << "\n";
            } else {
                cout << "Δεν βρέθηκε υποχρεωτικό ματ.\n";
            }
            cout << "Χρόνος: " << elapsed.count() << " δευτερόλεπτα\n";
            cout << "Θέσεις που εξετάστηκαν: " << nodes << "\n";
            cout << "Ταχύτητα (NPS): " << nps << " θέσεις/δευτερόλεπτο\n";
            cout << "Memo entries: " << memo.size() << "\n" << string(55, '=') << "\n";
        }
        else if(choice == "3") {
            cout << "Έγινε έξοδος.\n";
            break;
        }
    }
    return 0;
}
