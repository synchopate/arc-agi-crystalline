#!/usr/bin/env python3
"""ARC-AGI-3 r11l Solver v2 — Sequential move planning with barrier awareness.

Key insight: each piece move triggers a barrier collision check on ALL canvases.
If any canvas collides with a barrier, the moved piece BOUNCES BACK.
So we must plan moves where every intermediate canvas state is barrier-safe.

The animation runs entirely within one env.step() call (havofgepjpl=1).
No need for extra wait ticks.
"""

import sys
import arc_agi
import numpy as np
from itertools import permutations
from typing import List, Dict, Tuple, Set, Optional


def is_wall_blocked(game, piece, x, y) -> bool:
    """Check if piece at (x,y) collides with any wall."""
    game.wiayqaumjug = piece
    blocked = game.gabrtablhx(x, y)
    game.wiayqaumjug = None
    return blocked


def compute_canvas_pos(pieces_positions, pw, ph, cw, ch):
    """Compute canvas position from piece positions (centroid formula)."""
    n = len(pieces_positions)
    off_x = pw // 2
    off_y = ph // 2
    sum_cx = sum(x + off_x for x, y in pieces_positions)
    sum_cy = sum(y + off_y for x, y in pieces_positions)
    return sum_cx // n - cw // 2, sum_cy // n - ch // 2


def canvas_hits_target(canvas, target, cx, cy) -> bool:
    """Check if canvas at (cx,cy) collides with target."""
    old_x, old_y = canvas.x, canvas.y
    canvas.set_position(cx, cy)
    hits = canvas.collides_with(target)
    canvas.set_position(old_x, old_y)
    return hits


def build_safe_canvas_set(canvas, barriers) -> Set[Tuple[int, int]]:
    """Find all canvas positions that don't collide with barriers."""
    safe = set()
    old_x, old_y = canvas.x, canvas.y
    for cy in range(64 - canvas.height + 1):
        for cx in range(64 - canvas.width + 1):
            canvas.set_position(cx, cy)
            if not any(canvas.collides_with(b) for b in barriers):
                safe.add((cx, cy))
    canvas.set_position(old_x, old_y)
    return safe


def build_free_positions(game, piece) -> Set[Tuple[int, int]]:
    """Find all positions where piece doesn't collide with walls."""
    free = set()
    for y in range(64 - piece.height + 1):
        for x in range(64 - piece.width + 1):
            if not is_wall_blocked(game, piece, x, y):
                free.add((x, y))
    return free


def move_piece(env, piece, dest_x, dest_y):
    """Select piece and click destination. Returns (success, description, obs)."""
    old_x, old_y = piece.x, piece.y
    obs = env.step(6, data={"x": piece.x + piece.width // 2,
                            "y": piece.y + piece.height // 2})
    obs = env.step(6, data={"x": dest_x + piece.width // 2,
                            "y": dest_y + piece.height // 2})
    moved = (piece.x != old_x or piece.y != old_y)
    desc = f"({old_x},{old_y})→({piece.x},{piece.y})" if moved else f"BOUNCE@({old_x},{old_y})"
    return moved, desc, obs


def check_sequential_safety(pos, current_positions, order, pw, ph, cw, ch, safe_canvas,
                            other_pieces_positions=None):
    """Check if moving pieces in given order keeps canvas safe at every step.
    Also checks that no piece's destination click would hit another piece already there,
    including pieces from OTHER groups (other_pieces_positions).
    """
    temp = list(current_positions)
    for idx in order:
        if temp[idx] == pos[idx]:
            continue
        dest = pos[idx]
        # Check: clicking at dest center must not hit another piece already there
        dest_cx = dest[0] + pw // 2
        dest_cy = dest[1] + ph // 2
        # Check against same-group pieces
        for j, (px, py) in enumerate(temp):
            if j == idx:
                continue
            if px <= dest_cx < px + pw and py <= dest_cy < py + ph:
                return False
        # Check against other-group pieces
        if other_pieces_positions:
            for (px, py) in other_pieces_positions:
                if px <= dest_cx < px + pw and py <= dest_cy < py + ph:
                    return False
        temp[idx] = dest
        cx, cy = compute_canvas_pos(temp, pw, ph, cw, ch)
        if (cx, cy) not in safe_canvas:
            return False
    return True


def positions_are_unique(pos, pw=5, ph=5, other_positions=None):
    """Check that no two positions overlap (would block click selection).
    Also checks against other_positions (pieces from other groups).
    """
    all_pos = list(pos)
    if other_positions:
        all_pos.extend(other_positions)
    for i in range(len(pos)):
        for j in range(len(all_pos)):
            if i == j:
                continue
            # Check if clicking center of pos[i] would land inside pos[j]
            ci_x = pos[i][0] + pw // 2
            ci_y = pos[i][1] + ph // 2
            if all_pos[j][0] <= ci_x < all_pos[j][0] + pw and all_pos[j][1] <= ci_y < all_pos[j][1] + ph:
                return False
    return True


# ═══════════════════════════════════════════
# 2-PIECE SOLVER
# ═══════════════════════════════════════════

def find_2piece_solutions(free_positions, safe_canvas, pw, ph, cw, ch,
                          sum_cx_range, sum_cy_range, current_positions,
                          other_pieces_positions=None):
    off_x, off_y = pw // 2, ph // 2
    solutions = []

    for x0, y0 in free_positions:
        c0x, c0y = x0 + off_x, y0 + off_y
        for scx in range(sum_cx_range[0], sum_cx_range[1] + 1):
            x1 = scx - c0x - off_x
            for scy in range(sum_cy_range[0], sum_cy_range[1] + 1):
                y1 = scy - c0y - off_y
                if (x1, y1) not in free_positions:
                    continue
                pos = [(x0, y0), (x1, y1)]
                cx, cy = compute_canvas_pos(pos, pw, ph, cw, ch)
                if (cx, cy) not in safe_canvas:
                    continue
                for order in [[0, 1], [1, 0]]:
                    if check_sequential_safety(pos, current_positions, order, pw, ph, cw, ch, safe_canvas, other_pieces_positions):
                        solutions.append((pos, order))
                        if len(solutions) >= 3:
                            return solutions
    return solutions


# ═══════════════════════════════════════════
# 3-PIECE SOLVER
# ═══════════════════════════════════════════

def find_3piece_solutions(free_positions, safe_canvas, pw, ph, cw, ch,
                          sum_cx_range, sum_cy_range, current_positions,
                          other_pieces_positions=None):
    off_x, off_y = pw // 2, ph // 2
    n = 3
    free_list = list(free_positions)
    free_by_y = {}
    for x, y in free_list:
        free_by_y.setdefault(y, []).append(x)

    pos_sx_min = sum_cx_range[0] - n * off_x
    pos_sx_max = sum_cx_range[1] - n * off_x
    pos_sy_min = sum_cy_range[0] - n * off_y
    pos_sy_max = sum_cy_range[1] - n * off_y

    solutions = []
    for x0, y0 in free_list:
        if solutions:
            break
        for x1, y1 in free_list:
            p2y_min = pos_sy_min - y0 - y1
            p2y_max = pos_sy_max - y0 - y1
            p2x_min = pos_sx_min - x0 - x1
            p2x_max = pos_sx_max - x0 - x1

            for p2y in range(max(0, p2y_min), min(64 - ph, p2y_max) + 1):
                if p2y not in free_by_y:
                    continue
                for p2x in free_by_y[p2y]:
                    if not (p2x_min <= p2x <= p2x_max):
                        continue
                    pos = [(x0, y0), (x1, y1), (p2x, p2y)]
                    cx, cy = compute_canvas_pos(pos, pw, ph, cw, ch)
                    if (cx, cy) not in safe_canvas:
                        continue
                    for order in [[0,1,2],[0,2,1],[1,0,2],[1,2,0],[2,0,1],[2,1,0]]:
                        if check_sequential_safety(pos, current_positions, order, pw, ph, cw, ch, safe_canvas, other_pieces_positions):
                            solutions.append((pos, order))
                            return solutions
            if solutions:
                break
    return solutions


# ═══════════════════════════════════════════
# 4-PIECE SOLVER (meet in the middle)
# ═══════════════════════════════════════════

def find_4piece_solutions(free_positions, safe_canvas, pw, ph, cw, ch,
                          sum_cx_range, sum_cy_range, current_positions,
                          other_pieces_positions=None):
    """Meet-in-the-middle: precompute pair sums, then match."""
    off_x, off_y = pw // 2, ph // 2
    n = 4
    free_list = list(free_positions)

    # Total center sum range
    total_cx_min, total_cx_max = sum_cx_range
    total_cy_min, total_cy_max = sum_cy_range

    # Build half1: all (c0+c1) sums → list of (p0, p1) pairs
    print(f"      Building pair sums ({len(free_list)} free positions)...")
    half1 = {}  # (sum_cx_01, sum_cy_01) → [(p0, p1), ...]
    for i, (x0, y0) in enumerate(free_list):
        c0x, c0y = x0 + off_x, y0 + off_y
        # Compute valid range for c1
        c1x_min = total_cx_min - c0x - 2 * (64 - pw + off_x)  # rough lower bound
        c1x_max = total_cx_max - c0x

        for x1, y1 in free_list:
            c1x, c1y = x1 + off_x, y1 + off_y
            s01x = c0x + c1x
            s01y = c0y + c1y
            # Check if remaining half (c2+c3) can reach needed sum
            need_23x_min = total_cx_min - s01x
            need_23x_max = total_cx_max - s01x
            need_23y_min = total_cy_min - s01y
            need_23y_max = total_cy_max - s01y
            # c2 and c3 each in [off_x, 64-pw+off_x], so c2+c3 in [2*off_x, 2*(64-pw+off_x)]
            min_half = 2 * off_x
            max_half_x = 2 * (64 - pw + off_x)
            max_half_y = 2 * (64 - ph + off_y)
            if need_23x_max < min_half or need_23x_min > max_half_x:
                continue
            if need_23y_max < min_half or need_23y_min > max_half_y:
                continue
            key = (s01x, s01y)
            if key not in half1:
                half1[key] = []
            half1[key].append(((x0, y0), (x1, y1)))
            if len(half1[key]) > 20:  # limit per bucket
                half1[key] = half1[key][:20]

        if i % 500 == 0 and i > 0:
            print(f"        p0 #{i}/{len(free_list)}, {len(half1)} pair-sum buckets")

    print(f"      {len(half1)} pair-sum buckets")

    # Search half2: for each (p2, p3), check if matching half1 exists
    solutions = []
    checked = 0
    for x2, y2 in free_list:
        if solutions:
            break
        c2x, c2y = x2 + off_x, y2 + off_y
        for x3, y3 in free_list:
            c3x, c3y = x3 + off_x, y3 + off_y
            s23x = c2x + c3x
            s23y = c2y + c3y

            # Check all valid total sums
            for tsx in range(total_cx_min, total_cx_max + 1):
                need_01x = tsx - s23x
                for tsy in range(total_cy_min, total_cy_max + 1):
                    need_01y = tsy - s23y
                    key = (need_01x, need_01y)
                    if key not in half1:
                        continue

                    for (p0, p1) in half1[key]:
                        pos = [p0, p1, (x2, y2), (x3, y3)]
                        if not positions_are_unique(pos, pw, ph, other_pieces_positions):
                            continue
                        cx, cy = compute_canvas_pos(pos, pw, ph, cw, ch)
                        if (cx, cy) not in safe_canvas:
                            continue

                        # Try orderings (only a few — try most promising first)
                        for order in [[0,1,2,3],[3,2,1,0],[0,2,1,3],[1,0,3,2],[2,3,0,1],[3,1,2,0]]:
                            if check_sequential_safety(pos, current_positions, order, pw, ph, cw, ch, safe_canvas, other_pieces_positions):
                                solutions.append((pos, order))
                                return solutions

            checked += 1
            if checked % 100000 == 0:
                print(f"        half2 checked {checked}")
            if solutions:
                break

    return solutions


# ═══════════════════════════════════════════
# GENERIC N-PIECE SOLVER (fallback)
# ═══════════════════════════════════════════

def find_npiece_solutions(n, free_positions, safe_canvas, pw, ph, cw, ch,
                          sum_cx_range, sum_cy_range, current_positions,
                          other_pieces_positions=None):
    """Generic solver: iterate n-1 pieces, compute last from constraint."""
    if n == 2:
        return find_2piece_solutions(free_positions, safe_canvas, pw, ph, cw, ch,
                                     sum_cx_range, sum_cy_range, current_positions, other_pieces_positions)
    elif n == 3:
        return find_3piece_solutions(free_positions, safe_canvas, pw, ph, cw, ch,
                                     sum_cx_range, sum_cy_range, current_positions, other_pieces_positions)
    elif n == 4:
        return find_4piece_solutions(free_positions, safe_canvas, pw, ph, cw, ch,
                                     sum_cx_range, sum_cy_range, current_positions, other_pieces_positions)
    else:
        print(f"    Unsupported piece count: {n}")
        return []


# ═══════════════════════════════════════════
# GROUP SOLVER
# ═══════════════════════════════════════════

def solve_group(game, env, gname, canvas, target, pieces, barriers, safe_canvas, free_positions):
    """Solve a group by finding target positions with safe sequential moves.
    Returns (actions_used, solved, obs).
    """
    n = len(pieces)
    pw, ph = pieces[0].width, pieces[0].height
    cw, ch = canvas.width, canvas.height
    current_positions = [(p.x, p.y) for p in pieces]
    obs = None

    # Collect positions of ALL other pieces (from other groups) to avoid click interference
    my_pieces_set = set(id(p) for p in pieces)
    other_pieces_positions = []
    for gn, gd in game.kacotwgjcyq.items():
        for p in gd["lecfirgqbwunn"]:
            if id(p) not in my_pieces_set and p in game.bbijaigbknc:
                other_pieces_positions.append((p.x, p.y))

    print(f"  Solving '{gname}': {n} pieces, canvas@({canvas.x},{canvas.y}), target@({target.x},{target.y})")
    print(f"    Other pieces to avoid: {len(other_pieces_positions)} positions")

    # Find target canvas positions that collide with target and are safe
    target_canvas_positions = []
    for cx, cy in safe_canvas:
        if canvas_hits_target(canvas, target, cx, cy):
            target_canvas_positions.append((cx, cy))
    print(f"    Target-hitting safe canvas positions: {len(target_canvas_positions)}")

    if not target_canvas_positions:
        print(f"    ERROR: no safe canvas positions hit target!")
        return 0, False, obs

    # Search for solutions across target canvas positions
    best = None
    for tcx, tcy in target_canvas_positions:
        centroid_x = tcx + cw // 2
        centroid_y = tcy + ch // 2
        sum_cx_range = (centroid_x * n, centroid_x * n + n - 1)
        sum_cy_range = (centroid_y * n, centroid_y * n + n - 1)

        solutions = find_npiece_solutions(
            n, free_positions, safe_canvas, pw, ph, cw, ch,
            sum_cx_range, sum_cy_range, current_positions, other_pieces_positions
        )

        if solutions:
            best = solutions[0]
            break

    if not best:
        print(f"    No valid sequential solution found!")
        return 0, False, obs

    # Execute
    sol_positions, sol_order = best
    print(f"    Solution: order={sol_order}")
    for i in range(n):
        print(f"      P{i}: ({pieces[i].x},{pieces[i].y})→{sol_positions[i]}")
    # Re-verify sequential safety with debug
    temp = list(current_positions)
    for idx in sol_order:
        if temp[idx] == sol_positions[idx]:
            continue
        temp[idx] = sol_positions[idx]
        cx, cy = compute_canvas_pos(temp, pw, ph, cw, ch)
        in_safe = (cx, cy) in safe_canvas
        print(f"      After P{idx}: canvas@({cx},{cy}) safe={in_safe}")

    total_actions = 0
    for i in sol_order:
        bx, by = sol_positions[i]
        p = pieces[i]
        if p.x == bx and p.y == by:
            continue
        success, desc, obs = move_piece(env, p, bx, by)
        total_actions += 2
        # Show actual canvas after move
        actual_cx, actual_cy = canvas.x, canvas.y
        print(f"    P{i}: {desc} {'OK' if success else 'FAIL'} canvas@({actual_cx},{actual_cy})")
        if not success:
            # Debug: check ALL canvases
            for gn, gd in game.kacotwgjcyq.items():
                cv = gd["roduyfsmiznvg"]
                if not cv: continue
                for b in barriers:
                    col = cv.collides_with(b)
                    if col:
                        print(f"      {gn} canvas@({cv.x},{cv.y}) COLLIDES {b.name}!")
            return total_actions, False, obs

    collides = canvas.collides_with(target)
    print(f"    Result: canvas({canvas.x},{canvas.y}) {'HIT' if collides else 'MISS'} target({target.x},{target.y})")
    return total_actions, collides, obs


# ═══════════════════════════════════════════
# COLLECTIBLE SOLVER (L5-L6: whkxtx + puukul)
# ═══════════════════════════════════════════

def find_collection_positions(canvas, puukul):
    """Find all canvas positions where canvas collides with puukul."""
    positions = set()
    old_x, old_y = canvas.x, canvas.y
    # Only need to check near puukul (within canvas+puukul size range)
    for cy in range(max(0, puukul.y - canvas.height + 1), min(60, puukul.y + puukul.height)):
        for cx in range(max(0, puukul.x - canvas.width + 1), min(60, puukul.x + puukul.width)):
            canvas.set_position(cx, cy)
            if canvas.collides_with(puukul):
                positions.add((cx, cy))
    canvas.set_position(old_x, old_y)
    return positions


def find_piece_positions_for_canvas(canvas_target_positions, free_positions, pieces,
                                    pw, ph, cw, ch, other_all_positions):
    """Find piece positions that place canvas at one of the target positions.
    Returns list of (canvas_pos, piece_positions, order)."""
    n = len(pieces)
    off_x, off_y = pw // 2, ph // 2
    current = [(p.x, p.y) for p in pieces]
    # No barriers → all canvas positions are "safe"
    all_safe = {(cx, cy) for cy in range(64) for cx in range(64)}

    for tcx, tcy in canvas_target_positions:
        centroid_x = tcx + cw // 2
        centroid_y = tcy + ch // 2
        sum_cx_range = (centroid_x * n, centroid_x * n + n - 1)
        sum_cy_range = (centroid_y * n, centroid_y * n + n - 1)

        solutions = find_npiece_solutions(
            n, free_positions, all_safe, pw, ph, cw, ch,
            sum_cx_range, sum_cy_range, current, other_all_positions
        )
        if solutions:
            return (tcx, tcy), solutions[0]

    return None, None


def solve_collectible_level(game, env):
    """Solve a level with whkxtx canvases + puukul collectibles.
    Returns obs after solving (or attempting).
    """
    import numpy as np
    groups = game.kacotwgjcyq
    obs = None

    # Find whkxtx canvases (have canvas + pieces, no target)
    canvases = {}
    for gname, data in groups.items():
        c = data["roduyfsmiznvg"]
        pieces = [p for p in data["lecfirgqbwunn"] if p in game.bbijaigbknc]
        if c and pieces and not data["gosubdcyegamj"]:
            canvases[gname] = {"canvas": c, "pieces": pieces}

    # Find targets (have target, no canvas)
    targets = {}
    for gname, data in groups.items():
        t = data["gosubdcyegamj"]
        if t and not data["roduyfsmiznvg"] and "dirwzt" not in gname:
            px = np.array(t.pixels)
            colors = {int(v) for v in px.flatten() if v > 0}
            targets[gname] = {"target": t, "colors": colors}

    # Collectibles
    puukuls = game.owuypsqbino[:]
    puukul_colors = {}
    for s in puukuls:
        px = np.array(s.pixels)
        colors = {int(v) for v in px.flatten() if v > 0}
        puukul_colors[s.name] = colors

    print(f"  Collectible level: {len(canvases)} canvases, {len(targets)} targets, {len(puukuls)} puukuls")

    if not canvases or not targets:
        print(f"  No canvases or targets!")
        return obs

    # Build free positions
    first_pieces = list(canvases.values())[0]["pieces"]
    free_positions = build_free_positions(game, first_pieces[0])
    print(f"  {len(free_positions)} free positions")

    # Determine which puukuls each canvas should collect to match a target
    # Try all assignments of canvases to targets
    canvas_names = list(canvases.keys())
    target_names = list(targets.keys())

    # For each target, find which puukuls provide the needed colors
    target_puukul_map = {}
    for tname, tdata in targets.items():
        needed = tdata["colors"]
        matching_puukuls = []
        for s in puukuls:
            p_colors = puukul_colors[s.name]
            if p_colors & needed:  # puukul has at least one needed color
                matching_puukuls.append(s)
        target_puukul_map[tname] = matching_puukuls
        print(f"  Target '{tname}' needs {needed}, matched puukuls: {[s.name for s in matching_puukuls]}")

    # Simple assignment: try each canvas → target pairing
    from itertools import permutations
    for target_perm in permutations(target_names):
        assignment = list(zip(canvas_names, target_perm))
        print(f"\n  Trying assignment: {[(c, t) for c, t in assignment]}")

        # Check feasibility: each canvas collects puukuls for its assigned target
        feasible = True
        plan = []
        for cname, tname in assignment:
            cdata = canvases[cname]
            tdata = targets[tname]
            needed_colors = tdata["colors"]
            # Find puukuls that provide these colors
            needed_puukuls = []
            for s in puukuls:
                if puukul_colors[s.name] & needed_colors:
                    needed_puukuls.append(s)
            # Check: collected colors cover all needed
            collected_colors = set()
            for s in needed_puukuls:
                collected_colors |= puukul_colors[s.name]
            if not needed_colors.issubset(collected_colors):
                feasible = False
                break
            plan.append((cname, tname, needed_puukuls))

        if not feasible:
            continue

        # Execute the plan
        all_ok = True
        for cname, tname, needed_puukuls in plan:
            cdata = canvases[cname]
            tdata = targets[tname]
            canvas = cdata["canvas"]
            pieces = cdata["pieces"]
            target = tdata["target"]
            pw, ph = pieces[0].width, pieces[0].height
            cw, ch = canvas.width, canvas.height

            print(f"\n  Canvas '{cname}' → Target '{tname}'")
            print(f"    Collecting {len(needed_puukuls)} puukuls, then target at ({target.x},{target.y})")

            # Collect all other pieces positions
            my_ids = set(id(p) for p in pieces)
            other_pos = [(p.x, p.y) for gn, gd in groups.items()
                         for p in gd["lecfirgqbwunn"]
                         if id(p) not in my_ids and p in game.bbijaigbknc]

            # Step through: collect each puukul, then go to target
            for puukul in needed_puukuls:
                if puukul not in game.owuypsqbino:
                    print(f"    Puukul '{puukul.name}' already collected, skip")
                    continue

                # Find canvas positions that overlap this puukul
                collect_positions = find_collection_positions(canvas, puukul)
                print(f"    Collecting '{puukul.name}' at ({puukul.x},{puukul.y}): {len(collect_positions)} collection positions")

                if not collect_positions:
                    print(f"    ERROR: no collection positions!")
                    all_ok = False
                    break

                # Find piece positions for one of these canvas positions
                canvas_pos, solution = find_piece_positions_for_canvas(
                    list(collect_positions), free_positions, pieces,
                    pw, ph, cw, ch, other_pos
                )
                if not solution:
                    print(f"    ERROR: no valid piece positions for collection!")
                    all_ok = False
                    break

                sol_positions, sol_order = solution
                print(f"    → Canvas to ({canvas_pos}), order={sol_order}")

                # Execute moves
                for i in sol_order:
                    bx, by = sol_positions[i]
                    p = pieces[i]
                    if p.x == bx and p.y == by:
                        continue
                    success, desc, obs = move_piece(env, p, bx, by)
                    print(f"      P{i}: {desc} {'OK' if success else 'FAIL'}")
                    if not success:
                        all_ok = False
                        break
                if not all_ok:
                    break

                # Verify collection happened
                collected = puukul not in game.owuypsqbino
                print(f"    Collected? {collected}")
                # Update other_pos after pieces moved
                other_pos = [(p.x, p.y) for gn, gd in groups.items()
                             for p in gd["lecfirgqbwunn"]
                             if id(p) not in my_ids and p in game.bbijaigbknc]

            if not all_ok:
                break

            # Now position canvas on target
            # Find canvas positions that overlap target AND are valid
            target_positions = set()
            old_cx, old_cy = canvas.x, canvas.y
            for cy in range(max(0, target.y - ch + 1), min(60, target.y + target.height)):
                for cx in range(max(0, target.x - cw + 1), min(60, target.x + target.width)):
                    canvas.set_position(cx, cy)
                    if canvas.collides_with(target):
                        target_positions.add((cx, cy))
            canvas.set_position(old_cx, old_cy)
            print(f"    Positioning on target: {len(target_positions)} valid canvas positions")

            # Also check color match
            canvas_colors = {int(v) for v in np.array(canvas.pixels).flatten() if v > 0}
            print(f"    Canvas colors after collection: {canvas_colors}")
            print(f"    Target needs: {tdata['colors']}")

            canvas_pos, solution = find_piece_positions_for_canvas(
                list(target_positions), free_positions, pieces,
                pw, ph, cw, ch, other_pos
            )
            if not solution:
                print(f"    ERROR: no valid positions for target!")
                all_ok = False
                break

            sol_positions, sol_order = solution
            print(f"    → Canvas to ({canvas_pos}), order={sol_order}")

            for i in sol_order:
                bx, by = sol_positions[i]
                p = pieces[i]
                if p.x == bx and p.y == by:
                    continue
                success, desc, obs = move_piece(env, p, bx, by)
                print(f"      P{i}: {desc} {'OK' if success else 'FAIL'}")
                if not success:
                    all_ok = False
                    break
            if not all_ok:
                break

            # Update other_pos
            other_pos = [(p.x, p.y) for gn, gd in groups.items()
                         for p in gd["lecfirgqbwunn"]
                         if id(p) not in my_ids and p in game.bbijaigbknc]

        if all_ok:
            print(f"\n  All canvases positioned!")
            break

    return obs


# ═══════════════════════════════════════════
# MAIN SOLVER
# ═══════════════════════════════════════════

def solve():
    arc = arc_agi.Arcade()
    env = arc.make("r11l")
    obs = env.reset()
    game = env._game

    obs = env.step(6)  # START
    print(f"Game: r11l, levels: {obs.win_levels}")

    for level in range(1, obs.win_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        print(f"\n{'='*60}")
        print(f"LEVEL {level}/{obs.win_levels} (completed so far: {obs.levels_completed})")
        print(f"{'='*60}")

        groups = game.kacotwgjcyq
        barriers = [s for s in game.current_level.get_sprites() if s.name.startswith("defgjl")]

        if barriers:
            for b in barriers:
                print(f"  Barrier: {b.name} at ({b.x},{b.y}) {b.width}x{b.height}")

        # Check for collectible level (whkxtx + puukul mechanic)
        has_collectibles = len(game.owuypsqbino) > 0 or len(game.bulmhgivatv) > 0
        has_canvas_without_target = any(
            data["roduyfsmiznvg"] and not data["gosubdcyegamj"]
            and [p for p in data["lecfirgqbwunn"] if p in game.bbijaigbknc]
            for data in groups.values()
        )
        if has_collectibles or has_canvas_without_target:
            print(f"  Collectible level detected!")
            new_obs = solve_collectible_level(game, env)
            if new_obs:
                obs = new_obs
            obs = env.step(6, data={"x": -1000, "y": -1000})
            print(f"\n  Level {level}: completed={obs.levels_completed}, state={obs.state.name}")
            if obs.levels_completed >= level:
                print(f"  SOLVED!")
            continue

        # Build safe canvas and free positions if barriers present
        safe_canvas = None
        free_positions = None

        if barriers:
            # Use first group's canvas to compute safe positions (all canvases same size)
            for data in groups.values():
                if data["roduyfsmiznvg"]:
                    print(f"  Computing safe canvas positions...")
                    safe_canvas = build_safe_canvas_set(data["roduyfsmiznvg"], barriers)
                    print(f"  {len(safe_canvas)} safe positions")
                    break
            for data in groups.values():
                pieces = [p for p in data["lecfirgqbwunn"] if p in game.bbijaigbknc]
                if pieces:
                    print(f"  Computing free piece positions...")
                    free_positions = build_free_positions(game, pieces[0])
                    print(f"  {len(free_positions)} free positions")
                    break

        for gname, data in groups.items():
            canvas = data["roduyfsmiznvg"]
            target = data["gosubdcyegamj"]
            pieces = [p for p in data["lecfirgqbwunn"] if p in game.bbijaigbknc]
            if not canvas or not target or not pieces:
                print(f"  Skipping '{gname}': canvas={canvas is not None}, target={target is not None}, pieces={len(pieces) if pieces else 0}")
                continue
            if "dirwzt" in gname:
                print(f"  Skipping '{gname}': dirwzt group")
                continue

            tcx = target.x + target.width // 2
            tcy = target.y + target.height // 2
            ccx = canvas.x + canvas.width // 2
            ccy = canvas.y + canvas.height // 2
            dx, dy = tcx - ccx, tcy - ccy

            # Already solved? (canvas at target)
            if canvas.collides_with(target) and dx == 0 and dy == 0:
                print(f"\n  Group '{gname}': already solved")
                continue

            all_free = all(not is_wall_blocked(game, p, p.x + dx, p.y + dy) for p in pieces)

            if all_free and not barriers:
                # Simple direct delta
                print(f"\n  Group '{gname}': direct delta ({dx},{dy})")
                for i, p in enumerate(pieces):
                    success, desc, obs = move_piece(env, p, p.x + dx, p.y + dy)
                    print(f"    P{i}: {desc}")

            elif barriers:
                # Need barrier-aware planning
                if all_free:
                    # Try direct delta first
                    temp_pos = [(p.x, p.y) for p in pieces]
                    direct_ok = True
                    for i, p in enumerate(pieces):
                        temp_pos[i] = (p.x + dx, p.y + dy)
                        cx, cy = compute_canvas_pos(temp_pos, p.width, p.height, canvas.width, canvas.height)
                        if (cx, cy) not in safe_canvas:
                            direct_ok = False
                            break

                    if direct_ok:
                        print(f"\n  Group '{gname}': direct delta ({dx},{dy}) [safe]")
                        for i, p in enumerate(pieces):
                            success, desc, obs = move_piece(env, p, p.x + dx, p.y + dy)
                            print(f"    P{i}: {desc}")
                        continue

                print(f"\n  Group '{gname}': sequential planning needed")
                actions, solved, new_obs = solve_group(
                    game, env, gname, canvas, target, pieces, barriers,
                    safe_canvas, free_positions
                )
                if new_obs:
                    obs = new_obs
            else:
                # Wall-blocked, no barriers
                print(f"\n  Group '{gname}': wall-blocked, needs centroid search")
                if safe_canvas is None:
                    safe_canvas = {(cx, cy) for cy in range(60) for cx in range(60)}  # all safe
                actions, solved, new_obs = solve_group(
                    game, env, gname, canvas, target, pieces, barriers,
                    safe_canvas, free_positions or build_free_positions(game, pieces[0])
                )
                if new_obs:
                    obs = new_obs

        # Get fresh obs to check level completion
        obs = env.step(6, data={"x": -1000, "y": -1000})  # no-op click (out of bounds)
        print(f"\n  Level {level}: completed={obs.levels_completed}, state={obs.state.name}")
        if obs.levels_completed >= level:
            print(f"  SOLVED!")

    print(f"\n{'='*60}")
    print(f"RESULT: {obs.levels_completed}/{obs.win_levels} levels")
    print(f"{'='*60}")
    return obs.levels_completed, obs.win_levels


if __name__ == "__main__":
    solve()
