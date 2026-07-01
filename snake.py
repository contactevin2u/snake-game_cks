"""
Snake Game
==========
A classic snake game built with Python's built-in tkinter library.

Controls:
    Arrow keys or W / A / S / D  -> move the snake
    Space or P                   -> pause / resume
    R                            -> restart after game over
    Esc                          -> quit

Run it with:
    python snake.py
"""

import os
import random
import sqlite3
import tkinter as tk
from tkinter import simpledialog

# ---- Game configuration -------------------------------------------------
CELL_SIZE = 20          # pixel size of one grid cell
GRID_WIDTH = 30         # number of cells horizontally
GRID_HEIGHT = 20        # number of cells vertically
START_SPEED_MS = 120    # delay between moves in milliseconds (lower = faster)
MIN_SPEED_MS = 60       # fastest the game will get
SPEED_STEP_MS = 4       # how much faster it gets per food eaten

BG_COLOR = "#1e1e2e"
GRID_COLOR = "#2a2a3c"
SNAKE_COLOR = "#a6e3a1"
SNAKE_HEAD_COLOR = "#94e2d5"
FOOD_COLOR = "#f38ba8"
TEXT_COLOR = "#cdd6f4"

WIDTH = GRID_WIDTH * CELL_SIZE
HEIGHT = GRID_HEIGHT * CELL_SIZE

MAX_SCORES = 10  # how many entries the leaderboard keeps / shows

# The database file lives next to this script so scores persist between runs.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.db")


# ---- Database (SQLite, built into Python) -------------------------------
def init_db():
    """Create the scores table on first run."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS scores ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  name TEXT NOT NULL,"
            "  score INTEGER NOT NULL,"
            "  created_at TEXT DEFAULT CURRENT_TIMESTAMP"
            ")"
        )


def add_score(name, score):
    """Save one result to the database."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO scores (name, score) VALUES (?, ?)", (name, score)
        )


def get_top_scores(limit=MAX_SCORES):
    """Return the best scores as a list of (name, score), highest first."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT name, score FROM scores "
            "ORDER BY score DESC, created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return rows


def qualifies_for_leaderboard(score):
    """True if this score earns a spot in the top MAX_SCORES."""
    if score <= 0:
        return False
    top = get_top_scores(MAX_SCORES)
    if len(top) < MAX_SCORES:
        return True
    lowest = top[-1][1]
    return score > lowest


class SnakeGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Snake Game")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root, width=WIDTH, height=HEIGHT, bg=BG_COLOR, highlightthickness=0
        )
        self.canvas.pack()

        # Bind keyboard controls.
        root.bind("<Key>", self.on_key)

        self.reset()
        self.draw_grid()
        self.tick()

    # ---- Game state ------------------------------------------------------
    def reset(self):
        # Snake starts in the middle, length 3, moving right.
        mid_x = GRID_WIDTH // 2
        mid_y = GRID_HEIGHT // 2
        self.snake = [(mid_x - i, mid_y) for i in range(3)]
        self.direction = (1, 0)       # current movement (dx, dy)
        self.next_direction = (1, 0)  # buffered next move
        self.food = self.random_food()
        self.score = 0
        self.speed = START_SPEED_MS
        self.paused = False
        self.game_over = False
        self.score_recorded = False        # have we already handled game over?
        self.top_scores = get_top_scores()  # cached leaderboard for the overlay

    def random_food(self):
        """Pick a random empty cell for the food."""
        empty = {
            (x, y)
            for x in range(GRID_WIDTH)
            for y in range(GRID_HEIGHT)
        } - set(self.snake)
        return random.choice(tuple(empty)) if empty else None

    # ---- Input -----------------------------------------------------------
    def on_key(self, event):
        key = event.keysym.lower()

        if key == "escape":
            self.root.destroy()
            return

        if key == "r" and self.game_over:
            self.reset()
            return

        if key in ("space", "p") and not self.game_over:
            self.paused = not self.paused
            return

        # Map keys to direction vectors.
        directions = {
            "up": (0, -1), "w": (0, -1),
            "down": (0, 1), "s": (0, 1),
            "left": (-1, 0), "a": (-1, 0),
            "right": (1, 0), "d": (1, 0),
        }
        if key in directions:
            dx, dy = directions[key]
            # Prevent reversing directly into yourself.
            cur_dx, cur_dy = self.direction
            if (dx, dy) != (-cur_dx, -cur_dy):
                self.next_direction = (dx, dy)

    # ---- Main loop -------------------------------------------------------
    def tick(self):
        if not self.paused and not self.game_over:
            self.move()
            if self.game_over and not self.score_recorded:
                self.handle_game_over()
        self.render()
        # Schedule the next frame.
        self.root.after(self.speed, self.tick)

    def handle_game_over(self):
        """Ask for a name on a high score, save it, and refresh the ranking."""
        self.score_recorded = True  # set first so this runs only once
        self.render()  # show the final board behind the popup

        if qualifies_for_leaderboard(self.score):
            name = simpledialog.askstring(
                "New High Score!",
                f"Score: {self.score}\nEnter your name:",
                parent=self.root,
            )
            if name and name.strip():
                add_score(name.strip()[:20], self.score)

        # Reload so the overlay shows the latest ranking.
        self.top_scores = get_top_scores()

    def move(self):
        self.direction = self.next_direction
        dx, dy = self.direction
        head_x, head_y = self.snake[0]
        new_head = (head_x + dx, head_y + dy)

        # Collision with walls.
        if not (0 <= new_head[0] < GRID_WIDTH and 0 <= new_head[1] < GRID_HEIGHT):
            self.game_over = True
            return

        # Collision with self (ignore the tail cell, it will move away).
        if new_head in self.snake[:-1]:
            self.game_over = True
            return

        self.snake.insert(0, new_head)

        if new_head == self.food:
            self.score += 1
            self.speed = max(MIN_SPEED_MS, self.speed - SPEED_STEP_MS)
            self.food = self.random_food()
            if self.food is None:  # board full = you win!
                self.game_over = True
        else:
            self.snake.pop()  # move forward: remove tail

    # ---- Drawing ---------------------------------------------------------
    def draw_grid(self):
        for x in range(0, WIDTH, CELL_SIZE):
            self.canvas.create_line(x, 0, x, HEIGHT, fill=GRID_COLOR)
        for y in range(0, HEIGHT, CELL_SIZE):
            self.canvas.create_line(0, y, WIDTH, y, fill=GRID_COLOR)

    def draw_cell(self, cell, color):
        x, y = cell
        x1, y1 = x * CELL_SIZE, y * CELL_SIZE
        self.canvas.create_rectangle(
            x1 + 1, y1 + 1, x1 + CELL_SIZE - 1, y1 + CELL_SIZE - 1,
            fill=color, outline=""
        )

    def render(self):
        self.canvas.delete("dynamic")
        # Re-run with a tag so we can clear only game objects, not the grid.
        self._render_tagged()

    def _render_tagged(self):
        # Food
        if self.food:
            self._tagged_rect(self.food, FOOD_COLOR)
        # Snake body + head
        for i, cell in enumerate(self.snake):
            color = SNAKE_HEAD_COLOR if i == 0 else SNAKE_COLOR
            self._tagged_rect(cell, color)
        # Score
        self.canvas.create_text(
            8, 8, anchor="nw", fill=TEXT_COLOR,
            font=("Consolas", 12, "bold"),
            text=f"Score: {self.score}", tags="dynamic",
        )
        # Overlays
        if self.paused:
            self._center_text("PAUSED", "Press Space to resume")
        if self.game_over:
            won = self.food is None
            title = "YOU WIN!" if won else "GAME OVER"
            self._game_over_overlay(title)

    def _tagged_rect(self, cell, color):
        x, y = cell
        x1, y1 = x * CELL_SIZE, y * CELL_SIZE
        self.canvas.create_rectangle(
            x1 + 1, y1 + 1, x1 + CELL_SIZE - 1, y1 + CELL_SIZE - 1,
            fill=color, outline="", tags="dynamic",
        )

    def _center_text(self, title, subtitle):
        self.canvas.create_text(
            WIDTH // 2, HEIGHT // 2 - 12, fill=TEXT_COLOR,
            font=("Consolas", 26, "bold"), text=title, tags="dynamic",
        )
        self.canvas.create_text(
            WIDTH // 2, HEIGHT // 2 + 20, fill=TEXT_COLOR,
            font=("Consolas", 12), text=subtitle, tags="dynamic",
        )

    def _game_over_overlay(self, title):
        """Draw the game-over panel with the high-score ranking."""
        # Dark panel so the text is readable over the board.
        pad = 40
        self.canvas.create_rectangle(
            pad, 20, WIDTH - pad, HEIGHT - 20,
            fill="#181825", outline=SNAKE_HEAD_COLOR, width=2, tags="dynamic",
        )

        self.canvas.create_text(
            WIDTH // 2, 48, fill=TEXT_COLOR,
            font=("Consolas", 22, "bold"), text=title, tags="dynamic",
        )
        self.canvas.create_text(
            WIDTH // 2, 76, fill=FOOD_COLOR,
            font=("Consolas", 13), text=f"Your score: {self.score}", tags="dynamic",
        )

        # Ranking header.
        self.canvas.create_text(
            WIDTH // 2, 104, fill=SNAKE_HEAD_COLOR,
            font=("Consolas", 13, "bold"), text="TOP SCORES", tags="dynamic",
        )

        # Ranking rows: "1.  ALICE            123"
        start_y = 128
        row_h = 20
        if not self.top_scores:
            self.canvas.create_text(
                WIDTH // 2, start_y + 10, fill=TEXT_COLOR,
                font=("Consolas", 12), text="No scores yet - be the first!",
                tags="dynamic",
            )
        else:
            for i, (name, score) in enumerate(self.top_scores):
                rank = f"{i + 1:>2}."
                line = f"{rank}  {name[:14]:<14} {score:>5}"
                self.canvas.create_text(
                    WIDTH // 2, start_y + i * row_h, fill=TEXT_COLOR,
                    font=("Consolas", 12), text=line, tags="dynamic",
                )

        self.canvas.create_text(
            WIDTH // 2, HEIGHT - 36, fill=TEXT_COLOR,
            font=("Consolas", 11), text="Press R to restart   -   Esc to quit",
            tags="dynamic",
        )


def main():
    init_db()
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
