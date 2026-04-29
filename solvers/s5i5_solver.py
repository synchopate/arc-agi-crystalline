#!/usr/bin/env python3
"""Solver for ARC-AGI-3 game s5i5 — pipe extension/rotation puzzle.

Uses BFS for simple levels, BFS-compact for complex levels.
"""

import arc_agi
import numpy as np
from collections import deque
from universal_harness import grid_to_display, replay_solution
import time
import gc

TAG_BAR = "0001qwdmnlybkb"
TAG_GOAL = "0064ocqkuqacti"
TAG_TARGET = "0087vvmblxkzdi"
TAG_SLIDER = "0066ghlkyvdbgg"
TAG_BUTTON = "0089rvqdprjwpz"

VJQ = 3
FBN = 3


def get_rotation(bar):
    if bar.pixels[-1, 1] == FBN: return 0
    elif bar.pixels[1, 0] == FBN: return 90
    elif bar.pixels[0, 1] == FBN: return 180
    else: return 270


def save_sprites(game):
    state = {}
    for s in game.current_level.get_sprites():
        state[id(s)] = (s.x, s.y, s.pixels.copy())
    return state


def save_sprites_compact(game):
    state = {}
    for tag in [TAG_BAR, TAG_TARGET, TAG_GOAL]:
        for s in game.current_level.get_sprites_by_tag(tag):
            state[id(s)] = (s.x, s.y, s.pixels.copy())
    return state


def restore_sprites(game, state):
    for s in game.current_level.get_sprites():
        sid = id(s)
        if sid in state:
            x, y, px = state[sid]
            s.set_position(x, y)
            s.pixels = px.copy()


def restore_sprites_compact(game, state):
    for tag in [TAG_BAR, TAG_TARGET, TAG_GOAL]:
        for s in game.current_level.get_sprites_by_tag(tag):
            sid = id(s)
            if sid in state:
                x, y, px = state[sid]
                s.set_position(x, y)
                s.pixels = px.copy()


def check_win(game):
    targets = game.current_level.get_sprites_by_tag(TAG_TARGET)
    goals = game.current_level.get_sprites_by_tag(TAG_GOAL)
    goal_pos = {(g.x, g.y) for g in goals}
    for t in targets:
        if (t.x, t.y) not in goal_pos:
            return False
    return len(targets) > 0


def target_goal_dist(game):
    targets = game.current_level.get_sprites_by_tag(TAG_TARGET)
    goals = game.current_level.get_sprites_by_tag(TAG_GOAL)
    if not targets or not goals:
        return 0
    gpos = [(g.x, g.y) for g in goals]
    total = 0
    for t in targets:
        total += min(abs(t.x - gx) + abs(t.y - gy) for gx, gy in gpos)
    return total


def apply_slider(game, slider, grow):
    if slider not in game.pigtralzpb:
        return False
    controlled = game.pigtralzpb[slider]
    if not controlled:
        return False
    game.whoonmfbnp = dict()
    for bar in controlled:
        _save_tree(game, bar)
    for bar in controlled:
        idx = bar.height // VJQ if bar.height > bar.width else bar.width // VJQ
        new_idx = idx + 1 if grow else idx - 1
        if new_idx < 1:
            game.whoonmfbnp = dict()
            return False
        _resize_bar(game, bar, new_idx)
    if _check_collision(game):
        for sprite in game.whoonmfbnp:
            saved = game.whoonmfbnp[sprite]
            sprite.set_position(saved.x, saved.y)
            sprite.pixels = saved.pixels
        game.whoonmfbnp = dict()
        return False
    game.whoonmfbnp = dict()
    return True


def apply_button(game, button):
    color = int(button.pixels[button.height // 2, button.height // 2])
    bars = game.current_level.get_sprites_by_tag(TAG_BAR)
    game.whoonmfbnp = dict()
    for bar in bars:
        if int(bar.pixels[1, 1]) == color:
            _save_tree(game, bar)
            parents = [k for k in game.uricqfoplr if bar in game.uricqfoplr[k]]
            if parents:
                pr = get_rotation(parents[0])
                br = get_rotation(bar)
                if abs(br - 90 - pr) == 180:
                    _rotate_bar(game, bar)
                _rotate_bar(game, bar)
            else:
                _rotate_bar(game, bar)
    if _check_collision(game):
        for sprite in game.whoonmfbnp:
            saved = game.whoonmfbnp[sprite]
            sprite.set_position(saved.x, saved.y)
            sprite.pixels = saved.pixels
        game.whoonmfbnp = dict()
        return False
    game.whoonmfbnp = dict()
    return True


def _save_tree(game, sprite):
    game.whoonmfbnp[sprite] = sprite.clone()
    if sprite in game.uricqfoplr:
        for child in game.uricqfoplr[sprite]:
            _save_tree(game, child)


def _resize_bar(game, bar, new_idx):
    color = int(bar.pixels[1, 1])
    old_h, old_w = bar.pixels.shape
    ns = new_idx * VJQ
    rot = get_rotation(bar)
    dx, dy = 0, 0
    if rot == 0:
        bar.pixels = np.full((ns, VJQ), color, dtype=np.int8)
        bar.pixels[-1, :] = FBN
        dy = -(ns - old_h); bar.move(0, dy)
    elif rot == 90:
        bar.pixels = np.full((VJQ, ns), color, dtype=np.int8)
        bar.pixels[:, 0] = FBN
        dx = ns - old_w
    elif rot == 180:
        bar.pixels = np.full((ns, VJQ), color, dtype=np.int8)
        bar.pixels[0, :] = FBN
        dy = ns - old_h
    else:
        bar.pixels = np.full((VJQ, ns), color, dtype=np.int8)
        bar.pixels[:, -1] = FBN
        dx = -(ns - old_w); bar.move(dx, 0)
    if bar in game.uricqfoplr:
        for child in game.uricqfoplr[bar]:
            _move_tree(game, child, dx, dy)


def _move_tree(game, sprite, dx, dy):
    sprite.move(dx, dy)
    if sprite in game.uricqfoplr:
        for child in game.uricqfoplr[sprite]:
            _move_tree(game, child, dx, dy)


def _rotate_bar(game, bar):
    rot = get_rotation(bar)
    if rot == 0:
        ax, ay = bar.x, bar.y + bar.height - VJQ
        for c in game.uricqfoplr.get(bar, []): _rotate_child(game, c, ax, ay)
        bar.move(-bar.height + VJQ, bar.height - VJQ)
    elif rot == 90:
        ax, ay = bar.x, bar.y
        for c in game.uricqfoplr.get(bar, []): _rotate_child(game, c, ax, ay)
        bar.move(0, -bar.width + VJQ)
    elif rot == 180:
        ax, ay = bar.x, bar.y
        for c in game.uricqfoplr.get(bar, []): _rotate_child(game, c, ax, ay)
    elif rot == 270:
        ax, ay = bar.x + bar.width - VJQ, bar.y
        for c in game.uricqfoplr.get(bar, []): _rotate_child(game, c, ax, ay)
        bar.move(bar.width - VJQ, 0)
    bar.pixels = np.rot90(bar.pixels)


def _rotate_child(game, sprite, ax, ay):
    dx, dy = ax - sprite.x, ay - sprite.y
    sprite.set_position(ax - dy, ay + dx - (sprite.width - VJQ))
    sprite.pixels = np.rot90(sprite.pixels)
    if sprite in game.uricqfoplr:
        for child in game.uricqfoplr[sprite]:
            _rotate_child(game, child, ax, ay)


def _check_collision(game):
    bars = game.current_level.get_sprites_by_tag(TAG_BAR)
    for i, b1 in enumerate(bars):
        for b2 in bars[i+1:]:
            if b1.collides_with(b2):
                return True
    return False


def state_key(game):
    bars = game.current_level.get_sprites_by_tag(TAG_BAR)
    parts = []
    for b in sorted(bars, key=lambda s: s.name):
        c = int(b.pixels[1, 1])
        if c == 15 or c == -1: continue
        parts.append((b.x, b.y, b.width, b.height))
    return tuple(parts)


def build_actions(game):
    cam = game.camera
    sliders = game.current_level.get_sprites_by_tag(TAG_SLIDER)
    buttons = game.current_level.get_sprites_by_tag(TAG_BUTTON)

    actions = []
    inverse_map = {}

    for si, sl in enumerate(sliders):
        is_h = sl.width > sl.height
        if is_h:
            gx, gy = sl.x + sl.width - 2, sl.y + sl.height // 2
            sx, sy = sl.x + 2, sl.y + sl.height // 2
        else:
            gx, gy = sl.x + sl.width // 2, sl.y + sl.height - 2
            sx, sy = sl.x + sl.width // 2, sl.y + 2
        gdx, gdy = grid_to_display(gx, gy, cam)
        sdx, sdy = grid_to_display(sx, sy, cam)
        grow_idx = len(actions)
        actions.append({"disp": (gdx, gdy), "fn": lambda g=game, s=sl: apply_slider(g, s, True), "name": "G%d" % si, "type": "grow", "slider": si})
        shrink_idx = len(actions)
        actions.append({"disp": (sdx, sdy), "fn": lambda g=game, s=sl: apply_slider(g, s, False), "name": "S%d" % si, "type": "shrink", "slider": si})
        inverse_map[grow_idx] = shrink_idx
        inverse_map[shrink_idx] = grow_idx

    for bi, btn in enumerate(buttons):
        bx = btn.x + btn.width // 2
        by = btn.y + btn.height // 2
        dx, dy = grid_to_display(bx, by, cam)
        actions.append({"disp": (dx, dy), "fn": lambda g=game, b=btn: apply_button(g, b), "name": "R%d" % bi, "type": "button", "button": bi})

    return actions, inverse_map


def is_prunable(actions, last_action, ci, inverse_map):
    """Check if action ci should be pruned given last_action."""
    if last_action < 0:
        return False
    # Don't undo slider grow/shrink
    if ci in inverse_map and inverse_map[ci] == last_action:
        return True
    # Button presses are rotations — consecutive presses are valid (90°, 180°, 270°)
    # Only prune the 4th consecutive press (360° = identity) — handled by visited set
    return False


def solve_level_bfs(env, game, level, level_solutions, time_limit=120, max_states=500000, use_compact=False):
    """BFS with full or compact sprite state copies."""
    actions, inverse_map = build_actions(game)
    n = len(actions)
    if n == 0:
        return None

    init_saved = save_sprites(game)

    _save = save_sprites_compact if use_compact else save_sprites
    _restore = restore_sprites_compact if use_compact else restore_sprites

    visited = {state_key(game)}
    queue = deque([([], _save(game), -1)])
    explored = 0
    t0 = time.time()

    while queue:
        moves, parent_saved, last_action = queue.popleft()
        depth = len(moves)
        if depth >= 80:
            continue

        elapsed = time.time() - t0
        if elapsed > time_limit:
            break

        for ci in range(n):
            if is_prunable(actions, last_action, ci, inverse_map):
                continue

            _restore(game, parent_saved)
            ok = actions[ci]["fn"]()
            if not ok:
                continue

            if check_win(game):
                result = moves + [ci]
                restore_sprites(game, init_saved)
                return [actions[i]["disp"] for i in result]

            sk = state_key(game)
            if sk not in visited:
                visited.add(sk)
                queue.append((moves + [ci], _save(game), ci))
                explored += 1

                if explored % 50000 == 0:
                    h = target_goal_dist(game)
                    elapsed2 = time.time() - t0
                    print("  BFS %dk d=%d q=%d h=%d %.0fs" % (explored//1000, depth+1, len(queue), h, elapsed2))

        if explored >= max_states:
            break

    elapsed = time.time() - t0
    print("  BFS done: %d states %.0fs" % (explored, elapsed))
    restore_sprites(game, init_saved)
    return None


def solve_level_progressive_bfs(env, game, level, level_solutions, time_limit=420):
    """Progressive BFS: collect best frontier states, restart BFS from them.

    Phase 1: BFS to find states with best heuristic
    Phase 2: BFS from those states with fresh visited set
    Repeat until solved or time runs out.
    """
    actions, inverse_map = build_actions(game)
    n = len(actions)
    if n == 0:
        return None

    init_saved = save_sprites(game)
    _save = save_sprites_compact
    _restore = restore_sprites_compact

    t0_total = time.time()
    global_visited = {state_key(game)}
    best_h_ever = target_goal_dist(game)

    # Phase 1: initial BFS to map the space
    # Collect frontier states sorted by heuristic
    frontier = []  # (h, moves, saved_state, last_action)
    frontier.append((best_h_ever, [], _save(game), -1))

    phase = 0
    while time.time() - t0_total < time_limit:
        phase += 1
        t0 = time.time()

        # Process frontier: BFS from each frontier state
        new_frontier = []
        states_this_phase = 0
        max_states_phase = 500000 if phase == 1 else 300000

        queue = deque(frontier)
        frontier = []

        while queue:
            h_parent, moves, parent_saved, last_action = queue.popleft()
            depth = len(moves)
            if depth >= 80:
                continue

            elapsed = time.time() - t0
            if elapsed > time_limit / 3:
                break

            for ci in range(n):
                if is_prunable(actions, last_action, ci, inverse_map):
                    continue

                _restore(game, parent_saved)
                ok = actions[ci]["fn"]()
                if not ok:
                    continue

                if check_win(game):
                    result = moves + [ci]
                    restore_sprites(game, init_saved)
                    return [actions[i]["disp"] for i in result]

                sk = state_key(game)
                if sk not in global_visited:
                    global_visited.add(sk)
                    h = target_goal_dist(game)
                    new_moves = moves + [ci]
                    saved = _save(game)

                    if h < best_h_ever:
                        best_h_ever = h
                        goals = game.current_level.get_sprites_by_tag(TAG_GOAL)
                        gpos = [(g.x, g.y) for g in goals]
                        elapsed_total = time.time() - t0_total
                        print("  P%d: new best h=%d at d=%d goals=%s %.0fs" % (
                            phase, h, len(new_moves), gpos, elapsed_total))

                    # Add to BFS queue
                    queue.append((h, new_moves, saved, ci))
                    # Also collect as potential frontier for next phase
                    new_frontier.append((h, new_moves, saved, ci))
                    states_this_phase += 1

                    if states_this_phase % 50000 == 0:
                        elapsed_total = time.time() - t0_total
                        print("  P%d: %dk states d=%d best_h=%d %.0fs visited=%dk" % (
                            phase, states_this_phase//1000, depth+1, best_h_ever,
                            elapsed_total, len(global_visited)//1000))

            if states_this_phase >= max_states_phase:
                break

        elapsed_total = time.time() - t0_total
        print("  P%d done: %dk states, best_h=%d, visited=%dk %.0fs" % (
            phase, states_this_phase//1000, best_h_ever, len(global_visited)//1000, elapsed_total))

        if not new_frontier:
            break

        # Select best frontier states for next phase
        new_frontier.sort(key=lambda x: x[0])
        frontier = new_frontier[:20000]  # Keep top 20K by heuristic
        new_frontier = None
        gc.collect()

    restore_sprites(game, init_saved)
    return None


def solve_level_astar(env, game, level, level_solutions, time_limit=600, max_states=5000000):
    """A* search using target-goal distance as heuristic."""
    import heapq

    actions, inverse_map = build_actions(game)
    n = len(actions)
    if n == 0:
        return None

    init_saved = save_sprites(game)
    _save = save_sprites_compact
    _restore = restore_sprites_compact

    init_h = target_goal_dist(game)
    init_sk = state_key(game)
    visited = {init_sk}
    counter = [0]
    # (f, counter, moves, saved_state, last_action)
    heap = [(init_h, 0, [], _save(game), -1)]
    explored = 0
    best_h = init_h
    t0 = time.time()

    while heap:
        f, _, moves, parent_saved, last_action = heapq.heappop(heap)
        depth = len(moves)
        if depth >= 80:
            continue

        elapsed = time.time() - t0
        if elapsed > time_limit:
            break

        for ci in range(n):
            if is_prunable(actions, last_action, ci, inverse_map):
                continue

            _restore(game, parent_saved)
            ok = actions[ci]["fn"]()
            if not ok:
                continue

            if check_win(game):
                result = moves + [ci]
                restore_sprites(game, init_saved)
                return [actions[i]["disp"] for i in result]

            sk = state_key(game)
            if sk not in visited:
                visited.add(sk)
                h = target_goal_dist(game)
                if h < best_h:
                    best_h = h
                    elapsed2 = time.time() - t0
                    print("  A* new best h=%d d=%d %.0fs" % (h, depth+1, elapsed2))
                counter[0] += 1
                heapq.heappush(heap, (depth + 1 + h, counter[0], moves + [ci], _save(game), ci))
                explored += 1

                if explored % 50000 == 0:
                    elapsed2 = time.time() - t0
                    print("  A* %dk d=%d heap=%d best_h=%d %.0fs" % (
                        explored//1000, depth+1, len(heap), best_h, elapsed2))

        if explored >= max_states:
            break

    elapsed = time.time() - t0
    print("  A* done: %d states %.0fs best_h=%d" % (explored, elapsed, best_h))
    restore_sprites(game, init_saved)
    return None


def solve_level(env, game, level, level_solutions, time_limit=120):
    sliders = game.current_level.get_sprites_by_tag(TAG_SLIDER)
    buttons = game.current_level.get_sprites_by_tag(TAG_BUTTON)
    n_actions = len(sliders) * 2 + len(buttons)

    print("  Strategy: %d actions (%d sl + %d btn)" % (n_actions, len(sliders), len(buttons)))

    if n_actions <= 8:
        return solve_level_bfs(env, game, level, level_solutions, time_limit=time_limit)
    elif n_actions <= 12:
        return solve_level_bfs(env, game, level, level_solutions,
                                time_limit=time_limit,
                                max_states=500000)
    else:
        # Try A* first (heuristic-guided), fall back to progressive BFS
        result = solve_level_astar(env, game, level, level_solutions,
                                   time_limit=time_limit * 2 // 3,
                                   max_states=3000000)
        if result:
            return result
        print("  A* failed, trying progressive BFS...")
        return solve_level_progressive_bfs(env, game, level, level_solutions,
                                           time_limit=time_limit // 3)


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make("s5i5")
    obs = env.reset()
    obs = env.step(6)
    game = env._game

    print("s5i5: %d levels" % obs.win_levels)
    level_solutions = {}

    for level in range(1, obs.win_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        cam = game.camera
        goals = game.current_level.get_sprites_by_tag(TAG_GOAL)
        targets = game.current_level.get_sprites_by_tag(TAG_TARGET)
        sliders = game.current_level.get_sprites_by_tag(TAG_SLIDER)
        buttons = game.current_level.get_sprites_by_tag(TAG_BUTTON)

        print("\nL%d: %d sl %d btn G:%s T:%s" % (
            level, len(sliders), len(buttons),
            [(g.x, g.y) for g in goals], [(t.x, t.y) for t in targets]))

        t0 = time.time()
        n_actions = len(sliders) * 2 + len(buttons)
        if n_actions <= 4: tlim = 30
        elif n_actions <= 8: tlim = 60
        elif n_actions <= 12: tlim = 180
        else: tlim = 900

        solution = solve_level(env, game, level, level_solutions, time_limit=tlim)
        elapsed = time.time() - t0

        if solution:
            print("  SOLVED L%d: %d clicks %.1fs" % (level, len(solution), elapsed))
            level_solutions[level] = solution
            obs = replay_solution(env, level_solutions)
            game = env._game
            print("  Replay: completed=%d" % obs.levels_completed)
        else:
            print("  L%d FAILED %.1fs" % (level, elapsed))
            break

    total = obs.levels_completed
    if obs.state.name == "WIN":
        total = obs.win_levels
    print("\n" + "=" * 40)
    print("s5i5 RESULT: %d/%d" % (total, obs.win_levels))
    print("=" * 40)
    return total


if __name__ == "__main__":
    solve()
