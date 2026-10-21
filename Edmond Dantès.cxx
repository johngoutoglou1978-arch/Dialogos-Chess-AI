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
// Νέο, ελαφρύ entry αποκλειστικά για την ταχύτητα του Gameplay
struct MainTTEntry {
    uint64_t hash;       // Για να είμαστε σίγουροι ότι δεν έχουμε collision
    int depth;          // Το βάθος της ανάλυσης
    int score;          // Το σκορ της θέσης
    int flag;           // 0 = EXACT, 1 = ALPHA (Upper Bound), 2 = BETA (Lower Bound)
    chess::Move best_move; // Η καλύτερη κίνηση που βρέθηκε σε αυτή τη θέση
    bool valid;         // Αν η θέση είναι έγκυρη
};

// Καθορισμός μεγέθους του πίνακα (1.048.576 στοιχεία)
const int TT_SIZE = 1 << 20; 
MainTTEntry main_tt_table[TT_SIZE];

// Συνάρτηση για να καθαρίζουμε το TT πριν από κάθε νέα αναζήτηση
void clear_main_tt() {
    for (int i = 0; i < TT_SIZE; i++) {
        main_tt_table[i].valid = false;
        main_tt_table[i].hash = 0;
    }
}

// Μέγιστες διαστάσεις για τον πίνακα LMR (καλύπτει βάθος έως 64 και 64 κινήσεις)
int LMR_TABLE[64][64];

// Συνάρτηση που υπολογίζει τον πίνακα ΜΙΑ φορά κατά την εκκίνηση της engine
void init_lmr_table() {
    for (int depth = 0; depth < 64; depth++) {
        for (int moves = 0; moves < 64; moves++) {
            if (depth == 0 || moves == 0) {
                LMR_TABLE[depth][moves] = 0;
            } else {
                // Κλασικός, δοκιμασμένος μαθηματικός τύπος για LMR (τύπου Stockfish/Ethereal)
                double r = 0.5 + log(depth) * log(moves) / 2.25;
                LMR_TABLE[depth][moves] = (int)r;
            }
        }
    }
}

std::atomic<bool> ai_interrupt_flag(false);
std::chrono::time_point<std::chrono::steady_clock> start_time;
int MAX_SEARCH_TIME_MS = 0;
#include <exception>

// Ορισμός της εξαίρεσης για τη διακοπή της αναζήτησης λόγω χρόνου
class SearchInterruptException : public std::exception {
public:
    const char* what() const noexcept override {
        return "Search interrupted by time limit.";
    }
};

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

const int pawn_pst[64] = {
     0,   0,   0,   0,   0,   0,   0,   0,
     3,   3,  10,  19,  16,  19,   7,  -5,
    -9, -15,  11,  15,  32,  22,   5, -22,
    -4, -23,   6,  20,  40,  17,   4,  -8,
    13,   0, -13,   1,  11,  -2, -13,   5,
     5, -12,  -7,  22,  -8,  -5, -15,  -8,
    -7,   7,  -3, -13,   5, -16,  10,  -8,
     0,   0,   0,   0,   0,   0,   0,   0
};

const int knight_pst[64] = {
  -201,  -83,  -56,  -26,  -26,  -56,  -83, -201,
   -67,  -27,    4,   37,   37,    4,  -27,  -67,
    -9,   22,   58,   53,   53,   58,   22,   -9,
   -34,   13,   44,   51,   51,   44,   13,  -34,
   -35,    8,   40,   49,   49,   40,    8,  -35,
   -61,  -17,    6,   12,   12,    6,  -17,  -61,
   -77,  -41,  -27,  -15,  -15,  -27,  -41,  -77,
  -175,  -92,  -74,  -73,  -73,  -74,  -92, -175
};

const int bishop_pst[64] = {
   -48,    1,  -14,  -23,  -23,  -14,    1,  -48,
   -17,  -14,    5,    0,    0,    5,  -14,  -17,
   -16,    6,    1,   11,   11,    1,    6,  -16,
   -12,   29,   22,   31,   31,   22,   29,  -12,
    -5,   11,   25,   39,   39,   25,   11,   -5,
    -7,   21,   -5,   17,   17,   -5,   21,   -7,
   -15,    8,   19,    4,    4,   19,    8,  -15,
   -53,   -5,   -8,  -23,  -23,   -8,   -5,  -53
};

const int rook_pst[64] = {
   -17,  -19,   -1,    9,    9,   -1,  -19,  -17,
    -2,   12,   16,   18,   18,   16,   12,   -2,
   -22,   -2,    6,   12,   12,    6,   -2,  -22,
   -27,  -15,   -4,    3,    3,   -4,  -15,  -27,
   -13,   -5,   -4,   -6,   -6,   -4,   -5,  -13,
   -25,  -11,   -1,    3,    3,   -1,  -11,  -25,
   -21,  -13,   -8,    6,    6,   -8,  -13,  -21,
   -31,  -20,  -14,   -5,   -5,  -14,  -20,  -31
};

const int queen_pst[64] = {
    -2,   -2,    1,   -2,   -2,    1,   -2,   -2,
    -5,    6,   10,    8,    8,   10,    6,   -5,
    -4,   10,    6,    8,    8,    6,   10,   -4,
     0,   14,   12,    5,    5,   12,   14,    0,
     4,    5,    9,    8,    8,    9,    5,    4,
    -3,    6,   13,    7,    7,   13,    6,   -3,
    -3,    5,    8,   12,   12,    8,    5,   -3,
     3,   -5,   -5,    4,    4,   -5,   -5,    3
};

const int king_middle_pst[64] = {
    59,   89,   45,   -1,   -1,   45,   89,   59,
    88,  120,   65,   33,   33,   65,  120,   88,
   123,  145,   81,   31,   31,   81,  145,  123,
   154,  179,  105,   70,   70,  105,  179,  154,
   164,  190,  138,   98,   98,  138,  190,  164,
   195,  258,  169,  120,  120,  169,  258,  195,
   278,  303,  234,  179,  179,  234,  303,  278,
   271,  327,  271,  198,  198,  271,  327,  271
};
const int pawn_endgame_pst[64] = {
     0,   0,   0,   0,   0,   0,   0,   0,
   -10,  -10,  -10,    0,    4,    3,  -10,  -19,
   -10,  -10,  -10,    4,    4,    3,   -6,   -4,
     6,   -2,   -8,   -4,  -13,  -12,  -10,   -9,
    10,    5,    4,   -5,   -5,   -5,   14,    9,
    28,   20,   21,   28,   30,    7,    6,   13,
     0,  -11,   12,   21,   25,   19,    4,    7,
     0,   0,   0,   0,   0,   0,   0,   0
};

const int knight_endgame_pst[64] = {
  -100,  -88,  -56,  -17,  -17,  -56,  -88, -100,
   -69,  -50,  -51,   12,   12,  -51,  -50,  -69,
   -51,  -44,  -16,   17,   17,  -16,  -44,  -51,
   -45,  -16,    9,   39,   39,    9,  -16,  -45,
   -35,   -2,   13,   28,   28,   13,   -2,  -35,
   -40,  -27,   -8,   29,   29,   -8,  -27,  -40,
   -67,  -54,  -18,    8,    8,  -18,  -54,  -67,
   -96,  -65,  -49,  -21,  -21,  -49,  -65,  -96
};

const int bishop_endgame_pst[64] = {
   -46,  -42,  -37,  -24,  -24,  -37,  -42,  -46,
   -31,  -20,   -1,    1,    1,   -1,  -20,  -31,
   -30,    6,    4,    6,    6,    4,    6,  -30,
   -17,   -1,  -14,   15,   15,  -14,   -1,  -17,
   -20,   -6,    0,   17,   17,    0,   -6,  -20,
   -16,   -1,   -2,   10,   10,   -2,   -1,  -16,
   -37,  -13,  -17,    1,    1,  -17,  -13,  -37,
   -57,  -30,  -37,  -12,  -12,  -37,  -30,  -57
};

const int rook_endgame_pst[64] = {
    18,    0,   19,   13,   13,   19,    0,   18,
     4,    5,   20,   -5,   -5,   20,    5,    4,
     6,    1,   -7,   10,   10,   -7,    1,    6,
    -5,    8,    7,   -6,   -6,    7,    8,   -5,
    -6,    1,   -9,    7,    7,   -9,    1,   -6,
     6,   -8,   -2,   -6,   -6,   -2,   -8,    6,
   -12,   -9,   -1,   -2,   -2,   -1,   -9,  -12,
    -9,  -13,  -10,   -9,   -9,  -10,  -13,   -9
};

const int queen_endgame_pst[64] = {
   -75,  -52,  -43,  -36,  -36,  -43,  -52,  -75,
   -50,  -27,  -24,   -8,   -8,  -24,  -27,  -50,
   -38,  -18,  -12,    1,    1,  -12,  -18,  -38,
   -29,   -6,    9,   21,   21,    9,   -6,  -29,
   -23,   -3,   13,   24,   24,   13,   -3,  -23,
   -39,  -18,   -9,    3,    3,   -9,  -18,  -39,
   -55,  -31,  -22,   -4,   -4,  -22,  -31,  -55,
   -69,  -57,  -47,  -26,  -26,  -47,  -57,  -69
};

const int king_endgame_pst[64] = {
    11,   59,   73,   78,   78,   73,   59,   11,
    47,  121,  116,  131,  131,  116,  121,   47,
    92,  172,  184,  191,  191,  184,  172,   92,
    96,  166,  199,  199,  199,  199,  166,   96,
   103,  156,  172,  172,  172,  172,  156,  103,
    88,  130,  169,  175,  175,  169,  130,   88,
    53,  100,  133,  135,  135,  133,  100,   53,
     1,   45,   85,   76,   76,   85,   45,    1
};


// --- KING SAFETY TABLE (Stockfish / Glaurung style) ---
static const int SafetyTable[100] = {
   0,   0,   0,   1,   1,   2,   3,   4,   5,   6,
   8,  10,  13,  16,  20,  25,  30,  36,  42,  48,
  55,  62,  70,  80,  90, 100, 110, 120, 130, 140,
 150, 160, 170, 180, 190, 200, 210, 220, 230, 240,
 250, 260, 270, 280, 290, 300, 310, 320, 330, 340,
 350, 360, 370, 380, 390, 400, 410, 420, 430, 440,
 450, 460, 470, 480, 490, 500, 510, 520, 530, 540,
 550, 560, 570, 580, 590, 600, 610, 620, 630, 640,
 650, 650, 650, 650, 650, 650, 650, 650, 650, 650,
 650, 650, 650, 650, 650, 650, 650, 650, 650, 650
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
// Κρατάμε έως 2 killer κινήσεις ανά βάθος (ply) χρησιμοποιώντας το raw 16-bit integer της κίνησης
uint16_t KILLERS[64][2] = {{0}};

// Πίνακας Ιστορικού: 64 τετράγωνα εκκίνησης x 64 τετράγωνα προορισμού
int HISTORY[64][64] = {{0}};



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
// Βοηθητική συνάρτηση που ελέγχει αν η θέση είναι αυτόματη ισοπαλία λόγω υλικού
bool is_insufficient_material(const Board& board) {
    // Αν υπάρχει έστω και ένα πιόνι, πύργος ή βασίλισσα, το ματ είναι εφικτό
    if (board.pieces(chess::PieceType::PAWN).count() > 0 ||
        board.pieces(chess::PieceType::ROOK).count() > 0 ||
        board.pieces(chess::PieceType::QUEEN).count() > 0) {
        return false;
    }

    int w_knights = board.pieces(chess::PieceType::KNIGHT, chess::Color::WHITE).count();
    int b_knights = board.pieces(chess::PieceType::KNIGHT, chess::Color::BLACK).count();
    int w_bishops = board.pieces(chess::PieceType::BISHOP, chess::Color::WHITE).count();
    int b_bishops = board.pieces(chess::PieceType::BISHOP, chess::Color::BLACK).count();

    int total_minors = w_knights + b_knights + w_bishops + b_bishops;

    // 1. Βασιλιάς εναντίον Βασιλιά (K vs K)
    if (total_minors == 0) return true;

    // 2. Ένας μόνο Αξιωματικός ή ένας μόνο Ίππος στη σκακιέρα (KB vs K ή KN vs K)
    if (total_minors == 1) return true;

    // 3. Ένας Αξιωματικός για τον καθένα (KB vs KB)
    if (total_minors == 2 && w_bishops == 1 && b_bishops == 1) {
        // Έλεγχος αν οι αξιωματικοί βρίσκονται σε ίδιου χρώματος τετράγωνα
        constexpr uint64_t dark_squares_mask = 0xAA55AA55AA55AA55ULL;
        chess::Bitboard dark_squares(dark_squares_mask);

        chess::Bitboard white_bishop_bb = board.pieces(chess::PieceType::BISHOP, chess::Color::WHITE);
        chess::Bitboard black_bishop_bb = board.pieces(chess::PieceType::BISHOP, chess::Color::BLACK);

        bool white_bishop_is_dark = (white_bishop_bb & dark_squares) ? true : false;
        bool black_bishop_is_dark = (black_bishop_bb & dark_squares) ? true : false;

        // Αν είναι και οι δύο σε μαύρα ή και οι δύο σε λευκά τετράγωνα -> Ισοπαλία!
        if (white_bishop_is_dark == black_bishop_is_dark) {
            return true;
        }
    }

    return false;
}
int evaluate_board(const chess::Board& board, chess::Color must_win_color = chess::Color::NONE) {
    // =========================================================================
    // ΠΡΩΤΟΣ ΕΛΕΓΧΟΣ: ΑΥΤΟΜΑΤΗ ΙΣΟΠΑΛΙΑ ΛΟΓΩ ΥΛΙΚΟΥ
    // =========================================================================
    if (is_insufficient_material(board)) {
        // ΑΝ ΠΡΕΠΕΙ ΝΑ ΚΕΡΔΙΣΟΥΜΕ, Η ΙΣΟΠΑΛΙΑ ΕΙΝΑΙ ΗΤΤΑ!
        // Τιμωρούμε την ισοπαλία με βάση το ποιος καίγεται για νίκη
        if (must_win_color == chess::Color::WHITE) return -9999; // Καταστροφή για το Λευκό
        if (must_win_color == chess::Color::BLACK) return 9999;  // Καταστροφή για το Μαύρο
        return 0; // Κανονική ισοπαλία
    }

    // =========================================================================
    // ⚡ ΝΕΟ: TAPERED EVALUATION (ΣΤΑΔΙΑΚΗ ΑΞΙΟΛΟΓΗΣΗ - ΠΡΟΤΥΠΑ 2026)
    // =========================================================================
    int mg_score = 0; // Σκορ για το Middlegame
    int eg_score = 0; // Σκορ για το Endgame
    
    int white_pawns_in_file[8] = {0}; // 💥 Διορθώθηκε με το μέγεθος [8]
    int black_pawns_in_file[8] = {0}; // 💥 Διορθώθηκε με το μέγεθος [8]
    
    // 1. ΥΠΟΛΟΓΙΣΜΟΣ ΦΑΣΗΣ ΠΑΙΧΝΙΔΙΟΥ (GAME PHASE)
    int phase = 0;
    phase += board.pieces(chess::PieceType::KNIGHT, chess::Color::WHITE).count() * 1;
    phase += board.pieces(chess::PieceType::KNIGHT, chess::Color::BLACK).count() * 1;
    phase += board.pieces(chess::PieceType::BISHOP, chess::Color::WHITE).count() * 1;
    phase += board.pieces(chess::PieceType::BISHOP, chess::Color::BLACK).count() * 1;
    phase += board.pieces(chess::PieceType::ROOK,   chess::Color::WHITE).count() * 2;
    phase += board.pieces(chess::PieceType::ROOK,   chess::Color::BLACK).count() * 2;
    phase += board.pieces(chess::PieceType::QUEEN,  chess::Color::WHITE).count() * 4;
    phase += board.pieces(chess::PieceType::QUEEN,  chess::Color::BLACK).count() * 4;
    if (phase > 24) phase = 24; // Ασφάλεια για την περίπτωση προαγωγών

    // 2. ΥΛΙΚΗ ΑΞΙΑ ΚΑΙ ΠΙΝΑΚΕΣ ΘΕΣΗΣ (PST) ΜΕ TAPERED ΜΙΞΗ
    for (int sq = 0; sq < 64; ++sq) {
        chess::Piece p = board.at(chess::Square(sq));
        if (p == chess::Piece::NONE) continue;
        
        int p_val = 0;
        const int* mg_pst = nullptr;
        const int* eg_pst = nullptr;
        
        if (p.type() == chess::PieceType::PAWN) {
            if (p.color() == chess::Color::WHITE) white_pawns_in_file[sq % 8]++;
            else black_pawns_in_file[sq % 8]++;
        }
        
        if (p.type() == chess::PieceType::PAWN)         { p_val = 100;   mg_pst = pawn_pst;        eg_pst = pawn_endgame_pst; }
        else if (p.type() == chess::PieceType::KNIGHT)  { p_val = 320;   mg_pst = knight_pst;      eg_pst = knight_endgame_pst; }
        else if (p.type() == chess::PieceType::BISHOP)  { p_val = 330;   mg_pst = bishop_pst;      eg_pst = bishop_endgame_pst; }
        else if (p.type() == chess::PieceType::ROOK)    { p_val = 500;   mg_pst = rook_pst;        eg_pst = rook_endgame_pst; }
        else if (p.type() == chess::PieceType::QUEEN)   { p_val = 900;   mg_pst = queen_pst;       eg_pst = queen_endgame_pst; }
        else if (p.type() == chess::PieceType::KING)    { p_val = 20000; mg_pst = king_middle_pst;  eg_pst = king_endgame_pst; }
        
        int sq_idx = (p.color() == chess::Color::WHITE) ? sq : (sq ^ 56);
        
        // Υπολογισμός Middlegame και Endgame σκορ
        int mg_piece_total = p_val + ((mg_pst != nullptr) ? mg_pst[sq_idx] : 0);
        int eg_piece_total = p_val + ((eg_pst != nullptr) ? eg_pst[sq_idx] : 0);
        
        if (p.color() == chess::Color::WHITE) {
            mg_score += mg_piece_total;
            eg_score += eg_piece_total;
        } else {
            mg_score -= mg_piece_total;
            eg_score -= eg_piece_total;
        }
    }

    // 3. ΓΡΑΜΜΙΚΗ ΜΙΞΗ (TAPERED EVALUATION SCORE)
    int score = ((mg_score * phase) + (eg_score * (24 - phase))) / 24;

    // 4. ΟΡΙΣΜΟΣ ΤΗΣ IS_ENDGAME ΓΙΑ ΤΑ ΕΠΟΜΕΝΑ IF ΤΟΥ ΚΩΔΙΚΑ ΣΑΣ
    bool is_endgame = (phase <= 6);

    // =========================================================================
    // ΑΠΟ ΕΔΩ ΚΑΙ ΚΑΤΩ ΣΥΝΕΧΙΖΕΙ Ο ΥΠΟΛΟΙΠΟΣ ΚΩΔΙΚΑΣ ΣΑΣ ΩΣ ΕΧΕΙ
    // (2. Ποινές για Διπλωμένα Πιόνια, Κινητικότητα, King Safety κλπ.)
    // =========================================================================


    // 2. Ποινές για Διπλωμένα Πιόνια
    for (int file = 0; file < 8; ++file) {
        if (white_pawns_in_file[file] > 1) score -= (white_pawns_in_file[file] - 1) * 30;
        if (black_pawns_in_file[file] > 1) score += (black_pawns_in_file[file] - 1) * 30;
    }    

    // 3. Κινητικότητα Κομματιών (Mobility)
    int white_mobility = 0, black_mobility = 0;
    chess::Bitboard white_filter = ~board.us(chess::Color::WHITE);
    chess::Bitboard black_filter = ~board.us(chess::Color::BLACK);
    chess::Bitboard occ = board.occ();

    // --- ΛΕΥΚΑ ΚΟΜΜΑΤΙΑ ---
    chess::Bitboard w_knights_bb = board.pieces(chess::PieceType::KNIGHT, chess::Color::WHITE);
    while (w_knights_bb) {
        chess::Bitboard att = chess::attacks::knight(w_knights_bb.pop());
        white_mobility += (att & white_filter).count();
    }
    chess::Bitboard w_bishops_bb = board.pieces(chess::PieceType::BISHOP, chess::Color::WHITE);
    while (w_bishops_bb) {
        chess::Bitboard att = chess::attacks::bishop(w_bishops_bb.pop(), occ);
        white_mobility += (att & white_filter).count();
    }
    chess::Bitboard w_rooks_bb = board.pieces(chess::PieceType::ROOK, chess::Color::WHITE);
    while (w_rooks_bb) {
        chess::Bitboard att = chess::attacks::rook(w_rooks_bb.pop(), occ);
        white_mobility += (att & white_filter).count();
    }
    chess::Bitboard w_queens_bb = board.pieces(chess::PieceType::QUEEN, chess::Color::WHITE);
    while (w_queens_bb) {
        chess::Bitboard att = chess::attacks::queen(w_queens_bb.pop(), occ);
        white_mobility += (att & white_filter).count();
    }

    // --- ΜΑΥΡΑ ΚΟΜΜΑΤΙΑ ---
    chess::Bitboard b_knights_bb = board.pieces(chess::PieceType::KNIGHT, chess::Color::BLACK);
    while (b_knights_bb) {
        chess::Bitboard att = chess::attacks::knight(b_knights_bb.pop());
        black_mobility += (att & black_filter).count();
    }
    chess::Bitboard b_bishops_bb = board.pieces(chess::PieceType::BISHOP, chess::Color::BLACK);
    while (b_bishops_bb) {
        chess::Bitboard att = chess::attacks::bishop(b_bishops_bb.pop(), occ);
        black_mobility += (att & black_filter).count();
    }
    chess::Bitboard b_rooks_bb = board.pieces(chess::PieceType::ROOK, chess::Color::BLACK);
    while (b_rooks_bb) {
        chess::Bitboard att = chess::attacks::rook(b_rooks_bb.pop(), occ);
        black_mobility += (att & black_filter).count();
    }
    chess::Bitboard b_queens_bb = board.pieces(chess::PieceType::QUEEN, chess::Color::BLACK);
    while (b_queens_bb) {
        chess::Bitboard att = chess::attacks::queen(b_queens_bb.pop(), occ);
        black_mobility += (att & black_filter).count();
    }

    const int MOBILITY_WEIGHT = 2;
    score += (white_mobility - black_mobility) * MOBILITY_WEIGHT;
    // =========================================================================
    // 4. KING SAFETY MECHANISM (STOCKFISH / GLAURUNG)
    // =========================================================================
    if (!is_endgame) { 
        // --- 4α. Ζώνη Λευκού Βασιλιά ---
        Square w_king_sq = board.kingSq(Color::WHITE);
        chess::Bitboard w_king_zone = chess::attacks::king(w_king_sq);
        int w_rank = w_king_sq.rank();
        int w_file = w_king_sq.file();
        if (w_rank < 7) {
            w_king_zone.set((w_rank + 1) * 8 + w_file);
            if (w_file > 0) w_king_zone.set((w_rank + 1) * 8 + (w_file - 1));
            if (w_file < 7) w_king_zone.set((w_rank + 1) * 8 + (w_file + 1));
        }

        // --- 4β. Ζώνη Μαύρου Βασιλιά ---
        Square b_king_sq = board.kingSq(Color::BLACK);
        chess::Bitboard b_king_zone = chess::attacks::king(b_king_sq);
        int b_rank = b_king_sq.rank();
        int b_file = b_king_sq.file();
        if (b_rank > 0) {
            b_king_zone.set((b_rank - 1) * 8 + b_file);
            if (b_file > 0) b_king_zone.set((b_rank - 1) * 8 + (b_file - 1));
            if (b_file < 7) b_king_zone.set((b_rank - 1) * 8 + (b_file + 1));
        }

        // --- 4γ. Καταμέτρηση Μονάδων Επίθεσης στα Λευκά (Από Μαύρα Κομμάτια) ---
        int white_king_attack_units = 0;
        int black_attacking_pieces = 0;

        chess::Bitboard b_k = board.pieces(chess::PieceType::KNIGHT, chess::Color::BLACK);
        while (b_k) { if (chess::attacks::knight(b_k.pop()) & w_king_zone) { white_king_attack_units += 2; black_attacking_pieces++; } }
        chess::Bitboard b_b = board.pieces(chess::PieceType::BISHOP, chess::Color::BLACK);
        while (b_b) { if (chess::attacks::bishop(b_b.pop(), occ) & w_king_zone) { white_king_attack_units += 2; black_attacking_pieces++; } }
        chess::Bitboard b_r = board.pieces(chess::PieceType::ROOK, chess::Color::BLACK);
        while (b_r) { if (chess::attacks::rook(b_r.pop(), occ) & w_king_zone) { white_king_attack_units += 3; black_attacking_pieces++; } }
        chess::Bitboard b_q = board.pieces(chess::PieceType::QUEEN, chess::Color::BLACK);
        while (b_q) { if (chess::attacks::queen(b_q.pop(), occ) & w_king_zone) { white_king_attack_units += 5; black_attacking_pieces++; } }

        if (black_attacking_pieces >= 2) {
            if (white_king_attack_units >= 100) white_king_attack_units = 99;
            int safety_penalty = SafetyTable[white_king_attack_units];
            
            // [MUST WIN] Αν το Μαύρο πρέπει να κερδίσει, ενισχύουμε την επιθετικότητά του κατά 40%
            if (must_win_color == chess::Color::BLACK) {
                safety_penalty = (safety_penalty * 140) / 100;
            }
            score -= safety_penalty;
        }
        // [MUST WIN] Ακόμα και με 1 κομμάτι, δίνουμε ένα μικρό κίνητρο στο Μαύρο να πιέσει τον Λευκό Βασιλιά
        else if (black_attacking_pieces == 1 && must_win_color == chess::Color::BLACK) {
            score -= white_king_attack_units * 8;
        }

        // --- 4δ. Καταμέτρηση Μονάδων Επίθεσης στα Μαύρα (Από Λευκά Κομμάτια) ---
        int black_king_attack_units = 0;
        int white_attacking_pieces = 0;

        chess::Bitboard w_k = board.pieces(chess::PieceType::KNIGHT, chess::Color::WHITE);
        while (w_k) { if (chess::attacks::knight(w_k.pop()) & b_king_zone) { black_king_attack_units += 2; white_attacking_pieces++; } }
        chess::Bitboard w_b = board.pieces(chess::PieceType::BISHOP, chess::Color::WHITE);
        while (w_b) { if (chess::attacks::bishop(w_b.pop(), occ) & b_king_zone) { black_king_attack_units += 2; white_attacking_pieces++; } }
        chess::Bitboard w_r = board.pieces(chess::PieceType::ROOK, chess::Color::WHITE);
        while (w_r) { if (chess::attacks::rook(w_r.pop(), occ) & b_king_zone) { black_king_attack_units += 3; white_attacking_pieces++; } }
        chess::Bitboard w_q = board.pieces(chess::PieceType::QUEEN, chess::Color::WHITE);
        while (w_q) { if (chess::attacks::queen(w_q.pop(), occ) & b_king_zone) { black_king_attack_units += 5; white_attacking_pieces++; } }

        if (white_attacking_pieces >= 2) {
            if (black_king_attack_units >= 100) black_king_attack_units = 99;
            int safety_bonus = SafetyTable[black_king_attack_units];
            
            // [MUST WIN] Αν το Λευκό πρέπει να κερδίσει, ενισχύουμε την επιθετικότητά του κατά 40%
            if (must_win_color == chess::Color::WHITE) {
                safety_bonus = (safety_bonus * 140) / 100;
            }
            score += safety_bonus;
        }
        // [MUST WIN] Ακόμα και με 1 κομμάτι, δίνουμε ένα μικρό κίνητρο στο Λευκό να πιέσει τον Μαύρο Βασιλιά
        else if (white_attacking_pieces == 1 && must_win_color == chess::Color::WHITE) {
            score += black_king_attack_units * 8;
        }
    }

    // =========================================================================
    // 5. ΔΥΝΑΜΙΚΗ ΠΟΛΥΠΛΟΚΟΤΗΤΑ & ΑΠΟΦΥΓΗ ΑΛΛΑΓΗΣ ΚΟΜΜΑΤΙΩΝ (MUST WIN MODE)
    // =========================================================================
    if (must_win_color != chess::Color::NONE) {
        int game_phase = calculate_game_phase(board); 

        // Εφαρμόζουμε τη στρατηγική μόνο αν δεν είμαστε ήδη σε βαθύ endgame (π.χ. phase > 6)
        if (game_phase > 6) {
            
            // 1. Καταμέτρηση των κομματιών για κάθε χρώμα
            int w_queens = board.pieces(chess::PieceType::QUEEN, chess::Color::WHITE).count();
            int b_queens = board.pieces(chess::PieceType::QUEEN, chess::Color::BLACK).count();
            
            int w_rooks  = board.pieces(chess::PieceType::ROOK,  chess::Color::WHITE).count();
            int b_rooks  = board.pieces(chess::PieceType::ROOK,  chess::Color::BLACK).count();
            
            int w_bishops = board.pieces(chess::PieceType::BISHOP, chess::Color::WHITE).count();
            int b_bishops = board.pieces(chess::PieceType::BISHOP, chess::Color::BLACK).count();
            
            int w_knights = board.pieces(chess::PieceType::KNIGHT, chess::Color::WHITE).count();
            int b_knights = board.pieces(chess::PieceType::KNIGHT, chess::Color::BLACK).count();

            // 2. Υπολογισμός Bonus περιπλοκότητας ανάλογα με το ποιος πρέπει να κερδίσει
            if (must_win_color == chess::Color::WHITE) {
                // ⚡ Επιβράβευση για κάθε δικό μας κομμάτι που ΠΑΡΑΜΕΝΕΙ ζωντανό (Αποφυγή ανταλλαγών)
                score += w_queens  * 20; // Υψηλό bonus για τη Βασίλισσα
                score += w_rooks   * 10; // Μεσαίο bonus για τους Πύργους
                score += w_bishops * 8; // Μικρό bonus για Αξιωματικούς
                score += w_knights * 8; // Μικρό bonus για Ίππους

                // ⚡ Επιπλέον Bonus πολυπλοκότητας: Όσο περισσότερα κομμάτια (και των δύο) 
                // υπάρχουν συνολικά, τόσο πιο πολύπλοκη παραμένει η σκακιέρα.
                int total_minor_major_pieces = (w_queens + b_queens + w_rooks + b_rooks + w_bishops + b_bishops + w_knights + b_knights);
                score += total_minor_major_pieces * 5; 
            } 
            else if (must_win_color == chess::Color::BLACK) {
                // ⚡ Αντίστοιχα για το Μαύρο (αφαιρούμε από το score του Λευκού)
                score -= b_queens  * 20;
                score -= b_rooks   * 10;
                score -= b_bishops * 8;
                score -= b_knights * 8;

                int total_minor_major_pieces = (w_queens + b_queens + w_rooks + b_rooks + w_bishops + b_bishops + w_knights + b_knights);
                score -= total_minor_major_pieces * 5;
            }
        }
    }


    // =========================================================================
    // ΓΝΩΣΗ ΦΙΝΑΛΕ: ΠΑΣΕ ΠΙΟΝΙΑ & ΚΑΤΑΔΙΩΞΗ ΑΝΤΙΠΑΛΟΥ ΒΑΣΙΛΙΑ
    // =========================================================================
    if (is_endgame) { 
        
        Square w_king = board.kingSq(chess::Color::WHITE);
        Square b_king = board.kingSq(chess::Color::BLACK);
        
        int w_kf = static_cast<int>(w_king.file());
        int w_kr = static_cast<int>(w_king.rank());
        int b_kf = static_cast<int>(b_king.file());
        int b_kr = static_cast<int>(b_king.rank());

        // --- 1. ΚΑΤΑΔΙΩΞΗ ΑΝΤΙΠΑΛΟΥ ΒΑΣΙΛΙΑ (MOP-UP COOPERATION) ---
        // Υπολογισμός απόστασης (Manhattan) μεταξύ των δύο Βασιλιάδων
        int king_distance = std::abs(w_kf - b_kf) + std::abs(w_kr - b_kr);
        
        // Αν το Λευκό έχει υλική υπεροχή, στριμώχνει τον Μαύρο Βασιλιά στις άκρες
        if (score > 150) {
            score += (14 - king_distance) * 10; 
            int b_king_push_to_edge = std::max(std::abs(b_kf - 3), std::abs(b_kr - 3));
            score += b_king_push_to_edge * 15;
        }
        // Αν το Μαύρο έχει υλική υπεροχή, στριμώχνει τον Λευκό Βασιλιά στις άκρες
        else if (score < -150) {
            score -= (14 - king_distance) * 10;
            int w_king_push_to_edge = std::max(std::abs(w_kf - 3), std::abs(w_kr - 3));
            score -= w_king_push_to_edge * 15;
        }

        // --- 2. ΑΝΙΧΝΕΥΣΗ ΠΑΣΕ ΠΙΟΝΙΩΝ & KING ESCORT ---
        chess::Bitboard w_pawns = board.pieces(chess::PieceType::PAWN, chess::Color::WHITE);
        chess::Bitboard b_pawns = board.pieces(chess::PieceType::PAWN, chess::Color::BLACK);

        // Έλεγχος για Λευκά Πασέ Πιόνια
        chess::Bitboard w_pawns_temp = w_pawns;
        while (w_pawns_temp) {
            Square p_sq = w_pawns_temp.pop();
            int file = static_cast<int>(p_sq.file());
            int rank = static_cast<int>(p_sq.rank());
            
            chess::Bitboard mask = chess::Bitboard(0x0101010101010101ULL << file);
            if (file > 0) mask |= chess::Bitboard(0x0101010101010101ULL << (file - 1));
            if (file < 7) mask |= chess::Bitboard(0x0101010101010101ULL << (file + 1));
            chess::Bitboard front_mask = chess::Bitboard(0xFFFFFFFFFFFFFFFFULL << ((rank + 1) * 8));
            
            if (!(mask & front_mask & b_pawns)) { // Αν είναι Πασέ!
                int pawn_bonus = (rank * rank) * 6; // Εκθετικό μπόνους ανάλογα με τη γραμμή
                
                // King Escort: Αν ο Λευκός Βασιλιάς στέκεται δίπλα στο πασέ του πιόνι
                int dist_to_king = std::max(std::abs(w_kf - file), std::abs(w_kr - rank));
                if (dist_to_king <= 1) {
                    pawn_bonus += 50; 
                }
                
                score += pawn_bonus;
            }
        }

        // Έλεγχος για Μαύρα Πασέ Πιόνια
        chess::Bitboard b_pawns_temp = b_pawns;
        while (b_pawns_temp) {
            Square p_sq = b_pawns_temp.pop();
            int file = static_cast<int>(p_sq.file());
            int rank = static_cast<int>(p_sq.rank());
            
            chess::Bitboard mask = chess::Bitboard(0x0101010101010101ULL << file);
            if (file > 0) mask |= chess::Bitboard(0x0101010101010101ULL << (file - 1));
            if (file < 7) mask |= chess::Bitboard(0x0101010101010101ULL << (file + 1));
            chess::Bitboard front_mask = chess::Bitboard(0xFFFFFFFFFFFFFFFFULL >> ((8 - rank) * 8));
            
            if (!(mask & front_mask & w_pawns)) { // Αν είναι Πασέ!
                int inv_rank = 7 - rank;
                int pawn_bonus = (inv_rank * inv_rank) * 6;
                
                // King Escort: Αν ο Μαύρος Βασιλιάς στέκεται δίπλα στο πασέ του πιόνι
                int dist_to_king = std::max(std::abs(b_kf - file), std::abs(b_kr - rank));
                if (dist_to_king <= 1) {
                    pawn_bonus += 50;
                }
                
                score -= pawn_bonus;
            }
        }
    }

// =========================================================================
// ΣΤΡΑΤΗΓΙΚΗ ΓΝΩΣΗ: ΚΥΡΙΑΡΧΙΑ ΠΥΡΓΩΝ ΣΤΗΝ 7η / 2η ΓΡΑΜΜΗ (ROOKS ON 7th/2nd RANK)
// =========================================================================
int w_rooks_on_7th = 0;
int b_rooks_on_2nd = 0;

for (int sq_idx = 0; sq_idx < 64; ++sq_idx) {
    chess::Square current_sq = chess::Square(sq_idx);
    chess::Piece piece = board.at(current_sq);
    
    if (piece != chess::Piece::NONE) {
        int rank = static_cast<int>(current_sq.rank());
        
        // ⚪ ΛΕΥΚΑ ΚΟΜΜΑΤΙΑ (Ψάχνουν την 7η γραμμή -> Rank Index 6)
        if (piece.color() == chess::Color::WHITE) {
            if (rank == 6) { // 7η γραμμή
                if (piece.type() == chess::PieceType::ROOK) {
                    w_rooks_on_7th++;
                    score += 40; // Μπόνους για τον Πύργο στην 7η γραμμή!
                } else if (piece.type() == chess::PieceType::QUEEN) {
                    score += 20; // Μικρότερο μπόνους για τη Βασίλισσα
                }
            }
        }
        // ⚫ ΜΑΥΡΑ ΚΟΜΜΑΤΙΑ (Ψάχνουν τη 2η γραμμή -> Rank Index 1)
        else if (piece.color() == chess::Color::BLACK) {
            if (rank == 1) { // 2η γραμμή
                if (piece.type() == chess::PieceType::ROOK) {
                    b_rooks_on_2nd++;
                    score -= 40; // Μπόνους για τα Μαύρα
                } else if (piece.type() == chess::PieceType::QUEEN) {
                    score -= 20;
                }
            }
        }
    }
}

// Έξτρα μπόνους αν οι Πύργοι είναι ΔΙΠΛΩΜΕΝΟΙ (Connected Rooks) στην 7η/2η γραμμή!
if (w_rooks_on_7th >= 2) score += 35; // Τρομερή δύναμη για το Λευκό
if (b_rooks_on_2nd >= 2) score -= 35; // Τρομερή δύναμη για το Μαύρο

// =========================================================================
// 6. ΓΝΩΣΗ ΓΙΑ ΜΑΤ ΜΕ ΑΞΙΩΜΑΤΙΚΟ ΚΑΙ ΙΠΠΟ (ΣΩΣΤΗ ΓΩΝΙΑ)
// =========================================================================
if (occ.count() <= 4) {
    Square w_king_sq = board.kingSq(chess::Color::WHITE);
    Square b_king_sq = board.kingSq(chess::Color::BLACK);
    
    // Λάμδα συνάρτηση για τον υπολογισμό της σκακιστικής απόστασης (Chebyshev / King Distance)
    auto square_distance = [](Square s1, Square s2) {
        return std::max(std::abs(static_cast<int>(s1.file()) - static_cast<int>(s2.file())),
                        std::abs(static_cast<int>(s1.rank()) - static_cast<int>(s2.rank())));
    };

    // Ορισμός των 4 γωνιών με βάση τη βιβλιοθήκη σου
    // Συνήθως: a1=0, h1=7, a8=56, h8=63
    Square corner_a1(0), corner_h1(7), corner_a8(56), corner_h8(63);

    // --- ΕΛΕΓΧΟΣ ΓΙΑ ΤΑ ΛΕΥΚΑ (Αξιωματικός + Ίππος εναντίον Βασιλιά) ---
    chess::Bitboard w_bishops_bb = board.pieces(chess::PieceType::BISHOP, chess::Color::WHITE);
    bool b_has_queen = board.pieces(chess::PieceType::QUEEN, chess::Color::BLACK).count() > 0;
    bool b_has_rook  = board.pieces(chess::PieceType::ROOK, chess::Color::BLACK).count() > 0;

    if (w_bishops_bb && !b_has_queen && !b_has_rook) {
        chess::Bitboard w_b_copy = w_bishops_bb;
        Square first_bishop = w_b_copy.pop();
        
        // Έλεγχος αν ο Αξιωματικός είναι σε λευκό τετράγωνο (όπως στην Python: (file + rank) % 2 != 0)
        bool is_light_squared = ((static_cast<int>(first_bishop.file()) + static_cast<int>(first_bishop.rank())) % 2 != 0);
        
        int dist_to_corner = 999;
        if (is_light_squared) {
            dist_to_corner = std::min(square_distance(b_king_sq, corner_h1), square_distance(b_king_sq, corner_a8));
        } else {
            dist_to_corner = std::min(square_distance(b_king_sq, corner_a1), square_distance(b_king_sq, corner_h8));
        }
        
        score += (7 - dist_to_corner) * 45;
        score += (7 - square_distance(w_king_sq, b_king_sq)) * 20;
    }

    // --- ΕΛΕΓΧΟΣ ΓΙΑ ΤΑ ΜΑΥΡΑ (Αξιωματικός + Ίππος εναντίον Βασιλιά) ---
    chess::Bitboard b_bishops_bb = board.pieces(chess::PieceType::BISHOP, chess::Color::BLACK);
    bool w_has_queen = board.pieces(chess::PieceType::QUEEN, chess::Color::WHITE).count() > 0;
    bool w_has_rook  = board.pieces(chess::PieceType::ROOK, chess::Color::WHITE).count() > 0;

    if (b_bishops_bb && !w_has_queen && !w_has_rook) {
        chess::Bitboard b_b_copy = b_bishops_bb;
        Square first_bishop = b_b_copy.pop();
        
        bool is_light_squared = ((static_cast<int>(first_bishop.file()) + static_cast<int>(first_bishop.rank())) % 2 != 0);
        
        int dist_to_corner = 999;
        if (is_light_squared) {
            dist_to_corner = std::min(square_distance(w_king_sq, corner_h1), square_distance(w_king_sq, corner_a8));
        } else {
            dist_to_corner = std::min(square_distance(w_king_sq, corner_a1), square_distance(w_king_sq, corner_h8));
        }
        
        score -= (7 - dist_to_corner) * 45;
        score -= (7 - square_distance(b_king_sq, w_king_sq)) * 20;
    }
}
// =========================================================================
// [ΠΡΩΤΟΣ ΠΑΓΚΟΣΜΙΑ] ΔΟΣΗ 1: ΑΣΦΥΞΙΑ ΤΟΥ ΒΑΣΙΛΙΑ (SUFFOCATION ENGINE)
// =========================================================================
if (!is_endgame) {
    chess::Bitboard occ = board.occ();
    chess::Square w_king = board.kingSq(chess::Color::WHITE);
    chess::Square b_king = board.kingSq(chess::Color::BLACK);

    // Όλα τα λευκά και μαύρα κομμάτια στη σκακιέρα
    chess::Bitboard white_pieces = board.us(chess::Color::WHITE);
    chess::Bitboard black_pieces = board.us(chess::Color::BLACK);

    // --- Ασφυξία για τον Μαύρο Βασιλιά (Επίθεση Λευκού) ---
    chess::Bitboard b_king_zone = chess::attacks::king(b_king);
    chess::Bitboard b_blocking_pieces = b_king_zone & black_pieces;
    
    while (b_blocking_pieces) {
        chess::Square sq = b_blocking_pieces.pop();
        
        // Υπολογίζουμε αν οποιοδήποτε Λευκό κομμάτι σημαδεύει αυτό το τετράγωνο (sq)
        chess::Bitboard pawn_attacks   = chess::attacks::pawn(chess::Color::BLACK, sq) & board.pieces(chess::PieceType::PAWN, chess::Color::WHITE);
        chess::Bitboard knight_attacks = chess::attacks::knight(sq) & board.pieces(chess::PieceType::KNIGHT, chess::Color::WHITE);
        chess::Bitboard bishop_attacks = chess::attacks::bishop(sq, occ) & board.pieces(chess::PieceType::BISHOP, chess::Color::WHITE);
        chess::Bitboard rook_attacks   = chess::attacks::rook(sq, occ) & board.pieces(chess::PieceType::ROOK, chess::Color::WHITE);
        chess::Bitboard queen_attacks  = chess::attacks::queen(sq, occ) & board.pieces(chess::PieceType::QUEEN, chess::Color::WHITE);

        // Αν έστω και ένα λευκό κομμάτι επιτίθεται, ο Μαύρος βασιλιάς πνίγεται!
        if (pawn_attacks || knight_attacks || bishop_attacks || rook_attacks || queen_attacks) {
            score += 15; 
        }
    }

    // --- Ασφυξία για τον Λευκό Βασιλιά (Επίθεση Μαύρου) ---
    chess::Bitboard w_king_zone = chess::attacks::king(w_king);
    chess::Bitboard w_blocking_pieces = w_king_zone & white_pieces;
    
    while (w_blocking_pieces) {
        chess::Square sq = w_blocking_pieces.pop();
        
        // Υπολογίζουμε αν οποιοδήποτε Μαύρο κομμάτι σημαδεύει αυτό το τετράγωνο (sq)
        chess::Bitboard pawn_attacks   = chess::attacks::pawn(chess::Color::WHITE, sq) & board.pieces(chess::PieceType::PAWN, chess::Color::BLACK);
        chess::Bitboard knight_attacks = chess::attacks::knight(sq) & board.pieces(chess::PieceType::KNIGHT, chess::Color::BLACK);
        chess::Bitboard bishop_attacks = chess::attacks::bishop(sq, occ) & board.pieces(chess::PieceType::BISHOP, chess::Color::BLACK);
        chess::Bitboard rook_attacks   = chess::attacks::rook(sq, occ) & board.pieces(chess::PieceType::ROOK, chess::Color::BLACK);
        chess::Bitboard queen_attacks  = chess::attacks::queen(sq, occ) & board.pieces(chess::PieceType::QUEEN, chess::Color::BLACK);

        if (pawn_attacks || knight_attacks || bishop_attacks || rook_attacks || queen_attacks) {
            score -= 15; 
        }
    }
}
// =========================================================================
// =========================================================================
// [ΠΡΩΤΟΣ ΠΑΓΚΟΣΜΙΑ] ΔΟΣΗ 2: ΤΑΚΤΙΚΟ ΧΑΟΣ (CHAOS ENGINE)
// =========================================================================
if (!is_endgame) {
    int chaos_tension_count = 0;
    chess::Bitboard occ = board.occ();

    // Σαρώνουμε τα κομμάτια στο κέντρο της σκακιέρας (Ranks 3,4,5,6 και Files B έως G)
    for (int sq = 0; sq < 64; ++sq) {
        chess::Square cell(sq);
        
        // Μετατροπή των Rank και File σε int για να μη μπερδεύεται ο compiler
        int r_idx = static_cast<int>(cell.rank());
        int f_idx = static_cast<int>(cell.file());
        
        // Φίλτρο για το κέντρο της σκακιέρας (Ranks 2-5 και Files 1-6)
        if (r_idx >= 2 && r_idx <= 5 && f_idx >= 1 && f_idx <= 6) {
            Piece p = board.at(cell);
            if (p == Piece::NONE || p.type() == PieceType::KING) continue;

            chess::Bitboard pawn_attacks, knight_attacks, bishop_attacks, rook_attacks, queen_attacks;
            bool is_under_attack = false;

            // Αν το κομμάτι είναι ΛΕΥΚΟ, ελέγχουμε αν του επιτίθενται τα ΜΑΥΡΑ
            if (p.color() == chess::Color::WHITE) {
                pawn_attacks   = chess::attacks::pawn(chess::Color::WHITE, cell) & board.pieces(chess::PieceType::PAWN, chess::Color::BLACK);
                knight_attacks = chess::attacks::knight(cell) & board.pieces(chess::PieceType::KNIGHT, chess::Color::BLACK);
                bishop_attacks = chess::attacks::bishop(cell, occ) & board.pieces(chess::PieceType::BISHOP, chess::Color::BLACK);
                rook_attacks   = chess::attacks::rook(cell, occ) & board.pieces(chess::PieceType::ROOK, chess::Color::BLACK);
                queen_attacks  = chess::attacks::queen(cell, occ) & board.pieces(chess::PieceType::QUEEN, chess::Color::BLACK);
                
                if (pawn_attacks || knight_attacks || bishop_attacks || rook_attacks || queen_attacks) {
                    is_under_attack = true;
                }
            }
            // Αν το κομμάτι είναι ΜΑΥΡΟ, ελέγχουμε αν του επιτίθενται τα ΛΕΥΚΑ
            else {
                pawn_attacks   = chess::attacks::pawn(chess::Color::BLACK, cell) & board.pieces(chess::PieceType::PAWN, chess::Color::WHITE);
                knight_attacks = chess::attacks::knight(cell) & board.pieces(chess::PieceType::KNIGHT, chess::Color::WHITE);
                bishop_attacks = chess::attacks::bishop(cell, occ) & board.pieces(chess::PieceType::BISHOP, chess::Color::WHITE);
                rook_attacks   = chess::attacks::rook(cell, occ) & board.pieces(chess::PieceType::ROOK, chess::Color::WHITE);
                queen_attacks  = chess::attacks::queen(cell, occ) & board.pieces(chess::PieceType::QUEEN, chess::Color::WHITE);
                
                if (pawn_attacks || knight_attacks || bishop_attacks || rook_attacks || queen_attacks) {
                    is_under_attack = true;
                }
            }

            if (is_under_attack) {
                chaos_tension_count++;
            }
        }
    }

    // Αν υπάρχουν 3 ή περισσότερα κομμάτια που απειλούνται ταυτόχρονα στο κέντρο, η σκακιέρα φλέγεται!
    if (chaos_tension_count >= 3) {
        if (board.sideToMove() == chess::Color::WHITE) score += 10;
        else score -= 10;
    }
}

// =========================================================================
// [ΠΡΩΤΟΣ ΠΑΓΚΟΣΜΙΑ] ΔΟΣΗ 3: ΥΠΕΡΟΧΗ ΧΩΡΟΥ (SPACE ADVANTAGE ENGINE)
// =========================================================================
if (!is_endgame) {
    int white_space_bonus = 0;
    int black_space_bonus = 0;

    chess::Bitboard w_pawns = board.pieces(chess::PieceType::PAWN, chess::Color::WHITE);
    chess::Bitboard b_pawns = board.pieces(chess::PieceType::PAWN, chess::Color::BLACK);

    // Αρχικοποίηση άδειων bitboards με τον σωστό τρόπο της βιβλιοθήκης σας
    chess::Bitboard w_pawn_attacks = chess::Bitboard(0);
    chess::Bitboard b_pawn_attacks = chess::Bitboard(0);

    // Υπολογισμός όλων των τετραγώνων που ελέγχουν τα λευκά πιόνια
    chess::Bitboard w_pawns_copy = w_pawns;
    while (w_pawns_copy) {
        chess::Square sq = w_pawns_copy.pop();
        w_pawn_attacks |= chess::attacks::pawn(chess::Color::WHITE, sq);
    }

    // Υπολογισμός όλων των τετραγώνων που ελέγχουν τα μαύρα πιόνια
    chess::Bitboard b_pawns_copy = b_pawns;
    while (b_pawns_copy) {
        chess::Square sq = b_pawns_copy.pop();
        b_pawn_attacks |= chess::attacks::pawn(chess::Color::BLACK, sq);
    }

    // Σαρώνουμε τη σκακιέρα για να βρούμε εδαφική υπεροχή
    for (int sq = 0; sq < 64; ++sq) {
        chess::Square cell(sq);
        int r_idx = static_cast<int>(cell.rank());

        // --- Υπεροχή Χώρου για τον Λευκό (Ranks 4 και 5) ---
        if (r_idx == 4 || r_idx == 5) {
            if ((chess::Bitboard::fromSquare(cell) & w_pawn_attacks) && !(chess::Bitboard::fromSquare(cell) & b_pawn_attacks)) {
                white_space_bonus += 5; 

                Piece p = board.at(cell);
                if (p != Piece::NONE && p.color() == chess::Color::WHITE && 
                   (p.type() == PieceType::KNIGHT || p.type() == PieceType::BISHOP)) {
                    white_space_bonus += 25; 
                }
            }
        }

        // --- Υπεροχή Χώρου για τον Μαύρο (Ranks 2 και 3) ---
        if (r_idx == 2 || r_idx == 3) {
            if ((chess::Bitboard::fromSquare(cell) & b_pawn_attacks) && !(chess::Bitboard::fromSquare(cell) & w_pawn_attacks)) {
                black_space_bonus += 5;

                Piece p = board.at(cell);
                if (p != Piece::NONE && p.color() == chess::Color::BLACK && 
                   (p.type() == PieceType::KNIGHT || p.type() == PieceType::BISHOP)) {
                    black_space_bonus += 25;
                }
            }
        }
    }

    // Προσθήκη του Space Advantage στο τελικό score
    score += (white_space_bonus - black_space_bonus);
}

// =========================================================================
// [ΠΕΙΡΑΜΑΤΙΚΟ - INSANE MODE] ΔΟΣΗ 4: ΤΟ ΑΚΡΑΙΟ ΜΑΓΝΗΤΙΚΟ ΠΕΔΙΟ
// =========================================================================
if (!is_endgame) {
    int white_magnet_bonus = 0;
    int black_space_magnet = 0;

    chess::Square w_king = board.kingSq(chess::Color::WHITE);
    chess::Square b_king = board.kingSq(chess::Color::BLACK);

    for (int sq = 0; sq < 64; ++sq) {
        chess::Square cell(sq);
        Piece p = board.at(cell);
        
        if (p == Piece::NONE || p.type() == PieceType::KING || p.type() == PieceType::PAWN) continue;

        int f_idx = static_cast<int>(cell.file());
        int r_idx = static_cast<int>(cell.rank());

        // --- ΑΚΡΑΙΟΙ ΠΕΙΡΑΜΑΤΙΚΟΙ ΠΟΛΛΑΠΛΑΣΙΑΣΤΕΣ ---
        int piece_multiplier = 4; // Πύργος (*10)
        if (p.type() == PieceType::QUEEN)   piece_multiplier = 5; // Βασίλισσα (*30) -> Απόλυτος Κυνηγός
        if (p.type() == PieceType::KNIGHT)  piece_multiplier = 3; // Ίππος (*20)
        if (p.type() == PieceType::BISHOP)  piece_multiplier = 3; // Αξιωματικός (*15)

        // --- Αν το κομμάτι είναι ΛΕΥΚΟ, έλκεται από τον ΜΑΥΡΟ Βασιλιά ---
        if (p.color() == chess::Color::WHITE) {
            int b_king_f = static_cast<int>(b_king.file());
            int b_king_r = static_cast<int>(b_king.rank());
            
            int distance = std::max(std::abs(f_idx - b_king_f), std::abs(r_idx - b_king_r));
            
            // Υπολογισμός του ακραίου bonus
            white_magnet_bonus += (7 - distance) * piece_multiplier; 
        }
        // --- Αν το κομμάτι είναι ΜΑΥΡΟ, έλκεται από τον ΛΕΥΚΟ Βασιλιά ---
        else {
            int w_king_f = static_cast<int>(w_king.file());
            int w_king_r = static_cast<int>(w_king.rank());
            
            int distance = std::max(std::abs(f_idx - w_king_f), std::abs(r_idx - w_king_r));
            
            black_space_magnet += (7 - distance) * piece_multiplier;
        }
    }

    // Προσθέτουμε την ακραία μαγνητική έλξη στο τελικό score
    score += (white_magnet_bonus - black_space_magnet);
}

    return (board.sideToMove() == chess::Color::WHITE) ? score : -score;
}


// ============================================================================
// --- ΟΛΟΚΛΗΡΩΜΕΝΟ & ΣΥΜΒΑΤΟ MOVE ORDERING (ΧΩΡΙΣ CONST) ---
// // Έλεγχος αν μια κίνηση είναι ήρεμη (Quiet Move) - Απαραίτητη για όλο το πρόγραμμα!
bool is_quiet(chess::Board& board, chess::Move move) {
    return !board.isCapture(move) && move.typeOf() != chess::Move::PROMOTION;
}

// Βαθμολόγηση της κίνησης σύμφωνα με τα πρότυπα (Staged Move Ordering)
int order_score(chess::Board& board, chess::Move move, int ply) {
    // 1. Προαγωγές Πιονιών (Promotions) - Ύψιστη προτεραιότητα
    if (move.typeOf() == chess::Move::PROMOTION) {
        if (move.promotionType() == chess::PieceType::QUEEN) {
            return 3000000; 
        } else {
            return 2500000;
        }
    }
    
    // 2. Αιχμαλωτίσεις (Captures) με χρήση MVV-LVA
    if (board.isCapture(move)) {
        chess::PieceType attacker = board.at(move.from()).type();
        chess::PieceType victim = board.at(move.to()).type();
        
        // Σταθερός πίνακας τιμών κομματιών
        const int vals[] = { 0, 100, 300, 300, 500, 900, 10000 };
        int attacker_val = vals[static_cast<int>(attacker)];
        int victim_val = vals[static_cast<int>(victim)];
        
        return 2000000 + (victim_val * 10) - attacker_val;
    }
    
    // Μετατρέπουμε την κίνηση στο μοναδικό της ID (αριθμητικό) και παίρνουμε τα index των τετραγώνων
    uint16_t move_raw = move.move();
    int from = move.from().index();
    int to = move.to().index();

    // 3. Killer Moves (Έλεγχος των 2 killer slots για το τρέχον ply)
    if (ply < 64) {
        if (KILLERS[ply][0] == move_raw || KILLERS[ply][1] == move_raw) {
            return 1000000;
        }
    }
    
    // 4. History Heuristic (Άμεση ανάγνωση από τον πίνακα 64x64)
    return HISTORY[from][to];
}


// Η κύρια συνάρτηση - Πλήρως συμβατή με τις 4 παραμέτρους που ζητάει η alphabeta σας!
std::vector<chess::Move> order_moves(chess::Board& board, chess::Movelist& moves, const std::string& tt_best_uci, int ply) {
    std::vector<std::pair<int, chess::Move>> scored_moves;
    scored_moves.reserve(moves.size());
    
    for (size_t i = 0; i < moves.size(); ++i) {
        // Καλούμε την order_score (το tt_best_uci αγνοείται με ασφάλεια)
        scored_moves.push_back({order_score(board, moves[i], ply), moves[i]});
    }
    
    // Ταξινόμηση από το μεγαλύτερο σκορ στο μικρότερο
    std::sort(scored_moves.begin(), scored_moves.end(), [](const std::pair<int, chess::Move>& a, const std::pair<int, chess::Move>& b) {
        return a.first > b.first;
    });
    
    std::vector<chess::Move> result;
    result.reserve(moves.size());
    for (size_t i = 0; i < scored_moves.size(); ++i) {
        result.push_back(scored_moves[i].second);
    }
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

bool was_tt_move = false; // <-- Προσθέστε αυτή τη γραμμή εδώ!

int alphabeta(int alpha, int beta, int depth, chess::Board& board, int ply, chess::Move& best_move) {
    // Κρατάμε το αρχικό άλφα για τον καθορισμό των flags του TT στο τέλος
    int alpha_orig = alpha;

    // --- 1. ΕΛΕΓΧΟΣ ΧΡΟΝΟΥ (Bitwise AND για μέγιστη ταχύτητα) ---
    NODES++;
    if ((NODES & 2047) == 0) { 
        auto current_time = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - start_time).count();
        
        if (elapsed >= MAX_SEARCH_TIME_MS) {
            ai_interrupt_flag.store(true);
        }
        if (ai_interrupt_flag.load()) throw SearchInterruptException();
    }

    // Έλεγχος επαναλήψεων και κανόνα 50 κινήσεων
    if (ply > 0 && (board.isRepetition() || board.halfMoveClock() >= 100)) {
        return 0; 
    }
    
    // Όταν φτάσουμε στο τελικό βάθος, καλούμε την αναζήτηση ηρεμίας
    if (depth <= 0) return quiescence(alpha, beta, board);

    // --- MATE DISTANCE PRUNING ---
    int mated_score = -MATE_VALUE + ply;
    int mate_score  =  MATE_VALUE - ply;
    if (alpha < mated_score) alpha = mated_score;
    if (beta > mate_score)   beta = mate_score;
    if (alpha >= beta) return alpha;

    // --- TRANSPOSITION TABLE LOOKUP ---
    uint64_t current_hash = board.hash(); 
    int tt_index = current_hash % TT_SIZE;
    chess::Move tt_move = chess::Move::NO_MOVE;

    if (main_tt_table[tt_index].valid && main_tt_table[tt_index].hash == current_hash) {
        tt_move = main_tt_table[tt_index].best_move;
        
        if (main_tt_table[tt_index].depth >= depth) {
            int tt_score = main_tt_table[tt_index].score;
            int tt_flag = main_tt_table[tt_index].flag;
            
            // Προσαρμογή των Mate Scores ανάλογα με το τρέχον ply
            if (tt_score > MATE_VALUE - 100)  tt_score -= ply;
            if (tt_score < -MATE_VALUE + 100) tt_score += ply;

            if (tt_flag == 0) { // EXACT
                if (ply == 0) {
                    best_move = tt_move;
                    was_tt_move = true; // Η κίνηση βγήκε 100% από τη μνήμη
                }
                return tt_score;
            }
            if (tt_flag == 1 && tt_score <= alpha) return alpha; // ALPHA CUTOFF
            if (tt_flag == 2 && tt_score >= beta)  return beta;  // BETA CUTOFF
        }
    }

    // --- RAZORING ---
    if (!board.inCheck() && depth <= 3) {
        int static_eval = evaluate_board(board); 
        if (static_eval < alpha - 400 * depth) {
            int q_score = quiescence(alpha, beta, board);
            if (q_score <= alpha) return q_score; 
        }
    }

    // --- NULL MOVE PRUNING ---
    bool is_endgame = (calculate_game_phase(board) <= 6); 
    if (depth >= 3 && !board.inCheck() && !is_endgame && ply > 0) {
        board.makeNullMove();
        
        chess::Move null_best_move = chess::Move::NO_MOVE;
        int R = 3 + (depth / 4); 
        int null_score = 0;
        
        try {
            null_score = -alphabeta(-beta, -beta + 1, depth - 1 - R, board, ply + 1, null_best_move);
        }
        catch (const SearchInterruptException&) {
            board.unmakeNullMove();
            throw;
        }
        board.unmakeNullMove();

        if (null_score >= beta) return beta; 
    }

    // Παραγωγή νόμιμων κινήσεων
    chess::Movelist moves;
    chess::movegen::legalmoves<chess::movegen::MoveGenType::ALL>(moves, board);
    
    // --- MOVE ORDERING ---
    int move_scores[256] = {0}; 
    for (size_t i = 0; i < moves.size(); i++) {
        chess::Move mv = moves[i];
        
        if (mv == tt_move) {
            move_scores[i] = 2000000; // Απόλυτη προτεραιότητα στην κίνηση του TT
        }
        else if (board.isCapture(mv)) {
            // MVV-LVA
            int victim = (int)board.at(mv.to()).type();
            int attacker = (int)board.at(mv.from()).type();
            move_scores[i] = 1000000 + (victim * 100) - attacker;
            
            if (attacker > victim && board.isAttacked(mv.to(), ~board.sideToMove())) {
                move_scores[i] -= 500000;
            }
        } else {
            if (mv.move() == KILLERS[ply][0])      move_scores[i] = 900000;
            else if (mv.move() == KILLERS[ply][1]) move_scores[i] = 800000;
            else                                   move_scores[i] = HISTORY[mv.from().index()][mv.to().index()];
        }
    }

    int score;
    int legal_moves_searched = 0;
    chess::Move local_best_move = chess::Move::NO_MOVE;
    int best_score = -MATE_VALUE * 2;

    // Loop αναζήτησης κινήσεων
    for (size_t i = 0; i < moves.size(); i++) {
        if (ai_interrupt_flag.load()) throw SearchInterruptException();

        // Selection Sort on-the-fly
        for (size_t j = i + 1; j < moves.size(); j++) {
            if (move_scores[j] > move_scores[i]) {
                std::swap(moves[i], moves[j]);
                std::swap(move_scores[i], move_scores[j]);
            }
        }

        chess::Move mv = moves[i];
        bool capture = board.isCapture(mv); 
        
        // --- FUTILITY PRUNING ---
        if (legal_moves_searched >= 4 && depth <= 4 && !board.inCheck() && !capture) {
            int static_eval = evaluate_board(board);
            if (static_eval + 130 * depth <= alpha) {
                continue; 
            }
        }

        board.makeMove(mv);
        legal_moves_searched++;

        int extension = (board.inCheck() && ply < 30) ? 1 : 0;
        chess::Move sub_best_move = chess::Move::NO_MOVE;

        try {
            // --- ΔΥΝΑΜΙΚΟ LMR ΜΕ ΠΙΝΑΚΑ (LMR TABLE) ---
            if (legal_moves_searched > 3 && depth >= 3 && !capture && !board.inCheck()) {
                int d_idx = (depth < 64) ? depth : 63;
                int m_idx = (legal_moves_searched < 64) ? legal_moves_searched : 63;
                
                int reduction = LMR_TABLE[d_idx][m_idx];
                
                int lmr_depth = depth - 1 - reduction + extension;
                if (lmr_depth < 1) lmr_depth = 1;
                
                // Null Window Search (PVS)
                score = -alphabeta(-alpha - 1, -alpha, lmr_depth, board, ply + 1, sub_best_move);
                
                // Επανέρευνα (Research) αν η κίνηση αποδειχθεί καλή
                if (score > alpha) {
                    score = -alphabeta(-beta, -alpha, depth - 1 + extension, board, ply + 1, sub_best_move);
                }
            } else {
                score = -alphabeta(-beta, -alpha, depth - 1 + extension, board, ply + 1, sub_best_move);
            }
        } 
        catch (const SearchInterruptException&) {
            board.unmakeMove(mv);
            throw;
        }
        board.unmakeMove(mv);

        if (score > best_score) {
            best_score = score;
            local_best_move = mv;
        }

        // --- BETA CUTOFF ---
        if (score >= beta) {
            if (ply == 0) { 
                best_move = mv; 
                was_tt_move = false; 
            }

            if (!capture && ply < 64) {
                uint16_t mv_raw = mv.move();
                if (KILLERS[ply][0] != mv_raw) {
                    KILLERS[ply][1] = KILLERS[ply][0]; 
                    KILLERS[ply][0] = mv_raw;          
                }
                int from = mv.from().index();
                int to = mv.to().index();
                HISTORY[from][to] += depth * depth; 
            }

            // Αποθήκευση BETA BOUND στο TT
            MainTTEntry entry;
            entry.hash = current_hash;
            entry.depth = depth;
            entry.score = (beta > MATE_VALUE - 100) ? beta + ply : ((beta < -MATE_VALUE + 100) ? beta - ply : beta);
            entry.best_move = mv;
            entry.flag = 2; // BETA
            entry.valid = true;
            main_tt_table[tt_index] = entry;

            return beta; 
        }
        
        // --- ALPHA UPDATE ---
        if (score > alpha) {
            alpha = score;
            if (ply == 0) {
                best_move = mv;
                was_tt_move = false;
            }
        }
    }
    
    if (legal_moves_searched == 0) {
        if (board.inCheck()) return -MATE_VALUE + ply;
        return 0;
    }
    
    // --- ΑΠΟΘΗΚΕΥΣΗ ΣΤΟ ΤΤ ΠΡΙΝ ΤΗΝ ΕΠΙΣΤΡΟΦΗ ---
    MainTTEntry entry;
    entry.hash = current_hash;
    entry.depth = depth;
    entry.valid = true;
    entry.best_move = local_best_move;
    entry.score = (best_score > MATE_VALUE - 100) ? best_score + ply : ((best_score < -MATE_VALUE + 100) ? best_score - ply : best_score);

    if (best_score <= alpha_orig) {
        entry.flag = 1; // ALPHA BOUND
    } else {
        entry.flag = 0; // EXACT
    }
    main_tt_table[tt_index] = entry;

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
// 1. Μετατρέπουμε το uci string σε αντικείμενο κίνησης της βιβλιοθήκης σας
chess::Move parsed_mv = chess::uci::uciToMove(board, best_uci);

// 2. Παίρνουμε τα indexes των τετραγώνων και το raw ID της κίνησης
int from_sq = parsed_mv.from().index();
int to_sq   = parsed_mv.to().index();
uint16_t mv_raw = parsed_mv.move();

// 3. Αποθήκευση Killer (Αριθμητικά)
if (ply < 64) {
    if (KILLERS[ply][0] != mv_raw) {
        KILLERS[ply][1] = KILLERS[ply][0];
        KILLERS[ply][0] = mv_raw;
    }
}

// 4. Αποθήκευση History Bonus (Αριθμητικά)
HISTORY[from_sq][to_sq] += 1 + depth;

                Tree tree;
                TreePtr node = make_shared<Node>();
                node->move = mv;
                node->children = result.second;
                tree.push_back(node);
                TT[key] = {depth, true, tree, best_uci, 0, 0};
                return make_pair(true, tree);
            } else {
                string best_uci = uci::moveToUci(mv);
chess::Move penalty_mv1 = chess::uci::uciToMove(board, best_uci);
HISTORY[penalty_mv1.from().index()][penalty_mv1.to().index()] -= 1;

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
chess::Move penalty_mv2 = chess::uci::uciToMove(board, best_uci);
HISTORY[penalty_mv2.from().index()][penalty_mv2.to().index()] -= 1;

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
std::memset(KILLERS, 0, sizeof(KILLERS));
std::memset(HISTORY, 0, sizeof(HISTORY));

    TT.clear();
    cout << "\033[33m>> Engine reset έγινε.\033[0m\n";
}
// --- Κύρια Ροή Διαδραστικού Παιχνιδιού (Πλήρης & Διορθωμένη για UCI κινήσεις) ---
#include <vector>

#include <iomanip> // Απαραίτητο για το setprecision

void interactive_gameplay() {
    // =========================================================================
    // ΟΡΙΣΜΟΙ ΚΑΙ ΔΟΜΕΣ ΧΡΟΝΟΥ (TOΠΟΘΕΤΗΜΕΝΑ ΜΕΣΑ ΣΤΗ ΣΥΝΑΡΤΗΣΗ ΓΙΑ ΑΣΦΑΛΕΙΑ)
    // =========================================================================
    enum GameLevelLocal {
        BLITZ_5MIN,        
        BLITZ_10MIN,       
        TOURNAMENT_30MIN,  
        CLASSIC_TOURNAMENT, 
        FIXED_TIME         
    };

    struct TimeControlLocal {
        GameLevelLocal level;
        long long ai_time_left_ms;  
        int moves_played;           
        long long fixed_time_ms;    
        bool time_control_passed;   
    };

    static TimeControlLocal ai_clock = { FIXED_TIME, 0, 0, 0, false };

    // 🎯 Ο ΝΕΟΣ ΕΠΑΓΓΕΛΜΑΤΙΚΟΣ ΤΑΚΤΙΚΟΣ TIME MANAGER (ΒΑΣΕΙ ΚΟΨΙΜΑΤΩΝ)
    auto calculate_dynamic_move_time_local = [](chess::Board& b, int score_change) -> long long {
        if (ai_clock.level == FIXED_TIME) {
            return ai_clock.fixed_time_ms;
        }

        ai_clock.moves_played++;
        long long base_time_ms = 0;

        // ΕΛΕΓΧΟΣ 40ης ΚΙΝΗΣΗΣ: Προσθήκη χρόνου (+60 λεπτά)
        // Διόρθωση: Ο έλεγχος γίνεται στην 40η κίνηση (αφού αυξήθηκε το moves_played)
        if (ai_clock.level == CLASSIC_TOURNAMENT && ai_clock.moves_played == 40 && !ai_clock.time_control_passed) {
            ai_clock.ai_time_left_ms += 60LL * 60LL * 1000LL; 
            ai_clock.time_control_passed = true;
            cout << "\n\033[1;33m[Time Control Passed] Προστέθηκαν +60 λεπτά στο ρολόι του AI!\033[0m\n";
        }

        if (ai_clock.level == CLASSIC_TOURNAMENT) {
            if (ai_clock.moves_played <= 40) {
                int moves_left_to_control = 40 - ai_clock.moves_played + 1;
                if (moves_left_to_control < 3) moves_left_to_control = 3; 
                base_time_ms = ai_clock.ai_time_left_ms / moves_left_to_control;
            } else {
                base_time_ms = ai_clock.ai_time_left_ms / 30;
            }
        } else {
            int estimated_moves_left = std::max(10, 40 - (ai_clock.moves_played / 2));
            base_time_ms = ai_clock.ai_time_left_ms / estimated_moves_left;
        }

        // ΜΕΤΡΗΣΗ ΤΑΚΤΙΚΗΣ ΕΝΤΑΣΗΣ (ΠΟΣΑ ΚΟΨΙΜΑΤΑ ΥΠΑΡΧΟΥΝ ΣΤΗ ΘΕΣΗ)
        chess::Movelist moves_eval;
        chess::movegen::legalmoves<chess::movegen::MoveGenType::ALL>(moves_eval, b);
        
        if (moves_eval.size() == 1) {
            return 600; // Easy Move Protection: Ακαριαία κίνηση αν υπάρχει μόνο 1 επιλογή!
        }

        int capture_count = 0;
        for (size_t i = 0; i < moves_eval.size(); ++i) {
            if (b.isCapture(moves_eval[i])) {
                capture_count++;
            }
        }

        // ⚡ ΔΥΝΑΜΙΚΟΣ ΠΟΛΛΑΠΛΑΣΙΑΣΜΟΣ ΒΑΣΕΙ ΚΟΨΙΜΑΤΩΝ
        if (capture_count >= 5) {
            base_time_ms = base_time_ms * 2.5;
        } 
        else if (capture_count >= 2) {
            base_time_ms = base_time_ms * 1.4;
        } 
        else {
            base_time_ms = base_time_ms * 0.75;
        }

        // Panic Time Buffer (Αν το Eval έπεσε στην προηγούμενη κίνηση)
        if (score_change < -50) {
            base_time_ms = base_time_ms * 1.5; 
        }

        // =========================================================================
        // 🚨 EMERGENCY TIME BUFFER (ΑΠΟΛΥΤΗ ΠΟΣΤΑΣΙΑ ΓΙΑ ΤΑ 2 ΔΕΥΤΕΡΟΛΕΠΤΑ)
        // =========================================================================
        // Αν ο συνολικός χρόνος που απομένει είναι κάτω από 2500ms (2.5 δευτερόλεπτα):
        if (ai_clock.ai_time_left_ms <= 2500) {
            // Αν έχουμε έστω και λίγο χρόνο, δίνουμε 200ms για να κάνει ένα ρηχό 
            // αλλά λογικό ψάξιμο (όχι τυχαία κίνηση), αλλιώς παίζει σε 50ms για τη σημαία.
            return (ai_clock.ai_time_left_ms > 400) ? 200 : 50;
        }

        // Περιορισμός μέγιστου χρόνου ανά κίνηση (όχι πάνω από το 1/4 του εναπομείναντος)
        long long absolute_max = ai_clock.ai_time_left_ms / 4; 
        if (base_time_ms > absolute_max) base_time_ms = absolute_max;

        // Διόρθωση: Μην αναγκάζεις το AI να σπαταλάει 1 full δευτερόλεπτο αν ο 
        // συνολικός χρόνος είναι ήδη οριακός (π.χ. κάτω από 4 δευτερόλεπτα).
        if (base_time_ms < 800 && ai_clock.ai_time_left_ms > 4000) {
            base_time_ms = 800;
        }

        return base_time_ms;
    };


    // =========================================================================
    // =========================================================================
    // ΜΕΡΟΣ 1: Don Zouάν Chess AI Interactive (Αρχική παραμετροποίηση)
    // =========================================================================
    cout << "\033[1;32m=== Don Zouάν Chess AI Interactive (MTD+) ===\033[0m\n";
    cout << "\033[36mΔώσε αρχικό FEN ή άφησέ το κενό για default:\033[0m ";
    string fen_input;
    cin.ignore();
    getline(cin, fen_input);

    chess::Board board = fen_input.empty() ? chess::Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1") : chess::Board(fen_input);
    
    std::vector<chess::Move> game_history;

    cout << "\033[36mAI παίζει με ποιο χρώμα; (w=Λευκά, b=Μαύρα):\033[0m ";
    string ai_side_input;
    cin >> ai_side_input;
    chess::Color ai_side = (ai_side_input == "w") ? chess::Color::WHITE : chess::Color::BLACK;

    cout << "\n\033[1;32m=== ΕΠΙΛΟΓΗ ΕΠΙΠΕΔΟΥ ΧΡΟΝΟΥ ===\033[0m\n";
    cout << "1. Blitz 5 Λεπτά\n";
    cout << "2. Blitz 10 Λεπτά\n";
    cout << "3. Tournament 30 Λεπτά\n";
    cout << "4. Classic Tournament (2 Ώρες / 40 Κινήσεις - Όπως το Millennium)\n";
    cout << "5. Σταθερός Χρόνος ανά Κίνηση (Fixed Time)\n";
    cout << "\033[36mΕπιλογή επιπέδου (1-5):\033[0m ";
    int tc_choice;
    cin >> tc_choice;

    ai_clock.moves_played = 0;
    ai_clock.time_control_passed = false;

    if (tc_choice == 1) {
        ai_clock.level = BLITZ_5MIN;
        ai_clock.ai_time_left_ms = 5LL * 60LL * 1000LL;
    } else if (tc_choice == 2) {
        ai_clock.level = BLITZ_10MIN;
        ai_clock.ai_time_left_ms = 10LL * 60LL * 1000LL;
    } else if (tc_choice == 3) {
        ai_clock.level = TOURNAMENT_30MIN;
        ai_clock.ai_time_left_ms = 30LL * 60LL * 1000LL;
    } else if (tc_choice == 4) {
        ai_clock.level = CLASSIC_TOURNAMENT;
        ai_clock.ai_time_left_ms = 120LL * 60LL * 1000LL; 
    } else {
        ai_clock.level = FIXED_TIME;
        cout << "\033[36mΔώσε δευτερόλεπτα σκέψης ανά κίνηση (π.χ. 5):\033[0m ";
        int secs;
        cin >> secs;
        ai_clock.fixed_time_ms = secs * 1000LL;
    }

    int move_number = board.fullMoveNumber();
    int previous_ai_score = 0; // Κρατάει το προηγούμενο Eval για τον επόμενο MTD+ driver

    while (true) {
        chess::Movelist moves;
        chess::movegen::legalmoves(moves, board);
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
                chess::Move only_move = moves.front();
                string san = uci::moveToSan(board, only_move);
                string uci_str = uci::moveToUci(only_move);
                string prefix = (board.sideToMove() == chess::Color::WHITE) ? to_string(move_number) + "." : to_string(move_number) + "...";
                cout << "\033[1;32m" << prefix << " " << san << " (" << uci_str << ") (AI μόνο κίνηση)\033[0m\n";
                
                game_history.push_back(only_move); 
                board.makeMove(only_move);
                if (board.sideToMove() == chess::Color::WHITE) move_number++;
                continue;
            }

            chess::Move book_move = get_book_move(board, game_history);

            if (book_move != chess::Move::NO_MOVE) {
                string san = uci::moveToSan(board, book_move);
                string uci_str = uci::moveToUci(book_move);
                string prefix = (board.sideToMove() == chess::Color::WHITE) ? to_string(move_number) + "." : to_string(move_number) + "...";
                cout << "\033[1;32m" << prefix << " " << san << " (" << uci_str << ") (AI από book)\033[0m\n";
                
                game_history.push_back(book_move); 
                board.makeMove(book_move);
                if (board.sideToMove() == chess::Color::WHITE) move_number++;
                continue;
            }

            // Προετοιμασία δυναμικού χρόνου σκέψης
            int score_change = 0; 
            MAX_SEARCH_TIME_MS = calculate_dynamic_move_time_local(board, score_change); 

            cout << "\033[1;32mΣκέψη AI... (Πάτα ENTER για άμεση κίνηση)\033[0m\n" << flush;
            ai_interrupt_flag = false;
            
            cin.clear();
            cin.ignore(std::numeric_limits<std::streamsize>::max(), '\n');

            std::thread input_thread([]() {
                string dummy;
                getline(cin, dummy); 
                ai_interrupt_flag = true; 
            });

            NODES = 0;
            start_time = std::chrono::steady_clock::now(); 
// [Η συνέχεια στο Μέρος 2...]
            chess::Move best_move_full = chess::Move::NO_MOVE;
            int best_score_full = 0;
            int depth = 1;
            int first_guess = previous_ai_score; // Ξεκινάμε από το σκορ της προηγούμενης κίνησης για ταχύτερη σύγκλιση

            // --- ITERATIVE DEEPENING LOOP ΜΕ MTD+ ---
            while (true) {
                auto current_time = std::chrono::steady_clock::now();
                auto elapsed_ms = std::chrono::duration_cast<std::chrono::milliseconds>(current_time - start_time).count();
                
                if (elapsed_ms >= (MAX_SEARCH_TIME_MS - 200)) {
                    ai_interrupt_flag = true;
                    break;
                }

                chess::Move current_best = chess::Move::NO_MOVE;
                int g = first_guess;
                int upper_bound = INF;
                int lower_bound = -INF;
                int cycles = 0;
                bool mtd_failed = false;

                try {
                    // Εσωτερικός βρόχος MTD+ για το τρέχον βάθος
                    while (lower_bound < upper_bound) {
                        int beta = (g == lower_bound) ? g + 1 : g;
                        
                        // Κλήση της alphabeta με Μηδενικό Παράθυρο αναζήτησης [beta - 1, beta]
                        int score = alphabeta(beta - 1, beta, depth, board, 0, current_best);
                        
                        if (score < beta) {
                            upper_bound = score;
                        } else {
                            lower_bound = score;
                            if (current_best != chess::Move::NO_MOVE) {
                                best_move_full = current_best;
                            }
                        }
                        g = score;

                        // Προστασία Infinite Loop: Αν γίνουν πάνω από 15 δοκιμές στο ίδιο βάθος λόγω TT collisions,
                        // σταματάμε τον MTD+ και ενεργοποιούμε το κλασικό alpha-beta fallback.
                        if (++cycles > 15) { 
                            mtd_failed = true; 
                            break; 
                        }
                    }

                    // Fallback σε κλασικό Alpha-Beta αν ο MTD+ απέτυχε να συγκλίνει
                    if (mtd_failed) {
                        g = alphabeta(-INF, INF, depth, board, 0, current_best);
                        if (current_best != chess::Move::NO_MOVE) best_move_full = current_best;
                    }

                    // Αποθήκευση αποτελεσμάτων βάθους
                    best_score_full = g;
                    first_guess = g; // Η επόμενη αρχική εκτίμηση (first guess)

                    // Εμφάνιση στατιστικών αναζήτησης στην κονσόλα σε πραγματικό χρόνο
                    string move_san = (best_move_full != chess::Move::NO_MOVE) ? uci::moveToSan(board, best_move_full) : "???";
                    string move_uci = (best_move_full != chess::Move::NO_MOVE) ? uci::moveToUci(best_move_full) : "???";
                    
                    cout << "\r\033[36m[Depth " << depth << "] Best: " << move_san << " (" << move_uci << ")";
                    
                    if (best_score_full > MATE_VALUE - 100) {
                        int plys = MATE_VALUE - best_score_full;
                        int moves_to_mate = (plys + 1) / 2;
                        cout << " | Eval: m" << moves_to_mate; 
                    } 
                    else if (best_score_full < -MATE_VALUE + 100) {
                        int plys = MATE_VALUE + best_score_full;
                        int moves_to_mate = (plys + 1) / 2;
                        cout << " | Eval: -m" << moves_to_mate; 
                    } 
                    else {
                        cout << " | Eval: " << fixed << setprecision(2) << (best_score_full / 100.0);
                    }

                    cout << " | Nodes: " << NODES << "\033[0m" << flush;

                    if (abs(best_score_full) >= MATE_VALUE - 100) break; 

                    depth++;
                    if (depth > 20) break; 

                } catch (const SearchInterruptException&) {
                    ai_interrupt_flag = true;
                    break; 
                }
            }

            previous_ai_score = best_score_full; // Αποθήκευση για την επόμενη κίνηση

            // Ενημέρωση του εναπομείναντος χρόνου του AI
            auto search_end_time = std::chrono::steady_clock::now();
            long long time_spent_ms = std::chrono::duration_cast<std::chrono::milliseconds>(search_end_time - start_time).count();

            if (ai_clock.level != FIXED_TIME) {
                ai_clock.ai_time_left_ms -= time_spent_ms;
                if (ai_clock.ai_time_left_ms < 200) ai_clock.ai_time_left_ms = 200; 
            }

            if (ai_interrupt_flag) {
                input_thread.detach(); 
            } else {
                cout << "\n\033[33m[AI ολοκλήρωσε τη σκέψη. Πάτα ENTER για να συνεχίσεις...]\033[0m\n";
                if (input_thread.joinable()) {
                    input_thread.join();
                }
            }

            if (best_move_full != chess::Move::NO_MOVE) {
                string san = uci::moveToSan(board, best_move_full);
                string uci_str = uci::moveToUci(best_move_full);
                string prefix = (board.sideToMove() == chess::Color::WHITE) ? to_string(move_number) + "." : to_string(move_number) + "...";
                
                long long final_secs = ai_clock.ai_time_left_ms / 1000;
                long long f_min = final_secs / 60;
                long long f_sec = final_secs % 60;

                cout << "\n\033[1;32m" << prefix << " AI παίζει: " << san << " (" << uci_str << ") (";
                
                if (best_score_full > MATE_VALUE - 100) {
                    cout << "m" << ((MATE_VALUE - best_score_full) + 1) / 2;
                } else if (best_score_full < -MATE_VALUE + 100) {
                    cout << "-m" << ((MATE_VALUE + best_score_full) + 1) / 2;
                } else {
                    cout << fixed << setprecision(2) << (best_score_full / 100.0);
                }
                
                if (ai_clock.level != FIXED_TIME) {
                    cout << ") [Ρολόι AI: " << setfill('0') << setw(2) << f_min << ":" 
                         << setfill('0') << setw(2) << f_sec << "]\033[0m\n";
                } else {
                    cout << ") [Σκέφτηκε: " << (time_spent_ms / 1000.0) << "s]\033[0m\n";
                }
                
                game_history.push_back(best_move_full); 
                board.makeMove(best_move_full);
                if (board.sideToMove() == chess::Color::WHITE) move_number++;
            } else {
                chess::Move fallback = moves.front(); 
                game_history.push_back(fallback); 
                board.makeMove(fallback);
                cout << "\n\033[31mAI: Fallback Move\033[0m\n";
            }
        } 
        else {
            cout << "\033[1;32m==> Η σειρά σου!\033[0m\n";
            cout << "\033[36mΗ κίνησή σου (e2e4 | undo):\033[0m ";
            string move_str;
            cin >> move_str;

            if (move_str == "undo") {
                if (game_history.size() >= 2) {
                    board.unmakeMove(game_history.back());
                    game_history.pop_back();

                    board.unmakeMove(game_history.back());
                    game_history.pop_back();

                    if (board.sideToMove() == chess::Color::BLACK) move_number--;
                    
                    if (ai_clock.level != FIXED_TIME && ai_clock.moves_played > 0) {
                        ai_clock.moves_played--;
                    }

                    cout << "\033[33m⏪ Έγινε αναίρεση των 2 τελευταίων κινήσεων!\033[0m\n";
                } else {
                    cout << "\033[31m❌ Δεν υπάρχουν αρκετές κινήσεις για αναίρεση.\033[0m\n";
                }
                continue;
            }

            chess::Move user_move = chess::Move::NO_MOVE;
            bool is_legal = false;

            for (size_t i = 0; i < moves.size(); ++i) {
                if (uci::moveToUci(moves[i]) == move_str) { 
                    user_move = moves[i];
                    is_legal = true;
                    break;
                }
            }

            if (is_legal && user_move != chess::Move::NO_MOVE) {
                game_history.push_back(user_move); 
                board.makeMove(user_move);
                if (board.sideToMove() == chess::Color::WHITE) move_number++;
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
std::memset(KILLERS, 0, sizeof(KILLERS));
std::memset(HISTORY, 0, sizeof(HISTORY));


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

// --- Κύρια Συνάρτηση Main με το Καθαρό Μενού Επιλογών ---
int main() {
    init_lmr_table(); // Αρχικοποίηση του LMR Table κατά την εκκίνηση του προγράμματος

    while (true) {
        cout << "\n=== Don Zouάν Mate Solver & AI Game v4.5 (C++) ===\n";
        cout << "1. Αποθήκευση νέου FEN με περιγραφή\n";
        cout << "2. Προβολή/Λύση αποθηκευμένου ή νέου FEN (Εύρεση Ματ)\n";
        cout << "3. Διαδραστικό Παιχνίδι (Interactive Gameplay vs AI) 🎮\n";
        cout << "4. Έξοδος\n";
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
            // Η παλιά επιλογή 3 έγινε τώρα 3, και μπαίνει κατευθείαν στο παιχνίδι!
            interactive_gameplay();
        } else if (choice == "4") {
            cout << "Έγινε έξοδος.\n";
            break;
        } else {
            cout << "Μη έγκυρη επιλογή.\n";
        }
    }
    return 0;
}
