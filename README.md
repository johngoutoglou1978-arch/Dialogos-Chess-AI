# Dialogos Chess AI

# Dialogos Chess Engine

Dialogos is a strategic, complete chess engine written in Python. It features a highly tuned evaluation function, sophisticated move ordering, and tactical quiescence search, achieving a performance equivalent to 2000+ Elo against top chess platform bots (e.g., Chess.com's Wally).

## 💡 The Story Behind the Engine (My Journey with AI)
This project is a unique experiment in Conversational Coding. 

As a passionate chess enthusiast with zero background in computer science or programming, I wanted to see if I could bring my chess vision to life. Over the course of 1.5 years, I built this engine piece by piece through an intensive dialogue with Advanced Artificial Intelligence models. I provided the chess concepts, tactical guidelines, and rigorous benchmarking, while the AI translated my ideas into clean, functional Python code.

Dialogos stands as a proof of concept that deep domain knowledge combined with AI collaboration can produce elite software without traditional coding expertise.

## 🛠️ Engine Architecture & Features
Despite the inherent speed limitations of pure Python and running entirely without Transposition Tables (TT) to maximize execution stability, I designed Dialogos to compensate using advanced heuristics:

* **Iterative Deepening Search:** Multi-threaded loop allowing manual interrupts and ensuring a safe fallback move under strict time limits.
* **Highly Calibrated Evaluation:**
  * **Dynamic King Tables:** Defensive positioning (castling priority) in the middlegame, transforming into aggressive king centralization in the endgame.
  * **Rook Strategy:** Advanced bonuses for 7th-rank infiltration, open/semi-open file control, and positioning rooks behind passed pawns.
  * **Tactical Elements:** Strict space control, minor piece development rules, and bishop pair bonuses.
* **State-of-the-Art Move Ordering:** Fully optimized Alpha-Beta pruning using MVV-LVA, a 2-slot Killer Moves table per ply, and a History Heuristic weighted by depth.
* **Static Exchange Evaluation (SEE):** A lightning-fast, look-ahead capture filter that prunes suicidal tactics before entering deep sub-trees.
* **Ultra-Fast Quiescence Search:** Eliminates the horizon effect by stabilizing volatile capturing sequences.
* **Endgame Detector:** Automatic behavior shift when heavy pieces clear out or passed pawns become prominent.
* **Fidelity Relief CLI:** A beautifully rendered, ANSI-colored terminal chessboard interface.

## 🚀 Getting Started

### Prerequisites
* Python 3.8+
* `python-chess` library

```bash
pip install python-chess
```

### Running the Engine
Simply download `dialogos.py` from this repository and run it via your terminal:

```bash
python dialogos.py
```
Follow the on-screen prompts to select your side, set the AI thinking time limit, or paste a custom FEN position.

## 📊 Benchmarks & Performance
In my full-game testing against Chess.com's Li (a 2000 Elo bot), Dialogos secured decisive victories operating at a steady Depth 5, maintaining an average Accuracy of 86.5% with 0 blunders and 0 mistakes.

## 📱 Android Optimization & Mobile Performance
I uniquely designed and fully optimized Dialogos to run directly on mobile devices, delivering high-level tactical performance even within the hardware and resource constraints of smartphone processors.

* **Mobile Deployment:** The engine runs flawlessly on Android environments using apps like Pydroid 3 or terminal emulators like Termux.
* **Android Benchmarks:** In pure Python mobile environments, my engine achieves a steady speed of 1,500+ NPS (Nodes Per Second).
* **Tree Optimization:** Thanks to aggressive Alpha-Beta pruning, Killer Moves, and Static Exchange Evaluation (SEE), the engine severely restricts tree explosion. This allows it to reach deep tactical solutions (such as finding Depth 7 mating combinations like Qxh7+) on a mobile CPU without overheating the device or draining the battery.
* **Fidelity Relief CLI:** The interface uses an ultra-lightweight, ANSI-colored terminal chessboard that renders perfectly on mobile screens, avoiding the heavy memory overhead of standard graphical interfaces (GUIs).
* 



---

## 🚀 C++ Version: Edmond Dantes

**Edmond Dantes** is the direct successor of the *Dialogos* project, fully ported to **C++** (`Edmond dantes modexristo.cxx` and `mat solver.cxx`). 

This version is engineered to achieve high computational speeds (Knps) at the hardware level, incorporating core search structures alongside a **specialized Mat Solver function**.

### 🛠️ Architecture & Features:

- **Iterative Deepening Search:** A strategic search loop that progressively increases search depth to maintain precise control over thinking time.
- **Evaluation Function with Original Chess Knowledge:** The positional evaluation is built entirely on authentic chess understanding.
- **Move Ordering:** Advanced move sorting to prioritize and search the most promising tactical lines first within the Alpha-Beta algorithm.
- **Alpha-Beta Search & Transposition Table (TT):** A classic Alpha-Beta search backed by a transposition table (2²⁰ entries) to cache and reuse previously analyzed positions.
- **MDT Algorithm (Mate Distance TT Correction):** A custom mechanism that dynamically adjusts mate scores based on the current depth (`ply`), ensuring the engine always selects the shortest path to checkmate.
- **Tactical Quiescence Search:** A specialized search executed at the end of the main loop to stabilize tactical lines by exhaustively analyzing violent piece captures.
- **Specialized Mat Solver Mode:** A dedicated search mode tuned exclusively for solving complex chess puzzles and forcing checkmates within the required number of moves.

### 📦 Prerequisites & Compilation (How to run it on every platform)

This project is **header-only**. The required **`chess.hpp`** library is already included in the main repository folder, so you do not need to download any external dependencies.

#### 📱 1. For Android (via Termux):
Open Termux, navigate to the project directory, and execute:
```bash
g++ -O3 -std=c++17 "Edmond dantes modexristo.cxx" -o edmond_dantes
./edmond_dantes
```
*(If you are using mobile IDE apps like CxxDroid, simply open the file inside the app and press the Run button).*

#### 💻 2. For Windows:
If you are using the Command Prompt or PowerShell with `g++` installed (via MinGW):
```cmd
g++ -O3 -std=c++17 "Edmond dantes modexristo.cxx" -o edmond_dantes.exe
edmond_dantes.exe
```
*(Alternatively, you can open the project folder in IDEs like Visual Studio or CLion and build it directly through their compiler tools).*

#### 🐧 3. For Linux:
Open your terminal in the project directory and run:
```bash
g++ -O3 -std=c++17 "Edmond dantes modexristo.cxx" -o edmond_dantes
./edmond_dantes
```

#### 🍏 4. For macOS (Mac):
Open your terminal, ensure you have the Command Line Tools installed (`xcode-select --install`), and execute:
```bash
clang++ -O3 -std=c++17 "Edmond dantes modexristo.cxx" -o edmond_dantes
./edmond_dantes
```

---

## 📜 Credits & Licensing

- **Edmond Dantes Engine & Mat Solver:** The entire strategic conception, chess knowledge base, search core algorithms, Transposition Table management, MDT logic, and pruning structures are my own intellectual work, developed over 1.5 years of intensive AI collaboration.
- **Chess Rules Engine (C++):** The C++ version utilizes the excellent open-source **`chess-library`** by developer **Disservin** (available at https://github.com). This library is included directly in the repository (`chess.hpp`) under the official MIT License, respecting the original creator's rights and solely for the purpose of ensuring a seamless compilation process for users.
- 
