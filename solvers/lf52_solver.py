#!/usr/bin/env python3
"""lf52 solver — Peg solitaire with slider tracks.

CRITICAL FIXES:
  1. env.step(0) is RESET
  2. game.ikhhdzfmarl changes on level advance
  3. grid.cdpcbbnfdp changes on camera scroll
  4. Slider ordering matters (furthest in direction first)
  5. Obstacles on sliders move with them
  6. Red pieces are MOVABLE but can't be removed (different type)
  7. Jumping over different-type piece = reposition without removal
  8. Blue pieces are permanent, not counted, can be jumped over
"""
import arc_agi
import warnings
import logging
import time
from collections import deque
import heapq

warnings.filterwarnings('ignore')
logging.disable(logging.WARNING)

DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]
DIR_TO_ACTION = {(0, -1): 1, (0, 1): 2, (-1, 0): 3, (1, 0): 4}


def execute_jump(env, game, piece_pos, land_pos):
    grid = game.ikhhdzfmarl.hncnfaqaddg
    off = grid.cdpcbbnfdp
    px, py = off[0] + piece_pos[0]*6 + 3, off[1] + piece_pos[1]*6 + 3
    lx, ly = off[0] + land_pos[0]*6 + 3, off[1] + land_pos[1]*6 + 3
    env.step(6, data={'x': px, 'y': py})
    return env.step(6, data={'x': lx, 'y': ly})

def execute_keyboard(env, direction):
    return env.step(DIR_TO_ACTION[direction])


class PegState:
    """State with typed pieces: normal (removable), red (permanent), blue (movable permanent).
    Optionally tracks camera offset for viewport-constrained levels."""
    __slots__ = ('normal', 'red', 'sliders', 'mob_obst', 'blues', 'cam_off', '_hash')
    def __init__(self, normal, red, sliders, mob_obst=frozenset(), blues=frozenset(), cam_off=None):
        self.normal = normal    # frozenset of normal piece positions
        self.red = red          # frozenset of red piece positions
        self.sliders = sliders  # tuple of slider positions
        self.mob_obst = mob_obst
        self.blues = blues      # frozenset of blue piece positions (movable but permanent)
        self.cam_off = cam_off  # (ox, oy) camera offset or None if unconstrained
        self._hash = hash((self.normal, self.red, self.sliders, self.mob_obst, self.blues, self.cam_off))
    def __hash__(self): return self._hash
    def __eq__(self, other):
        return (self.normal == other.normal and self.red == other.red and
                self.sliders == other.sliders and self.mob_obst == other.mob_obst and
                self.blues == other.blues and self.cam_off == other.cam_off)

    @property
    def all_pieces(self):
        return self.normal | self.red | self.blues


def jump_in_viewport(piece, land, cam_off):
    """Check if both piece click and land click are within 0-63 display coords."""
    if cam_off is None:
        return True
    ox, oy = cam_off
    px, py = ox + piece[0]*6 + 3, oy + piece[1]*6 + 3
    lx, ly = ox + land[0]*6 + 3, oy + land[1]*6 + 3
    return 0 <= px <= 63 and 0 <= py <= 63 and 0 <= lx <= 63 and 0 <= ly <= 63


def compute_jump_scroll(level, land_pos, cam_off):
    """Compute camera scroll triggered by a piece landing at a specific position.
    Returns new cam_off after the jump scroll (if any)."""
    if cam_off is None:
        return None
    ox, oy = cam_off
    if level == 9 and land_pos == (6, 5):
        return (ox - 20, oy)
    # No jump-triggered scroll for other levels/positions we handle
    return cam_off


def compute_cam_scroll(level, dx, dy, state, moves, wall_cells):
    """Compute camera scroll delta when a keyboard move causes a slider+piece to hit a wall.
    Returns new cam_off tuple or same cam_off if no scroll."""
    if state.cam_off is None:
        return None
    # Check which sliders stopped (hit a wall) and had a normal piece on them
    all_normal = state.normal
    scroll_delta = (0, 0)
    scroll_found = False
    for old_pos, new_pos in moves.items():
        if scroll_found:
            break
        # A slider moved from old_pos to new_pos. Check if old_pos had a normal piece.
        if old_pos in all_normal:
            # Normal piece was on this slider - compute scroll based on level
            if level == 8:
                scroll_delta = (0, -dy * 6)
            elif level >= 9:
                scroll_delta = (-dx * 6, -dy * 6)
    if scroll_delta == (0, 0):
        return state.cam_off
    ox, oy = state.cam_off
    # Guard: don't scroll right if offset.x >= 5 (except L5 which we don't handle here)
    if ox >= 5 and scroll_delta[0] > 0:
        return state.cam_off
    return (ox + scroll_delta[0], oy + scroll_delta[1])


def move_sliders(state_sliders, dx, dy, wall_cells):
    sorted_sl = list(state_sliders)
    if dx != 0:
        sorted_sl.sort(key=lambda s: s[0], reverse=dx > 0)
    else:
        sorted_sl.sort(key=lambda s: s[1], reverse=dy > 0)
    cur = set(state_sliders)
    new_sliders = []
    moved = False
    moves = {}
    for sx, sy in sorted_sl:
        nx, ny = sx + dx, sy + dy
        if (nx, ny) in wall_cells and (nx, ny) not in cur:
            moved = True
            cur.discard((sx, sy))
            cur.add((nx, ny))
            new_sliders.append((nx, ny))
            moves[(sx, sy)] = (nx, ny)
        else:
            new_sliders.append((sx, sy))
    return tuple(sorted(new_sliders)), moved, moves


def solve_bfs(normal_init, red_init, walkable, wall_cells, slider_starts,
              death=frozenset(), win_count=1, static_obst=frozenset(),
              mobile_obst=frozenset(), blues=frozenset(),
              max_states=5000000, max_time=180, movable_blues=False,
              cam_off=None, level_num=0):
    """A* solver with typed pieces.

    normal_init: normal piece positions (can be removed by jumping over same type)
    red_init: red piece positions (permanent, can reposition by jumping)
    win_count: number of normal pieces needed to remain
    movable_blues: if True, blue pieces can be jumped (repositioned, never removed)
    cam_off: (ox, oy) initial camera offset for viewport constraint, or None for unconstrained
    level_num: game level number (for camera scroll rules)
    """
    slider_tuple = tuple(sorted(slider_starts))
    blues_fs = frozenset(blues)
    if movable_blues:
        initial = PegState(frozenset(normal_init), frozenset(red_init),
                           slider_tuple, frozenset(mobile_obst), blues_fs, cam_off)
    else:
        initial = PegState(frozenset(normal_init), frozenset(red_init),
                           slider_tuple, frozenset(mobile_obst), cam_off=cam_off)

    counter = [0]
    heap = [(len(normal_init) * 100, 0, initial, [])]
    visited = {initial}
    t0 = time.time()
    best = len(normal_init)

    while heap:
        if len(visited) > max_states or time.time() - t0 > max_time:
            print(f"  Exhausted: {len(visited)} states, {time.time()-t0:.1f}s, best={best}")
            return None

        _, _, state, actions = heapq.heappop(heap)
        slider_set = frozenset(state.sliders)
        all_obst = static_obst | state.mob_obst
        cur_blues = state.blues if movable_blues else blues_fs
        all_pieces = state.all_pieces
        # Landing: walkable or slider, not occupied by piece/obstacle/blue
        landable = (walkable | slider_set) - all_pieces - all_obst

        if len(state.normal) <= win_count:
            if actions and actions[-1][0] == 'jump' and actions[-1][2] in death:
                continue
            return actions

        if len(state.normal) < best:
            best = len(state.normal)
            print(f"  Progress: {best} normal pcs at {len(visited)} states, {time.time()-t0:.1f}s")

        # Jump actions
        # Jumpable mid-cells: any piece (normal, red, blue), obstacles
        jumpable = all_pieces | all_obst

        # Normal pieces jumping
        for px, py in state.normal:
            for dx, dy in DIRS:
                mid = (px+dx, py+dy)
                far = (px+2*dx, py+2*dy)
                if mid in jumpable and far in landable:
                    if not jump_in_viewport((px,py), far, state.cam_off):
                        continue
                    # Determine what happens
                    new_normal = state.normal - {(px,py)}
                    new_red = state.red
                    if mid in state.normal:
                        # Normal jumps over normal: remove mid
                        new_normal = new_normal - {mid}
                    # If mid is red/obstacle/blue: no removal, just reposition
                    new_normal = new_normal | {far}
                    new_cam = compute_jump_scroll(level_num, far, state.cam_off)
                    ns = PegState(frozenset(new_normal), new_red, state.sliders,
                                  state.mob_obst, cur_blues if movable_blues else frozenset(),
                                  new_cam)
                    if ns not in visited:
                        visited.add(ns)
                        counter[0] += 1
                        jr = len(new_normal) < len(state.normal)
                        cost = len(new_normal) * 100 + len(actions) + 1 - (50 if jr else 0)
                        heapq.heappush(heap, (cost, counter[0], ns, actions + [('jump', (px,py), far)]))

        # Red pieces jumping (reposition only, never removes)
        for px, py in state.red:
            for dx, dy in DIRS:
                mid = (px+dx, py+dy)
                far = (px+2*dx, py+2*dy)
                if mid in jumpable and far in landable:
                    if not jump_in_viewport((px,py), far, state.cam_off):
                        continue
                    new_red = (state.red - {(px,py)}) | {far}
                    new_cam = compute_jump_scroll(level_num, far, state.cam_off)
                    ns = PegState(state.normal, frozenset(new_red), state.sliders,
                                  state.mob_obst, cur_blues if movable_blues else frozenset(),
                                  new_cam)
                    if ns not in visited:
                        visited.add(ns)
                        counter[0] += 1
                        cost = len(state.normal) * 100 + len(actions) + 1
                        heapq.heappush(heap, (cost, counter[0], ns, actions + [('jump', (px,py), far)]))

        # Blue pieces jumping (reposition only, never removes, only if movable_blues)
        if movable_blues:
            for px, py in cur_blues:
                for dx, dy in DIRS:
                    mid = (px+dx, py+dy)
                    far = (px+2*dx, py+2*dy)
                    if mid in jumpable and far in landable:
                        if not jump_in_viewport((px,py), far, state.cam_off):
                            continue
                        new_blues = (cur_blues - {(px,py)}) | {far}
                        new_cam = compute_jump_scroll(level_num, far, state.cam_off)
                        ns = PegState(state.normal, state.red, state.sliders,
                                      state.mob_obst, frozenset(new_blues),
                                      new_cam)
                        if ns not in visited:
                            visited.add(ns)
                            counter[0] += 1
                            cost = len(state.normal) * 100 + len(actions) + 1
                            heapq.heappush(heap, (cost, counter[0], ns, actions + [('jump', (px,py), far)]))

        # Keyboard actions
        for dx, dy in DIRS:
            new_sl, moved, moves = move_sliders(state.sliders, dx, dy, wall_cells)
            if moved:
                new_normal = set(state.normal)
                new_red = set(state.red)
                new_mob = set(state.mob_obst)
                new_blues_set = set(cur_blues) if movable_blues else set()
                for old, new in moves.items():
                    if old in new_normal:
                        new_normal.discard(old)
                        new_normal.add(new)
                    if old in new_red:
                        new_red.discard(old)
                        new_red.add(new)
                    if old in new_mob:
                        new_mob.discard(old)
                        new_mob.add(new)
                    if movable_blues and old in new_blues_set:
                        new_blues_set.discard(old)
                        new_blues_set.add(new)
                # Compute camera scroll for viewport-constrained levels
                new_cam = compute_cam_scroll(level_num, dx, dy, state, moves, wall_cells)
                ns = PegState(frozenset(new_normal), frozenset(new_red),
                              new_sl, frozenset(new_mob),
                              frozenset(new_blues_set) if movable_blues else frozenset(),
                              new_cam)
                if ns not in visited:
                    visited.add(ns)
                    counter[0] += 1
                    cost = len(state.normal) * 100 + len(actions) + 1
                    heapq.heappush(heap, (cost, counter[0], ns, actions + [('key', (dx, dy))]))

    return None


def extract_level_data(game):
    world = game.ikhhdzfmarl
    grid = world.hncnfaqaddg
    level = world.whtqurkphir

    walkable = set()
    normal_pieces = []
    red_pieces = []
    static_obst = set()
    mobile_obst = set()
    wall_cells = set()
    sliders = []
    blues = set()

    slider_positions = set()
    for y in range(grid.kfiapdsgfly):
        for x in range(grid.ksfoftduxiu):
            items = grid.ijpoqzvnjt(x, y)
            names = [i.yrxvacxlgrf for i in items]
            if 'hupkpseyuim2' in names:
                slider_positions.add((x, y))

    for y in range(grid.kfiapdsgfly):
        for x in range(grid.ksfoftduxiu):
            items = grid.ijpoqzvnjt(x, y)
            names = [i.yrxvacxlgrf for i in items]

            if 'hupkpseyuim' in names:
                walkable.add((x, y))
            if 'hupkpseyuim2' in names:
                sliders.append((x, y))
            if any('kraubslpehi' in n for n in names):
                wall_cells.add((x, y))
            if 'fozwvlovdui' in names:
                normal_pieces.append((x, y))
            if 'fozwvlovdui_red' in names:
                red_pieces.append((x, y))
            if any(n == 'fozwvlovdui_blue' for n in names):
                blues.add((x, y))
            if any('dgxfozncuiz' in n for n in names):
                if (x, y) in slider_positions:
                    mobile_obst.add((x, y))
                else:
                    static_obst.add((x, y))

    death = set()
    if level == 1: death = {(0,2),(2,2),(5,1)}
    elif level == 2: death = {(0,1),(2,1),(4,1)}
    elif level == 3: death = {(1,0),(0,3),(10,0),(13,2),(13,4)}
    elif level == 6:
        # Special death: landing at (16,2) when red is at (6,6)
        # We'll handle this in the solver by checking post-jump
        pass

    # Win count: for L6-7 need 2 total (1 normal + 1 red), so normal win = 1
    # For L8+ blues don't count, need 1 normal remaining
    win_count = 1  # always need 1 normal piece remaining

    return {
        'walkable': walkable, 'normal': normal_pieces, 'red': red_pieces,
        'static_obst': static_obst, 'mobile_obst': mobile_obst,
        'wall_cells': wall_cells, 'sliders': sliders, 'death': death,
        'win_count': win_count, 'level': level, 'blues': blues,
    }


# --- Level Solvers ---

def solve_level_1(env, game):
    data = extract_level_data(game)
    sol = solve_bfs(data['normal'], data['red'], data['walkable'], data['wall_cells'],
                    data['sliders'], death=data['death'],
                    static_obst=frozenset(data['static_obst']),
                    max_states=100000, max_time=10)
    if not sol: return False
    print(f"  L1: {sum(1 for a in sol if a[0]=='jump')} jumps")
    for a in sol:
        if a[0] == 'jump': execute_jump(env, game, a[1], a[2])
        else: execute_keyboard(env, a[1])
    return True

def solve_level_2(env, game):
    K = lambda d: execute_keyboard(env, d)
    J = lambda s, l: execute_jump(env, game, s, l)
    for _ in range(4): K((1, 0))
    for _ in range(3): K((0, -1))
    K((-1, 0))
    J((1,1),(3,1)); J((3,1),(5,1)); J((5,1),(7,1))
    K((1, 0))
    for _ in range(3): K((0, 1))
    for _ in range(7): K((-1, 0))
    for _ in range(3): K((0, 1))
    for _ in range(4): K((1, 0))
    J((5,7),(7,7))
    return True

def solve_level_3(env, game):
    J = lambda p, l: execute_jump(env, game, p, l)
    K = lambda d: execute_keyboard(env, d)
    J((1,1),(1,3)); J((1,3),(3,3)); J((3,3),(3,1))
    K((-1,0)); J((3,1),(5,1))
    K((1,0)); K((1,0)); K((1,0))
    J((8,1),(10,1)); J((12,2),(10,2)); J((10,1),(10,3))
    J((12,4),(10,4)); J((10,3),(10,5)); J((10,5),(10,7))
    for d in [(0,-1),(0,-1),(1,0),(1,0),(0,1),(0,1),(1,0)]: K(d)
    J((11,7),(9,7))
    for d in [(-1,0),(0,-1),(0,-1),(-1,0),(-1,0),(0,1),(0,1),(-1,0),(-1,0)]: K(d)
    J((4,7),(2,7)); J((2,7),(0,7))
    return True


def solve_slider_heavy(normal_init, red_init, walkable, wall_cells, slider_starts,
                        death=frozenset(), win_count=1, static_obst=frozenset(),
                        mobile_obst=frozenset(), blues=frozenset(),
                        max_states=20000000, max_time=400, movable_blues=False,
                        cam_off=None, level_num=0):
    """Optimized solver for levels with many sliders.

    Key optimization: compress slider state by hashing, use deque BFS
    to find paths with minimum jumps (BFS explores by jump count first).
    """
    slider_tuple = tuple(sorted(slider_starts))
    blues_fs = frozenset(blues)
    if movable_blues:
        initial = PegState(frozenset(normal_init), frozenset(red_init),
                           slider_tuple, frozenset(mobile_obst), blues_fs, cam_off)
    else:
        initial = PegState(frozenset(normal_init), frozenset(red_init),
                           slider_tuple, frozenset(mobile_obst), cam_off=cam_off)

    # Use BFS (not A*) to find shortest path
    queue = deque([(initial, [])])
    visited = {initial}
    t0 = time.time()
    best = len(normal_init)

    while queue:
        if len(visited) > max_states or time.time() - t0 > max_time:
            print(f"  Slider-heavy exhausted: {len(visited)} states, {time.time()-t0:.1f}s, best={best}")
            return None

        state, actions = queue.popleft()
        slider_set = frozenset(state.sliders)
        all_obst = static_obst | state.mob_obst
        cur_blues = state.blues if movable_blues else blues_fs
        all_pieces = state.all_pieces
        landable = (walkable | slider_set) - all_pieces - all_obst

        if len(state.normal) <= win_count:
            if actions and actions[-1][0] == 'jump' and actions[-1][2] in death:
                continue
            return actions

        if len(state.normal) < best:
            best = len(state.normal)
            print(f"  Progress: {best} normal pcs at {len(visited)} states, {time.time()-t0:.1f}s")

        jumpable = all_pieces | all_obst

        # Process jumps first (they reduce piece count)
        for px, py in state.normal:
            for dx, dy in DIRS:
                mid = (px+dx, py+dy)
                far = (px+2*dx, py+2*dy)
                if mid in jumpable and far in landable:
                    if not jump_in_viewport((px,py), far, state.cam_off):
                        continue
                    new_normal = state.normal - {(px,py)}
                    new_red = state.red
                    if mid in state.normal:
                        new_normal = new_normal - {mid}
                    new_normal = new_normal | {far}
                    new_cam = compute_jump_scroll(level_num, far, state.cam_off)
                    ns = PegState(frozenset(new_normal), new_red, state.sliders,
                                  state.mob_obst, cur_blues if movable_blues else frozenset(),
                                  new_cam)
                    if ns not in visited:
                        visited.add(ns)
                        queue.append((ns, actions + [('jump', (px,py), far)]))

        for px, py in state.red:
            for dx, dy in DIRS:
                mid = (px+dx, py+dy)
                far = (px+2*dx, py+2*dy)
                if mid in jumpable and far in landable:
                    if not jump_in_viewport((px,py), far, state.cam_off):
                        continue
                    new_red = (state.red - {(px,py)}) | {far}
                    new_cam = compute_jump_scroll(level_num, far, state.cam_off)
                    ns = PegState(state.normal, frozenset(new_red), state.sliders,
                                  state.mob_obst, cur_blues if movable_blues else frozenset(),
                                  new_cam)
                    if ns not in visited:
                        visited.add(ns)
                        queue.append((ns, actions + [('jump', (px,py), far)]))

        # Blue pieces jumping (reposition, never removed)
        if movable_blues:
            for px, py in cur_blues:
                for dx, dy in DIRS:
                    mid = (px+dx, py+dy)
                    far = (px+2*dx, py+2*dy)
                    if mid in jumpable and far in landable:
                        if not jump_in_viewport((px,py), far, state.cam_off):
                            continue
                        new_blues = (cur_blues - {(px,py)}) | {far}
                        new_cam = compute_jump_scroll(level_num, far, state.cam_off)
                        ns = PegState(state.normal, state.red, state.sliders,
                                      state.mob_obst, frozenset(new_blues),
                                      new_cam)
                        if ns not in visited:
                            visited.add(ns)
                            queue.append((ns, actions + [('jump', (px,py), far)]))

        # Keyboard actions
        for dx, dy in DIRS:
            new_sl, moved, moves = move_sliders(state.sliders, dx, dy, wall_cells)
            if moved:
                new_normal = set(state.normal)
                new_red = set(state.red)
                new_mob = set(state.mob_obst)
                new_blues_set = set(cur_blues) if movable_blues else set()
                for old, new in moves.items():
                    if old in new_normal:
                        new_normal.discard(old)
                        new_normal.add(new)
                    if old in new_red:
                        new_red.discard(old)
                        new_red.add(new)
                    if old in new_mob:
                        new_mob.discard(old)
                        new_mob.add(new)
                    if movable_blues and old in new_blues_set:
                        new_blues_set.discard(old)
                        new_blues_set.add(new)
                new_cam = compute_cam_scroll(level_num, dx, dy, state, moves, wall_cells)
                ns = PegState(frozenset(new_normal), frozenset(new_red),
                              new_sl, frozenset(new_mob),
                              frozenset(new_blues_set) if movable_blues else frozenset(),
                              new_cam)
                if ns not in visited:
                    visited.add(ns)
                    queue.append((ns, actions + [('key', (dx, dy))]))

    return None


def solve_level_7(env, game):
    """L7: Hardcoded solution. Two normals + one red leapfrog through 3 slider tracks."""
    J = lambda p, l: execute_jump(env, game, p, l)
    K = lambda d: execute_keyboard(env, d)
    L, R, U, D = (-1,0), (1,0), (0,-1), (0,1)
    # Phase 1: N exits track 2 to bottom walkable
    for _ in range(2): K(L)
    for _ in range(2): K(U)
    for _ in range(3): K(L)
    J((0,1),(0,3))
    for _ in range(3): K(R)
    for _ in range(2): K(D)
    for _ in range(3): K(R)
    K(D)
    J((6,6),(6,8))
    # Phase 1b: R exits track 2 to bottom walkable
    K(U)
    for _ in range(3): K(L)
    for _ in range(2): K(U)
    for _ in range(3): K(R)
    J((6,1),(6,3))
    for _ in range(3): K(L)
    for _ in range(2): K(D)
    for _ in range(2): K(L)
    K(D)
    J((1,6),(1,8))
    # Phase 2: Leapfrog bottom
    J((1,8),(3,8)); J((3,8),(5,8)); J((5,8),(7,8))
    J((6,8),(8,8)); J((7,8),(9,8))
    # Phase 3: Enter track 1
    K(D); K(L); K(D); K(D); K(R); K(R); K(D)
    J((8,8),(10,8)); J((9,8),(11,8))
    # N rides track 1 to (12,3), exits
    K(U); K(L); K(L); K(U); K(U); K(R); K(U); K(U); K(R); K(R); K(R)
    J((12,3),(14,3))
    # R enters track 1
    K(L); K(L); K(L); K(D); K(D); K(R); K(R); K(D)
    J((11,8),(11,6))
    # R rides track 1 to (14,2)
    K(U); K(L); K(L); K(U); K(U); K(R); K(R); K(U); K(U); K(R); K(R); K(R); K(D)
    # Phase 4: Leapfrog middle
    J((14,2),(14,4)); J((14,3),(14,5)); J((14,4),(14,6))
    J((14,5),(16,5)); J((16,5),(18,5))
    J((14,6),(16,6)); J((16,6),(18,6))
    # Phase 5: N enters track 0
    K(L); K(L); K(D); K(L); K(D); K(R); K(D); K(R); K(D)
    J((18,5),(18,3))
    # N rides track 0 to (22,3)
    K(U); K(R); K(R); K(R); K(R); K(D)
    J((22,3),(22,5))
    # Final: right N jumps over left N for win
    K(U); K(L); K(U); K(L); K(L); K(D); K(R); K(D); K(D)
    J((22,6),(22,4))
    return True


def solve_level_10(env, game):
    """L10: Two-phase solver. Phase 1: slider BFS to get piece from (4,0) to lower area.
    Phase 2: jump BFS with movable blues to win."""
    data = extract_level_data(game)
    walkable = data['walkable']
    wall_cells = data['wall_cells']
    grid = game.ikhhdzfmarl.hncnfaqaddg
    init_cam_off = tuple(grid.cdpcbbnfdp)

    lower_walkable = frozenset(c for c in walkable if c[1] >= 5)
    sl_init = tuple(sorted(data['sliders']))
    rcb = frozenset(b for b in data['blues'] if b[0] == 8)
    lab = frozenset(b for b in data['blues'] if b[0] != 8)

    # Find the piece in the upper area
    upper_piece = None
    lower_piece = None
    for p in data['normal']:
        if p[1] < 5:
            upper_piece = p
        else:
            lower_piece = p

    if upper_piece is None:
        print("  L10: No upper piece found, trying generic")
        return solve_generic(env, game, 10)

    print(f"  L10: upper={upper_piece}, lower={lower_piece}, cam_off={init_cam_off}")

    class P1State:
        __slots__ = ('sliders', 'rcb', 'piece', 'cam_off', '_hash')
        def __init__(self, sliders, rcb, piece, cam_off):
            self.sliders = sliders
            self.rcb = rcb
            self.piece = piece
            self.cam_off = cam_off
            self._hash = hash((sliders, rcb, piece, cam_off))
        def __hash__(self): return self._hash
        def __eq__(self, other):
            return (self.sliders == other.sliders and self.rcb == other.rcb and
                    self.piece == other.piece and self.cam_off == other.cam_off)

    init = P1State(sl_init, rcb, upper_piece, init_cam_off)
    visited = {init}
    queue = deque([(init, [])])
    t0 = time.time()
    found = None

    while queue:
        if len(visited) > 10000000 or time.time() - t0 > 180:
            print(f"  Phase 1 exhausted: {len(visited)} states, {time.time()-t0:.1f}s")
            break

        state, actions = queue.popleft()
        sl_set = frozenset(state.sliders)
        px, py = state.piece
        all_blues = state.rcb | lab

        if state.piece in lower_walkable:
            found = actions
            print(f"  Phase 1: {len(actions)} moves, piece at {state.piece}")
            break

        for dx, dy in DIRS:
            mid = (px+dx, py+dy)
            far = (px+2*dx, py+2*dy)
            mid_jumpable = mid in all_blues
            far_landable = (far in walkable or far in sl_set) and far not in all_blues and far != lower_piece
            if mid_jumpable and far_landable:
                if not jump_in_viewport(state.piece, far, state.cam_off):
                    continue
                ns = P1State(state.sliders, state.rcb, far, state.cam_off)
                if ns not in visited:
                    visited.add(ns)
                    queue.append((ns, actions + [('jump', state.piece, far)]))

        for dx, dy in DIRS:
            new_sl, moved, moves = move_sliders(state.sliders, dx, dy, wall_cells)
            if moved:
                new_rcb = set(state.rcb)
                new_piece = state.piece
                actually_moved = False
                for old, new in moves.items():
                    if old in new_rcb:
                        new_rcb.discard(old)
                        new_rcb.add(new)
                        actually_moved = True
                    if old == new_piece:
                        new_piece = new
                # L10 camera scroll: check if normal piece hit wall
                # L10 uses level=10 which has nybfuxmyrv = (0, 0) -- no scroll!
                # So cam_off stays the same for L10
                ns = P1State(new_sl, frozenset(new_rcb), new_piece, state.cam_off)
                if ns not in visited:
                    visited.add(ns)
                    queue.append((ns, actions + [('key', (dx, dy))]))

    if not found:
        print("  Phase 1 failed")
        return False

    for a in found:
        if a[0] == 'jump':
            execute_jump(env, game, a[1], a[2])
        else:
            execute_keyboard(env, a[1])

    data2 = extract_level_data(game)
    grid2 = game.ikhhdzfmarl.hncnfaqaddg
    cam_off2 = tuple(grid2.cdpcbbnfdp)
    print(f"  Phase 2: {len(data2['normal'])} normal, {len(data2['blues'])} blues, cam_off={cam_off2}")

    sol2 = solve_bfs(
        data2['normal'], data2['red'], data2['walkable'], data2['wall_cells'],
        data2['sliders'], death=data2['death'], win_count=data2['win_count'],
        static_obst=frozenset(data2['static_obst']),
        mobile_obst=frozenset(data2['mobile_obst']),
        blues=frozenset(data2['blues']),
        max_states=30000000, max_time=120,
        movable_blues=True,
        cam_off=cam_off2, level_num=10,
    )
    if not sol2:
        print("  Phase 2 failed")
        return False

    jumps = sum(1 for a in sol2 if a[0] == 'jump')
    keys = sum(1 for a in sol2 if a[0] == 'key')
    print(f"  Phase 2: {jumps} jumps + {keys} key moves")

    for a in sol2:
        if a[0] == 'jump': execute_jump(env, game, a[1], a[2])
        else: execute_keyboard(env, a[1])
    return True


def solve_generic(env, game, level_num):
    data = extract_level_data(game)
    print(f"  L{level_num}: {len(data['normal'])} normal, {len(data['red'])} red, "
          f"{len(data['sliders'])} sl, {len(data['blues'])} blues, win={data['win_count']}")
    print(f"  Normal: {data['normal']}")
    print(f"  Red: {data['red']}")
    print(f"  Blues: {sorted(data['blues'])}")
    print(f"  Sliders: {data['sliders']}")

    total_pcs = len(data['normal']) + len(data['red'])
    n_sliders = len(data['sliders'])
    has_blues = len(data['blues']) > 0
    # Blues are movable in levels >= 8
    movable_blues = has_blues and data['level'] >= 8

    # For levels >= 8, enable viewport constraint with camera scroll tracking
    cam_off = None
    if data['level'] >= 8:
        grid = game.ikhhdzfmarl.hncnfaqaddg
        cam_off = tuple(grid.cdpcbbnfdp)
        print(f"  Viewport constraint: cam_off={cam_off}")

    if n_sliders >= 6:
        sol = solve_slider_heavy(
            data['normal'], data['red'], data['walkable'], data['wall_cells'],
            data['sliders'], death=data['death'], win_count=data['win_count'],
            static_obst=frozenset(data['static_obst']),
            mobile_obst=frozenset(data['mobile_obst']),
            blues=frozenset(data['blues']),
            max_states=30000000, max_time=600,
            movable_blues=movable_blues,
            cam_off=cam_off, level_num=data['level'],
        )
    else:
        max_s = 20000000
        max_t = 600
        sol = solve_bfs(
            data['normal'], data['red'], data['walkable'], data['wall_cells'],
            data['sliders'], death=data['death'], win_count=data['win_count'],
            static_obst=frozenset(data['static_obst']),
            mobile_obst=frozenset(data['mobile_obst']),
            blues=frozenset(data['blues']),
            max_states=max_s, max_time=max_t,
            movable_blues=movable_blues,
            cam_off=cam_off, level_num=data['level'],
        )

    if not sol:
        print(f"  No solution found")
        return False

    jumps = sum(1 for a in sol if a[0] == 'jump')
    keys = sum(1 for a in sol if a[0] == 'key')
    print(f"  Solution: {jumps} jumps + {keys} key moves")

    for a in sol:
        if a[0] == 'jump': execute_jump(env, game, a[1], a[2])
        else: execute_keyboard(env, a[1])
    return True


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('lf52')
    obs = env.reset()
    game = env._game

    print(f"lf52: {obs.win_levels} levels")

    solvers = {1: solve_level_1, 2: solve_level_2, 3: solve_level_3, 7: solve_level_7, 10: solve_level_10}

    for level in range(1, obs.win_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        cur_level = game.ikhhdzfmarl.whtqurkphir
        print(f"\n--- Level {level} (game_level={cur_level}) ---")

        if level in solvers:
            success = solvers[level](env, game)
        else:
            success = solve_generic(env, game, level)

        if not success:
            print(f"  FAILED level {level}")
            break

        obs_check = env.step(6, data={'x': 0, 'y': 0})
        print(f"  completed={obs_check.levels_completed}, state={obs_check.state.name}")
        obs = obs_check

    final_obs = env.step(6, data={'x': 0, 'y': 0})
    total = final_obs.levels_completed
    if final_obs.state.name == "WIN":
        total = obs.win_levels if hasattr(obs, 'win_levels') and obs.win_levels > 0 else 10
    win_levels = obs.win_levels if hasattr(obs, 'win_levels') and obs.win_levels > 0 else final_obs.win_levels
    print(f"\nlf52 RESULT: {total}/{win_levels}")
    return total


if __name__ == "__main__":
    solve()
