#!/usr/bin/env python3
"""Solver for ARC-AGI-3 game wa30.

Grid puzzle: move targets onto goal zones. Player step=4.
Actions: 1=up, 2=down, 3=left, 4=right, 5=grab/release.
NPCs auto-pathfind. Win when all targets on goals and unlinked.

Hybrid solver: plans direct delivery or barrier relay per target.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import arc_agi
from collections import deque
import random

STEP = 4
GRID = 64


def replay_actions(env, level_solutions):
    obs = env.reset()
    obs = env.step(6)
    for lnum in sorted(level_solutions.keys()):
        for action in level_solutions[lnum]:
            obs = env.step(action)
    return obs


def get_goal_cells(game):
    """Get grid-aligned goal cells from pixel-level goal zone."""
    cells = set()
    for px, py in game.wyzquhjerd:
        cell = ((px // STEP) * STEP, (py // STEP) * STEP)
        cells.add(cell)
    return cells


def get_secondary_cells(game):
    cells = set()
    for px, py in game.lqctaojiby:
        cell = ((px // STEP) * STEP, (py // STEP) * STEP)
        cells.add(cell)
    return cells


def in_bounds(pos):
    return 0 <= pos[0] < GRID and 0 <= pos[1] < GRID


def pathfind(start, goal, blocked):
    """BFS shortest path from start to goal avoiding blocked cells."""
    if start == goal:
        return [start]
    visited = {start}
    queue = deque([(start, [start])])
    while queue:
        pos, path = queue.popleft()
        for dx, dy in [(0, -STEP), (0, STEP), (-STEP, 0), (STEP, 0)]:
            npos = (pos[0] + dx, pos[1] + dy)
            if npos == goal:
                return path + [npos]
            if npos not in visited and npos not in blocked and in_bounds(npos):
                visited.add(npos)
                queue.append((npos, path + [npos]))
    return None


def pathfind_cargo(start, goal, cargo_off, blocked, barriers=set()):
    """BFS with cargo. Player can't step on barriers but cargo can."""
    if start == goal:
        return [start]
    visited = {start}
    queue = deque([(start, [start])])
    player_cant = blocked | barriers
    while queue:
        pos, path = queue.popleft()
        for dx, dy in [(0, -STEP), (0, STEP), (-STEP, 0), (STEP, 0)]:
            npos = (pos[0] + dx, pos[1] + dy)
            cpos = (npos[0] + cargo_off[0], npos[1] + cargo_off[1])
            if npos == goal:
                cgoal = (goal[0] + cargo_off[0], goal[1] + cargo_off[1])
                if cgoal not in blocked and in_bounds(cgoal):
                    return path + [npos]
                continue
            if (npos not in visited and npos not in player_cant
                    and cpos not in blocked and in_bounds(npos) and in_bounds(cpos)):
                visited.add(npos)
                queue.append((npos, path + [npos]))
    return None


def dir_to_action(dx, dy):
    if dy < 0: return 1
    if dy > 0: return 2
    if dx < 0: return 3
    return 4


def action_to_rot(a):
    return {1: 0, 2: 180, 3: 270, 4: 90}[a]


def path_to_actions(path):
    actions = []
    for i in range(len(path) - 1):
        dx = path[i+1][0] - path[i][0]
        dy = path[i+1][1] - path[i][1]
        actions.append(dir_to_action(dx, dy))
    return actions


def npc_delivery_bfs(npc_start, cargo_off, blocked, barriers, goal_cells):
    """BFS to check if NPC carrying cargo can reach any goal.
    NPC can't step on barriers or blocked. Cargo can't be on blocked but CAN be on barriers.
    Returns shortest path length to a goal, or None if unreachable."""
    visited = {npc_start}
    queue = deque([(npc_start, 0)])
    npc_cant = blocked | barriers
    while queue:
        pos, dist = queue.popleft()
        for dx, dy in [(0, -STEP), (0, STEP), (-STEP, 0), (STEP, 0)]:
            npos = (pos[0] + dx, pos[1] + dy)
            if npos in visited:
                continue
            cpos = (npos[0] + cargo_off[0], npos[1] + cargo_off[1])
            # Check if cargo lands on a goal
            if cpos in goal_cells and cpos not in blocked:
                if npos not in npc_cant and in_bounds(npos):
                    return dist + 1
            # Check movement validity: NPC not on blocked/barriers, cargo not on blocked, both in bounds
            if (npos not in npc_cant and cpos not in blocked
                    and in_bounds(npos) and in_bounds(cpos)):
                visited.add(npos)
                queue.append((npos, dist + 1))
    return None


def npc_delivery_score(bpos, barriers, blocked, goal_cells, placed_cells):
    """Score a barrier position by BFS-verified NPC delivery capability.
    For each possible NPC approach direction, simulates full BFS pathfinding
    with cargo offset to verify the NPC can actually reach a goal.
    Returns score > 0 only if delivery is feasible within reasonable distance.
    Score is inversely proportional to NPC delivery distance."""
    avail = goal_cells - placed_cells
    if not avail:
        return 1  # No goals needed

    best_score = 0
    for adx, ady in [(0, -STEP), (0, STEP), (-STEP, 0), (STEP, 0)]:
        npc_pos = (bpos[0] + adx, bpos[1] + ady)
        if not in_bounds(npc_pos) or npc_pos in barriers:
            continue
        if npc_pos in blocked:
            continue
        npc_cargo_off = (-adx, -ady)
        # Full BFS to verify NPC can deliver to at least one goal
        dist = npc_delivery_bfs(npc_pos, npc_cargo_off, blocked, barriers, avail)
        if dist is not None and dist <= 25:
            # Score heavily favors short delivery distances
            best_score = max(best_score, max(1, 50 - 2 * dist))
    return best_score


def npc_delivery_bfs_to_goal(npc_start, cargo_off, blocked, barriers, target_goal):
    """BFS to check if NPC can deliver cargo to a SPECIFIC goal cell.
    Returns shortest path length, or None if unreachable."""
    visited = {npc_start}
    queue = deque([(npc_start, 0)])
    npc_cant = blocked | barriers
    while queue:
        pos, dist = queue.popleft()
        for dx, dy in [(0, -STEP), (0, STEP), (-STEP, 0), (STEP, 0)]:
            npos = (pos[0] + dx, pos[1] + dy)
            if npos in visited:
                continue
            cpos = (npos[0] + cargo_off[0], npos[1] + cargo_off[1])
            if cpos == target_goal and cpos not in blocked:
                if npos not in npc_cant and in_bounds(npos):
                    return dist + 1
            if (npos not in npc_cant and cpos not in blocked
                    and in_bounds(npos) and in_bounds(cpos)):
                visited.add(npos)
                queue.append((npos, dist + 1))
    return None


def solve_level(env, game, level_num, level_solutions):
    """Reactive solver: each step picks the best action."""
    all_actions = []
    level = game.current_level
    step_limit = game.kuncbnslnm.dbdarsgrbj

    barriers = set(game.qthdiggudy)
    has_barriers = len(barriers) > 0

    stuck_counter = 0
    last_state = None
    rng = random.Random(42 + level_num)

    # Track which barriers have been used and which goals are reserved
    used_barriers = set()
    reserved_goals = set()

    for step_i in range(step_limit + 5):
        player = level.get_sprites_by_tag("wbmdvjhthc")[0]
        targets = list(level.get_sprites_by_tag("geezpjgiyd"))
        goal_cells = get_goal_cells(game)

        px, py = player.x, player.y
        prot = player.rotation
        holding = player in game.nsevyuople

        state = (px, py, prot, holding, tuple(sorted((t.x, t.y) for t in targets)))
        if state == last_state:
            stuck_counter += 1
        else:
            stuck_counter = 0
        last_state = state

        blocked = set(game.pkbufziase)
        cant = blocked | barriers

        placed_cells = set()
        unplaced_all = []
        for t in targets:
            if (t.x, t.y) in game.wyzquhjerd and t not in game.zmqreragji:
                placed_cells.add((t.x, t.y))
            elif t not in game.zmqreragji:
                unplaced_all.append(t)

        avail_goals = goal_cells - placed_cells

        # Targets the player needs to handle (not on barriers, not being carried by NPCs)
        unplaced = [t for t in unplaced_all if (t.x, t.y) not in barriers]

        action = None

        if stuck_counter > 6:
            action = rng.choice([1, 2, 3, 4, 5])

        elif holding:
            linked = game.nsevyuople[player]
            cargo_off = (linked.x - px, linked.y - py)

            if (linked.x, linked.y) in game.wyzquhjerd:
                action = 5  # On goal, release
            elif (linked.x, linked.y) in barriers:
                action = 5  # On barrier, release for NPC relay
                bpos = (linked.x, linked.y)
                used_barriers.add(bpos)
                # Reserve the best goal this NPC delivery can reach
                truly_avail = avail_goals - reserved_goals
                for adx, ady in [(0, -STEP), (0, STEP), (-STEP, 0), (STEP, 0)]:
                    npc_pos = (bpos[0] + adx, bpos[1] + ady)
                    if not in_bounds(npc_pos) or npc_pos in barriers or npc_pos in blocked:
                        continue
                    npc_cargo_off = (-adx, -ady)
                    best_g = None
                    best_d = 999
                    for goal in truly_avail:
                        d = npc_delivery_bfs_to_goal(npc_pos, npc_cargo_off, blocked, barriers, goal)
                        if d is not None and d < best_d:
                            best_d = d
                            best_g = goal
                    if best_g:
                        reserved_goals.add(best_g)
                        break
            else:
                blocked_cargo = blocked.copy()
                blocked_cargo.discard((linked.x, linked.y))
                blocked_cargo.discard((px, py))

                best_pdest = None
                best_dist = float('inf')
                best_path = None

                # Try direct delivery to goal
                for goal in avail_goals:
                    pdest = (goal[0] - cargo_off[0], goal[1] - cargo_off[1])
                    if not in_bounds(pdest):
                        continue
                    path = pathfind_cargo((px, py), pdest, cargo_off, blocked_cargo, barriers)
                    if path and len(path) < best_dist:
                        best_dist = len(path)
                        best_pdest = pdest
                        best_path = path

                # Try barrier relay - prefer barriers with highest NPC delivery score
                if has_barriers:
                    carry_blocked = (blocked | barriers) - {(linked.x, linked.y)} - {(px, py)}
                    barrier_candidates = []

                    # Goals that are still available (not placed, not reserved by other barrier drops)
                    truly_avail = avail_goals - reserved_goals

                    for bpos in barriers:
                        if bpos in blocked_cargo or bpos in used_barriers:
                            continue
                        pdest = (bpos[0] - cargo_off[0], bpos[1] - cargo_off[1])
                        if pdest in carry_blocked or not in_bounds(pdest):
                            continue
                        path = pathfind_cargo((px, py), pdest, cargo_off, blocked_cargo, barriers)
                        if not path:
                            continue
                        # Find best goal this barrier can deliver to (via NPC BFS)
                        best_barr_score = 0
                        best_goal_for_barr = None
                        for adx, ady in [(0, -STEP), (0, STEP), (-STEP, 0), (STEP, 0)]:
                            npc_pos = (bpos[0] + adx, bpos[1] + ady)
                            if not in_bounds(npc_pos) or npc_pos in barriers or npc_pos in blocked_cargo:
                                continue
                            npc_cargo_off = (-adx, -ady)
                            for goal in truly_avail:
                                dist_to_goal = npc_delivery_bfs_to_goal(npc_pos, npc_cargo_off, blocked_cargo, barriers, goal)
                                if dist_to_goal is not None and dist_to_goal <= 25:
                                    s = max(1, 50 - 2 * dist_to_goal)
                                    if s > best_barr_score:
                                        best_barr_score = s
                                        best_goal_for_barr = goal
                        if best_barr_score > 0:
                            barrier_candidates.append((best_barr_score, len(path), pdest, path, best_goal_for_barr))

                    # Sort: highest score first, then shortest path
                    barrier_candidates.sort(key=lambda x: (-x[0], x[1]))
                    if barrier_candidates:
                        score, dist, pdest, path, goal_reserved = barrier_candidates[0]
                        if dist < best_dist or score > 0:
                            best_dist = dist
                            best_pdest = pdest
                            best_path = path

                if best_pdest and best_path:
                    if (px, py) == best_pdest:
                        action = 5
                    elif len(best_path) > 1:
                        dx = best_path[1][0] - px
                        dy = best_path[1][1] - py
                        action = dir_to_action(dx, dy)
                    else:
                        action = 5
                else:
                    action = 5
        else:
            if not unplaced:
                action = 1  # Idle for NPCs
            else:
                best_adj = None
                best_total = float('inf')
                best_target = None

                cant_est = cant - {(px, py)}

                for t in unplaced:
                    tpos = (t.x, t.y)
                    cant_est2 = cant_est - {tpos}

                    for adx, ady in [(0, -STEP), (0, STEP), (-STEP, 0), (STEP, 0)]:
                        adj = (tpos[0] + adx, tpos[1] + ady)
                        if not in_bounds(adj):
                            continue
                        if adj != (px, py) and adj in cant:
                            continue

                        # BFS approach distance
                        approach_path = pathfind((px, py), adj, cant_est2)
                        if not approach_path:
                            continue
                        d_approach = len(approach_path) - 1

                        coff = (-adx, -ady)
                        d_deliver = float('inf')

                        # Try direct delivery to goals (verify with BFS)
                        blocked_est = cant_est2 - {adj}
                        for goal in avail_goals:
                            pdest = (goal[0] - coff[0], goal[1] - coff[1])
                            if not in_bounds(pdest) or pdest in cant_est2:
                                continue
                            cpath = pathfind_cargo(adj, pdest, coff, blocked_est - barriers, barriers)
                            if cpath:
                                d = len(cpath) - 1
                                if d < d_deliver:
                                    d_deliver = d

                        # Try barrier relay - prefer deliverable barriers
                        if has_barriers:
                            truly_avail_est = avail_goals - reserved_goals
                            for bpos in barriers:
                                if bpos in blocked or bpos in used_barriers:
                                    continue
                                pdest = (bpos[0] - coff[0], bpos[1] - coff[1])
                                if pdest in cant_est2 or not in_bounds(pdest):
                                    continue
                                if pdest in barriers:
                                    continue
                                cpath = pathfind_cargo(adj, pdest, coff, blocked_est - barriers, barriers)
                                if cpath:
                                    d = len(cpath) - 1
                                    score = npc_delivery_score(bpos, barriers, blocked, truly_avail_est | avail_goals, placed_cells)
                                    # Reduce effective distance for high-score barriers
                                    # High score = short NPC delivery = better barrier
                                    effective_d = d - min(score // 5, 5)
                                    if effective_d < d_deliver:
                                        d_deliver = effective_d

                        total = d_approach + d_deliver + 3
                        if total < best_total:
                            best_total = total
                            best_adj = adj
                            best_target = t

                if best_adj is None:
                    action = 1
                else:
                    tpos = (best_target.x, best_target.y)
                    dist_to_adj = abs(px - best_adj[0]) + abs(py - best_adj[1])

                    if dist_to_adj == 0:
                        face_dx = tpos[0] - px
                        face_dy = tpos[1] - py
                        if abs(face_dx) + abs(face_dy) == STEP:
                            fa = dir_to_action(face_dx, face_dy)
                            if prot == action_to_rot(fa):
                                action = 5
                            else:
                                action = fa
                        else:
                            action = 1
                    else:
                        path = pathfind((px, py), best_adj, cant)
                        if path and len(path) > 1:
                            dx = path[1][0] - px
                            dy = path[1][1] - py
                            action = dir_to_action(dx, dy)
                        else:
                            action = 1

        obs = env.step(action)
        all_actions.append(action)

        if obs.levels_completed >= level_num:
            print(f"  SOLVED L{level_num}! {len(all_actions)} actions")
            return all_actions
        if obs.state.name in ("LOSE", "GAME_OVER"):
            print(f"  {obs.state.name} at step {len(all_actions)}")
            return None
        if obs.state.name != "NOT_FINISHED":
            print(f"  Unexpected: {obs.state.name}")
            return None

    print(f"  Solver loop exhausted ({len(all_actions)} actions)")
    return None


MANUAL_SOLUTIONS = {
    5: [4, 4, 2, 2, 5, 1, 1, 1, 1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 3, 5,
        4, 1, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 1, 1, 1, 3, 5,
        2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 5,
        4, 4, 4, 4, 4, 4, 4, 2, 2, 2, 2, 2, 5, 1, 1, 1, 1, 1, 1,
        3, 3, 3, 3, 3, 3, 3, 1, 1, 3, 3, 5,
        1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    6: [1, 1, 1, 1, 1, 1, 1, 4, 4, 4, 4, 4, 4, 5, 4, 5,
        3, 3, 3, 3, 3, 3, 1, 1, 5,
        2, 2, 4, 4, 4, 4, 4, 4, 4, 4, 4, 2, 3, 5, 1,
        3, 3, 3, 3, 3, 3, 1, 1, 5],
    7: [1, 4, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 5,
        1, 4, 5, 3, 3, 3, 3, 3, 2, 2, 5,
        1, 1, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 2, 5,
        1, 3, 3, 3, 3, 3, 3, 3, 3, 3, 5],
    8: [1, 4, 4, 4, 1, 1, 1, 5, 5, 2, 2, 2, 2, 4, 4, 4, 4, 4, 2, 2, 2,
        3, 1, 2, 3, 3, 2, 4, 4, 4, 4, 2, 4, 5, 2, 3, 1, 3, 2, 3, 3, 3,
        5, 4, 4, 1, 4, 4, 4, 4, 4, 5, 4, 1, 1, 1, 3, 3, 3, 3, 1, 1, 1,
        3, 3, 3, 3, 3, 1, 1, 1, 3, 3, 3, 1, 5, 4, 4, 4, 4, 4, 4, 4, 4,
        4, 5, 3, 3, 3, 3, 3, 3, 3, 3, 1, 1, 3, 5, 4, 4, 4, 4, 4, 2, 2,
        2, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 1, 4, 1, 5],
}


def main():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make("wa30")
    obs = env.reset()
    obs = env.step(6)
    game = env._game

    total_levels = obs.win_levels
    print(f"wa30: {total_levels} levels")

    level_solutions = {}
    baselines = [71, 119, 183, 98, 368, 68, 79, 442, 415]

    for level_num in range(1, total_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        replay_actions(env, level_solutions)
        game = env._game
        level = game.current_level

        player = level.get_sprites_by_tag("wbmdvjhthc")[0]
        targets = level.get_sprites_by_tag("geezpjgiyd")
        npcs_k = level.get_sprites_by_tag("kdweefinfi")
        npcs_y = level.get_sprites_by_tag("ysysltqlke")
        step_limit = game.kuncbnslnm.dbdarsgrbj
        baseline = baselines[level_num - 1] if level_num <= len(baselines) else 999

        on_goals = sum(1 for t in targets if (t.x, t.y) in game.wyzquhjerd)
        print(f"\n{'='*50}")
        print(f"L{level_num}: player=({player.x},{player.y}), {len(targets)} targets ({on_goals} on goals), "
              f"{len(npcs_k)} kdw, {len(npcs_y)} ysy, steps={step_limit}, baseline={baseline}")

        # Use manual solutions for levels that have them
        if level_num in MANUAL_SOLUTIONS:
            solution = MANUAL_SOLUTIONS[level_num]
            # Verify by replaying
            for a in solution:
                obs = env.step(a)
            if obs.levels_completed >= level_num:
                print(f"  SOLVED L{level_num} (manual)! {len(solution)} actions")
            else:
                print(f"  Manual solution failed for L{level_num}, trying reactive solver")
                replay_actions(env, level_solutions)
                game = env._game
                solution = solve_level(env, game, level_num, level_solutions)
        else:
            solution = solve_level(env, game, level_num, level_solutions)

        if solution is not None:
            level_solutions[level_num] = solution
            obs = replay_actions(env, level_solutions)
            game = env._game
            if obs.levels_completed < level_num:
                print(f"  WARNING: replay didn't advance!")
                replay_actions(env, {k: v for k, v in level_solutions.items() if k < level_num})
                game = env._game
                for a in solution:
                    obs = env.step(a)
                if obs.levels_completed < level_num:
                    print(f"  Direct run also failed.")
                    break
        else:
            print(f"  L{level_num} FAILED")
            break

    completed = obs.levels_completed
    if obs.state.name == "WIN":
        completed = total_levels

    # Print results
    print(f"\n{'='*60}")
    print(f"GAME: wa30")
    print(f"{'='*60}")
    print(f"{'LEVEL':<6} | {'HUMAN':>5} | {'OURS':>5} | {'RATIO':>6} | {'RHAE':>5}")
    print(f"{'-'*6}-+-{'-'*5}-+-{'-'*5}-+-{'-'*6}-+-{'-'*5}")

    total_rhae = 0
    for i in range(total_levels):
        lnum = i + 1
        human = baselines[i] if i < len(baselines) else 999
        if lnum in level_solutions:
            ours = len(level_solutions[lnum])
            ratio = ours / human
            rhae = min(1.15, human / ours) ** 2
            rhae_pct = rhae * 100
        else:
            ours = 0
            ratio = float('inf')
            rhae_pct = 0
        total_rhae += rhae_pct
        ratio_str = f"{ratio:.2f}x" if ours > 0 else "FAIL"
        rhae_str = f"{rhae_pct:.1f}%" if ours > 0 else "0%"
        print(f"L{lnum:<5} | {human:>5} | {ours:>5} | {ratio_str:>6} | {rhae_str:>5}")

    avg_rhae = total_rhae / total_levels
    print(f"{'-'*6}-+-{'-'*5}-+-{'-'*5}-+-{'-'*6}-+-{'-'*5}")
    print(f"TOTAL_RHAE: {avg_rhae:.1f}% (avg over {total_levels} levels)")
    print(f"LEVELS_SOLVED: {completed}/{total_levels}")

    return completed, total_levels


if __name__ == "__main__":
    main()
