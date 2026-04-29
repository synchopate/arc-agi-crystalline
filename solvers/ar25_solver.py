#!/usr/bin/env python3
"""ar25 solver — Reflection/mirror puzzle.

Mechanics:
  - 21x21 grid with colored shape sprites and axis lines (mirrors)
  - Vertical axis (0054kgxrvfihgm): reflects x' = 2*A - x, moves left/right only
  - Horizontal axis (0002nuguepuujf): reflects y' = 2*B - y, moves up/down only
  - Reflections chain across multiple axes via BFS (max depth 12)
  - Colored sprites (0006lxjtqggkmi) can be moved in 4 directions
  - Goal: position sprites + axes so that reflections cover all dot markers (color 11)
  - ACTION7 = undo, ACTION5 = cycle selection, ACTION6 = click to select
  - Step counter limits total moves before losing

Actions: 1=up, 2=down, 3=left, 4=right, 5=cycle_selection, 6=click, 7=undo

Solutions (pre-computed target positions):
  L1: sprite -> (1,15), fixed V axis at x=10
  L2: V axis -> x=10, sprite -> (15,14)
  L3: H axis -> y=9, sprite0 -> (11,14), sprite1 -> (3,14)
  L4: H axis -> y=9, U-shape -> (11,6), bar -> (13,3)
  L5: H axis -> y=9, V axis -> x=8, sprite -> (4,5)
  L6: H axis -> y=11, V axis -> x=6, T -> (2,12), C -> (7,15)
  L7: H axis -> y=7, V axis -> x=12, zigzag -> (15,1), cross -> (8,10)
  L8: H axis -> y=11, V axis -> x=12, E-shape -> (4,6), L-shape -> (16,3)
"""
import sys
import warnings
import logging

sys.path.insert(0, '/home/paolo/arc-agi/solver')
import arc_agi

warnings.filterwarnings('ignore')
logging.disable(logging.WARNING)


def execute(env, actions):
    """Execute a sequence of actions, return final obs."""
    obs = None
    for a in actions:
        obs = env.step(a)
    return obs


def move_to(current, target, horiz=True):
    """Generate actions to move from current to target position.
    horiz=True: left/right (actions 3/4), horiz=False: up/down (actions 1/2)."""
    if horiz:
        diff = target - current
        if diff > 0:
            return [4] * diff  # right
        elif diff < 0:
            return [3] * (-diff)  # left
    else:
        diff = target - current
        if diff > 0:
            return [2] * diff  # down
        elif diff < 0:
            return [1] * (-diff)  # up
    return []


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('ar25')
    obs = env.reset()
    game = env._game

    total_levels = obs.win_levels

    # --- Level 1 ---
    # Only 1 sprite selected, fixed V axis at x=10
    # Move sprite from (6,5) to (1,15): left 5, down 10
    obs = execute(env, [3]*5 + [2]*10)
    print(f'L1: completed={obs.levels_completed}')

    # --- Level 2 ---
    # Selected = V axis at x=12. Sprite at (15,6).
    # Move axis from x=12 to x=10: left 2
    # Select sprite, move down 8 (y=6 -> y=14)
    obs = execute(env, [3, 3, 5] + [2]*8)
    print(f'L2: completed={obs.levels_completed}')

    # --- Level 3 ---
    # Selected = H axis at y=16. Sprites at (4,7) and (15,9).
    # Move axis from y=16 to y=9: up 7
    # Select sprite0, move right 7 down 7: (4,7) -> (11,14)
    # Select sprite1, move left 12 down 5: (15,9) -> (3,14)
    obs = execute(env, [1]*7 + [5] + [4]*7 + [2]*7 + [5] + [3]*12 + [2]*5)
    print(f'L3: completed={obs.levels_completed}')

    # --- Level 4 ---
    # Selected = H axis at y=3. U-shape at (4,6), bar at (6,10).
    # Move axis from y=3 to y=9: down 6
    # Select U, move right 7: (4,6) -> (11,6)
    # Select bar, move right 7 up 7: (6,10) -> (13,3)
    obs = execute(env, [2]*6 + [5] + [4]*7 + [5] + [4]*7 + [1]*7)
    print(f'L4: completed={obs.levels_completed}')

    # --- Level 5 ---
    # Selected = H axis at y=0. V axis at x=3. Sprite at (14,12).
    # Move H axis from y=0 to y=9: down 9
    # Select V axis, move from x=3 to x=8: right 5
    # Select sprite, move from (14,12) to (4,5): left 10, up 7
    obs = execute(env, [2]*9 + [5] + [4]*5 + [5] + [3]*10 + [1]*7)
    print(f'L5: completed={obs.levels_completed}')

    # --- Level 6 ---
    # Selected = H axis at y=0. V axis at x=7. T at (17,8). C at (14,3).
    # Move H axis from y=0 to y=11: down 11
    # Select V axis, move from x=7 to x=6: left 1
    # Select T, move from (17,8) to (2,12): left 15, down 4
    # Select C, move from (14,3) to (7,15): left 7, down 12
    obs = execute(env, [2]*11 + [5] + [3] + [5] + [3]*15 + [2]*4 + [5] + [3]*7 + [2]*12)
    print(f'L6: completed={obs.levels_completed}')

    # --- Level 7 ---
    # Selected = H axis at y=5. V axis at x=3. Zigzag at (17,13). Cross at (5,16).
    # Move H axis from y=5 to y=7: down 2
    # Select V axis, move from x=3 to x=12: right 9
    # Select zigzag, move from (17,13) to (15,1): left 2, up 12
    # Select cross, move from (5,16) to (8,10): right 3, up 6
    obs = execute(env, [2]*2 + [5] + [4]*9 + [5] + [3]*2 + [1]*12 + [5] + [4]*3 + [1]*6)
    print(f'L7: completed={obs.levels_completed}')

    # --- Level 8 ---
    # Selected = H axis at y=5. V axis at x=3. E-shape at (13,13). L-shape at (7,7).
    # Move H axis from y=5 to y=11: down 6
    # Select V axis, move from x=3 to x=12: right 9
    # Select E-shape, move from (13,13) to (4,6): left 9, up 7
    # Select L-shape, move from (7,7) to (16,3): right 9, up 4
    obs = execute(env, [2]*6 + [5] + [4]*9 + [5] + [3]*9 + [1]*7 + [5] + [4]*9 + [1]*4)
    print(f'L8: completed={obs.levels_completed}, state={obs.state.name}')

    levels_solved = obs.levels_completed
    print(f'\n{"="*60}')
    print(f'GAME_ID: ar25')
    print(f'LEVELS_SOLVED: {levels_solved}')
    print(f'TOTAL_LEVELS: {total_levels}')
    print(f'MECHANICS: Reflection/mirror puzzle. Sprites reflect across movable axis lines (vertical/horizontal). Reflections chain via BFS (depth 12). Goal: cover all dot markers with sprite reflections. Actions: move selected piece (1-4), cycle selection (5), click-select (6), undo (7). Step counter limits total moves.')
    print(f'KEY_LESSONS: (1) Dots exhibit 2-fold or 4-fold symmetry matching axis placement. (2) Find axis positions first by checking dot symmetry, then position sprites so originals+reflections cover all dots. (3) With 2 axes, reflections chain to produce 4-fold coverage. (4) Minimize total moves to stay within step budget. (5) Selection order matters: axes first (selected by default), then sprites via ACTION5 cycling.')
    print(f'{"="*60}')

    return levels_solved


if __name__ == '__main__':
    solve()
