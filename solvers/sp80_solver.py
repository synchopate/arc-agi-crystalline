#!/usr/bin/env python3
"""
Solver for ARC-AGI-3 game sp80 — Liquid flow puzzle.

Approach: Pure Python liquid simulator + brute-force position search.
For each level, find platform positions that fill all receptacles,
then execute the moves and spill.
"""

import arc_agi
import logging
import time
import itertools
import random

logging.disable(logging.WARNING)


def simulate_spill(sprites_data, overrides, sources, spouts, embedded_spouts):
    """
    Fast pure-Python liquid flow simulation.
    spouts: list of (x, y) for standalone sowlljgtjvn
    embedded_spouts: list of (sprite_idx, x_offset, y_offset) for spouts inside platforms
    Returns: (all_cups_filled, hit_wall, n_filled)
    """
    cell_map = {}
    cup_ids = set()

    for idx, (tag, x, y, w, h, mask) in enumerate(sprites_data):
        if idx in overrides:
            x, y = overrides[idx]
        if tag == "repwkzbkhxl":
            cup_ids.add(idx)
        for dy in range(h):
            for dx in range(w):
                if mask[dy][dx]:
                    cell_map[(x + dx, y + dy)] = idx

    tags = {idx: tag for idx, (tag, _, _, _, _, _) in enumerate(sprites_data)}

    particles = []
    occupied = set()

    for sx, sy in sources:
        particles.append((sx, sy, 0, 1))
        occupied.add((sx, sy))

    # Standalone spouts
    for sx, sy in spouts:
        nx, ny = sx, sy + 1
        if (nx, ny) not in cell_map and (nx, ny) not in occupied:
            particles.append((nx, ny, 0, 1))
            occupied.add((nx, ny))

    # Embedded spouts (move with platform)
    for sprite_idx, x_off, y_off in embedded_spouts:
        tag, ox, oy, w, h, mask = sprites_data[sprite_idx]
        if sprite_idx in overrides:
            ox, oy = overrides[sprite_idx]
        sx, sy = ox + x_off, oy + y_off
        nx, ny = sx, sy + 1
        # Check if there's already a liquid source there
        existing = any(s[0] == nx and s[1] == ny for s in sources)
        if not existing and (nx, ny) not in cell_map and (nx, ny) not in occupied:
            particles.append((nx, ny, 0, 1))
            occupied.add((nx, ny))

    filled_cups = set()
    hit_wall = False

    for tick in range(300):
        if not particles:
            break

        new_particles = []
        for wx, wy, ddx, ddy in particles:
            nx, ny = wx + ddx, wy + ddy

            if ddy != 0:
                perps = [(-1, 0), (1, 0)]
            else:
                perps = [(0, -1), (0, 1)]

            target_idx = cell_map.get((nx, ny))

            if target_idx is None:
                if (nx, ny) not in occupied:
                    new_particles.append((nx, ny, ddx, ddy))
                    occupied.add((nx, ny))
                else:
                    new_particles.append((nx, ny, ddx, ddy))
                continue

            target_tag = tags.get(target_idx, "")

            if target_tag == "liolfvkveqg":
                new_particles.append((nx, ny, ddx, ddy))
                continue

            if target_tag == "plzwjbfyfli":
                for pdx, pdy in perps:
                    px, py = wx + pdx, wy + pdy
                    if (px, py) not in cell_map and (px, py) not in occupied:
                        new_particles.append((px, py, ddx, ddy))
                        occupied.add((px, py))
                continue

            if target_tag == "repwkzbkhxl":
                side_a = cell_map.get((wx + perps[0][0], wy + perps[0][1]))
                side_b = cell_map.get((wx + perps[1][0], wy + perps[1][1]))
                if side_a == target_idx and side_b == target_idx:
                    filled_cups.add(target_idx)
                else:
                    for pdx, pdy in perps:
                        px, py = wx + pdx, wy + pdy
                        if (px, py) not in cell_map and (px, py) not in occupied:
                            new_particles.append((px, py, ddx, ddy))
                            occupied.add((px, py))
                continue

            if target_tag == "tuvkdkhdokr":
                side_a_idx = cell_map.get((wx + perps[0][0], wy + perps[0][1]))
                side_b_idx = cell_map.get((wx + perps[1][0], wy + perps[1][1]))

                # Match game logic exactly: two independent if checks + else on second
                # Case 1: side_a IS deflector AND side_b is empty -> redirect + spread
                if side_a_idx == target_idx and side_b_idx is None:
                    ndx2, ndy2 = ddy, -ddx
                    px, py = wx + ndx2, wy + ndy2
                    if (px, py) not in cell_map and (px, py) not in occupied:
                        new_particles.append((px, py, ndx2, ndy2))
                        occupied.add((px, py))
                # Case 2: side_b IS deflector AND side_a is empty -> redirect only
                if side_b_idx == target_idx and side_a_idx is None:
                    ndx2, ndy2 = -ddy, ddx
                    px, py = wx + ndx2, wy + ndy2
                    if (px, py) not in cell_map and (px, py) not in occupied:
                        new_particles.append((px, py, ndx2, ndy2))
                        occupied.add((px, py))
                else:
                    # else of second if: spread perpendicular with original direction
                    for pdx, pdy in perps:
                        px, py = wx + pdx, wy + pdy
                        if (px, py) not in cell_map and (px, py) not in occupied:
                            new_particles.append((px, py, ddx, ddy))
                            occupied.add((px, py))
                continue

            if target_tag == "waoewejnqzc":
                hit_wall = True
                continue

            # bodekplurlf (border) - liquid stops but no wall-hit penalty
            if target_tag == "bodekplurlf":
                continue

        particles = new_particles

    return filled_cups == cup_ids and len(cup_ids) > 0, hit_wall, len(filled_cups)


def extract_level_data(game):
    """Extract sprite data from current game level for simulator."""
    level = game.current_level
    sprites_data = []
    sources = []
    spouts = []  # standalone sowlljgtjvn: (x, y)
    embedded_spouts = []  # embedded in platforms: (sprite_idx, x_offset, y_offset)
    moveable_indices = []

    for s in level.get_sprites():
        tag = None
        if "plzwjbfyfli" in s.tags:
            tag = "plzwjbfyfli"
        elif "tuvkdkhdokr" in s.tags:
            tag = "tuvkdkhdokr"
        elif "repwkzbkhxl" in s.tags:
            tag = "repwkzbkhxl"
        elif "waoewejnqzc" in s.tags:
            tag = "waoewejnqzc"
        elif "liolfvkveqg" in s.tags:
            sources.append((s.x, s.y))
            continue
        elif "sowlljgtjvn" in s.tags:
            if "plzwjbfyfli" not in s.tags:
                px = s.pixels
                for py_off in range(px.shape[0]):
                    for px_off in range(px.shape[1]):
                        if int(px[py_off, px_off]) == 4:
                            spouts.append((s.x + px_off, s.y + py_off))
                continue
        elif s.name.startswith("bodekplurlf"):
            tag = "bodekplurlf"
        else:
            continue

        w, h = s.width, s.height
        pixels = s.pixels
        # Apply rotation to pixels to match displayed (w, h)
        import numpy as np
        rot = getattr(s, 'rotation', 0) or 0
        k = rot // 90 % 4
        if k != 0:
            pixels = np.rot90(pixels, k=-k)  # inverse rotation to get display orientation
        mask = tuple(tuple(int(pixels[r, c]) >= 0 for c in range(w)) for r in range(h))

        idx = len(sprites_data)
        sprites_data.append((tag, s.x, s.y, w, h, mask))

        if tag in ("plzwjbfyfli", "tuvkdkhdokr"):
            moveable_indices.append(idx)
            # Check for embedded sowlljgtjvn (color 4 pixels) - track as relative offsets
            if "sowlljgtjvn" in s.tags:
                for py_off in range(pixels.shape[0]):
                    for px_off in range(pixels.shape[1]):
                        if int(pixels[py_off, px_off]) == 4:
                            embedded_spouts.append((idx, px_off, py_off))

    return sprites_data, sources, spouts, embedded_spouts, moveable_indices


def count_actions(solution, sprites_data, moveable_indices, selected_mi):
    """Count exact actions for a solution: clicks + moves + 1 spill."""
    actions = 1  # spill
    first_moved = True
    for mi in moveable_indices:
        if mi not in solution:
            continue
        nx, ny = solution[mi]
        tag, ox, oy, w, h, mask = sprites_data[mi]
        dx = abs(nx - ox)
        dy = abs(ny - oy)
        if dx == 0 and dy == 0:
            continue
        # Need click to select unless it's the currently selected platform
        if mi != selected_mi:
            actions += 1  # click to select
        actions += dx + dy  # moves
    return actions


def find_best_config(sprites_data, moveable_indices, sources, spouts, embedded_spouts, budget, selected_mi=None):
    """Find optimal platform positions using brute-force simulation.

    Strategy: find MINIMUM distance solution. First try x-only with increasing
    distance, then x+y, then random search keeping best found.
    """
    recep_data = []
    for i, (tag, x, y, w, h, mask) in enumerate(sprites_data):
        if tag == "repwkzbkhxl":
            recep_data.append((x, y, w, h))

    # Find border inner bounds
    inner_x_min, inner_x_max = 0, 999
    inner_y_min, inner_y_max = 0, 999
    for i, (tag, x, y, w, h, mask) in enumerate(sprites_data):
        if tag == "bodekplurlf":
            inner_x_min = x + 1
            inner_x_max = x + w - 2
            inner_y_min = y + 1
            inner_y_max = y + h - 2
            break

    def is_valid_pos(mi, nx, ny):
        tag, ox, oy, w, h, mask = sprites_data[mi]
        if ny < 3:
            return False
        # Must stay within border
        if nx < inner_x_min or nx + w - 1 > inner_x_max:
            return False
        if ny < inner_y_min or ny + h - 1 > inner_y_max:
            return False
        for rx, ry, rw, rh in recep_data:
            if (nx < rx + rw + 1 and nx + w > rx - 1 and
                ny < ry + rh + 1 and ny + h > ry - 1):
                return False
        return True

    n = len(moveable_indices)
    t0 = time.time()

    best_solution = None
    best_actions = budget  # start at budget, look for better

    # Generate x-only positions for each platform
    x_positions = []  # per platform: list of (nx, ny, dist)
    for mi in moveable_indices:
        tag, ox, oy, w, h, mask = sprites_data[mi]
        positions = [(ox, oy, 0)]  # include original
        max_range = min(budget, 15)
        for dx in range(-max_range, max_range + 1):
            if dx == 0:
                continue
            nx = ox + dx
            if is_valid_pos(mi, nx, oy):
                positions.append((nx, oy, abs(dx)))
        positions.sort(key=lambda p: p[2])
        x_positions.append(positions)

    print(f"    X-positions per platform: {[len(p) for p in x_positions]}")

    tested = 0

    # Phase 1: x-only moves, try increasing number of changed platforms
    # Enumerate by total distance to find minimum
    for n_changed in range(1, n + 1):
        for changed_set in itertools.combinations(range(n), n_changed):
            pos_lists = []
            for pi in range(n):
                if pi in changed_set:
                    pos_lists.append([p for p in x_positions[pi] if p[2] > 0])
                else:
                    pos_lists.append([x_positions[pi][0]])

            for combo in itertools.product(*pos_lists):
                total_dist = sum(c[2] for c in combo)
                if total_dist + n >= budget:
                    continue

                # Quick bound: can't beat best_actions
                # actions = moves(total_dist) + clicks(n_moved-1 if selected moves, else n_moved) + spill(1)
                n_moved = sum(1 for c in combo if c[2] > 0)
                min_clicks = max(0, n_moved - 1) if any(
                    moveable_indices[i] == selected_mi and combo[i][2] > 0
                    for i in range(n)
                ) else n_moved
                min_possible = total_dist + min_clicks + 1
                if min_possible >= best_actions:
                    continue

                # Overlap check
                valid = True
                for i in range(n):
                    for j in range(i + 1, n):
                        x1, y1 = combo[i][0], combo[i][1]
                        x2, y2 = combo[j][0], combo[j][1]
                        w1 = sprites_data[moveable_indices[i]][3]
                        h1 = sprites_data[moveable_indices[i]][4]
                        w2 = sprites_data[moveable_indices[j]][3]
                        h2 = sprites_data[moveable_indices[j]][4]
                        if (x1 < x2 + w2 and x1 + w1 > x2 and
                            y1 < y2 + h2 and y1 + h1 > y2):
                            valid = False
                            break
                    if not valid:
                        break
                if not valid:
                    continue

                overrides = {moveable_indices[i]: (combo[i][0], combo[i][1]) for i in range(n)}
                ok, hit, nf = simulate_spill(sprites_data, overrides, sources, spouts, embedded_spouts)
                tested += 1

                if ok and not hit:
                    acts = count_actions(overrides, sprites_data, moveable_indices, selected_mi)
                    if acts < best_actions:
                        best_actions = acts
                        best_solution = overrides
                        elapsed = time.time() - t0
                        print(f"    FOUND x-only ({n_changed} changed, dist={total_dist}, "
                              f"acts={acts}, {tested} tested, {elapsed:.1f}s)")
                        for i, mi in enumerate(moveable_indices):
                            nx, ny = combo[i][0], combo[i][1]
                            ox, oy = sprites_data[mi][1], sprites_data[mi][2]
                            if nx != ox or ny != oy:
                                print(f"      [{mi}] ({ox},{oy}) -> ({nx},{ny})")

            elapsed = time.time() - t0
            if elapsed > 30:
                break
        elapsed = time.time() - t0
        if elapsed > 30:
            print(f"    X-only timeout at n_changed={n_changed} ({tested} tested, {elapsed:.1f}s)")
            break

    # Phase 2: x+y moves - sorted by total distance ascending
    print(f"    Trying x+y moves...")
    xy_positions = []
    for mi in moveable_indices:
        tag, ox, oy, w, h, mask = sprites_data[mi]
        positions = [(ox, oy, 0)]
        max_r = min(budget // n, 18)
        for dx in range(-max_r, max_r + 1):
            for dy in range(-max_r, max_r + 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = ox + dx, oy + dy
                if is_valid_pos(mi, nx, ny):
                    positions.append((nx, ny, abs(dx) + abs(dy)))
        positions.sort(key=lambda p: p[2])
        xy_positions.append(positions)

    # For large n, limit positions per platform - but keep more if we need better solutions
    max_pos = max(40, 400 // max(n, 1))
    trimmed = [pp[:max_pos] for pp in xy_positions]
    print(f"    XY-positions (trimmed): {[len(p) for p in trimmed]}")

    for combo in itertools.product(*trimmed):
        total_dist = sum(c[2] for c in combo)
        if total_dist + n >= budget:
            continue

        n_moved = sum(1 for c in combo if c[2] > 0)
        min_clicks = max(0, n_moved - 1) if any(
            moveable_indices[i] == selected_mi and combo[i][2] > 0
            for i in range(n)
        ) else n_moved
        min_possible = total_dist + min_clicks + 1
        if min_possible >= best_actions:
            continue

        valid = True
        for i in range(n):
            for j in range(i + 1, n):
                x1, y1 = combo[i][0], combo[i][1]
                x2, y2 = combo[j][0], combo[j][1]
                w1 = sprites_data[moveable_indices[i]][3]
                h1 = sprites_data[moveable_indices[i]][4]
                w2 = sprites_data[moveable_indices[j]][3]
                h2 = sprites_data[moveable_indices[j]][4]
                if (x1 < x2 + w2 and x1 + w1 > x2 and
                    y1 < y2 + h2 and y1 + h1 > y2):
                    valid = False
                    break
            if not valid:
                break
        if not valid:
            continue

        overrides = {moveable_indices[i]: (combo[i][0], combo[i][1]) for i in range(n)}
        ok, hit, nf = simulate_spill(sprites_data, overrides, sources, spouts, embedded_spouts)
        tested += 1

        if ok and not hit:
            acts = count_actions(overrides, sprites_data, moveable_indices, selected_mi)
            if acts < best_actions:
                best_actions = acts
                best_solution = overrides
                elapsed = time.time() - t0
                print(f"    FOUND x+y (dist={total_dist}, acts={acts}, {tested} tested, {elapsed:.1f}s)")
                for i, mi in enumerate(moveable_indices):
                    nx, ny = combo[i][0], combo[i][1]
                    ox, oy = sprites_data[mi][1], sprites_data[mi][2]
                    if nx != ox or ny != oy:
                        print(f"      [{mi}] ({ox},{oy}) -> ({nx},{ny})")

        elapsed = time.time() - t0
        if elapsed > 60:
            break

    # Phase 3: random search (effective for deflector levels)
    # Keep best solution found, optimize for minimum distance
    # Skip random search if x-only or x+y already found a compact solution
    if best_solution is not None and best_actions <= 12:
        print(f"    Skipping random search (best_acts={best_actions})")
        return best_solution
    print(f"    Trying random search...")
    all_positions = []
    for mi in moveable_indices:
        tag, ox, oy, w, h, mask = sprites_data[mi]
        positions = []
        for nx in range(inner_x_min, inner_x_max - w + 2):
            for ny in range(3, inner_y_max - h + 2):
                if is_valid_pos(mi, nx, ny):
                    positions.append((nx, ny, abs(nx - ox) + abs(ny - oy)))
        positions.sort(key=lambda p: p[2])
        all_positions.append(positions)

    # Try multiple seeds, keep improving best
    # Phase 3a: First find ANY solution with full random, then optimize
    for seed in [1, 42, 137, 2024, 7, 99, 13, 256, 3, 17, 31, 53, 71, 97, 113, 199,
                 500, 777, 1000, 1337, 2000, 3000, 4000, 5000]:
        random.seed(seed)
        seed_t0 = time.time()
        iters = 0
        time_limit = 180 if best_solution is None else 150
        while time.time() - seed_t0 < 12 and time.time() - t0 < time_limit:
            iters += 1
            # Strategy mix: full random for finding, biased for optimizing
            if best_solution is None or iters % 3 == 0:
                combo = tuple(random.choice(pp) for pp in all_positions)
            elif iters % 3 == 1:
                # Biased toward short distances
                combo = tuple(
                    pp[random.randint(0, max(0, len(pp) // 3))]
                    for pp in all_positions
                )
            else:
                # Very biased: top 10%
                combo = tuple(
                    pp[random.randint(0, max(0, len(pp) // 10))]
                    for pp in all_positions
                )
            total_dist = sum(c[2] for c in combo)
            if total_dist + n >= budget:
                continue

            n_moved = sum(1 for c in combo if c[2] > 0)
            min_clicks = max(0, n_moved - 1) if any(
                moveable_indices[i] == selected_mi and combo[i][2] > 0
                for i in range(n)
            ) else n_moved
            min_possible = total_dist + min_clicks + 1
            if best_solution is not None and min_possible >= best_actions:
                continue

            valid = True
            for i in range(n):
                for j in range(i + 1, n):
                    x1, y1 = combo[i][0], combo[i][1]
                    x2, y2 = combo[j][0], combo[j][1]
                    w1 = sprites_data[moveable_indices[i]][3]
                    h1 = sprites_data[moveable_indices[i]][4]
                    w2 = sprites_data[moveable_indices[j]][3]
                    h2 = sprites_data[moveable_indices[j]][4]
                    if (x1 < x2 + w2 and x1 + w1 > x2 and
                        y1 < y2 + h2 and y1 + h1 > y2):
                        valid = False
                        break
                if not valid:
                    break
            if not valid:
                continue

            overrides = {moveable_indices[i]: (combo[i][0], combo[i][1]) for i in range(n)}
            ok, hit, nf = simulate_spill(sprites_data, overrides, sources, spouts, embedded_spouts)
            tested += 1

            if ok and not hit:
                acts = count_actions(overrides, sprites_data, moveable_indices, selected_mi)
                if acts < best_actions:
                    best_actions = acts
                    best_solution = overrides
                    elapsed = time.time() - t0
                    print(f"    FOUND random seed={seed} (dist={total_dist}, acts={acts}, "
                          f"{tested} tested, {elapsed:.1f}s)")
                    for i, mi in enumerate(moveable_indices):
                        nx, ny = combo[i][0], combo[i][1]
                        ox, oy = sprites_data[mi][1], sprites_data[mi][2]
                        if nx != ox or ny != oy:
                            print(f"      [{mi}] ({ox},{oy}) -> ({nx},{ny})")
        if time.time() - t0 >= time_limit:
            break

    # Phase 4: multi-round local search around best solution
    if best_solution is not None and best_actions > 12:
        print(f"    Local search around best (acts={best_actions})...")
        local_tested = 0

        for local_round in range(5):
            if time.time() - t0 > 300 or best_actions <= 12:
                break

            # Phase 4a: single-platform perturbation (full scan)
            improved = True
            while improved and time.time() - t0 < 300:
                improved = False
                for pi in range(n):
                    mi = moveable_indices[pi]
                    if mi not in best_solution:
                        continue
                    bx, by = best_solution[mi]
                    tag, ox, oy, w, h, mask = sprites_data[mi]
                    for pos in all_positions[pi]:
                        nx, ny, d = pos
                        if nx == bx and ny == by:
                            continue
                        test_sol = dict(best_solution)
                        test_sol[mi] = (nx, ny)
                        acts = count_actions(test_sol, sprites_data, moveable_indices, selected_mi)
                        if acts >= best_actions:
                            continue
                        valid = True
                        for pj in range(n):
                            if pj == pi:
                                continue
                            mj = moveable_indices[pj]
                            if mj in test_sol:
                                x2, y2 = test_sol[mj]
                            else:
                                x2, y2 = sprites_data[mj][1], sprites_data[mj][2]
                            w2 = sprites_data[mj][3]
                            h2 = sprites_data[mj][4]
                            if (nx < x2 + w2 and nx + w > x2 and
                                ny < y2 + h2 and ny + h > y2):
                                valid = False
                                break
                        if not valid:
                            continue
                        ok, hit, nf = simulate_spill(sprites_data, test_sol, sources, spouts, embedded_spouts)
                        local_tested += 1
                        if ok and not hit:
                            best_solution = test_sol
                            best_actions = acts
                            improved = True
                            print(f"    LOCAL1 improved: acts={acts} (round={local_round}, tested={local_tested})")
                            break

            if best_actions <= 12 or time.time() - t0 > 300:
                break

            # Phase 4b: two-platform perturbation with wider radius
            improved2 = True
            while improved2 and time.time() - t0 < 300:
                improved2 = False
                for pi in range(n):
                    for pj in range(pi + 1, n):
                        mi = moveable_indices[pi]
                        mj = moveable_indices[pj]
                        bxi, byi = best_solution.get(mi, (sprites_data[mi][1], sprites_data[mi][2]))
                        bxj, byj = best_solution.get(mj, (sprites_data[mj][1], sprites_data[mj][2]))
                        near_i = [p for p in all_positions[pi] if abs(p[0]-bxi) + abs(p[1]-byi) <= 8][:30]
                        near_j = [p for p in all_positions[pj] if abs(p[0]-bxj) + abs(p[1]-byj) <= 8][:30]
                        for pos_i in near_i:
                            for pos_j in near_j:
                                test_sol = dict(best_solution)
                                test_sol[mi] = (pos_i[0], pos_i[1])
                                test_sol[mj] = (pos_j[0], pos_j[1])
                                acts = count_actions(test_sol, sprites_data, moveable_indices, selected_mi)
                                if acts >= best_actions:
                                    continue
                                all_pos_list = []
                                valid = True
                                for pk in range(n):
                                    mk = moveable_indices[pk]
                                    if mk in test_sol:
                                        px, py = test_sol[mk]
                                    else:
                                        px, py = sprites_data[mk][1], sprites_data[mk][2]
                                    pw, ph = sprites_data[mk][3], sprites_data[mk][4]
                                    for prev_px, prev_py, prev_pw, prev_ph in all_pos_list:
                                        if (px < prev_px + prev_pw and px + pw > prev_px and
                                            py < prev_py + prev_ph and py + ph > prev_py):
                                            valid = False
                                            break
                                    if not valid:
                                        break
                                    all_pos_list.append((px, py, pw, ph))
                                if not valid:
                                    continue
                                ok, hit, nf = simulate_spill(sprites_data, test_sol, sources, spouts, embedded_spouts)
                                local_tested += 1
                                if ok and not hit:
                                    best_solution = test_sol
                                    best_actions = acts
                                    improved2 = True
                                    print(f"    LOCAL2 improved: acts={acts} (round={local_round}, tested={local_tested})")
                            if improved2:
                                break
                        if improved2:
                            break
                    if improved2:
                        break

        print(f"    Local search done ({local_tested} tested, acts={best_actions})")

    if best_solution is not None:
        return best_solution

    elapsed = time.time() - t0
    print(f"    No solution ({tested} tested, {elapsed:.1f}s)")
    return None


def game_to_display_click(gx, gy, rot_k, scale=4):
    """Convert game grid coords to display coords for clicking."""
    dx, dy = gx * scale, gy * scale
    if rot_k == 0:
        return dx, dy
    elif rot_k == 1:
        return dy, 63 - dx
    elif rot_k == 2:
        return 63 - dx, 63 - dy
    else:
        return 63 - dy, dx


def game_action_to_env(game_action, rot_k):
    """Convert game-coordinate action to env action."""
    if rot_k == 0:
        return game_action
    inv = {
        1: {1: 3, 2: 4, 3: 2, 4: 1},
        2: {1: 2, 2: 1, 3: 4, 4: 3},
        3: {1: 4, 2: 3, 3: 1, 4: 2},
    }
    return inv[rot_k][game_action]


def execute_solution(env, game, solution, sprites_data, moveable_indices, rot_k):
    """Move platforms to target positions and spill."""
    from universal_harness import grid_to_display
    cam = game.camera

    # Build a mapping from sprite_data index to actual sprite object
    level = game.current_level
    all_plats = (list(level.get_sprites_by_tag("plzwjbfyfli")) +
                 list(level.get_sprites_by_tag("tuvkdkhdokr")))

    # Match sprites_data entries to actual sprite objects by position/size
    mi_to_sprite = {}
    used_sprites = set()
    for mi in moveable_indices:
        tag, ox, oy, w, h, mask = sprites_data[mi]
        for s in all_plats:
            if id(s) not in used_sprites and s.x == ox and s.y == oy and s.width == w and s.height == h:
                mi_to_sprite[mi] = s
                used_sprites.add(id(s))
                break

    # Determine which mi is currently selected
    selected_sprite = game.vsoxmtrhqt
    selected_mi = None
    for mi, s in mi_to_sprite.items():
        if s is selected_sprite:
            selected_mi = mi
            break

    # Sort: move currently selected first (saves a click), then others
    def sort_key(mi):
        # Platforms that don't move go last
        if mi in solution:
            nx, ny = solution[mi]
            tag, ox, oy, w, h, mask = sprites_data[mi]
            if nx == ox and ny == oy:
                return (2, 0)
        else:
            return (2, 0)
        return (0 if mi == selected_mi else 1, 0)

    order = sorted(moveable_indices, key=sort_key)

    for mi in order:
        if mi not in solution:
            continue

        nx, ny = solution[mi]
        tag, ox, oy, w, h, mask = sprites_data[mi]
        dx_move = nx - ox
        dy_move = ny - oy

        if dx_move == 0 and dy_move == 0:
            continue

        sprite = mi_to_sprite.get(mi)
        if sprite is None:
            print(f"    WARNING: No sprite for index {mi}")
            continue

        # Select this platform if not currently selected
        if game.vsoxmtrhqt is not sprite:
            # Click on the sprite's CURRENT position center
            cx = sprite.x + sprite.width // 2
            cy = sprite.y + sprite.height // 2
            display_x, display_y = grid_to_display(cx, cy, cam)
            # Apply rotation for click coordinates
            if rot_k == 1:
                display_x, display_y = display_y, 63 - display_x
            elif rot_k == 2:
                display_x, display_y = 63 - display_x, 63 - display_y
            elif rot_k == 3:
                display_x, display_y = 63 - display_y, display_x
            obs = env.step(6, data={"x": int(display_x), "y": int(display_y)})
            if obs.state.name != "NOT_FINISHED":
                return obs
            if game.vsoxmtrhqt is not sprite:
                print(f"    WARNING: Failed to select {sprite.name} at ({sprite.x},{sprite.y})")
                # Try clicking at different offset
                for off_x in range(-1, 2):
                    for off_y in range(-1, 2):
                        if off_x == 0 and off_y == 0:
                            continue
                        cx2, cy2 = cx + off_x, cy + off_y
                        dx2, dy2 = grid_to_display(cx2, cy2, cam)
                        if rot_k == 1:
                            dx2, dy2 = dy2, 63 - dx2
                        elif rot_k == 2:
                            dx2, dy2 = 63 - dx2, 63 - dy2
                        elif rot_k == 3:
                            dx2, dy2 = 63 - dy2, dx2
                        obs = env.step(6, data={"x": int(dx2), "y": int(dy2)})
                        if game.vsoxmtrhqt is sprite:
                            break
                    if game.vsoxmtrhqt is sprite:
                        break

        # Move horizontally
        if dx_move > 0:
            act = game_action_to_env(4, rot_k)
            for _ in range(dx_move):
                obs = env.step(act)
                if obs.state.name != "NOT_FINISHED":
                    return obs
        elif dx_move < 0:
            act = game_action_to_env(3, rot_k)
            for _ in range(-dx_move):
                obs = env.step(act)
                if obs.state.name != "NOT_FINISHED":
                    return obs

        # Move vertically
        if dy_move > 0:
            act = game_action_to_env(2, rot_k)
            for _ in range(dy_move):
                obs = env.step(act)
                if obs.state.name != "NOT_FINISHED":
                    return obs
        elif dy_move < 0:
            act = game_action_to_env(1, rot_k)
            for _ in range(-dy_move):
                obs = env.step(act)
                if obs.state.name != "NOT_FINISHED":
                    return obs

    # Verify positions before spill
    for mi in moveable_indices:
        if mi in solution:
            nx, ny = solution[mi]
            sprite = mi_to_sprite.get(mi)
            if sprite and (sprite.x != nx or sprite.y != ny):
                print(f"    WARNING: Platform [{mi}] at ({sprite.x},{sprite.y}) expected ({nx},{ny})")

    # Spill
    obs = env.step(5)
    return obs


def main():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make("sp80")
    obs = env.reset()
    obs = env.step(6)
    game = env._game

    total_levels = obs.win_levels
    print(f"sp80: {total_levels} levels")
    total_t0 = time.time()

    human_baselines = [39, 58, 25, 148, 96, 152]
    level_actions = []  # actions per level (excluding initial step(6))

    for level_num in range(1, total_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        rot_k = game.fahhoimkk
        grid_w, grid_h = game.current_level.grid_size
        budget = game.current_level.get_data("steps") or 50
        rot = game.current_level.get_data("dojfslwbg") or 0

        print(f"\n{'='*50}")
        print(f"Level {level_num} (grid={grid_w}x{grid_h}, budget={budget}, rot={rot}, k={rot_k})")
        print(f"{'='*50}")

        sprites_data, sources, spouts, embedded_spouts, moveable_indices = extract_level_data(game)

        n_cups = sum(1 for tag, *_ in sprites_data if tag == "repwkzbkhxl")
        print(f"  {len(moveable_indices)} moveables, {n_cups} cups")
        print(f"  sources={sources}, spouts={spouts}, embedded={embedded_spouts}")
        for mi in moveable_indices:
            tag, x, y, w, h, mask = sprites_data[mi]
            print(f"    [{mi}] {tag} ({x},{y}) {w}x{h}")

        # Find which platform is currently selected
        selected_sprite = game.vsoxmtrhqt
        level = game.current_level
        all_plats = (list(level.get_sprites_by_tag("plzwjbfyfli")) +
                     list(level.get_sprites_by_tag("tuvkdkhdokr")))
        selected_mi = None
        used = set()
        mi_to_sprite_map = {}
        for mi in moveable_indices:
            tag, ox, oy, w, h, mask = sprites_data[mi]
            for s in all_plats:
                if id(s) not in used and s.x == ox and s.y == oy and s.width == w and s.height == h:
                    mi_to_sprite_map[mi] = s
                    used.add(id(s))
                    if s is selected_sprite:
                        selected_mi = mi
                    break

        solution = find_best_config(sprites_data, moveable_indices, sources, spouts,
                                     embedded_spouts, budget, selected_mi)

        if solution is None:
            print(f"  FAILED - no valid configuration found")
            level_actions.append(budget)
            break

        # Count actions BEFORE executing
        acts = count_actions(solution, sprites_data, moveable_indices, selected_mi)
        if level_num == 1:
            acts += 1  # initial step(6) counts for level 1
        level_actions.append(acts)

        obs = execute_solution(env, game, solution, sprites_data, moveable_indices, rot_k)

        if obs.levels_completed >= level_num:
            print(f"  Level {level_num} SOLVED! (acts={acts}, completed={obs.levels_completed})")
        else:
            print(f"  Level {level_num} FAILED after spill")
            print(f"    state={obs.state.name}, filled={len(game.cevwbinfgl)}/{n_cups}")
            break

    completed = obs.levels_completed
    if obs.state.name == "WIN":
        completed = total_levels

    elapsed = time.time() - total_t0

    # Print results table
    print(f"\n{'='*70}")
    print(f"GAME: sp80  |  LEVELS_SOLVED: {completed}/{total_levels}  |  Time: {elapsed:.1f}s")
    print(f"{'='*70}")
    print(f"{'LEVEL':>5} | {'HUMAN':>5} | {'OURS':>5} | {'RATIO':>6} | {'RHAE':>8}")
    print(f"{'-'*5}-+-{'-'*5}-+-{'-'*5}-+-{'-'*6}-+-{'-'*8}")
    total_rhae = 0
    for i in range(len(level_actions)):
        h = human_baselines[i]
        a = level_actions[i]
        ratio = h / a if a > 0 else 0
        rhae = ratio ** 2
        total_rhae += rhae
        print(f"{i+1:>5} | {h:>5} | {a:>5} | {ratio:>6.2f} | {rhae:>8.4f}")
    print(f"{'-'*5}-+-{'-'*5}-+-{'-'*5}-+-{'-'*6}-+-{'-'*8}")
    print(f"{'TOTAL':>5} | {sum(human_baselines[:len(level_actions)]):>5} | "
          f"{sum(level_actions):>5} | {'':>6} | {total_rhae:>8.4f}")
    print(f"{'='*70}")

    return completed, total_levels


if __name__ == "__main__":
    main()
