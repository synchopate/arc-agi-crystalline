#!/usr/bin/env python3
"""ka59 solver — Sokoban-like puzzle with sliding push through walls.

Key mechanics:
  - Actions: 1=up(-3), 2=down(+3), 3=left(-3), 4=right(+3), 6=click(select player)
  - Active player moves by step=3. Blocked by walls+borders. If hits movable -> push.
  - PUSHED pieces slide THROUGH walls, stopped only by border or other blocked movable.
  - Push lasts 5 ticks. If piece is ON a wall after 5 ticks, keeps sliding until off.
  - Win: all goal frames contain matching player box, all cross goals contain matching cross.
"""
import sys
import warnings
import logging
from collections import deque
import numpy as np

sys.path.insert(0, '/home/paolo/arc-agi/solver')
import arc_agi

warnings.filterwarnings('ignore')
logging.disable(logging.WARNING)

STEP = 3


def grid_to_display(game, gx, gy):
    cam = game.camera
    scale = min(64 // cam.width, 64 // cam.height)
    offset_x = (64 - cam.width * scale) // 2
    offset_y = (64 - cam.height * scale) // 2
    return offset_x + (gx - cam.x) * scale, offset_y + (gy - cam.y) * scale


def rects_overlap(x1, y1, w1, h1, x2, y2, w2, h2):
    return not (x1 >= x2 + w2 or x2 >= x1 + w1 or y1 >= y2 + h2 or y2 >= y1 + h1)


def sprite_hits_cells(x, y, w, h, cell_set):
    for dy in range(h):
        for dx in range(w):
            if (x + dx, y + dy) in cell_set:
                return True
    return False


def pixels_collide(x1, y1, pix1, x2, y2, pix2):
    """Pixel-level collision between two sprites.
    pix1, pix2 are sets of (dx, dy) offsets of solid pixels.
    """
    # Convert pix2 to world positions
    for dx2, dy2 in pix2:
        wx, wy = x2 + dx2, y2 + dy2
        rdx, rdy = wx - x1, wy - y1
        if (rdx, rdy) in pix1:
            return True
    return False


def sprite_pixels_hit_cells(x, y, solid_pixels, cell_set):
    """Check if any solid pixel of a sprite hits a cell set."""
    for dx, dy in solid_pixels:
        if (x + dx, y + dy) in cell_set:
            return True
    return False


def build_solid_pixels(sprite):
    """Extract set of (dx, dy) offsets where pixels are solid (>= 0)."""
    pix = set()
    for r in range(sprite.pixels.shape[0]):
        for c in range(sprite.pixels.shape[1]):
            if sprite.pixels[r, c] >= 0:
                pix.add((c, r))
    return frozenset(pix)


def build_grids(game):
    """Build obstacle, border-only, and wall-only grids."""
    level = game.current_level
    borders = level.get_sprites_by_tag('0029ifoxxfvvvs')
    walls = level.get_sprites_by_tag('0015qniapgwsvb')

    obstacle = set()
    border_only = set()
    wall_only = set()

    border = borders[0]
    bp = border.pixels
    for r in range(bp.shape[0]):
        for c in range(bp.shape[1]):
            if bp[r, c] >= 0:
                pos = (border.x + c, border.y + r)
                obstacle.add(pos)
                border_only.add(pos)

    for wall in walls:
        wp = wall.pixels
        for r in range(wp.shape[0]):
            for c in range(wp.shape[1]):
                if wp[r, c] >= 0:
                    pos = (wall.x + c, wall.y + r)
                    obstacle.add(pos)
                    wall_only.add(pos)

    return obstacle, border_only, wall_only


def _try_move_one(pos, sizes, piece_pixsets, piece_idx, dx, dy, border_cells, n, depth=0):
    """Try to move one piece by (dx,dy). Returns updated pos list or None if blocked.

    Uses pixel-level collision for accurate cross-shaped piece handling.
    Matches engine's ifoelczjjh.
    """
    if depth > 10:
        return None
    px, py = pos[piece_idx]
    nx, ny = px + dx, py + dy

    # Check border collision using piece's solid pixels
    if sprite_pixels_hit_cells(nx, ny, piece_pixsets[piece_idx], border_cells):
        return None  # blocked by border

    # Check pixel-level collision with other movable pieces
    for j in range(n):
        if j == piece_idx:
            continue
        jx, jy = pos[j]
        # Quick bbox check first
        pw, ph = sizes[piece_idx]
        jw, jh = sizes[j]
        if not rects_overlap(nx, ny, pw, ph, jx, jy, jw, jh):
            continue
        # Pixel-level check
        if pixels_collide(nx, ny, piece_pixsets[piece_idx], jx, jy, piece_pixsets[j]):
            # Try to push that piece too
            result = _try_move_one(pos, sizes, piece_pixsets, j, dx, dy, border_cells, n, depth + 1)
            if result is None:
                return None  # chain push blocked
            pos = result
            # Re-check pixel collision after push
            if pixels_collide(nx, ny, piece_pixsets[piece_idx],
                              pos[j][0], pos[j][1], piece_pixsets[j]):
                return None  # still blocked

    pos = list(pos)
    pos[piece_idx] = (nx, ny)
    return pos


def slide_piece(positions, sizes, piece_pixsets, piece_idx, dx, dy, border_cells, wall_cells, n, depth=0):
    """Simulate push-slide matching engine tick-by-tick behavior.

    Uses pixel-level collision for accurate cross-shaped piece handling.
    """
    pos = list(positions)

    for tick in range(30):
        # Check stop condition BEFORE moving (engine checks xrxdckwsth >= 5 first)
        if tick >= 5:
            if not sprite_pixels_hit_cells(pos[piece_idx][0], pos[piece_idx][1],
                                           piece_pixsets[piece_idx], wall_cells):
                break

        # Try to move the piece one step (matching ifoelczjjh)
        result = _try_move_one(pos, sizes, piece_pixsets, piece_idx, dx, dy, border_cells, n)
        if result is None:
            break  # blocked by border or immovable piece
        pos = result

    return tuple(pos)


def solve_bfs(game, level_idx, max_iters=5_000_000):
    """BFS solver."""
    level = game.current_level
    players = level.get_sprites_by_tag('0022vrxelxosfy')
    goals = level.get_sprites_by_tag('0010xzmuziohuf')
    crosses = level.get_sprites_by_tag('0001uqqokjrptk')
    cross_goals = level.get_sprites_by_tag('0027jbgxilrocf')
    bombs = level.get_sprites_by_tag('0003umnkyodpjp')

    n_players = len(players)
    n_crosses = len(crosses)
    n_bombs = len(bombs)
    n_mov = n_players + n_crosses + n_bombs
    sizes = ([(p.width, p.height) for p in players]
             + [(c.width, c.height) for c in crosses]
             + [(b.width, b.height) for b in bombs])
    piece_pixsets = ([build_solid_pixels(p) for p in players]
                     + [build_solid_pixels(c) for c in crosses]
                     + [build_solid_pixels(b) for b in bombs])
    init_pos = (tuple((p.x, p.y) for p in players)
                + tuple((c.x, c.y) for c in crosses)
                + tuple((b.x, b.y) for b in bombs))

    active_idx = next(i for i, p in enumerate(players)
                      if p.x == game.prkgpeyexo.x and p.y == game.prkgpeyexo.y)

    goal_targets = [(g.x + 1, g.y + 1, g.width - 2, g.height - 2) for g in goals]
    cross_goal_targets = [(g.x + 1, g.y + 1, g.width - 2, g.height - 2) for g in cross_goals]

    print("  Building grids...")
    obstacle, border_cells, wall_cells = build_grids(game)

    def is_goal(pos):
        for gx, gy, gw, gh in goal_targets:
            if not any(pos[i] == (gx, gy) and sizes[i] == (gw, gh) for i in range(n_players)):
                return False
        for gx, gy, gw, gh in cross_goal_targets:
            if not any(pos[i] == (gx, gy) and sizes[i] == (gw, gh) for i in range(n_players, n_mov)):
                return False
        return True

    def try_move(positions, active, dx, dy):
        ax, ay = positions[active]
        nx, ny = ax + dx, ay + dy
        # Check wall+border collision using pixel-level check
        if sprite_pixels_hit_cells(nx, ny, piece_pixsets[active], obstacle):
            return None
        # Check pixel-level collision with other movable pieces
        collisions = []
        aw, ah = sizes[active]
        for j in range(n_mov):
            if j == active:
                continue
            jx, jy = positions[j]
            jw, jh = sizes[j]
            if rects_overlap(nx, ny, aw, ah, jx, jy, jw, jh):
                if pixels_collide(nx, ny, piece_pixsets[active], jx, jy, piece_pixsets[j]):
                    collisions.append(j)
        if not collisions:
            pos = list(positions)
            pos[active] = (nx, ny)
            return tuple(pos)
        pos = list(positions)
        for pushed in collisions:
            result = slide_piece(tuple(pos), sizes, piece_pixsets, pushed, dx, dy, border_cells, wall_cells, n_mov)
            if result is None:
                return None
            pos = list(result)
        return tuple(pos)

    if is_goal(init_pos):
        return []

    queue = deque([(active_idx, init_pos, [])])
    visited = {(active_idx, init_pos)}
    moves = [(1, 0, -STEP), (2, 0, STEP), (3, -STEP, 0), (4, STEP, 0)]
    step_limit = game.urgssjskot.koyyeuyzyr
    iters = 0

    while queue and iters < max_iters:
        iters += 1
        if iters % 500_000 == 0:
            print(f"    BFS: {iters} iters, {len(visited)} visited")

        active, positions, actions = queue.popleft()
        if len(actions) >= step_limit:
            continue

        for aid, dx, dy in moves:
            result = try_move(positions, active, dx, dy)
            if result is not None and result != positions:
                if is_goal(result):
                    final = actions + [(aid, None)]
                    print(f"  BFS found solution in {len(final)} moves ({iters} iters)")
                    return final
                state = (active, result)
                if state not in visited:
                    visited.add(state)
                    queue.append((active, result, actions + [(aid, None)]))

        if n_players > 1:
            for i in range(n_players):
                if i != active:
                    state = (i, positions)
                    if state not in visited:
                        visited.add(state)
                        px, py = positions[i]
                        pw, ph = sizes[i]
                        queue.append((i, positions, actions + [(6, (px + pw // 2, py + ph // 2))]))

    print(f"  BFS exhausted: {iters} iters, {len(visited)} visited")
    return None


def solve_astar(game, level_idx, max_iters=10_000_000):
    """A* solver with Manhattan distance heuristic for complex multi-player levels."""
    import heapq

    level = game.current_level
    players = level.get_sprites_by_tag('0022vrxelxosfy')
    goals = level.get_sprites_by_tag('0010xzmuziohuf')
    crosses = level.get_sprites_by_tag('0001uqqokjrptk')
    cross_goals = level.get_sprites_by_tag('0027jbgxilrocf')

    n_players = len(players)
    n_crosses = len(crosses)
    bombs = level.get_sprites_by_tag('0003umnkyodpjp')
    n_bombs = len(bombs)
    n_mov = n_players + n_crosses + n_bombs
    sizes = ([(p.width, p.height) for p in players]
             + [(c.width, c.height) for c in crosses]
             + [(b.width, b.height) for b in bombs])
    piece_pixsets = ([build_solid_pixels(p) for p in players]
                     + [build_solid_pixels(c) for c in crosses]
                     + [build_solid_pixels(b) for b in bombs])
    init_pos = (tuple((p.x, p.y) for p in players)
                + tuple((c.x, c.y) for c in crosses)
                + tuple((b.x, b.y) for b in bombs))

    active_idx = next(i for i, p in enumerate(players)
                      if p.x == game.prkgpeyexo.x and p.y == game.prkgpeyexo.y)

    goal_targets = [(g.x + 1, g.y + 1, g.width - 2, g.height - 2) for g in goals]
    cross_goal_targets = [(g.x + 1, g.y + 1, g.width - 2, g.height - 2) for g in cross_goals]

    # Build goal map: size -> target position
    goal_map = {}
    for gx, gy, gw, gh in goal_targets:
        goal_map[(gw, gh)] = (gx, gy)
    cross_goal_map = {}
    for gx, gy, gw, gh in cross_goal_targets:
        cross_goal_map[(gw, gh)] = (gx, gy)

    print("  Building grids...")
    obstacle, border_cells, wall_cells = build_grids(game)

    def heuristic(positions):
        h = 0
        for i in range(n_players):
            sz = sizes[i]
            if sz in goal_map:
                gx, gy = goal_map[sz]
                px, py = positions[i]
                h += (abs(px - gx) + abs(py - gy)) // STEP
        for i in range(n_players, n_mov):
            sz = sizes[i]
            if sz in cross_goal_map:
                gx, gy = cross_goal_map[sz]
                px, py = positions[i]
                h += (abs(px - gx) + abs(py - gy)) // STEP
        return h

    def is_goal(pos):
        for gx, gy, gw, gh in goal_targets:
            if not any(pos[i] == (gx, gy) and sizes[i] == (gw, gh) for i in range(n_players)):
                return False
        for gx, gy, gw, gh in cross_goal_targets:
            if not any(pos[i] == (gx, gy) and sizes[i] == (gw, gh) for i in range(n_players, n_mov)):
                return False
        return True

    def try_move(positions, active, dx, dy):
        ax, ay = positions[active]
        nx, ny = ax + dx, ay + dy
        if sprite_pixels_hit_cells(nx, ny, piece_pixsets[active], obstacle):
            return None
        collisions = []
        aw, ah = sizes[active]
        for j in range(n_mov):
            if j == active:
                continue
            jx, jy = positions[j]
            jw, jh = sizes[j]
            if rects_overlap(nx, ny, aw, ah, jx, jy, jw, jh):
                if pixels_collide(nx, ny, piece_pixsets[active], jx, jy, piece_pixsets[j]):
                    collisions.append(j)
        if not collisions:
            pos = list(positions)
            pos[active] = (nx, ny)
            return tuple(pos)
        pos = list(positions)
        for pushed in collisions:
            result = slide_piece(tuple(pos), sizes, piece_pixsets, pushed, dx, dy, border_cells, wall_cells, n_mov)
            if result is None:
                return None
            pos = list(result)
        return tuple(pos)

    if is_goal(init_pos):
        return []

    step_limit = game.urgssjskot.koyyeuyzyr
    moves_dirs = [(1, 0, -STEP), (2, 0, STEP), (3, -STEP, 0), (4, STEP, 0)]

    counter = 0
    h0 = heuristic(init_pos)
    # (f, g, counter, active, positions)
    heap = [(h0, 0, counter, active_idx, init_pos)]
    best_g = {(active_idx, init_pos): 0}
    parent = {(active_idx, init_pos): None}
    iters = 0

    while heap and iters < max_iters:
        iters += 1
        if iters % 500_000 == 0:
            f, g, _, _, _ = heap[0]
            print(f"    A*: {iters} iters, {len(best_g)} visited, f={f}, g={g}")

        f, g, _, active, positions = heapq.heappop(heap)
        state_key = (active, positions)
        if best_g.get(state_key, 999999) < g:
            continue
        if g >= step_limit:
            continue

        for aid, dx, dy in moves_dirs:
            result = try_move(positions, active, dx, dy)
            if result is not None and result != positions:
                new_g = g + 1
                sk = (active, result)
                if sk not in best_g or best_g[sk] > new_g:
                    best_g[sk] = new_g
                    parent[sk] = (state_key, (aid, None))
                    if is_goal(result):
                        # Reconstruct path
                        path = [(aid, None)]
                        cur = state_key
                        while parent[cur] is not None:
                            prev_state, action = parent[cur]
                            path.append(action)
                            cur = prev_state
                        path.reverse()
                        print(f"  A* found solution in {len(path)} moves ({iters} iters)")
                        return path
                    h = heuristic(result)
                    counter += 1
                    heapq.heappush(heap, (new_g + h, new_g, counter, active, result))

        if n_players > 1:
            for i in range(n_players):
                if i != active:
                    new_g = g + 1
                    sk = (i, positions)
                    if sk not in best_g or best_g[sk] > new_g:
                        best_g[sk] = new_g
                        px, py = positions[i]
                        pw, ph = sizes[i]
                        parent[sk] = (state_key, (6, (px + pw // 2, py + ph // 2)))
                        h = heuristic(positions)
                        counter += 1
                        heapq.heappush(heap, (new_g + h, new_g, counter, i, positions))

    print(f"  A* exhausted: {iters} iters, {len(best_g)} visited")
    return None


def execute_actions(env, game, action_list):
    obs = None
    for action_id, data in action_list:
        if action_id == 6:
            cx, cy = data
            dx, dy = grid_to_display(game, cx, cy)
            obs = env.step(6, data={'x': dx, 'y': dy})
        else:
            obs = env.step(action_id)
        if obs is None or obs.state.name != "NOT_FINISHED":
            return obs
    return obs


# ─── Engine-based BFS for levels with bombs ────────────────────────────────

def solve_engine_bfs(env, game, completed_before, max_depth=50, max_iters=100_000):
    """Engine-based BFS using deepcopy for exact state tracking.

    Used for levels with bombs or other mechanics not modeled in simulation.
    """
    import copy
    import hashlib

    def frame_key(g):
        parts = []
        for s in sorted(g.current_level.get_sprites(), key=lambda s: s.name):
            parts.append(f'{s.name}:{s.x},{s.y}:{hashlib.md5(np.array(s.pixels).tobytes()).hexdigest()[:8]}')
        return tuple(parts)

    queue = deque([(copy.deepcopy(game), [])])
    init_key = frame_key(game)
    visited = {init_key}
    n_players = len(game.current_level.get_sprites_by_tag('0022vrxelxosfy'))
    iters = 0

    while queue and iters < max_iters:
        g, actions = queue.popleft()
        iters += 1
        if iters % 5000 == 0:
            print(f"    eBFS: {iters} iters, {len(visited)} visited, q={len(queue)}, d={len(actions)}")
        if len(actions) >= max_depth:
            continue

        for aid in [1, 2, 3, 4]:
            g2 = copy.deepcopy(g)
            env._game = g2
            try:
                obs = env.step(aid)
            except Exception:
                continue
            if obs.state.name == 'WIN' or obs.levels_completed > completed_before:
                env._game = game
                print(f"  eBFS solved in {len(actions)+1} actions ({iters} iters)")
                return actions + [(aid, None)]
            if obs.state.name == 'GAME_OVER':
                continue
            key = frame_key(g2)
            if key not in visited:
                visited.add(key)
                queue.append((g2, actions + [(aid, None)]))

        if n_players > 1:
            players = g.current_level.get_sprites_by_tag('0022vrxelxosfy')
            for p in players:
                if p.x == g.prkgpeyexo.x and p.y == g.prkgpeyexo.y:
                    continue
                g2 = copy.deepcopy(g)
                px, py = p.x + p.width // 2, p.y + p.height // 2
                dx, dy = grid_to_display(g2, px, py)
                env._game = g2
                try:
                    obs = env.step(6, data={'x': dx, 'y': dy})
                except Exception:
                    continue
                if obs.state.name == 'GAME_OVER':
                    continue
                key = frame_key(g2)
                if key not in visited:
                    visited.add(key)
                    queue.append((g2, actions + [(6, (px, py))]))

    env._game = game
    print(f"  eBFS exhausted: {iters} iters, {len(visited)} visited")
    return None


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('ka59')
    obs = env.reset()
    game = env._game

    print(f"ka59: {obs.win_levels} levels")
    total_levels = obs.win_levels
    levels_solved = 0

    for level_idx in range(total_levels):
        if obs.state.name != "NOT_FINISHED":
            break

        print(f"\n--- Level {level_idx + 1} ---")
        level = game.current_level
        players = level.get_sprites_by_tag('0022vrxelxosfy')
        goals = level.get_sprites_by_tag('0010xzmuziohuf')
        crosses = level.get_sprites_by_tag('0001uqqokjrptk')
        cross_goals = level.get_sprites_by_tag('0027jbgxilrocf')
        bombs = level.get_sprites_by_tag('0003umnkyodpjp')

        print(f"  Players({len(players)}): {[(p.x,p.y,p.width,p.height) for p in players]}")
        print(f"  Goals({len(goals)}): targets={[(g.x+1,g.y+1,g.width-2,g.height-2) for g in goals]}")
        if crosses:
            print(f"  Crosses({len(crosses)}): {[(c.x,c.y,c.width,c.height) for c in crosses]}")
        if cross_goals:
            print(f"  CrossGoals: targets={[(c.x+1,c.y+1,c.width-2,c.height-2) for c in cross_goals]}")
        if bombs:
            print(f"  Bombs({len(bombs)}): {[(b.x,b.y,b.width,b.height,b.rotation) for b in bombs]}")
        print(f"  Steps: {game.urgssjskot.koyyeuyzyr}")

        # Choose solver strategy based on level complexity
        result = None
        completed_before = obs.levels_completed if obs else 0

        if bombs:
            # Bomb levels: try A* first (fast), then engine BFS if needed
            print("  Trying A* (ignoring bomb mechanics)...")
            import copy
            game_backup = copy.deepcopy(game)
            result = solve_astar(game, level_idx, max_iters=5_000_000)
            if result is not None:
                obs_test = execute_actions(env, game, result)
                if obs_test and (obs_test.state.name == "WIN" or obs_test.levels_completed > completed_before):
                    obs = obs_test
                    levels_solved = obs.levels_completed if obs.state.name != "WIN" else total_levels
                    print(f"  Level {level_idx + 1} solved with A*! ({len(result)} actions, completed={levels_solved})")
                    continue
                else:
                    # A* solution didn't work, restore game state
                    print("  A* execution failed, restoring and trying engine BFS...")
                    game = game_backup
                    env._game = game
                    result = None
            if result is None:
                print("  Using engine-based BFS (bomb level)...")
                result = solve_engine_bfs(env, game, completed_before,
                                          max_depth=50, max_iters=200_000)
        elif len(players) > 2:
            # Many players -> use A* with Manhattan heuristic
            result = solve_astar(game, level_idx)
        else:
            # Simple levels -> use BFS
            result = solve_bfs(game, level_idx)

        if result is not None:
            obs = execute_actions(env, game, result)
            if obs and obs.state.name == "WIN":
                levels_solved = total_levels
                print(f"  WIN!")
                break
            elif obs and obs.levels_completed > level_idx:
                levels_solved = obs.levels_completed
                print(f"  Level {level_idx + 1} solved! ({len(result)} actions, completed={levels_solved})")
            else:
                print(f"  Execution FAILED (state={obs.state.name if obs else 'None'})")
                if obs: levels_solved = obs.levels_completed
                break
        else:
            print(f"  FAILED - no solution found")
            break

    print(f"\n{'='*60}")
    print(f"GAME_ID: ka59")
    print(f"LEVELS_SOLVED: {levels_solved}")
    print(f"TOTAL_LEVELS: {total_levels}")
    print(f"MECHANICS: Sokoban-variant with sliding push. Player boxes moved by step=3. "
          f"Pushed pieces slide THROUGH walls for 5 ticks (more if on wall). "
          f"Click to switch active player. Win = nest all player boxes in goal frames "
          f"and crosses in cross goal frames. Bombs explode pushing nearby pieces.")
    print(f"KEY_LESSONS: Pushed pieces pass through walls (only stopped by borders). "
          f"Push distance = 5*step=15 unless blocked. Border sprite has pixel-level "
          f"collision including internal walls with doorways. Engine handles push "
          f"animation automatically within single env.step() call.")

    return levels_solved


if __name__ == "__main__":
    solve()
