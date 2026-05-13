# Dialogos Chess AI

**Dialogos** is a strategic, complete chess engine written in Python. It features a highly tuned evaluation function, sophisticated move ordering, and tactical quiescence search, achieving a performance equivalent to **1800+ Elo** against top chess platform bots (e.g., Chess.com's Wally).

---

## 💡 The Story Behind the Engine (Human-AI Collaboration)

This project is a unique experiment in **Conversational Coding**. 

The creator of this engine is a passionate chess enthusiast with **zero background in computer science or programming**. Over the course of **1.5 years**, this engine was built piece by piece through an intensive dialogue between the creator (who provided the chess vision, tactical guidelines, and rigorous benchmarking) and Advanced Artificial Intelligence models (who translated those ideas into clean Python code).

*Dialogos* stands as a proof of concept that deep domain knowledge combined with AI collaboration can produce elite software without traditional coding expertise.

---

## 🛠️ Engine Architecture & Features

Despite the inherent speed limitations of pure Python and running entirely **without Transposition Tables (TT)** to maximize execution stability, *Dialogos* compensates with advanced heuristics:

*   **Iterative Deepening Search:** Multi-threaded loop allowing manual interrupts and ensuring a safe fallback move under strict time limits.
*   **Highly Calibrated Evaluation:** 
    *   *Dynamic King Tables:* Defensive positioning (castling priority) in the middlegame, transforming into aggressive king centralization in the endgame.
    *   *Rook Strategy:* Advanced bonuses for 7th-rank infiltration, open/semi-open file control, and positioning rooks behind passed pawns.
    *   *Tactical Elements:* Strict space control, minor piece development rules, and bishop pair bonuses.
*   **State-of-the-Art Move Ordering:** Fully optimized Alpha-Beta pruning using **MVV-LVA**, a **2-slot Killer Moves table per ply**, and a **History Heuristic** weighted by depth.
*   **Static Exchange Evaluation (SEE):** A lightning-fast, look-ahead capture filter that prunes suicidal tactics before entering deep sub-trees.
*   **Ultra-Fast Quiescence Search:** Eliminates the horizon effect by stabilizing volatile capturing sequences.
*   **Endgame Detector:** Automatic behavior shift when heavy pieces clear out or passed pawns become prominent.
*   **Fidelity Relief CLI:** A beautifully rendered, ANSI-colored terminal chessboard interface.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.8+
*   `python-chess` library

```bash
pip install python-chess
```

### Running the Engine
Simply download `dialogos.py` from this repository and run it via your terminal:

```bash
python dialogos.py
```

Follow the on-screen prompts to select your side, set the AI thinking time limit, or paste a custom FEN position.

---

## 📊 Benchmarks & Performance
In full-game testing against Chess.com's **li (2000 Elo bot)**, *Dialogos* secured decisive victories operating at a steady **Depth 5**, maintaining an average **Accuracy of 86.5%** with 0 blunders and 0 mistakes.
