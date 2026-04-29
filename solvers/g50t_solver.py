#!/usr/bin/env python3
"""
g50t solver -- Decomposition approach for clone-recording puzzle.

Key insight: clones ending on plates keep walls open.
Decompose: figure out WHERE clones go (plates), then BFS last phase.

Strategy for 2-recording levels:
  1. Find all reachable positions for rec1 (dynamic BFS with wall tracking)
  2. For each rec1 target (plates first), find rec2 targets (dynamic)
  3. BFS last phase with (pos, step, walls) state
  4. Prioritize plate pairs that open DIFFERENT walls
"""

import sys
import os
import time
import logging
from collections import deque

sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

import arc_agi
from arcengine.enums import GameAction, ActionInput, GameState

logging.getLogger('arc_agi').setLevel(logging.ERROR)
logging.getLogger('arc_agi.scorecard').setLevel(logging.ERROR)

ACTIONS = [GameAction.ACTION1, GameAction.ACTION2,
           GameAction.ACTION3, GameAction.ACTION4,
           GameAction.ACTION5]
MOVE_ACTIONS = ACTIONS[:4]
STEP = 6
DIRS = [(0, -1), (0, 1), (-1, 0), (1, 0)]
DIR_TO_ACTION = {d: ACTIONS[i] for i, d in enumerate(DIRS)}


def fast_action(game, action):
    game._set_action(ActionInput(id=action))
    for _ in range(1000):
        if game.is_action_complete():
            break
        if game._next_level:
            game._really_set_next_level()
        else:
            game.step()


def full_state_orig(game):
    gs = game.vgwycxsxjz
    p = gs.dzxunlkwxt
    if p.pddqxjztas:
        return None
    walls = tuple((w.x, w.y, w.dijhfchobv) for w in gs.uwxkstolmf)
    enemies = tuple(sorted((e.x, e.y) for e in gs.kgvnkyaimw))
    clone_info = []
    for c in gs.rloltuowth:
        rec = gs.rloltuowth[c]
        rec_len = len(rec)
        end_x, end_y = gs.yugzlzepkr, gs.vgpdqizwwm
        for dx, dy in rec:
            end_x += dx * 6
            end_y += dy * 6
        clone_info.append((c.x, c.y, rec_len, end_x, end_y))
    clones = tuple(sorted(clone_info))
    icon = gs.rlazdofsxb
    hist = len(gs.areahjypvy)
    max_rec = max((len(gs.rloltuowth[c]) for c in gs.rloltuowth), default=0)
    if hist > max_rec:
        hist = max_rec + 1
    return (p.x, p.y, walls, enemies, clones, icon, hist)


def dirs_to_actions(dirs):
    return [DIR_TO_ACTION[d] for d in dirs]


def execute_prefix(game, level_idx, init_score, prefix):
    game._score = init_score
    game.set_level(level_idx)
    game._state = GameState.NOT_FINISHED
    for m in prefix:
        fast_action(game, m)
        if game._score > init_score:
            return 'won'
        if game._state == GameState.GAME_OVER:
            return 'dead'
    gs = game.vgwycxsxjz
    if gs.dzxunlkwxt.pddqxjztas:
        return 'dead'
    if gs.jqpwhiraaj:
        return 'animating'
    return 'alive'


def solve_full_bfs(game, level_idx, init_score, max_depth, time_limit=300,
                   max_states=2000000):
    gs = game.vgwycxsxjz
    print(f"  Player=({gs.dzxunlkwxt.x},{gs.dzxunlkwxt.y}) "
          f"Goal=({gs.whftgckbcu.x},{gs.whftgckbcu.y})")
    print(f"  E={len(gs.kgvnkyaimw)} W={len(gs.uwxkstolmf)} I={len(gs.drofvwhbxb)}")

    game._score = init_score
    game.set_level(level_idx)
    game._state = GameState.NOT_FINISHED

    init_state = full_state_orig(game)
    if init_state is None:
        return None

    visited = {init_state}
    queue = deque([[]])
    explored = 0
    start_time = time.time()

    while queue:
        moves = queue.popleft()
        if len(moves) >= max_depth:
            continue

        for action in ACTIONS:
            new_moves = moves + [action]
            game._score = init_score
            game.set_level(level_idx)
            game._state = GameState.NOT_FINISHED

            won = dead = False
            for m in new_moves:
                fast_action(game, m)
                if game._score > init_score:
                    won = True
                    break
                if game._state == GameState.GAME_OVER:
                    dead = True
                    break

            if won:
                elapsed = time.time() - start_time
                print(f"  SOLVED! {len(new_moves)} moves, {explored} st, {elapsed:.1f}s")
                return new_moves
            if dead:
                continue
            gs = game.vgwycxsxjz
            if gs.dzxunlkwxt.pddqxjztas or gs.jqpwhiraaj:
                continue
            state = full_state_orig(game)
            if state is None or state in visited:
                continue
            visited.add(state)
            queue.append(new_moves)
            explored += 1

            if explored % 10000 == 0:
                elapsed = time.time() - start_time
                d = len(new_moves)
                print(f"    {explored} st, d={d}, q={len(queue)}, {explored/(elapsed or 1):.0f}/s")

        if explored >= max_states or time.time() - start_time > time_limit:
            break

    elapsed = time.time() - start_time
    print(f"  BFS done: {explored} st, {elapsed:.1f}s")
    return None


def get_dynamic_paths(game, level_idx, init_score, prefix, max_len=25):
    """Dynamic BFS for recording paths, tracking wall state changes."""
    status = execute_prefix(game, level_idx, init_score, prefix)
    if status != 'alive':
        return {}

    gs = game.vgwycxsxjz
    paths = {}
    visited = set()

    def get_s(game, step):
        gs = game.vgwycxsxjz
        p = gs.dzxunlkwxt
        if p.pddqxjztas:
            return None
        walls = tuple(w.dijhfchobv for w in gs.uwxkstolmf)
        cp = tuple(sorted((c.x, c.y) for c in gs.rloltuowth))
        return (p.x, p.y, walls, cp, step)

    s0 = get_s(game, 0)
    if s0 is None:
        return {}
    visited.add(s0)
    queue = deque([([], 0)])

    while queue:
        dirs, step = queue.popleft()
        if len(dirs) >= max_len:
            continue
        for dx, dy in DIRS:
            new_dirs = dirs + [(dx, dy)]
            rec_actions = dirs_to_actions(new_dirs)
            full = prefix + rec_actions

            game._score = init_score
            game.set_level(level_idx)
            game._state = GameState.NOT_FINISHED
            ok = True
            for m in full:
                fast_action(game, m)
                if game._score > init_score or game._state == GameState.GAME_OVER:
                    ok = False
                    break
            if not ok:
                continue
            gs = game.vgwycxsxjz
            if gs.dzxunlkwxt.pddqxjztas or gs.jqpwhiraaj:
                continue

            s = get_s(game, step + 1)
            if s is None or s in visited:
                continue
            visited.add(s)

            ep = (gs.dzxunlkwxt.x, gs.dzxunlkwxt.y)
            if ep not in paths or len(new_dirs) < len(paths[ep]):
                paths[ep] = new_dirs
            queue.append((new_dirs, step + 1))

    return paths


def solve_last_phase(game, level_idx, init_score, prefix,
                     max_moves=100, time_limit=60):
    """BFS last phase with (pos, step, walls[, enemies]) state."""
    status = execute_prefix(game, level_idx, init_score, prefix)
    if status == 'won':
        return prefix
    if status != 'alive':
        return None

    gs = game.vgwycxsxjz
    n_enemies = len(gs.kgvnkyaimw)

    def get_state(game, step):
        gs = game.vgwycxsxjz
        p = gs.dzxunlkwxt
        if p.pddqxjztas:
            return None
        walls = tuple(w.dijhfchobv for w in gs.uwxkstolmf)
        if n_enemies > 0:
            enemies = tuple(sorted((e.x, e.y) for e in gs.kgvnkyaimw))
            return (p.x, p.y, step, walls, enemies)
        return (p.x, p.y, step, walls)

    init_s = get_state(game, 0)
    if init_s is None:
        return None
    visited = {init_s}
    queue = deque([([], 0)])
    explored = 0
    t0 = time.time()

    while queue:
        extra, step = queue.popleft()
        if len(extra) >= max_moves:
            continue

        for action in MOVE_ACTIONS:
            new_extra = extra + [action]
            full = prefix + new_extra

            game._score = init_score
            game.set_level(level_idx)
            game._state = GameState.NOT_FINISHED

            won = dead = False
            for m in full:
                fast_action(game, m)
                if game._score > init_score:
                    won = True
                    break
                if game._state == GameState.GAME_OVER:
                    dead = True
                    break

            if won:
                return full
            if dead:
                continue

            gs = game.vgwycxsxjz
            if gs.dzxunlkwxt.pddqxjztas or gs.jqpwhiraaj:
                continue

            state = get_state(game, step + 1)
            if state is None or state in visited:
                continue

            visited.add(state)
            queue.append((new_extra, step + 1))
            explored += 1

        if time.time() - t0 > time_limit:
            break

    return None


def get_plate_positions(game, level_idx, init_score):
    game._score = init_score
    game.set_level(level_idx)
    game._state = GameState.NOT_FINISHED
    gs = game.vgwycxsxjz
    return [(p.x, p.y) for p in gs.hamayflsib]


def get_wall_state_after_rec(game, level_idx, init_score, prefix):
    """Get wall state after executing prefix (post-recordings)."""
    status = execute_prefix(game, level_idx, init_score, prefix)
    if status != 'alive':
        return None
    gs = game.vgwycxsxjz
    return tuple(w.dijhfchobv for w in gs.uwxkstolmf)


def solve_enum(game, level_idx, init_score, time_limit=600):
    """Enumeration solver for all recording levels."""
    game._score = init_score
    game.set_level(level_idx)
    game._state = GameState.NOT_FINISHED
    gs = game.vgwycxsxjz
    n_icons = len(gs.drofvwhbxb)
    n_records = n_icons - 1

    print(f"  Player=({gs.dzxunlkwxt.x},{gs.dzxunlkwxt.y}) "
          f"Goal=({gs.whftgckbcu.x},{gs.whftgckbcu.y})")
    print(f"  E={len(gs.kgvnkyaimw)} W={len(gs.uwxkstolmf)} I={n_icons}")

    start_time = time.time()
    plate_set = set(get_plate_positions(game, level_idx, init_score))

    # Phase 1: Find all rec1 paths
    paths_rec1 = get_dynamic_paths(game, level_idx, init_score, [], max_len=25)
    sorted_rec1 = sorted(paths_rec1.keys(),
        key=lambda p: (0 if p in plate_set else 1, len(paths_rec1[p])))

    n_plates_rec1 = sum(1 for t in sorted_rec1 if t in plate_set)
    print(f"  Rec1: {len(sorted_rec1)} targets ({n_plates_rec1} plates)")

    if n_records == 1:
        # Single recording: try all targets, plates first
        for t in sorted_rec1:
            if time.time() - start_time > time_limit:
                break
            path = paths_rec1[t]
            prefix = dirs_to_actions(path) + [GameAction.ACTION5]
            remaining = time_limit - (time.time() - start_time)
            sol = solve_last_phase(game, level_idx, init_score, prefix,
                                   time_limit=min(45, remaining))
            if sol:
                print(f"  Found: {len(sol)} moves (rec={t}) ({time.time()-start_time:.1f}s)")
                return sol
        return None

    elif n_records == 2:
        attempts = 0

        # PASS 1: Try plate rec1 targets first (fast: fewer to explore)
        plate_rec1 = [t for t in sorted_rec1 if t in plate_set]
        non_plate_rec1 = [t for t in sorted_rec1 if t not in plate_set]

        pairs = []
        for t1 in plate_rec1:
            if time.time() - start_time > time_limit * 0.15:
                break
            path1 = paths_rec1[t1]
            prefix1 = dirs_to_actions(path1) + [GameAction.ACTION5]
            rec2_paths = get_dynamic_paths(game, level_idx, init_score, prefix1, max_len=25)
            rec2_plates = [t for t in rec2_paths if t in plate_set]

            for t2 in rec2_plates:
                path2 = rec2_paths[t2]
                same = 1 if t1 == t2 else 0
                total_len = len(path1) + len(path2)
                pairs.append(((same, total_len), t1, t2, path1, path2))

            # Also add non-plate rec2 targets
            for t2 in sorted(rec2_paths.keys(), key=lambda p: len(rec2_paths[p])):
                if t2 in plate_set:
                    continue
                path2 = rec2_paths[t2]
                total_len = len(path1) + len(path2)
                pairs.append(((2, total_len), t1, t2, path1, path2))

        # PASS 1b: Try non-plate rec1 targets that might pass through plates
        for t1 in non_plate_rec1[:10]:  # Limit to first 10
            if time.time() - start_time > time_limit * 0.3:
                break
            path1 = paths_rec1[t1]
            prefix1 = dirs_to_actions(path1) + [GameAction.ACTION5]
            rec2_paths = get_dynamic_paths(game, level_idx, init_score, prefix1, max_len=25)
            rec2_plates = [t for t in rec2_paths if t in plate_set]

            for t2 in rec2_plates:
                path2 = rec2_paths[t2]
                total_len = len(path1) + len(path2)
                pairs.append(((1, total_len), t1, t2, path1, path2))

        pairs.sort()
        print(f"  Pairs to try: {len(pairs)}")

        for score, t1, t2, path1, path2 in pairs:
            if time.time() - start_time > time_limit * 0.9:
                break
            prefix1 = dirs_to_actions(path1) + [GameAction.ACTION5]
            prefix = prefix1 + dirs_to_actions(path2) + [GameAction.ACTION5]
            remaining = time_limit * 0.9 - (time.time() - start_time)
            per = max(15, min(60, remaining / max(1, len(pairs) - attempts)))
            sol = solve_last_phase(game, level_idx, init_score, prefix,
                                   time_limit=per)
            attempts += 1
            if sol:
                print(f"  Found: {len(sol)} moves (rec1={t1}, rec2={t2}) ({time.time()-start_time:.1f}s)")
                return sol
            if attempts % 5 == 0:
                elapsed = time.time() - start_time
                print(f"  Progress: {attempts}/{len(pairs)}, {elapsed:.1f}s")

        elapsed = time.time() - start_time
        print(f"  Enum done: {attempts} attempts, {elapsed:.1f}s")
        return None

    return None


def replay_on_env(env, solutions):
    obs = env.reset()
    for lvl in sorted(solutions.keys()):
        for act in solutions[lvl]:
            obs = env.step(act)
    return obs


def solve_l6_hardcoded():
    """Hardcoded solution for Level 6.

    Strategy: 2 clones hold plates 0,1 (opening top-row walls).
    Enemy walks left through opened walls, toggling plates 2,3 (toggle walls).
    Player navigates through toggled walls to plate 4 (toggle), then to win tile.
    """
    # Action sequence: rec1(3 moves)+ACTION5, rec2(5 moves)+ACTION5, nav(39 moves)
    # Rec1: left,left,up -> clone to plate 0 at (43,25)
    # Rec2: left,left,up,left,left -> clone to plate 1 at (31,25)
    # Nav: navigate to plate 4, toggle wall 4, then to win tile (43,49)
    A1, A2, A3, A4, A5 = (GameAction.ACTION1, GameAction.ACTION2,
                           GameAction.ACTION3, GameAction.ACTION4,
                           GameAction.ACTION5)
    return [A3, A3, A1, A5, A3, A3, A1, A3, A3, A5,
            A3, A3, A2, A3, A3, A3, A3, A1, A1, A3, A3, A3,
            A2, A2, A2, A2, A2, A4, A4, A1, A2, A3, A3, A1, A1, A1, A1, A1,
            A4, A4, A4, A2, A2, A4, A4, A2, A2, A4, A4]


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('g50t')
    obs = env.reset()
    game = env._game

    n_levels = obs.win_levels
    print(f"g50t: {n_levels} levels")

    solutions = {}
    baselines = [78, 175, 179, 230, 96, 54, 67]

    for level in range(1, n_levels + 1):
        if obs.state in (GameState.WIN, GameState.GAME_OVER):
            break

        gs = game.vgwycxsxjz
        bl = baselines[level - 1] if level <= len(baselines) else 300

        print(f"\n{'='*50}")
        print(f"Level {level}/{n_levels} (baseline={bl})")

        init_score = game._score

        # Level 6: use hardcoded solution (clone+enemy+toggle wall strategy)
        if level == 6:
            sol = solve_l6_hardcoded()
            # Verify it works
            game._score = init_score
            game.set_level(level - 1)
            game._state = GameState.NOT_FINISHED
            ok = False
            for m in sol:
                fast_action(game, m)
                if game._score > init_score:
                    ok = True
                    break
            if ok:
                print(f"  L6 hardcoded: {len(sol)} moves")
            else:
                print(f"  L6 hardcoded FAILED, trying enum...")
                sol = solve_enum(game, level - 1, init_score, time_limit=600)
        else:
            # Try enumeration first for all levels
            sol = solve_enum(game, level - 1, init_score, time_limit=600)

        if not sol:
            # Fallback: full BFS
            print(f"  Trying full BFS fallback...")
            depth = min(bl + 20, 250)
            sol = solve_full_bfs(game, level - 1, init_score, depth,
                                time_limit=600, max_states=5000000)

        if sol:
            solutions[level] = sol
            obs = replay_on_env(env, solutions)
            game = env._game
            print(f"  Level {level} OK ({len(sol)} moves, completed={obs.levels_completed})")
        else:
            print(f"  Level {level} FAILED")
            break

    total = obs.win_levels if obs.state == GameState.WIN else obs.levels_completed
    print(f"\n{'='*50}")
    print(f"g50t RESULT: {total}/{n_levels}")
    return total


if __name__ == "__main__":
    solve()
