#!/usr/bin/env python3
"""cd82 solver — Painting puzzle with basket, palette, pours, and gates.

Mechanics:
  - 10x10 canvas starts black (color 0)
  - 10x10 target pattern to reproduce (ignoring diagonal pixels)
  - Basket rotates around canvas in 8 positions (ring navigation)
  - ACTION5 pours current color into a region (half-plane or triangle)
  - Click palette to select color, click gate to pour small rectangle
  - Actions 1-4 navigate basket around the ring (3x3 grid minus center)
  - Win when canvas matches target (excluding main+anti diagonal pixels)

Painting operations:
  Pour (ACTION5) from position:
    0: top half (rows 0:5)          4: bottom half (rows 5:10)
    6: left half (cols 0:5)         2: right half (cols 5:10)
    7: top-left triangle            1: top-right triangle (unused)
    5: bottom-left triangle         3: bottom-right triangle

  Gate (click ctwspzkygu) at position:
    0: rows 0:3, cols 3:7           2: rows 3:7, cols 7:10
    4: rows 7:10, cols 3:7          6: rows 3:7, cols 0:3
"""
import sys
import warnings
import logging
from collections import deque

sys.path.insert(0, '/home/paolo/arc-agi/solver')
import arc_agi

warnings.filterwarnings('ignore')
logging.disable(logging.WARNING)

# ─── Ring navigation ───────────────────────────────────────────────────────

POS_TO_GRID = {
    0: (0, 1), 1: (0, 2), 2: (1, 2), 3: (2, 2),
    4: (2, 1), 5: (2, 0), 6: (1, 0), 7: (0, 0),
}


def _neighbors(r, c):
    result = []
    for nr, nc, act in [
        (max(0, r - 1), c, 1), (min(2, r + 1), c, 2),
        (r, max(0, c - 1), 3), (r, min(2, c + 1), 4),
    ]:
        if (nr, nc) != (1, 1) and (nr, nc) != (r, c):
            result.append((nr, nc, act))
    return result


def path_between(start_pos, end_pos):
    """BFS shortest path between two ring positions (0-7). Returns list of actions."""
    if start_pos == end_pos:
        return []
    start_rc = POS_TO_GRID[start_pos]
    end_rc = POS_TO_GRID[end_pos]
    queue = deque([(start_rc, [])])
    visited = {start_rc}
    while queue:
        (r, c), actions = queue.popleft()
        for nr, nc, act in _neighbors(r, c):
            if (nr, nc) == end_rc:
                return actions + [act]
            if (nr, nc) not in visited:
                visited.add((nr, nc))
                queue.append(((nr, nc), actions + [act]))
    return []


# ─── Palette definitions per level ─────────────────────────────────────────

# Maps color -> (sprite_x, sprite_y) for each level
PALETTE = {
    1: {0: (35, 2), 15: (41, 2)},
    2: {0: (32, 2), 15: (38, 2), 12: (44, 2)},
}
for lv in range(3, 7):
    PALETTE[lv] = {
        0: (21, 2), 15: (27, 2), 12: (33, 2), 11: (39, 2),
        14: (45, 2), 8: (51, 2), 9: (57, 2),
    }

# Gate center grid coordinates (for levels 3-6 that have gates)
GATE_CENTER = {
    0: (32, 20),
    2: (51, 38),
    4: (32, 57),
    6: (14, 38),
}

# ─── Pre-computed solutions ────────────────────────────────────────────────
# Each solution is a list of (op_type, ring_position, color)
# op_type: 'pour' = ACTION5, 'gate' = click ctwspzkygu

SOLUTIONS = {
    1: [('pour', 4, 15)],
    2: [('pour', 0, 15), ('pour', 3, 12)],
    3: [('pour', 2, 14), ('pour', 6, 8), ('pour', 7, 15), ('gate', 0, 12)],
    4: [('pour', 0, 12), ('pour', 3, 15), ('pour', 6, 9), ('gate', 6, 11)],
    5: [('pour', 0, 9), ('pour', 5, 14), ('pour', 3, 12), ('gate', 0, 8)],
    6: [('pour', 2, 14), ('pour', 7, 8), ('gate', 0, 15), ('gate', 6, 11)],
}


# ─── Execution ─────────────────────────────────────────────────────────────

def select_color(env, level_num, color):
    """Click on palette swatch to select a color."""
    sx, sy = PALETTE[level_num][color]
    # Click center of 5x5 palette swatch
    return env.step(6, data={'x': sx + 2, 'y': sy + 2})


def click_gate(env, ring_pos):
    """Click the gate sprite at the given ring position."""
    gx, gy = GATE_CENTER[ring_pos]
    return env.step(6, data={'x': gx, 'y': gy})


def solve_level(env, game, level_num):
    """Execute the pre-computed solution for one level."""
    solution = SOLUTIONS[level_num]
    current_pos = 0     # basket always starts at position 0
    current_color = 15  # default starting color

    for op_type, target_pos, color in solution:
        # Select color if needed
        if color != current_color:
            select_color(env, level_num, color)
            current_color = color

        # Navigate basket to target position
        nav = path_between(current_pos, target_pos)
        for action in nav:
            env.step(action)
        current_pos = target_pos

        # Execute operation
        if op_type == 'pour':
            env.step(5)
        else:  # gate
            click_gate(env, target_pos)

    return True


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('cd82')
    obs = env.reset()
    game = env._game

    print(f"cd82: {obs.win_levels} levels")

    for level in range(1, obs.win_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        print(f"\n--- Level {level} ---")
        success = solve_level(env, game, level)

        # Trigger a no-op to read state after animations
        obs = env.step(6, data={'x': 0, 'y': 0})
        print(f"  completed={obs.levels_completed}, state={obs.state.name}")

        if not success:
            print(f"  FAILED")
            break

    if obs.state.name == "WIN":
        print(f"\ncd82 RESULT: 6/6 (WIN)")
        return 6
    total = obs.levels_completed
    print(f"\ncd82 RESULT: {total}/6")
    return total


if __name__ == "__main__":
    solve()
