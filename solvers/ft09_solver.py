#!/usr/bin/env python3
"""ft09 solver — Color-cycling puzzle (Lights Out variant).

Mechanics:
  - Grid of clickable sprites tagged "Hkx" (plain) or "NTi" (patterned), both "gOi"
  - Clicking a sprite cycles colors of neighboring sprites (and itself) according to a pattern
  - Hkx clicks: use level's irw pattern (default: only self)
  - NTi clicks: use sprite's own pixel pattern (6 marks affected neighbors)
  - Colors cycle through gqb list (e.g., [9,8] → 9→8→9, [9,8,12] → 9→8→12→9)
  - bsT constraint sprites define win condition:
    * center pixel [1][1] = target color
    * for each of 8 neighbors at offset ±4:
      if bsT pixel at that direction is 0 → neighbor must EQUAL target
      if bsT pixel at that direction is non-0 → neighbor must NOT EQUAL target
  - Win when all bsT constraints are satisfied
  - Timer (kCv) limits number of clicks
"""
import sys
import warnings
import logging
import itertools
import numpy as np
from copy import deepcopy

sys.path.insert(0, '/home/paolo/arc-agi/solver')
import arc_agi

warnings.filterwarnings('ignore')
logging.disable(logging.WARNING)

from universal_harness import grid_to_display, replay_solution


def analyze_level(game, level_idx):
    """Extract the puzzle structure for a level."""
    level = game._levels[level_idx]

    # Get sprites by tag
    bsT_sprites = level.get_sprites_by_tag("bsT")
    hkx_sprites = level.get_sprites_by_tag("Hkx")
    nti_sprites = level.get_sprites_by_tag("NTi")

    # Color cycle list
    gqb = level.get_data("cwU")
    if gqb is None:
        gqb = [9, 8]

    # Influence pattern for Hkx clicks
    irw = level.get_data("elp")
    if irw is None:
        irw = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]

    # All clickable sprites (Hkx + NTi)
    clickables = []
    for s in hkx_sprites:
        clickables.append(('Hkx', s))
    for s in nti_sprites:
        clickables.append(('NTi', s))

    # Build position -> clickable index mapping
    pos_to_idx = {}
    for i, (typ, s) in enumerate(clickables):
        pos_to_idx[(s.x, s.y)] = i

    n = len(clickables)
    n_colors = len(gqb)

    # Build influence matrix: click[i] affects which clickables
    # influence[i] = list of clickable indices affected
    GBS = [
        [(-1, -1), (0, -1), (1, -1)],
        [(-1, 0), (0, 0), (1, 0)],
        [(-1, 1), (0, 1), (1, 1)],
    ]

    influence = []
    for i, (typ, s) in enumerate(clickables):
        if typ == 'NTi':
            # NTi: affected based on sprite's own pixels (6 = affected)
            eHl = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
            for j in range(3):
                for k in range(3):
                    if s.pixels[j][k] == 6:
                        eHl[j][k] = 1
        else:
            eHl = irw

        affected = []
        for j in range(3):
            for k in range(3):
                if eHl[j][k] == 1:
                    dx, dy = GBS[j][k]
                    target_pos = (s.x + dx * 4, s.y + dy * 4)
                    if target_pos in pos_to_idx:
                        affected.append(pos_to_idx[target_pos])
        influence.append(affected)

    # Build constraints from bsT sprites
    constraints = []
    dirs = [
        (0, 0, -4, -4),   # [0][0] -> top-left
        (0, 1, 0, -4),    # [0][1] -> top
        (0, 2, 4, -4),    # [0][2] -> top-right
        (1, 0, -4, 0),    # [1][0] -> left
        (1, 2, 4, 0),     # [1][2] -> right
        (2, 0, -4, 4),    # [2][0] -> bottom-left
        (2, 1, 0, 4),     # [2][1] -> bottom
        (2, 2, 4, 4),     # [2][2] -> bottom-right
    ]

    for bs in bsT_sprites:
        target_color = int(bs.pixels[1][1])
        for py, px, dx, dy in dirs:
            pos = (bs.x + dx, bs.y + dy)
            if pos in pos_to_idx:
                cidx = pos_to_idx[pos]
                is_zero = bool(int(bs.pixels[py][px]) == 0)
                # if is_zero: clickable must have color == target_color
                # if not is_zero: clickable must have color != target_color
                constraints.append((cidx, target_color, is_zero))

    # Get initial colors (center pixel of each clickable)
    initial_colors = []
    for typ, s in clickables:
        initial_colors.append(int(s.pixels[1][1]))

    return {
        'clickables': clickables,
        'pos_to_idx': pos_to_idx,
        'n': n,
        'n_colors': n_colors,
        'gqb': gqb,
        'influence': influence,
        'constraints': constraints,
        'initial_colors': initial_colors,
    }


def simulate_clicks(info, click_counts):
    """Given click counts for each clickable, compute final colors."""
    n = info['n']
    gqb = info['gqb']
    n_colors = info['n_colors']

    # Start with initial color indices
    color_indices = []
    for c in info['initial_colors']:
        color_indices.append(gqb.index(c))

    # Apply click effects
    for i in range(n):
        if click_counts[i] > 0:
            for target in info['influence'][i]:
                color_indices[target] = (color_indices[target] + click_counts[i]) % n_colors

    # Convert back to colors
    final_colors = [gqb[ci] for ci in color_indices]
    return final_colors


def check_constraints(info, final_colors):
    """Check if all constraints are satisfied."""
    for cidx, target_color, must_equal in info['constraints']:
        if must_equal:
            if final_colors[cidx] != target_color:
                return False
        else:
            if final_colors[cidx] == target_color:
                return False
    return True


def solve_level_brute(info, max_total_clicks=None):
    """Brute force: try all combinations of click counts (mod n_colors)."""
    n = info['n']
    n_colors = info['n_colors']

    if max_total_clicks is None:
        max_total_clicks = 999

    # Each clickable can be clicked 0..n_colors-1 times (more is redundant)
    # For small n, enumerate all possibilities
    if n <= 12:
        best = None
        best_total = max_total_clicks + 1
        for combo in itertools.product(range(n_colors), repeat=n):
            total = sum(combo)
            if total >= best_total:
                continue
            counts = list(combo)
            final = simulate_clicks(info, counts)
            if check_constraints(info, final):
                if total < best_total:
                    best_total = total
                    best = counts
        return best
    return None


def solve_level_gf2(info):
    """For 2-color levels, solve as linear system over GF(2)."""
    n = info['n']
    n_colors = info['n_colors']
    gqb = info['gqb']

    if n_colors != 2:
        return None

    # Build target state: what each clickable's final color index should be
    # We need to figure out what each constraint requires
    # First, get initial color indices
    init_ci = []
    for c in info['initial_colors']:
        init_ci.append(gqb.index(c))

    # Build the influence matrix over GF(2)
    # A[j][i] = 1 if clicking i affects clickable j
    A = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in info['influence'][i]:
            A[j][i] = 1

    # For each constraint, determine what the target color index should be
    # Constraints: (cidx, target_color, must_equal)
    # For 2 colors, must_equal means final_color == target, !must_equal means != target
    # final_ci[cidx] = init_ci[cidx] + sum(A[cidx][i] * x[i]) mod 2
    # We need: final_color = gqb[final_ci]
    # must_equal: gqb[final_ci] == target → final_ci == gqb.index(target)
    # !must_equal: gqb[final_ci] != target → final_ci != gqb.index(target)

    # For 2 colors, each clickable has exactly one target (from must_equal constraints)
    # or is free / must avoid one value
    target_ci = [None] * n
    avoid_ci = [None] * n
    for cidx, target_color, must_equal in info['constraints']:
        tci = gqb.index(target_color)
        if must_equal:
            if target_ci[cidx] is not None and target_ci[cidx] != tci:
                return None  # Conflicting constraints
            target_ci[cidx] = tci
        else:
            avoid_ci[cidx] = tci

    # For avoid constraints, with 2 colors, not-X means must-be-(1-X)
    for i in range(n):
        if target_ci[i] is None and avoid_ci[i] is not None:
            target_ci[i] = 1 - avoid_ci[i]

    # Build system: for each constrained variable
    # init_ci[j] + sum(A[j][i] * x[i]) ≡ target_ci[j] (mod 2)
    # → sum(A[j][i] * x[i]) ≡ target_ci[j] - init_ci[j] (mod 2)
    constrained = [(j, target_ci[j]) for j in range(n) if target_ci[j] is not None]

    if not constrained:
        return [0] * n  # No constraints, do nothing

    m = len(constrained)
    # Build augmented matrix [A | b]
    mat = []
    for j, tci in constrained:
        row = [A[j][i] for i in range(n)]
        b = (tci - init_ci[j]) % 2
        row.append(b)
        mat.append(row)

    # Gaussian elimination over GF(2)
    rows = len(mat)
    cols = n
    pivot_col = [None] * rows
    r = 0
    for c in range(cols):
        # Find pivot
        found = None
        for rr in range(r, rows):
            if mat[rr][c] == 1:
                found = rr
                break
        if found is None:
            continue
        mat[r], mat[found] = mat[found], mat[r]
        pivot_col[r] = c
        for rr in range(rows):
            if rr != r and mat[rr][c] == 1:
                for cc in range(cols + 1):
                    mat[rr][cc] ^= mat[r][cc]
        r += 1

    # Check for inconsistency
    for rr in range(r, rows):
        if mat[rr][cols] == 1:
            return None  # No solution

    # Back-substitute, free variables = 0
    x = [0] * n
    for rr in range(r - 1, -1, -1):
        c = pivot_col[rr]
        if c is None:
            continue
        val = mat[rr][cols]
        for cc in range(c + 1, cols):
            val ^= mat[rr][cc] * x[cc]
        x[c] = val % 2

    return x


def mod_inverse(a, p):
    """Compute modular inverse of a mod p using extended Euclidean algorithm."""
    if a == 0:
        return None
    g, x, _ = extended_gcd(a % p, p)
    if g != 1:
        return None
    return x % p


def extended_gcd(a, b):
    if a == 0:
        return b, 0, 1
    g, x, y = extended_gcd(b % a, a)
    return g, y - (b // a) * x, x


def solve_level_modular(info):
    """For n-color levels (prime), solve as linear system over GF(p)."""
    n = info['n']
    n_colors = info['n_colors']
    gqb = info['gqb']
    p = n_colors

    # Build initial color indices
    init_ci = [gqb.index(c) for c in info['initial_colors']]

    # Build influence matrix
    A = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in info['influence'][i]:
            A[j][i] = (A[j][i] + 1) % p

    # Determine target for each clickable
    target_ci = [None] * n
    avoid_ci = [set() for _ in range(n)]
    for cidx, target_color, must_equal in info['constraints']:
        tci = gqb.index(target_color)
        if must_equal:
            if target_ci[cidx] is not None and target_ci[cidx] != tci:
                # Conflicting must-equal constraints - try all possible targets
                pass
            target_ci[cidx] = tci
        else:
            avoid_ci[cidx].add(tci)

    # For unconstrained-by-equality: if n_colors-1 values are avoided, the remaining is forced
    for i in range(n):
        if target_ci[i] is None and len(avoid_ci[i]) == p - 1:
            remaining = set(range(p)) - avoid_ci[i]
            target_ci[i] = remaining.pop()

    # For variables with avoid constraints but no equality constraint, try all possibilities
    # Collect free variables (with avoid but no target)
    free_vars = []
    for i in range(n):
        if target_ci[i] is None and len(avoid_ci[i]) > 0:
            possible = list(set(range(p)) - avoid_ci[i])
            free_vars.append((i, possible))

    # If there are free variables, enumerate all their possible values
    def try_solve_with_targets(target_ci_local):
        constrained = [(j, target_ci_local[j]) for j in range(n) if target_ci_local[j] is not None]
        if not constrained:
            return [0] * n

        # Build augmented matrix
        mat = []
        for j, tci in constrained:
            row = [A[j][i] for i in range(n)]
            b = (tci - init_ci[j]) % p
            row.append(b)
            mat.append(row)

        # Gaussian elimination over GF(p)
        rows = len(mat)
        cols = n
        pivot_col = [None] * rows
        r = 0
        for c in range(cols):
            found = None
            for rr in range(r, rows):
                if mat[rr][c] % p != 0:
                    found = rr
                    break
            if found is None:
                continue
            mat[r], mat[found] = mat[found], mat[r]
            pivot_col[r] = c

            inv = mod_inverse(mat[r][c], p)
            if inv is None:
                continue
            for cc in range(cols + 1):
                mat[r][cc] = (mat[r][cc] * inv) % p

            for rr in range(rows):
                if rr != r and mat[rr][c] % p != 0:
                    factor = mat[rr][c]
                    for cc in range(cols + 1):
                        mat[rr][cc] = (mat[rr][cc] - factor * mat[r][cc]) % p
            r += 1

        # Check consistency
        for rr in range(r, rows):
            if mat[rr][cols] % p != 0:
                return None

        # Back-substitute, free variables = 0
        x = [0] * n
        for rr in range(r - 1, -1, -1):
            c = pivot_col[rr]
            if c is None:
                continue
            val = mat[rr][cols]
            for cc in range(c + 1, cols):
                val = (val - mat[rr][cc] * x[cc]) % p
            x[c] = val % p

        # Verify solution satisfies avoid constraints
        final = simulate_clicks(info, x)
        if check_constraints(info, final):
            return x
        return None

    # If no free variables, just solve directly
    if not free_vars:
        return try_solve_with_targets(target_ci)

    # Enumerate free variable possibilities
    from itertools import product as iprod
    possible_values = [fv[1] for fv in free_vars]
    free_indices = [fv[0] for fv in free_vars]

    best = None
    best_total = 999999
    for combo in iprod(*possible_values):
        tc = list(target_ci)
        for idx, val in zip(free_indices, combo):
            tc[idx] = val
        sol = try_solve_with_targets(tc)
        if sol is not None:
            total = sum(sol)
            if total < best_total:
                best_total = total
                best = sol
                if total == 0:
                    break

    return best


def solve_with_bfs(env, game, level_solutions, level_idx, info, max_depth=8):
    """BFS solver as fallback."""
    from universal_harness import bfs_solve

    cam = game.camera
    click_coords = []
    for typ, s in info['clickables']:
        dx, dy = grid_to_display(s.x + 1, s.y + 1, cam)
        click_coords.append((dx, dy))

    solution, obs = bfs_solve(env, level_solutions, click_coords, level_idx + 1, max_depth=max_depth)
    return solution, obs


def clicks_to_sequence(info, click_counts, game):
    """Convert click counts to a sequence of display coordinates."""
    cam = game.camera
    seq = []
    for i, count in enumerate(click_counts):
        typ, s = info['clickables'][i]
        dx, dy = grid_to_display(s.x + 1, s.y + 1, cam)
        for _ in range(count):
            seq.append((dx, dy))
    return seq


def solve_all():
    import sys
    sys.stdout.reconfigure(line_buffering=True)

    arc_inst = arc_agi.Arcade()
    env = arc_inst.make("ft09")
    obs = env.reset()
    obs = env.step(6)  # START

    game = env._game
    level_solutions = {}
    total_levels = len(game._levels)

    print(f"ft09: {total_levels} levels")
    print(f"Camera: {game.camera.x},{game.camera.y} {game.camera.width}x{game.camera.height}")

    for level_idx in range(total_levels):
        print(f"\n--- Level {level_idx} ({game._levels[level_idx].name}) ---")

        # Analyze current level
        info = analyze_level(game, level_idx)
        print(f"  Clickables: {info['n']} (Hkx+NTi)")
        print(f"  Colors: {info['gqb']} ({info['n_colors']})")
        print(f"  Constraints: {len(info['constraints'])}")

        # Print initial colors
        init_colors = info['initial_colors']
        print(f"  Initial colors: {init_colors}")

        # Try analytical solve first
        solution_counts = None

        if info['n_colors'] == 2:
            solution_counts = solve_level_gf2(info)
            if solution_counts:
                print(f"  GF(2) solution: {solution_counts} (total clicks: {sum(solution_counts)})")

        if solution_counts is None:
            solution_counts = solve_level_modular(info)
            if solution_counts:
                print(f"  Modular solution: {solution_counts} (total clicks: {sum(solution_counts)})")

        if solution_counts is not None:
            seq = clicks_to_sequence(info, solution_counts, game)
            print(f"  Click sequence ({len(seq)} clicks): {seq}")

            # Execute
            for dx, dy in seq:
                obs = env.step(6, data={"x": dx, "y": dy})

            if obs.levels_completed > level_idx:
                print(f"  SOLVED level {level_idx}!")
                level_solutions[level_idx] = seq
            else:
                print(f"  Analytical solution didn't work, trying BFS...")
                # Reset and replay
                obs = env.reset()
                obs = env.step(6)
                for li in sorted(level_solutions.keys()):
                    for click in level_solutions[li]:
                        obs = env.step(6, data={"x": click[0], "y": click[1]})

                # BFS
                sol, obs = solve_with_bfs(env, game, level_solutions, level_idx, info)
                if sol:
                    level_solutions[level_idx] = sol
                    print(f"  BFS SOLVED level {level_idx}!")
                else:
                    print(f"  FAILED level {level_idx}")
                    break
        else:
            print(f"  No analytical solution, trying BFS...")
            sol, obs = solve_with_bfs(env, game, level_solutions, level_idx, info)
            if sol:
                level_solutions[level_idx] = sol
                print(f"  BFS SOLVED level {level_idx}!")
            else:
                print(f"  FAILED level {level_idx}")
                break

    levels_solved = len(level_solutions)
    print(f"\n{'='*60}")
    print(f"GAME_ID: ft09")
    print(f"LEVELS_SOLVED: {levels_solved}")
    print(f"TOTAL_LEVELS: {total_levels}")
    print(f"MECHANICS: Color-cycling Lights Out puzzle. Click Hkx/NTi sprites to cycle neighbor colors through gqb list. bsT constraint sprites define target: pixel==0 means neighbor must match center color, non-0 means must differ. Timer limits clicks.")
    print(f"KEY_LESSONS: Linear algebra over GF(n) solves color-cycling puzzles. NTi sprites have custom influence patterns (6-pixels). Constraints encode both equality and inequality requirements.")

    return levels_solved, total_levels


if __name__ == "__main__":
    solve_all()
