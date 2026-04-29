#!/usr/bin/env python3
"""sc25 solver — Wizard spell-casting puzzle.

Mechanics:
  - Player ("pluyoo") navigates 64x64 grid with walls ("duvwsv-*")
  - 3x3 clickable grid for casting spells
  - 3 spells:
    * tevyeq (teleport): cells (0,0),(0,1),(1,1)
    * sieesc_chwjgc (scale toggle): cells (0,1),(1,0),(1,2),(2,1) = cross
    * fibcey (fireball): cells (0,1),(1,1),(2,1) = center column
  - Actions 1=up, 2=down, 3=left, 4=right, 6=click(x,y)
  - exydhv = exit portal, tagsmh = destroyable barrier, dosorb = door
"""
import sys
import warnings
import logging

sys.path.insert(0, '/home/paolo/arc-agi/solver')
import arc_agi

warnings.filterwarnings('ignore')
logging.disable(logging.WARNING)

GRID = {
    (0, 0): (25, 50), (0, 1): (30, 50), (0, 2): (35, 50),
    (1, 0): (25, 55), (1, 1): (30, 55), (1, 2): (35, 55),
    (2, 0): (25, 60), (2, 1): (30, 60), (2, 2): (35, 60),
}

SPELL_PATTERNS = {
    'tevyeq': [(0, 0), (0, 1), (1, 1)],
    'sieesc_chwjgc': [(0, 1), (1, 0), (1, 2), (2, 1)],
    'fibcey': [(0, 1), (1, 1), (2, 1)],
}

HUMAN_BASELINES = [36, 6, 32, 83, 143, 50]


class Solver:
    def __init__(self):
        self.arc = arc_agi.Arcade()
        self.env = self.arc.make('sc25')
        self.obs = self.env.reset()
        self.game = self.env._game
        self._action_count = 0
        self._level_actions = []

        # Wrap env.step to count actions
        self._orig_step = self.env.step
        self.env.step = self._counting_step

    def _counting_step(self, *args, **kwargs):
        self._action_count += 1
        return self._orig_step(*args, **kwargs)

    @property
    def lvl(self):
        return self.game._current_level_index

    def noop(self, n=1):
        for _ in range(n):
            self.env.step(6, data={'x': 0, 'y': 0})

    def cast(self, spell):
        """Cast spell with zero trailing noops."""
        for r, c in SPELL_PATTERNS[spell]:
            self.env.step(6, data={'x': GRID[(r, c)][0], 'y': GRID[(r, c)][1]})

    def move(self, direction, times=1):
        for _ in range(times):
            self.env.step(direction)

    def solve_level_1(self):
        """L1: 1 noop (animation) + shrink + 12 left = 17 actions."""
        self.noop(1)
        self.cast('sieesc_chwjgc')
        self.move(3, 12)

    def solve_level_2(self):
        """L2: Teleport + 2 up = 5 actions."""
        self.cast('tevyeq')
        self.move(1, 2)

    def solve_level_3(self):
        """L3: Face right + fireball + navigate to exit = 12 actions."""
        self.move(4, 1)
        self.cast('fibcey')
        self.move(3, 3)
        self.move(2, 4)
        self.move(3, 1)

    def solve_level_4(self):
        """L4: Shrink, move to corridor, fireball, grow, navigate = 24 actions."""
        self.cast('sieesc_chwjgc')       # shrink (4)
        self.move(2, 5)                  # down 5 to y=29 (5)
        self.move(3, 1)                  # face left (1)
        self.cast('fibcey')              # fireball (3)
        self.cast('sieesc_chwjgc')       # grow (4)
        self.move(2, 2)                  # down 2 to y>=35 (2)
        self.move(4, 5)                  # right 5 to exit (5)

    def solve_level_5(self):
        """L5: Shrink, teleport, navigate corridors, double fireball = 40 actions."""
        self.cast('sieesc_chwjgc')       # shrink (4)
        self.cast('tevyeq')              # teleport to (29,39) (3)
        self.move(3, 7)                  # left 7 to x=15 (7)
        self.move(1, 2)                  # up 2 to y=35 (2)
        self.cast('fibcey')              # fireball (3)
        self.move(2, 4)                  # down 4 to y=43 (4)
        self.move(3, 1)                  # left to x=13 (1)
        self.cast('fibcey')              # fireball (3)
        self.cast('sieesc_chwjgc')       # grow (4)
        self.cast('tevyeq')              # teleport to (51,35) (3)
        self.move(1, 6)                  # up 6 to exit (6)

    def solve_level_6(self):
        """L6: Shrink, teleport, fireball, grow, double teleport = 38 actions."""
        self.cast('sieesc_chwjgc')       # shrink (4)
        self.cast('tevyeq')              # teleport to (13,41) (3)
        self.move(4, 2)                  # right 2 to x=17 (2)
        self.move(1, 3)                  # up 3 to y=37 (3) -- face up for fireball
        self.cast('fibcey')              # fireball → destroy tagsmh (3)
        self.cast('sieesc_chwjgc')       # grow (4)
        self.cast('tevyeq')              # teleport to (53,37) (3)
        self.move(3, 3)                  # left 3 to x=41 (3)
        self.cast('fibcey')              # fireball → destroy seofsw-tagsmh (3)
        self.cast('tevyeq')              # teleport to (29,33) (3)
        self.move(1, 1)                  # up 1 (1)
        self.move(4, 1)                  # right 1 (1)
        self.move(1, 5)                  # up 5 to exit → WIN (5)

    def solve(self):
        total_levels = self.obs.win_levels
        print(f"sc25: {total_levels} levels")

        solvers = [
            None,
            self.solve_level_1,
            self.solve_level_2,
            self.solve_level_3,
            self.solve_level_4,
            self.solve_level_5,
            self.solve_level_6,
        ]

        for level in range(1, total_levels + 1):
            if self.obs.state.name not in ("NOT_FINISHED", None):
                break

            self._action_count = 0
            solvers[level]()
            actions = self._action_count
            self._level_actions.append(actions)

            # Check state after level
            self.obs = self.env.step(6, data={'x': 0, 'y': 0})
            if self.obs.state.name == "WIN":
                # Last level — don't count the trailing noop
                break

        # Determine win
        levels_solved = self.obs.levels_completed
        if self.obs.state.name == "WIN":
            levels_solved = total_levels

        # Print results table
        print(f"\n{'='*64}")
        print(f"{'GAME':>6} {'LEVEL':>5} | {'HUMAN':>5} | {'OURS':>5} | {'RATIO':>6} | {'RHAE':>8}")
        print(f"{'-'*64}")

        total_rhae = 0.0
        for i, (h, ai) in enumerate(zip(HUMAN_BASELINES, self._level_actions)):
            ratio = h / ai
            rhae = ratio ** 2
            total_rhae += rhae
            print(f"{'sc25':>6} L{i+1:>3} | {h:>5} | {ai:>5} | {ratio:>6.2f} | {rhae:>8.4f}")

        print(f"{'-'*64}")
        print(f"{'':>6} {'TOTAL':>5} | {sum(HUMAN_BASELINES):>5} | "
              f"{sum(self._level_actions):>5} |        | {total_rhae:>8.4f}")
        print(f"\nTOTAL_RHAE = {total_rhae:.4f}")
        print(f"LEVELS_SOLVED: {levels_solved}/{total_levels}")
        print(f"STATE: {self.obs.state.name}")
        print(f"{'='*64}")

        return levels_solved


if __name__ == "__main__":
    Solver().solve()
