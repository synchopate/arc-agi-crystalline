#!/usr/bin/env python3
"""
ARC-AGI-3 sk48 Solver — Pure simulation BFS/A* with perpendicular track constraints.

Game: Track/chain puzzle - extend/retract/slide chains to arrange colored blocks.
Win condition: blocks on top track match blocks on bottom track sequence.
"""

import sys
import time
import heapq
from collections import deque
import logging
import functools
logging.disable(logging.WARNING)

# Force unbuffered output
_orig_print = print
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    _orig_print(*args, **kwargs)

import arc_agi

STEP = 6
DIR_MAP = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}


def extract_level_info(game):
    """Extract all static and initial dynamic state from current level."""

    bnd = game.lqwkgffeb
    bnd_w = bnd.pixels.shape[1] * STEP
    bnd_h = bnd.pixels.shape[0] * STEP
    bounds = (bnd.x, bnd.x + bnd_w, bnd.y, bnd.y + bnd_h)

    rails = []
    for r in game.current_level.get_sprites_by_name("irkeobngyh"):
        rails.append((r.x, r.y, r.width, r.height))

    walls = set()
    for w in game.current_level.get_sprites_by_name("mkgqjopcjn"):
        walls.add((w.x, w.y))

    pair_map = {}
    pidx = 0
    for top, bot in game.xpmcmtbcv.items():
        pair_map[id(top)] = (pidx, True)
        pair_map[id(bot)] = (pidx, False)
        pidx += 1
    for head in game.mwfajkguqx:
        if id(head) not in pair_map:
            pair_map[id(head)] = (pidx, True)
            pidx += 1

    heads_static = []
    heads_init = []
    head_id_to_idx = {}

    for head in game.mwfajkguqx:
        pi, is_top = pair_map[id(head)]
        hi = len(heads_static)
        heads_static.append((head.rotation, is_top, pi))
        heads_init.append((head.x, head.y, len(game.mwfajkguqx[head])))
        head_id_to_idx[id(head)] = hi

    active_idx = head_id_to_idx.get(id(game.vzvypfsnt), 0)

    switchable_tops = set()
    for top_head in game.xpmcmtbcv.keys():
        if 'sys_click' in top_head.tags:
            switchable_tops.add(head_id_to_idx[id(top_head)])
    top_head_indices = sorted(switchable_tops)

    all_blocks = []
    for b in game.vbelzuaian:
        all_blocks.append((b.x, b.y, int(b.pixels[1, 1])))

    bottom_blocks = set()
    top_blocks = []
    for bx, by, bc in all_blocks:
        on_bottom = False
        for head in game.mwfajkguqx:
            hi = head_id_to_idx[id(head)]
            if not heads_static[hi][1]:
                rot = heads_static[hi][0]
                dx, dy = DIR_MAP[rot]
                hx, hy, count = heads_init[hi]
                for i in range(count):
                    sx = hx + i * dx * STEP
                    sy = hy + i * dy * STEP
                    if sx == bx and sy == by:
                        on_bottom = True
                        break
            if on_bottom:
                break
        if on_bottom:
            bottom_blocks.add((bx, by, bc))
        else:
            top_blocks.append((bx, by, bc))

    target_colors = {}
    n_indicators = {}
    for top, bot in game.xpmcmtbcv.items():
        pi = pair_map[id(top)][0]
        bot_hi = head_id_to_idx[id(bot)]
        rot = heads_static[bot_hi][0]
        dx, dy = DIR_MAP[rot]
        hx, hy, count = heads_init[bot_hi]
        colors = []
        for i in range(count):
            sx = hx + i * dx * STEP
            sy = hy + i * dy * STEP
            for bx, by, bc in bottom_blocks:
                if bx == sx and by == sy:
                    colors.append(bc)
                    break
        target_colors[pi] = colors
        n_indicators[pi] = len(game.jdojcthkf.get(bot, []))

    head_sprites = {}
    for head in game.mwfajkguqx:
        hi = head_id_to_idx[id(head)]
        head_sprites[hi] = head

    return {
        'bounds': bounds,
        'rails': rails,
        'walls': walls,
        'heads_static': heads_static,
        'heads_init': heads_init,
        'active_idx': active_idx,
        'top_head_indices': top_head_indices,
        'top_blocks': top_blocks,
        'bottom_blocks': bottom_blocks,
        'target_colors': target_colors,
        'n_indicators': n_indicators,
        'head_sprites': head_sprites,
    }


def make_solver(info):
    """Create solver functions closed over level info."""
    bounds = info['bounds']
    rails = info['rails']
    walls = info['walls']
    heads_static = info['heads_static']
    top_indices = info['top_head_indices']
    target_colors = info['target_colors']
    n_indicators = info['n_indicators']
    n_heads = len(heads_static)

    def in_bounds(x, y):
        return x >= bounds[0] and x + 6 <= bounds[1] and y >= bounds[2] and y + 6 <= bounds[3]

    def is_oob(x, y):
        return x < bounds[0] or x + 6 > bounds[1] or y < bounds[2] or y + 6 > bounds[3]

    def has_wall(x, y):
        return (x, y) in walls

    def has_rail_at(hx, hy, cx, cy):
        for rx, ry, rw, rh in rails:
            if rx <= cx < rx + rw and ry <= cy < ry + rh:
                return True
        return False

    def find_block(blks, bx, by):
        for i, (x, y, c) in enumerate(blks):
            if x == bx and y == by:
                return i
        return -1

    def get_all_seg_positions(heads_var, exclude_head=-1):
        h_segs = set()
        v_segs = set()
        for hi in range(n_heads):
            if hi == exclude_head:
                continue
            hx, hy, count = heads_var[hi]
            rot = heads_static[hi][0]
            dx, dy = DIR_MAP[rot]
            is_horiz = rot in (0, 180)
            for i in range(count):
                pos = (hx + i * dx * STEP, hy + i * dy * STEP)
                if is_horiz:
                    h_segs.add(pos)
                else:
                    v_segs.add(pos)
        return h_segs, v_segs

    def can_push_chain(blks, bx, by, dx, dy, pushed_frozen, heads_var, h_segs, v_segs):
        if (bx, by) in pushed_frozen:
            return True
        nx, ny = bx + dx * STEP, by + dy * STEP
        if not in_bounds(nx, ny) or has_wall(nx, ny):
            return False
        push_horiz = dx != 0
        if push_horiz:
            if (bx, by) in v_segs or (nx, ny) in v_segs:
                return False
        else:
            if (bx, by) in h_segs or (nx, ny) in h_segs:
                return False
        bi = find_block(blks, nx, ny)
        if bi >= 0 and (nx, ny) not in pushed_frozen:
            return can_push_chain(blks, nx, ny, dx, dy, pushed_frozen | {(bx, by)}, heads_var, h_segs, v_segs)
        return True

    def push_chain(blks_list, bx, by, dx, dy, pushed):
        if (bx, by) in pushed:
            return
        nx, ny = bx + dx * STEP, by + dy * STEP
        bi = find_block(blks_list, nx, ny)
        if bi >= 0 and (nx, ny) not in pushed:
            push_chain(blks_list, nx, ny, dx, dy, pushed)
        for i, (x, y, c) in enumerate(blks_list):
            if x == bx and y == by:
                blks_list[i] = (nx, ny, c)
                pushed.add((nx, ny))
                return

    def get_seg_positions(heads_var, hi):
        hx, hy, count = heads_var[hi]
        rot = heads_static[hi][0]
        dx, dy = DIR_MAP[rot]
        return [(hx + i * dx * STEP, hy + i * dy * STEP) for i in range(count)]

    def is_solved(heads_var, blks):
        for pi, target in target_colors.items():
            n = n_indicators.get(pi, len(target))
            if n == 0:
                continue
            top_hi = None
            for i, hs in enumerate(heads_static):
                if hs[2] == pi and hs[1]:
                    top_hi = i
                    break
            if top_hi is None:
                return False
            seg_pos = get_seg_positions(heads_var, top_hi)
            colors = []
            for sx, sy in seg_pos:
                bi = find_block(blks, sx, sy)
                if bi >= 0:
                    colors.append(blks[bi][2])
            if len(colors) < n:
                return False
            for i in range(n):
                if i >= len(target) or colors[i] != target[i]:
                    return False
        return True

    def is_pair_solved(heads_var, blks, pair_idx):
        """Check if a specific pair is solved."""
        if pair_idx not in target_colors:
            return True
        target = target_colors[pair_idx]
        n = n_indicators.get(pair_idx, len(target))
        if n == 0:
            return True
        top_hi = None
        for i, hs in enumerate(heads_static):
            if hs[2] == pair_idx and hs[1]:
                top_hi = i
                break
        if top_hi is None:
            return False
        seg_pos = get_seg_positions(heads_var, top_hi)
        colors = []
        for sx, sy in seg_pos:
            bi = find_block(blks, sx, sy)
            if bi >= 0:
                colors.append(blks[bi][2])
        if len(colors) < n:
            return False
        for i in range(n):
            if i >= len(target) or colors[i] != target[i]:
                return False
        return True

    def heuristic(heads_var, blks):
        h = 0
        for pi, target in target_colors.items():
            n = n_indicators.get(pi, len(target))
            if n == 0:
                continue
            top_hi = None
            for i, hs in enumerate(heads_static):
                if hs[2] == pi and hs[1]:
                    top_hi = i
                    break
            if top_hi is None:
                h += 100
                continue

            seg_pos = get_seg_positions(heads_var, top_hi)

            for ti in range(n):
                if ti >= len(target):
                    h += 10
                    continue
                target_color = target[ti]
                if ti < len(seg_pos):
                    sx, sy = seg_pos[ti]
                    bi = find_block(blks, sx, sy)
                    if bi >= 0 and blks[bi][2] == target_color:
                        continue
                min_dist = 100
                for bx, by, bc in blks:
                    if bc == target_color:
                        if ti < len(seg_pos):
                            tx, ty = seg_pos[ti]
                        else:
                            hhx, hhy, count = heads_var[top_hi]
                            rot = heads_static[top_hi][0]
                            ddx, ddy = DIR_MAP[rot]
                            tx = hhx + ti * ddx * STEP
                            ty = hhy + ti * ddy * STEP
                        dist = abs(bx - tx) // STEP + abs(by - ty) // STEP
                        min_dist = min(min_dist, dist)
                h += min_dist

            hhx, hhy, count = heads_var[top_hi]
            if count < n + 1:
                h += (n + 1 - count)

        return h

    def try_move(heads_var, blks, active, action):
        hx, hy, count = heads_var[active]
        rot = heads_static[active][0]
        tdx, tdy = DIR_MAP[rot]

        move_map = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}
        mx, my = move_map[action]

        blks_list = list(blks)

        if (mx, my) == (tdx, tdy):
            # EXTEND
            lx = hx + (count - 1) * tdx * STEP
            ly = hy + (count - 1) * tdy * STEP
            nx, ny = lx + tdx * STEP, ly + tdy * STEP
            if not in_bounds(nx, ny) or has_wall(nx, ny):
                return None

            h_segs, v_segs = get_all_seg_positions(heads_var)

            pushed = set()
            for i in range(count - 1, -1, -1):
                sx = hx + i * tdx * STEP
                sy = hy + i * tdy * STEP
                dest_x = sx + tdx * STEP
                dest_y = sy + tdy * STEP

                bi = find_block(blks_list, sx, sy)
                if bi >= 0 and (sx, sy) not in pushed:
                    if can_push_chain(tuple(blks_list), sx, sy, tdx, tdy, frozenset(pushed), heads_var, h_segs, v_segs):
                        push_chain(blks_list, sx, sy, tdx, tdy, pushed)

                bi = find_block(blks_list, dest_x, dest_y)
                if bi >= 0 and (dest_x, dest_y) not in pushed:
                    if can_push_chain(tuple(blks_list), dest_x, dest_y, tdx, tdy, frozenset(pushed), heads_var, h_segs, v_segs):
                        push_chain(blks_list, dest_x, dest_y, tdx, tdy, pushed)

            new_heads = list(heads_var)
            new_heads[active] = (hx, hy, count + 1)
            return (tuple(new_heads), tuple(sorted(blks_list)))

        elif (mx, my) == (-tdx, -tdy):
            # RETRACT
            if count <= 1:
                return None

            rdx, rdy = -tdx, -tdy
            h_segs, v_segs = get_all_seg_positions(heads_var)

            pushed = set()
            for i in range(count - 1, 0, -1):
                sx = hx + i * tdx * STEP
                sy = hy + i * tdy * STEP
                dest_x = sx + rdx * STEP
                dest_y = sy + rdy * STEP

                bi = find_block(blks_list, sx, sy)
                if bi >= 0 and (sx, sy) not in pushed:
                    if can_push_chain(tuple(blks_list), sx, sy, rdx, rdy, frozenset(pushed), heads_var, h_segs, v_segs):
                        push_chain(blks_list, sx, sy, rdx, rdy, pushed)

                bi = find_block(blks_list, dest_x, dest_y)
                if bi >= 0 and (dest_x, dest_y) not in pushed:
                    if can_push_chain(tuple(blks_list), dest_x, dest_y, rdx, rdy, frozenset(pushed), heads_var, h_segs, v_segs):
                        push_chain(blks_list, dest_x, dest_y, rdx, rdy, pushed)

            new_heads = list(heads_var)
            new_heads[active] = (hx, hy, count - 1)
            return (tuple(new_heads), tuple(sorted(blks_list)))

        else:
            # LATERAL SLIDE
            check_x = hx + 2 + mx * STEP // 2
            check_y = hy + 2 + my * STEP // 2
            if not has_rail_at(hx, hy, check_x, check_y):
                return None

            h_segs, v_segs = get_all_seg_positions(heads_var, exclude_head=active)

            pushed = set()
            for i in range(count):
                sx = hx + i * tdx * STEP
                sy = hy + i * tdy * STEP
                dest_x = sx + mx * STEP
                dest_y = sy + my * STEP

                seg_oob = is_oob(sx, sy)
                if not seg_oob:
                    if not in_bounds(dest_x, dest_y):
                        return None
                    if has_wall(dest_x, dest_y):
                        return None

                bi = find_block(blks_list, sx, sy)
                if bi >= 0 and (sx, sy) not in pushed:
                    if can_push_chain(tuple(blks_list), sx, sy, mx, my, frozenset(pushed), heads_var, h_segs, v_segs):
                        push_chain(blks_list, sx, sy, mx, my, pushed)
                    elif not seg_oob:
                        return None

                bi = find_block(blks_list, dest_x, dest_y)
                if bi >= 0 and (dest_x, dest_y) not in pushed:
                    if can_push_chain(tuple(blks_list), dest_x, dest_y, mx, my, frozenset(pushed), heads_var, h_segs, v_segs):
                        push_chain(blks_list, dest_x, dest_y, mx, my, pushed)
                    elif not seg_oob:
                        return None

            new_heads = list(heads_var)
            new_heads[active] = (hx + mx * STEP, hy + my * STEP, count)
            return (tuple(new_heads), tuple(sorted(blks_list)))

    return try_move, is_solved, is_pair_solved, heuristic


def make_state_key(heads_var, blks, active, mutable_heads):
    hk = tuple(heads_var[hi] for hi in mutable_heads)
    return (hk, blks, active)


def make_state_key_noactive(heads_var, blks, mutable_heads):
    hk = tuple(heads_var[hi] for hi in mutable_heads)
    return (hk, blks)


def astar_solve(info, max_depth=80, max_states=5000000, time_limit=240,
                goal_check=None, active_only=None, weight=1.0):
    """A* search with heuristic.

    goal_check: optional function(heads_var, blks) -> bool for custom goal
    active_only: if set, only use this head (no switching)
    weight: heuristic weight (1.0 = optimal A*, >1.0 = faster but suboptimal)
    """
    start = time.time()
    try_move, is_solved, is_pair_solved, heuristic = make_solver(info)
    top_indices = info['top_head_indices']
    heads_static = info['heads_static']

    mutable_heads = [i for i, hs in enumerate(heads_static) if hs[1]]
    if not mutable_heads:
        mutable_heads = list(range(len(heads_static)))

    initial_heads = tuple(info['heads_init'])
    initial_blocks = tuple(sorted(info['top_blocks']))
    initial_active = info['active_idx'] if active_only is None else active_only

    if goal_check is None:
        goal_check = is_solved

    if goal_check(initial_heads, initial_blocks):
        return []

    h0 = heuristic(initial_heads, initial_blocks) * weight

    use_switch = len(top_indices) > 1 and active_only is None

    # For multi-head levels, use active-agnostic state key to cut state space
    if use_switch:
        initial_key = make_state_key_noactive(initial_heads, initial_blocks, mutable_heads)
    else:
        initial_key = make_state_key(initial_heads, initial_blocks, initial_active, mutable_heads)

    counter = 0
    heap = [(h0, counter, initial_heads, initial_blocks, initial_active, [])]
    visited = {}
    visited[initial_key] = 0

    states_explored = 0

    while heap:
        if time.time() - start > time_limit:
            print(f"    A* timeout: {states_explored} states, {time.time()-start:.1f}s")
            return None

        f, _, heads_var, blks, active, moves = heapq.heappop(heap)
        g = len(moves)

        if use_switch:
            nk = make_state_key_noactive(heads_var, blks, mutable_heads)
        else:
            nk = make_state_key(heads_var, blks, active, mutable_heads)
        if g > visited.get(nk, g):
            continue

        if g >= max_depth:
            continue

        states_explored += 1

        if use_switch:
            # Multi-head: try moves for ALL heads, inserting switches as needed
            for head_idx in top_indices:
                switch_cost = 0 if head_idx == active else 1
                for action in [1, 2, 3, 4]:
                    result = try_move(heads_var, blks, head_idx, action)
                    if result is None:
                        continue

                    new_heads, new_blks = result
                    new_key = make_state_key_noactive(new_heads, new_blks, mutable_heads)
                    new_g = g + 1 + switch_cost

                    if new_g > max_depth:
                        continue
                    if new_key in visited and visited[new_key] <= new_g:
                        continue
                    visited[new_key] = new_g

                    if switch_cost:
                        new_moves = moves + [('switch', head_idx), action]
                    else:
                        new_moves = moves + [action]

                    if goal_check(new_heads, new_blks):
                        print(f"    A* solved: {len(new_moves)} moves, {states_explored} states, {time.time()-start:.1f}s")
                        return new_moves

                    h = heuristic(new_heads, new_blks) * weight
                    counter += 1
                    heapq.heappush(heap, (new_g + h, counter, new_heads, new_blks, head_idx, new_moves))
        else:
            for action in [1, 2, 3, 4]:
                result = try_move(heads_var, blks, active, action)
                if result is None:
                    continue

                new_heads, new_blks = result
                new_key = make_state_key(new_heads, new_blks, active, mutable_heads)
                new_g = g + 1

                if new_key in visited and visited[new_key] <= new_g:
                    continue
                visited[new_key] = new_g

                new_moves = moves + [action]
                if goal_check(new_heads, new_blks):
                    print(f"    A* solved: {len(new_moves)} moves, {states_explored} states, {time.time()-start:.1f}s")
                    return new_moves

                h = heuristic(new_heads, new_blks) * weight
                counter += 1
                heapq.heappush(heap, (new_g + h, counter, new_heads, new_blks, active, new_moves))

        if len(visited) > max_states:
            print(f"    A* state limit: {len(visited)} states, {time.time()-start:.1f}s")
            return None

        if states_explored % 500000 == 0:
            print(f"    A*: {states_explored} explored, {len(visited)} visited, f={f}, {time.time()-start:.1f}s")

    print(f"    A* exhausted: {states_explored} states")
    return None


def execute_solution(env, game, solution, info):
    """Execute solution moves on the SDK. Returns (won, action_count).

    Uses action 7 (no-op) for animation waits instead of directional moves.
    """
    initial_level = game._current_level_index
    action_count = 0

    for mi, move in enumerate(solution):
        if isinstance(move, tuple) and move[0] == 'switch':
            new_active = move[1]
            head = info['head_sprites'].get(new_active)
            if head:
                cx = head.x + 3
                cy = head.y + 3
                obs = env.step(6, data={"x": cx, "y": cy})
                action_count += 1
                if game._current_level_index != initial_level:
                    return True, action_count
            continue

        obs = env.step(move)
        action_count += 1

        if game._current_level_index != initial_level:
            return True, action_count

        # Wait for animations with no-op action 7
        safety = 0
        while (game.ljprkjlji or game.pzzwlsmdt) and safety < 5:
            obs = env.step(7)
            action_count += 1
            safety += 1
            if game._current_level_index != initial_level:
                return True, action_count

        if game.lgdrixfno >= 0:
            # Level completion animation - wait until level advances or game ends
            anim_count = 0
            while game.lgdrixfno >= 0 and anim_count < 40:
                obs = env.step(7)
                action_count += 1
                anim_count += 1
                if game._current_level_index != initial_level:
                    break
                if obs.state.name != "NOT_FINISHED":
                    break
            print(f"    Animation wait: {anim_count} steps after move {mi+1}/{len(solution)}")
            return True, action_count

    # After all moves, check if level needs to complete
    if game.lgdrixfno >= 0:
        anim_count = 0
        while game.lgdrixfno >= 0 and anim_count < 40:
            obs = env.step(7)
            action_count += 1
            anim_count += 1
            if game._current_level_index != initial_level:
                break
            if obs.state.name != "NOT_FINISHED":
                break
        print(f"    Final animation wait: {anim_count} steps")
        return True, action_count

    return False, action_count


def solve_level(env, game, info, level_num):
    """Solve a single level. Returns shortest solution found or None."""
    try_move, is_solved, is_pair_solved, heuristic = make_solver(info)
    top_indices = info['top_head_indices']
    n_pairs = len(info['target_colors'])

    best_solution = None

    is_multi_head = n_pairs > 1 and len(top_indices) > 1

    # For multi-head levels, try sequential pair decomposition FIRST (much faster)
    if is_multi_head:
        print(f"  Strategy 2: Sequential pair solving (multi-head, {n_pairs} pairs)")
        for first_pair in range(n_pairs):
            print(f"    Trying pair {first_pair} first...")

            first_head = None
            for i, hs in enumerate(info['heads_static']):
                if hs[2] == first_pair and hs[1] and i in top_indices:
                    first_head = i
                    break
            if first_head is None:
                continue

            def goal_first(heads_var, blks, pi=first_pair):
                return is_pair_solved(heads_var, blks, pi)

            info_copy = dict(info)
            info_copy['active_idx'] = first_head

            max_d1 = 50
            if best_solution is not None:
                max_d1 = min(max_d1, len(best_solution) - 2)

            sol1 = astar_solve(info_copy, max_depth=max_d1, max_states=3000000,
                             time_limit=90, goal_check=goal_first, active_only=first_head)

            if sol1 is None:
                continue

            print(f"    Pair {first_pair} solved in {len(sol1)} moves")

            heads_var = tuple(info['heads_init'])
            blks = tuple(sorted(info['top_blocks']))
            for move in sol1:
                if isinstance(move, tuple):
                    continue
                result = try_move(heads_var, blks, first_head, move)
                if result:
                    heads_var, blks = result

            other_pair = 1 - first_pair
            other_head = None
            for i, hs in enumerate(info['heads_static']):
                if hs[2] == other_pair and hs[1] and i in top_indices:
                    other_head = i
                    break
            if other_head is None:
                continue

            # Solve remaining pair with just the other head
            info2 = dict(info)
            info2['heads_init'] = list(heads_var)
            info2['top_blocks'] = list(blks)
            info2['active_idx'] = other_head

            max_d2 = 60
            if best_solution is not None:
                max_d2 = min(max_d2, len(best_solution) - len(sol1) - 1)
                if max_d2 <= 0:
                    continue

            sol2 = astar_solve(info2, max_depth=max_d2, max_states=3000000,
                             time_limit=120, active_only=other_head)

            if sol2 is not None:
                combined = list(sol1)
                combined.append(('switch', other_head))
                combined.extend(sol2)
                print(f"    Combined solution: {len(combined)} moves")
                if best_solution is None or len(combined) < len(best_solution):
                    best_solution = combined

    # Strategy 1: Direct A* (for single-head, or multi-head when decomposition failed)
    if not is_multi_head or best_solution is None:
        print(f"  Strategy 1: Direct A*")
        max_s = 3000000 if is_multi_head else 5000000
        solution = astar_solve(info, max_depth=80, max_states=max_s, time_limit=180)
        if solution is not None:
            if best_solution is None or len(solution) < len(best_solution):
                best_solution = solution
                print(f"    Direct A* found {len(solution)} moves")
            # Try shortening
            cur_depth = len(best_solution) - 1
            while cur_depth > 0:
                shorter = astar_solve(info, max_depth=cur_depth, max_states=max_s, time_limit=120)
                if shorter is not None:
                    best_solution = shorter
                    print(f"    Shortened to {len(shorter)} moves")
                    cur_depth = len(shorter) - 1
                else:
                    break

    # Strategy 1.5: Weighted A*
    if best_solution is None:
        weights = [2.0, 3.0, 5.0, 8.0] if is_multi_head else [2.0, 3.0, 5.0]
        max_s = 3000000 if is_multi_head else 5000000
        for w in weights:
            print(f"  Strategy 1.5: Weighted A* (w={w})")
            solution = astar_solve(info, max_depth=100 if is_multi_head else 80,
                                   max_states=max_s, time_limit=180, weight=w)
            if solution is not None:
                if best_solution is None or len(solution) < len(best_solution):
                    best_solution = solution
                    print(f"    Weighted A* (w={w}) found {len(solution)} moves")
                break

    if best_solution is not None:
        print(f"  Best solution: {len(best_solution)} moves")
    return best_solution


def solve():
    arc = arc_agi.Arcade()
    env = arc.make('sk48')
    obs = env.reset()
    game = env._game

    total_levels = obs.win_levels
    levels_solved = 0
    level_actions = []

    human_baselines = [61, 177, 101, 103, 230, 181, 125, 92]

    print(f"Game: sk48, Levels: {total_levels}")

    for level_num in range(1, total_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        print(f"\n{'='*60}")
        print(f"LEVEL {level_num}/{total_levels} (moves_left={game.qiercdohl})")

        info = extract_level_info(game)

        for i, (hs, hi) in enumerate(zip(info['heads_static'], info['heads_init'])):
            role = "TOP" if hs[1] else "BOT"
            print(f"  {role} head[{i}] ({hi[0]},{hi[1]}) rot={hs[0]} segs={hi[2]} pair={hs[2]}")
        print(f"  Blocks: {info['top_blocks']}")
        print(f"  Targets: {info['target_colors']}")
        print(f"  Bounds: {info['bounds']}, Walls: {len(info['walls'])}, Rails: {len(info['rails'])}")

        solution = solve_level(env, game, info, level_num)

        if solution:
            move_strs = [str(m) if isinstance(m, int) else f"SW{m[1]}" for m in solution]
            print(f"  Solution ({len(solution)} moves): {' '.join(move_strs[:40])}")
            won, actions = execute_solution(env, game, solution, info)
            if won:
                levels_solved += 1
                level_actions.append(actions)
                print(f"  SOLVED level {level_num}! (actions={actions})")
                continue
            else:
                print(f"  Execution failed - sim mismatch")
        else:
            print(f"  No solution found")

        print(f"  FAILED level {level_num}")
        level_actions.append(999)
        break

    final_obs = env.step(1)
    levels_solved = max(levels_solved, final_obs.levels_completed)

    print(f"\n{'='*60}")
    print(f"GAME_ID: sk48")
    print(f"LEVELS_SOLVED: {levels_solved}")
    print(f"TOTAL_LEVELS: {total_levels}")

    # Print RHAE table
    print(f"\n{'='*60}")
    print(f"{'GAME':>6} {'LEVEL':>6}|{'HUMAN':>6}|{'OURS':>6}|{'RATIO':>7}|{'RHAE':>8}")
    print(f"{'-'*6} {'-'*6}|{'-'*6}|{'-'*6}|{'-'*7}|{'-'*8}")
    total_rhae = 0
    for i, actions in enumerate(level_actions):
        human = human_baselines[i] if i < len(human_baselines) else 100
        ratio = human / actions if actions > 0 else 0
        rhae = ratio ** 2
        total_rhae += rhae
        print(f"{'sk48':>6} L{i+1:>4}|{human:>6}|{actions:>6}|{ratio:>7.3f}|{rhae:>8.4f}")
    print(f"{'-'*6} {'-'*6}|{'-'*6}|{'-'*6}|{'-'*7}|{'-'*8}")
    print(f"{'':>6} {'TOTAL':>6}|{'':>6}|{'':>6}|{'':>7}|{total_rhae:>8.4f}")
    print(f"{'':>6} {'AVG':>6}|{'':>6}|{'':>6}|{'':>7}|{total_rhae/len(level_actions):>8.4f}")

    return levels_solved, total_levels


if __name__ == "__main__":
    solve()
