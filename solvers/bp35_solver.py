#!/usr/bin/env python3
"""bp35 solver — Gravity platformer puzzle."""

import sys
import os
import time
import re
from collections import deque

sys.path.insert(0, '/home/paolo/arc-agi/solver')

# =============================================================================
# Grid extraction from source
# =============================================================================

def load_grids():
    """Load grids from actual game source file."""
    src_path = '/home/paolo/arc-agi/solver/environment_files/bp35/0a0ad940/bp35.py'
    with open(src_path) as f:
        src = f.read()

    grids = {}
    for grid_num in range(1, 10):
        pattern = f'"grid{grid_num}": qipeamczaw' + r'\(\n\s+\[(.*?)\]\[::-1\]'
        m = re.search(pattern, src, re.DOTALL)
        if m:
            lines_text = m.group(1)
            strings = re.findall(r'"([^"]+)"', lines_text)
            strings = strings[::-1]
            grids[grid_num] = strings
    return grids

GRIDS_RAW = load_grids()


def extract_grid(level_num):
    """Extract grid dict and player position."""
    if level_num not in GRIDS_RAW:
        return None
    rows = GRIDS_RAW[level_num]
    grid = {}
    player_pos = None
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == 'n':
                player_pos = (x, y)
            elif ch != ' ':
                grid[(x, y)] = ch
    return grid, player_pos


# =============================================================================
# Game simulation
# =============================================================================

PASSABLE_TILES = frozenset((' ', '2', 'm', 'w'))
_MUTABLE = frozenset(('x', '1', '2', 'y', 'g'))
CLICKABLE = frozenset(('x', '1', '2', 'g', 'y'))

def get_tile(grid, x, y):
    return grid.get((x, y), ' ')


def is_passable(t):
    return t in PASSABLE_TILES


def simulate_fall(grid, x, y, grav_up):
    """Simulate gravity fall. Returns (fx, fy, result)."""
    dy = -1 if grav_up else 1
    prev = (x, y)
    ny = y + dy
    for _ in range(200):
        t = get_tile(grid, x, ny)
        if t == '+': return (x, ny, 'gem')
        if t in ('v', 'u'): return (prev[0], prev[1], 'die')
        if is_passable(t):
            prev = (x, ny)
            ny += dy
        else:
            return (prev[0], prev[1], 'land')
    return (prev[0], prev[1], 'land')


def try_move(grid, px, py, dx, grav_up):
    """Move player horizontally by dx. Returns (nx, ny, result)."""
    nx = px + dx
    t = get_tile(grid, nx, py)
    if t == '+': return (nx, py, 'gem')
    if not is_passable(t): return (px, py, 'blocked')
    dy = -1 if grav_up else 1
    ft = get_tile(grid, nx, py + dy)
    if ft == '+': return (nx, py + dy, 'gem')
    if ft in ('v', 'u'): return (nx, py, 'die')
    if is_passable(ft):
        return simulate_fall(grid, nx, py + dy, grav_up)
    return (nx, py, 'land')


def try_click(grid, px, py, cx, cy, grav_up):
    """Click tile at (cx,cy).
    Returns (new_grid, npx, npy, new_grav, result, changed_positions) or None.
    changed_positions is a set of positions that changed in the grid."""
    t = get_tile(grid, cx, cy)
    if t not in CLICKABLE:
        return None

    new_grid = dict(grid)
    changed = {(cx, cy)}

    if t == 'x':
        del new_grid[(cx, cy)]
        ng = grav_up
    elif t == '1':
        new_grid[(cx, cy)] = '2'
        ng = grav_up
    elif t == '2':
        new_grid[(cx, cy)] = '1'
        ng = grav_up
    elif t == 'g':
        del new_grid[(cx, cy)]
        ng = not grav_up
    elif t == 'y':
        del new_grid[(cx, cy)]
        for ddx, ddy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ax, ay = cx + ddx, cy + ddy
            if get_tile(new_grid, ax, ay) == ' ' and (ax, ay) != (px, py):
                new_grid[(ax, ay)] = 'y'
                changed.add((ax, ay))
        ng = grav_up
    else:
        return None

    dy = -1 if ng else 1
    if t == 'g':
        # Gravity flip: always check fall
        # Blocking: o, g, 1, x, y
        ft = get_tile(new_grid, px, py + dy)
        if ft in ('o', 'g', '1', 'x', 'y'):
            return (new_grid, px, py, ng, 'ok', changed)
        if ft == '+': return (new_grid, px, py + dy, ng, 'gem', changed)
        if ft in ('v', 'u'): return (new_grid, px, py, ng, 'die', changed)
        fx, fy, r = simulate_fall(new_grid, px, py + dy, ng)
        return (new_grid, fx, fy, ng, r, changed)
    else:
        old_dy = -1 if grav_up else 1
        if (cx, cy) != (px, py + old_dy):
            return (new_grid, px, py, ng, 'ok', changed)
        # Clicked tile was directly below player
        ft = get_tile(new_grid, px, py + old_dy)
        if is_passable(ft):
            fx, fy, r = simulate_fall(new_grid, px, py + old_dy, ng)
            return (new_grid, fx, fy, ng, r, changed)
        elif ft == '+':
            return (new_grid, px, py + old_dy, ng, 'gem', changed)
        elif ft in ('v', 'u'):
            return (new_grid, px, py, ng, 'die', changed)
        else:
            return (new_grid, px, py, ng, 'ok', changed)


def make_mkey(grid):
    """Create mutable tiles key from grid."""
    return frozenset((pos, t) for pos, t in grid.items() if t in _MUTABLE)

def update_mkey(old_mkey, old_grid, new_grid, changed):
    """Incrementally update mutable key after changes."""
    additions = set()
    removals = set()
    for pos in changed:
        old_t = old_grid.get(pos)
        new_t = new_grid.get(pos)
        if old_t in _MUTABLE:
            removals.add((pos, old_t))
        if new_t is not None and new_t in _MUTABLE:
            additions.add((pos, new_t))
    if not removals and not additions:
        return old_mkey
    return (old_mkey - removals) | additions


# =============================================================================
# Moving platform simulation for levels 1-3
# =============================================================================

def get_initial_platform_y(level_num):
    if level_num > 3:
        return None
    result = extract_grid(level_num)
    if result is None:
        return None
    grid, _ = result
    for (x, y), t in grid.items():
        if t == 'm':
            return y
    return None

PLATFORM_Y = {lv: get_initial_platform_y(lv) for lv in range(1, 4)}


# =============================================================================
# BFS solver
# =============================================================================

def solve_level_bfs(level_num, max_steps=None, max_states=2000000, verbose=True,
                    click_range=3, try_all_clicks=False):
    """Solve level using BFS with pruned click actions."""
    result = extract_grid(level_num)
    if result is None:
        return None
    grid, player_pos = result
    if player_pos is None:
        return None
    if max_steps is None:
        max_steps = 63 if level_num <= 6 else 127

    px, py = player_pos
    grav = True

    gem_pos = None
    for (x, y), t in grid.items():
        if t == '+':
            gem_pos = (x, y)
            break

    has_platform = level_num <= 3
    platform_y0 = PLATFORM_Y.get(level_num)

    if verbose:
        clicks = sum(1 for t in grid.values() if t in CLICKABLE)
        print(f"  Player: ({px},{py}), Gem: {gem_pos}, Clickables: {clicks}, Platform: {platform_y0}")

    init_mkey = make_mkey(grid)
    init_key = (px, py, grav, init_mkey)

    # Queue: (px, py, grav, grid, mkey, moves, depth, mcount)
    queue = deque()
    queue.append((px, py, grav, grid, init_mkey, [], 0, 0))
    visited = {init_key}
    explored = 0

    while queue:
        cpx, cpy, cg, cgrid, cmkey, moves, depth, mcount = queue.popleft()
        if depth >= max_steps:
            continue

        successors = []

        # Move left/right
        for dx, name in [(-1, 'left'), (1, 'right')]:
            nx, ny, r = try_move(cgrid, cpx, cpy, dx, cg)
            if r == 'gem':
                m = moves + [name]
                if verbose: print(f"  L{level_num}: SOLVED in {len(m)} moves ({explored} explored)")
                return m
            if r == 'die':
                continue
            new_mc = mcount + 1
            if has_platform and new_mc % 2 == 0:
                platform_y = platform_y0 - (new_mc // 2)
                if ny == platform_y:
                    continue
            if r in ('land', 'blocked'):
                successors.append((name, nx, ny, cg, cgrid, cmkey, new_mc))

        # Click at tile directly in gravity direction
        dy = -1 if cg else 1
        below_pos = (cpx, cpy + dy)
        t_below = get_tile(cgrid, below_pos[0], below_pos[1])
        if t_below in CLICKABLE:
            cr = try_click(cgrid, cpx, cpy, below_pos[0], below_pos[1], cg)
            if cr:
                ng, npx, npy, ngrav, result, changed = cr
                if result == 'gem':
                    m = moves + [f'click({below_pos[0]},{below_pos[1]},{t_below})']
                    if verbose: print(f"  L{level_num}: SOLVED in {len(m)} moves ({explored} explored)")
                    return m
                if result != 'die':
                    nmkey = update_mkey(cmkey, cgrid, ng, changed)
                    new_mc = mcount + 1
                    successors.append((f'click({below_pos[0]},{below_pos[1]},{t_below})', npx, npy, ngrav, ng, nmkey, new_mc))

        # Click gravity flips - only try ONE per state (all produce same position)
        gflips = [(cx, cy) for (cx, cy), ct in cgrid.items() if ct == 'g' and (cx, cy) != below_pos]
        if gflips:
            # Sort by distance, try closest
            gflips.sort(key=lambda p: abs(p[0] - cpx) + abs(p[1] - cpy))
            cx, cy = gflips[0]
            cr = try_click(cgrid, cpx, cpy, cx, cy, cg)
            if cr:
                ng, npx, npy, ngrav, result, changed = cr
                if result == 'gem':
                    m = moves + [f'click({cx},{cy},g)']
                    if verbose: print(f"  L{level_num}: SOLVED in {len(m)} moves ({explored} explored)")
                    return m
                if result != 'die':
                    nmkey = update_mkey(cmkey, cgrid, ng, changed)
                    new_mc = mcount + 1
                    successors.append((f'click({cx},{cy},g)', npx, npy, ngrav, ng, nmkey, new_mc))

        # Click non-gravity, non-below tiles
        for (cx, cy), ct in cgrid.items():
            if ct not in ('x', '1', '2', 'y'):
                continue
            if (cx, cy) == below_pos:
                continue

            should_try = False
            if try_all_clicks:
                should_try = True
            else:
                if cx == cpx and ((cg and cy < cpy) or (not cg and cy > cpy)):
                    should_try = True
                elif abs(cy - cpy) <= click_range and abs(cx - cpx) <= click_range:
                    should_try = True

            if should_try:
                cr = try_click(cgrid, cpx, cpy, cx, cy, cg)
                if cr:
                    ng, npx, npy, ngrav, result, changed = cr
                    if result == 'gem':
                        m = moves + [f'click({cx},{cy},{ct})']
                        if verbose: print(f"  L{level_num}: SOLVED in {len(m)} moves ({explored} explored)")
                        return m
                    if result != 'die':
                        nmkey = update_mkey(cmkey, cgrid, ng, changed)
                        new_mc = mcount + 1
                        successors.append((f'click({cx},{cy},{ct})', npx, npy, ngrav, ng, nmkey, new_mc))

        for aname, npx, npy, ngrav, ngrid, nmkey, nmc in successors:
            key = (npx, npy, ngrav, nmkey)
            if key not in visited:
                visited.add(key)
                queue.append((npx, npy, ngrav, ngrid, nmkey, moves + [aname], depth + 1, nmc))
                explored += 1
                if verbose and explored % 100000 == 0:
                    print(f"  L{level_num}: {explored} states, depth={depth+1}, q={len(queue)}")
                if explored >= max_states:
                    if verbose: print(f"  L{level_num}: Giving up at {explored} states")
                    return None

    if verbose: print(f"  L{level_num}: FAILED ({explored} states)")
    return None


# =============================================================================
# Verification
# =============================================================================

def verify_solution(level_num, moves):
    """Verify a solution in simulation. Returns True if it reaches gem."""
    grid, pos = extract_grid(level_num)
    px, py = pos
    grav = True
    g = dict(grid)

    for move in moves:
        if move == 'left':
            nx, ny, r = try_move(g, px, py, -1, grav)
            px, py = nx, ny
            if r == 'gem': return True
            if r == 'die': return False
        elif move == 'right':
            nx, ny, r = try_move(g, px, py, 1, grav)
            px, py = nx, ny
            if r == 'gem': return True
            if r == 'die': return False
        elif move.startswith('click('):
            parts = move[6:-1].split(',')
            cx, cy = int(parts[0]), int(parts[1])
            cr = try_click(g, px, py, cx, cy, grav)
            if cr:
                g, px, py, grav, result, _ = cr
                if result == 'gem': return True
                if result == 'die': return False
            else:
                return False
    return False


def trace_solution(level_num, moves):
    """Trace a solution step by step for debugging."""
    grid, pos = extract_grid(level_num)
    px, py = pos
    grav = True
    g = dict(grid)

    print(f"  Start: ({px},{py}), grav={'UP' if grav else 'DOWN'}")
    for i, move in enumerate(moves):
        if move == 'left':
            nx, ny, r = try_move(g, px, py, -1, grav)
            px, py = nx, ny
            print(f"  {i}: {move} -> ({px},{py}) result={r}")
            if r == 'gem': return True
            if r == 'die': return False
        elif move == 'right':
            nx, ny, r = try_move(g, px, py, 1, grav)
            px, py = nx, ny
            print(f"  {i}: {move} -> ({px},{py}) result={r}")
            if r == 'gem': return True
            if r == 'die': return False
        elif move.startswith('click('):
            parts = move[6:-1].split(',')
            cx, cy = int(parts[0]), int(parts[1])
            cr = try_click(g, px, py, cx, cy, grav)
            if cr:
                g, px, py, grav, result, _ = cr
                print(f"  {i}: {move} -> ({px},{py}) grav={'UP' if grav else 'DOWN'} result={result}")
                if result == 'gem': return True
                if result == 'die': return False
            else:
                print(f"  {i}: {move} -> INVALID CLICK")
                return False
    print(f"  End: ({px},{py}) - no gem reached")
    return False


# =============================================================================
# Game verification with actual engine
# =============================================================================

def grid_to_screen(gx, gy, cam_y, tile_size=6):
    sx = gx * tile_size + tile_size // 2
    sy = gy * tile_size - cam_y + tile_size // 2
    return sx, sy


def replay_and_verify(env, game, level_num, sim_moves, level_action_history):
    """Replay moves on actual game.

    Re-grabs game.oztjzzyqoek each step to track camera position correctly
    after level transitions.
    """
    obs = env.reset()
    for prev in sorted(level_action_history.keys()):
        for act in level_action_history[prev]:
            obs = _do_action(env, act)

    level_acts = []

    for move in sim_moves:
        # Re-grab engine each step (changes after level transition)
        game_engine = game.oztjzzyqoek

        if move == 'left':
            obs = env.step(3)
            level_acts.append((3, None))
        elif move == 'right':
            obs = env.step(4)
            level_acts.append((4, None))
        elif move.startswith('click('):
            parts = move[6:-1].split(',')
            gx, gy = int(parts[0]), int(parts[1])
            cam_y = game_engine.camera.rczgvgfsfb[1]
            sx, sy = grid_to_screen(gx, gy, cam_y)
            obs = env.step(6, data={"x": sx, "y": sy})
            level_acts.append((6, {"x": sx, "y": sy}))

        if obs.levels_completed >= level_num:
            return level_acts

    return None


def _do_action(env, act):
    aid, data = act
    if aid == 6 and data:
        return env.step(6, data=data)
    return env.step(aid)


# =============================================================================
# Main solver
# =============================================================================

def get_manual_solutions():
    """Hand-crafted solutions for levels too complex for BFS."""
    solutions = {}

    # L1: 15 moves
    solutions[1] = [
        'right', 'right', 'right', 'right',  # (3,23) -> (7,20) via gap
        'click(7,19,x)',                       # break, fall to (7,16)
        'left', 'left',                        # (5,16)
        'click(4,16,x)',                       # break x at (4,16)
        'left',                                # (4,16)
        'click(4,15,x)',                       # break, fall to (4,13)
        'click(4,12,x)',                       # break, fall to (4,10)
        'right',                               # (5,10)
        'click(5,9,x)',                        # break, fall to (5,7)
        'left',                                # (4,7)
        'left',                                # (3,7) = gem
    ]

    # L2: 44 moves
    solutions[2] = [
        'right', 'right', 'right', 'right', 'right',
        'click(8,36,x)', 'click(8,35,x)',
        'left', 'left',
        'click(5,29,x)', 'left',
        'click(4,29,x)', 'left',
        'click(3,29,x)', 'left',
        'click(2,29,x)', 'left',
        'click(2,28,x)',
        'right', 'right', 'right',
        'click(5,24,x)', 'click(5,23,x)',
        'click(3,16,x)', 'click(4,16,x)', 'click(5,16,x)',
        'click(6,16,x)', 'click(7,16,x)', 'click(8,16,x)',
        'left', 'left',
        'click(3,20,x)', 'click(3,17,x)',
        'right', 'right', 'right', 'right', 'right',
        'click(8,15,x)', 'click(8,14,x)',
        'left', 'left', 'left',
        'click(5,9,x)',
    ]

    # L3: 36 moves
    solutions[3] = [
        'right', 'click(5,28,1)', 'right', 'right',
        'click(6,27,x)',
        'click(5,23,2)', 'left',
        'click(4,23,2)', 'left',
        'click(3,23,2)', 'left',
        'left',                     # falls to (2,19)
        'right',                    # falls to (3,18)
        'right',                    # (4,18)
        'click(5,17,2)', 'click(6,17,2)',
        'click(5,18,1)', 'click(6,18,1)',
        'right', 'right', 'right',  # falls to (7,13)
        'click(2,12,1)',
        'click(6,12,2)', 'click(5,12,2)', 'click(4,12,2)',
        'left', 'left', 'left', 'left', 'left',  # falls to (2,7)
        'right', 'right',
        'click(5,7,1)',
        'right', 'right', 'right',  # (7,7) = gem
    ]

    # L4: 19 moves (camera-aware — all clicks visible on screen)
    solutions[4] = [
        'right', 'right',
        'click(5,7,g)',
        'left', 'left', 'left',
        'click(3,17,x)',
        'right', 'right',
        'click(3,23,g)',
        'right', 'right',
        'click(5,23,g)',
        'click(7,23,x)', 'click(7,24,x)',
        'left', 'left', 'left',
        'click(4,31,g)',
    ]

    # L5: 30 moves (camera-aware)
    solutions[5] = [
        'right', 'right', 'right', 'right',
        'click(7,9,x)', 'click(8,9,x)', 'click(9,9,x)',
        'click(8,12,g)',
        'click(7,16,x)',
        'right',
        'click(3,21,2)', 'click(8,21,x)',
        'left', 'left', 'left', 'left', 'left',
        'click(8,29,g)',
        'left',
        'right', 'right', 'right', 'right', 'right', 'right', 'right',
        'left', 'left', 'left', 'left',
    ]

    # L6: 41 moves (camera-aware)
    solutions[6] = [
        'right', 'right', 'right', 'right', 'right',
        'click(6,22,g)', 'click(4,31,g)',
        'left', 'left',
        'right', 'right',
        'left', 'left',
        'click(5,13,2)',
        'left', 'left',
        'right', 'right', 'right',
        'click(8,1,g)',
        'left', 'left',
        'click(4,13,2)',
        'left',
        'right', 'right',
        'click(6,13,1)',
        'left', 'left',
        'right',
        'click(6,25,2)',
        'right',
        'click(7,25,2)',
        'right', 'right',
        'left', 'left', 'left', 'left', 'left', 'left',
    ]

    # L7: 44 moves — gravity platformer with toggle tiles (2/1)
    # Navigate zones: A(start) -> shaft -> B -> C -> x=7 column -> x=9 shaft -> D(gem)
    solutions[7] = [
        # Phase 1: Zone A -> (7,20) via toggle+gravity flip
        'right', 'right', 'right',
        'click(6,21,2)',                       # toggle (6,21) to '1' (create floor)
        'click(6,19,2)',                       # toggle (6,19) to '1'
        'click(0,19,g)',                       # flip grav -> land (6,20)
        'right',                               # (7,20)
        'click(0,20,g)',                       # flip back -> (7,20) grav=True

        # Phase 2: Enter shaft -> Zone B
        'right',                               # fall to (8,15) via shaft
        'left', 'left', 'left', 'left',       # -> (4,13) via (7,13)

        # Phase 3: Zone B -> Zone C via toggle bridge
        'click(0,13,g)',                       # flip -> (4,17) grav=False
        'click(4,14,2)',                       # toggle (4,14) to '1' (create floor)
        'click(0,17,g)',                       # flip -> (4,15) grav=True
        'left', 'left',                        # -> (3,15) -> fall to (2,8)

        # Phase 4: Zone C navigation to x=7 column
        'right',                               # (3,8)
        'click(0,8,g)',                        # flip -> (3,11) grav=False
        'right',                               # (4,11)
        'click(6,9,1)',                        # toggle (6,9) to '2' (open passage)
        'click(4,9,2)',                        # toggle (4,9) to '1' (create floor)
        'click(0,11,g)',                       # flip -> (4,10) grav=True
        'click(5,10,1)',                       # toggle (5,10) to '2' (open passage)
        'right',                               # fall to (5,8)
        'click(5,10,2)',                       # toggle back to '1' (create floor)
        'click(0,9,g)',                        # flip -> (5,9) grav=False
        'right',                               # fall to (6,11) via (6,9)='2'
        'click(6,9,2)',                        # toggle back to '1' (create floor)
        'click(0,10,g)',                       # flip -> (6,10) grav=True
        'right',                               # fall to (7,4) via (7,10)='2'

        # Phase 5: x=7 column -> x=9 shaft -> Zone D
        'click(7,8,2)',                        # toggle (7,8) to '1' (create floor)
        'click(0,5,g)',                        # flip -> (7,7) grav=False
        'right',                               # (8,7)
        'right',                               # fall to (9,26) via x=9 shaft

        # Phase 6: Zone D -> gem
        'left', 'left',                        # (8,26) -> (7,26)
        'click(0,26,g)',                       # flip -> (7,23) grav=True
        'left', 'left', 'left', 'left',       # -> (3,23)
        'click(0,23,g)',                       # flip -> fall to gem at (3,25)
    ]

    return solutions


def solve_all():
    print("=" * 60)
    print("bp35 Solver — Gravity Platformer")
    print("=" * 60)

    start_time = time.time()
    total_levels = 9
    mechanics = set()

    for lv in range(1, total_levels + 1):
        r = extract_grid(lv)
        if r:
            grid, _ = r
            for t in set(grid.values()):
                if t == 'x': mechanics.add('breakable_blocks')
                if t in ('1', '2'): mechanics.add('toggle_blocks')
                if t == 'g': mechanics.add('gravity_flip')
                if t == 'y': mechanics.add('exploder')
                if t in ('v', 'u'): mechanics.add('spikes')
                if t == 'm': mechanics.add('moving_platform')

    sim_solutions = {}
    manual = get_manual_solutions()
    for lv in range(1, total_levels + 1):
        print(f"\n--- Level {lv} ---")

        # Try manual solution first
        if lv in manual:
            m = manual[lv]
            if verify_solution(lv, m):
                print(f"  Manual solution: {len(m)} moves, verified")
                sim_solutions[lv] = m
                continue
            else:
                print(f"  Manual solution FAILED verification")

        # Try BFS with increasing click range, with time limit
        solved = False
        level_start = time.time()
        for cr in [3, 5]:
            if time.time() - level_start > 15:
                break
            ms = 500000
            moves = solve_level_bfs(lv, max_states=ms, click_range=cr)
            if moves:
                sim_solutions[lv] = moves
                solved = True
                break

    sim_elapsed = time.time() - start_time
    print(f"\nSimulation: {len(sim_solutions)}/{total_levels} in {sim_elapsed:.1f}s")

    print("\n" + "=" * 60)
    print("Verification with actual game")
    print("=" * 60)

    verified = 0
    try:
        import arc_agi
        import numpy as np
        import logging
        logging.disable(logging.WARNING)

        arc_inst = arc_agi.Arcade()
        env = arc_inst.make("bp35")
        obs = env.reset()
        game = env._game

        level_action_history = {}

        for lv in range(1, total_levels + 1):
            if lv not in sim_solutions:
                print(f"\n  L{lv}: No solution")
                break

            print(f"\n  L{lv}: Verifying {len(sim_solutions[lv])} moves...")
            acts = replay_and_verify(env, game, lv, sim_solutions[lv], level_action_history)
            if acts:
                verified += 1
                level_action_history[lv] = acts
                print(f"  L{lv}: VERIFIED ({len(acts)} actions)")
            else:
                print(f"  L{lv}: FAILED verification")
                break

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    elapsed = time.time() - start_time
    solved = verified

    print("\n" + "=" * 60)
    print(f"GAME_ID: bp35")
    print(f"LEVELS_SOLVED: {solved}")
    print(f"TOTAL_LEVELS: {total_levels}")
    print(f"MECHANICS: {', '.join(sorted(mechanics))}")
    print(f"Time: {elapsed:.1f}s")
    print("=" * 60)

    return solved, total_levels


if __name__ == "__main__":
    solve_all()
