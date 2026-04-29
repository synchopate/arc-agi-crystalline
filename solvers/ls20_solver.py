#!/usr/bin/env python3
"""ls20 solver — Grid puzzle: match shape/color/rotation then step on goal tiles.

Handles pushable walls and MOVING MODIFIERS (dboxixicic).
Moving modifiers change position each step, making modifier positions
part of BFS state. Modifier movement undone when player is blocked.
"""

import sys
import warnings
import logging
from collections import deque

sys.path.insert(0, '/home/paolo/arc-agi/solver')
import arc_agi

warnings.filterwarnings('ignore')
logging.disable(logging.WARNING)

COLORS = [12, 9, 14, 8]
ROTATIONS = [0, 90, 180, 270]
NUM_SHAPES = 6
CELL = 5

GRID_XS = [4 + 5*i for i in range(12)]
GRID_YS = [5*i for i in range(12)]

MOVES = {
    1: (0, -CELL),
    2: (0, CELL),
    3: (-CELL, 0),
    4: (CELL, 0),
}


def sprite_overlaps_player(sprite_x, sprite_y, player_x, player_y, pw=5, ph=5):
    return (sprite_x >= player_x and sprite_x < player_x + pw and
            sprite_y >= player_y and sprite_y < player_y + ph)


class MovingModifier:
    """Simulates a dboxixicic moving modifier in pure BFS."""
    def __init__(self, mod_type, boundary_x, boundary_y, boundary_w, boundary_h,
                 boundary_pixels, start_x, start_y, cell=5):
        self.mod_type = mod_type  # 'shape', 'color', 'rotation'
        self.bnd_x = boundary_x
        self.bnd_y = boundary_y
        self.bnd_w = boundary_w
        self.bnd_h = boundary_h
        self.bnd_pixels = boundary_pixels  # 2D list
        self.start_x = start_x
        self.start_y = start_y
        self.cell = cell

    def is_valid_pos(self, x, y):
        """Check if position is within boundary and pixel >= 0."""
        lx = x - self.bnd_x
        ly = y - self.bnd_y
        if lx < 0 or lx >= self.bnd_w or ly < 0 or ly >= self.bnd_h:
            return False
        return self.bnd_pixels[ly][lx] >= 0

    def is_within_bounds(self, x, y):
        return (x >= self.bnd_x and y >= self.bnd_y and
                x < self.bnd_x + self.bnd_w and y < self.bnd_y + self.bnd_h)

    @staticmethod
    def dir_to_delta(d):
        # 0=down, 1=right, 2=up, 3=left
        if d == 0: return (0, 1)
        if d == 1: return (1, 0)
        if d == 2: return (0, -1)
        return (-1, 0)

    def step(self, x, y, direction):
        """Move modifier one step. Returns (new_x, new_y, new_dir).
        Priority: current dir, left turn (-1), right turn (+1), reverse (+2)."""
        priorities = [
            direction,
            (direction - 1) % 4,
            (direction + 1) % 4,
            (direction + 2) % 4,
        ]
        for d in priorities:
            dx, dy = self.dir_to_delta(d)
            nx = x + dx * self.cell
            ny = y + dy * self.cell
            if self.is_within_bounds(nx, ny) and self.is_valid_pos(nx, ny):
                return (nx, ny, d)
        return (x, y, direction)  # no valid move

    def grid_positions(self, mx, my):
        """Get grid positions this modifier covers at position (mx, my)."""
        positions = set()
        for gx in GRID_XS:
            for gy in GRID_YS:
                if sprite_overlaps_player(mx, my, gx, gy):
                    positions.add((gx, gy))
        return positions

    def precompute_all_states(self):
        """Find all reachable (x, y, dir) states for this modifier."""
        states = set()
        # Start from initial position with all directions
        queue = deque()
        init = (self.start_x, self.start_y, 0)
        queue.append(init)
        states.add(init)
        while queue:
            x, y, d = queue.popleft()
            nx, ny, nd = self.step(x, y, d)
            if (nx, ny, nd) not in states:
                states.add((nx, ny, nd))
                queue.append((nx, ny, nd))
        return states


def extract_level_info(game):
    """Extract level info from actual game state, including moving modifiers."""
    walls = set()
    for s in game.current_level.get_sprites_by_tag("ihdgageizm"):
        walls.add((s.x, s.y))

    fjzuynaokm = set()
    for s in game.current_level.get_sprites_by_tag("ihdgageizm"):
        fjzuynaokm.add((s.x, s.y))
    for s in game.current_level.get_sprites_by_tag("rjlbuycveu"):
        fjzuynaokm.add((s.x, s.y))

    walkable = set()
    for x in GRID_XS:
        for y in GRID_YS:
            if (x, y) not in walls:
                walkable.add((x, y))

    player = game.current_level.get_sprites_by_tag("sfqyzhzkij")[0]
    start = (player.x, player.y)

    def grid_positions_for_sprite(sx, sy):
        positions = set()
        for gx in GRID_XS:
            for gy in GRID_YS:
                if sprite_overlaps_player(sx, sy, gx, gy):
                    positions.add((gx, gy))
        return positions

    # Detect moving modifiers via wsoslqeku pattern
    # xfmluydglp sprites that overlap with modifier sprites
    boundary_sprites = game.current_level.get_sprites_by_tag("xfmluydglp")
    shape_sprites = game.current_level.get_sprites_by_tag("ttfwljgohq")
    color_sprites = game.current_level.get_sprites_by_tag("soyhouuebz")
    rotation_sprites = game.current_level.get_sprites_by_tag("rhsxkxzdjz")

    moving_modifiers = []
    moving_mod_sprites = set()  # track which modifier sprites are moving

    for bnd in boundary_sprites:
        for mod_tag, mod_list, mod_type in [
            ("ttfwljgohq", shape_sprites, "shape"),
            ("soyhouuebz", color_sprites, "color"),
            ("rhsxkxzdjz", rotation_sprites, "rotation"),
        ]:
            for mod_s in mod_list:
                if bnd.collides_with(mod_s, ignoreMode=True):
                    # Extract boundary pixel data
                    pixels_2d = []
                    rendered = bnd.pixels
                    if hasattr(rendered, 'tolist'):
                        pixels_2d = rendered.tolist()
                    else:
                        pixels_2d = list(rendered)
                    mm = MovingModifier(
                        mod_type=mod_type,
                        boundary_x=bnd.x, boundary_y=bnd.y,
                        boundary_w=bnd.width, boundary_h=bnd.height,
                        boundary_pixels=pixels_2d,
                        start_x=mod_s.x, start_y=mod_s.y,
                    )
                    moving_modifiers.append(mm)
                    moving_mod_sprites.add(id(mod_s))

    # Static modifiers (not moving)
    shape_changer_positions = set()
    color_changer_positions = set()
    rotation_changer_positions = set()

    for s in shape_sprites:
        if id(s) not in moving_mod_sprites:
            for pos in grid_positions_for_sprite(s.x, s.y):
                shape_changer_positions.add(pos)

    for s in color_sprites:
        if id(s) not in moving_mod_sprites:
            for pos in grid_positions_for_sprite(s.x, s.y):
                color_changer_positions.add(pos)

    for s in rotation_sprites:
        if id(s) not in moving_mod_sprites:
            for pos in grid_positions_for_sprite(s.x, s.y):
                rotation_changer_positions.add(pos)

    refill_grid_map = {}
    goal_positions = {}

    refill_sprites = game.current_level.get_sprites_by_tag("npxgalaybz")
    for ri, s in enumerate(refill_sprites):
        for pos in grid_positions_for_sprite(s.x, s.y):
            refill_grid_map[pos] = ri

    goal_sprites = game.current_level.get_sprites_by_tag("rjlbuycveu")
    goals = []
    for gi, s in enumerate(goal_sprites):
        goals.append((s.x, s.y))
        for pos in grid_positions_for_sprite(s.x, s.y):
            goal_positions[pos] = gi

    pushable_map = {}
    for h in game.hasivfwip:
        s = h.sprite
        dx_push = h.dx
        dy_push = h.dy
        width = s.width
        height = s.height

        wall_cx = s.x + 1 * dx_push
        wall_cy = s.y + 1 * dy_push
        push_dist = 0
        for n in range(1, 12):
            check_x = wall_cx + dx_push * width * n
            check_y = wall_cy + dy_push * height * n
            if (check_x, check_y) in fjzuynaokm:
                push_dist = max(0, n - 1)
                break

        if push_dist <= 0:
            continue

        for gx in GRID_XS:
            for gy in GRID_YS:
                if (gx < s.x + s.width and gx + 5 > s.x and
                    gy < s.y + s.height and gy + 5 > s.y):
                    if (gx, gy) in walkable:
                        dest_x = gx + dx_push * width * push_dist
                        dest_y = gy + dy_push * height * push_dist
                        pushable_map[(gx, gy)] = (dest_x, dest_y)

    return {
        'start': start,
        'walkable': walkable,
        'goals': goals,
        'shape_changers': shape_changer_positions,
        'color_changers': color_changer_positions,
        'rotation_changers': rotation_changer_positions,
        'refill_map': refill_grid_map,
        'goal_map': goal_positions,
        'num_refills': len(refill_sprites),
        'num_goals': len(goal_sprites),
        'pushable_map': pushable_map,
        'moving_modifiers': moving_modifiers,
    }


def get_moving_modifier_grid_effects(moving_mods, mod_states):
    """Get current grid effects from moving modifiers at their current positions."""
    shape_changers = set()
    color_changers = set()
    rotation_changers = set()
    for i, mm in enumerate(moving_mods):
        mx, my, _d = mod_states[i]
        positions = mm.grid_positions(mx, my)
        if mm.mod_type == 'shape':
            shape_changers.update(positions)
        elif mm.mod_type == 'color':
            color_changers.update(positions)
        elif mm.mod_type == 'rotation':
            rotation_changers.update(positions)
    return shape_changers, color_changers, rotation_changers


def apply_modifiers(pos, shape, col_idx, rot_idx, goals_mask, refills_mask,
                    info, goal_shapes, goal_colors, goal_rots,
                    dyn_shape, dyn_color, dyn_rot):
    """Apply all modifiers at a position. Returns (new_shape, new_col, new_rot, new_goals, new_refills, refill_happened, blocked)."""
    new_shape = shape
    new_col = col_idx
    new_rot = rot_idx
    new_goals = goals_mask
    new_refills = refills_mask
    refill_happened = False
    blocked = False

    if pos in info['shape_changers'] or pos in dyn_shape:
        new_shape = (shape + 1) % NUM_SHAPES
    if pos in info['color_changers'] or pos in dyn_color:
        new_col = (col_idx + 1) % len(COLORS)
    if pos in info['rotation_changers'] or pos in dyn_rot:
        new_rot = (rot_idx + 1) % 4

    if pos in info['refill_map']:
        ri = info['refill_map'][pos]
        if not (refills_mask & (1 << ri)):
            new_refills = refills_mask | (1 << ri)
            refill_happened = True

    if pos in info['goal_map']:
        gi = info['goal_map'][pos]
        if not (goals_mask & (1 << gi)):
            if (new_shape == goal_shapes[gi] and
                new_col == goal_colors[gi] and
                new_rot == goal_rots[gi]):
                new_goals = goals_mask | (1 << gi)
            else:
                blocked = True

    return new_shape, new_col, new_rot, new_goals, new_refills, refill_happened, blocked


def bfs_solve_level(level_num, info, ld):
    """BFS with pushable walls and moving modifier handling."""
    walkable = info['walkable']
    start_x, start_y = info['start']

    start_shape = ld['start_shape']
    start_color_idx = COLORS.index(ld['start_color'])
    start_rot_idx = ROTATIONS.index(ld['start_rotation'])

    goal_shapes = ld['goal_shapes']
    goal_colors = [COLORS.index(c) for c in ld['goal_colors']]
    goal_rots = [ROTATIONS.index(r) for r in ld['goal_rotations']]

    num_goals = info['num_goals']
    all_goals_mask = (1 << num_goals) - 1

    pushable_map = info['pushable_map']
    moving_mods = info['moving_modifiers']

    step_counter = ld['step_counter']
    steps_decrement = ld['steps_decrement']

    has_moving_mods = len(moving_mods) > 0

    # Initial moving modifier states: (x, y, direction=0)
    init_mod_states = tuple((mm.start_x, mm.start_y, 0) for mm in moving_mods)

    # State: (x, y, shape, col_idx, rot_idx, goals_mask, refills_mask, mod_states)
    initial_state = (start_x, start_y, start_shape, start_color_idx, start_rot_idx, 0, 0, init_mod_states)
    initial_steps = step_counter

    visited = {}
    queue = deque()
    queue.append((initial_state, initial_steps, []))
    visited[initial_state] = initial_steps

    best_solution = None
    iterations = 0

    while queue:
        state, steps, actions = queue.popleft()
        x, y, shape, col_idx, rot_idx, goals_mask, refills_mask, mod_states = state
        iterations += 1

        if iterations % 200000 == 0:
            print(f"  BFS L{level_num}: {iterations} states, q={len(queue)}")

        if iterations > 8000000:
            break

        if best_solution and len(actions) >= len(best_solution):
            continue

        for action_id, (dx, dy) in MOVES.items():
            nx, ny = x + dx, y + dy

            if (nx, ny) not in walkable and (nx, ny) not in info['goal_map']:
                # Player blocked - modifiers do NOT step
                continue

            # Step moving modifiers BEFORE checking player move effects
            # (in the real engine, wsoslqeku.step() happens before txnfzvzetn)
            new_mod_states = mod_states
            if has_moving_mods:
                new_mod_list = []
                for i, mm in enumerate(moving_mods):
                    mx, my, md = mod_states[i]
                    nmx, nmy, nmd = mm.step(mx, my, md)
                    new_mod_list.append((nmx, nmy, nmd))
                new_mod_states = tuple(new_mod_list)

            # Get dynamic modifier positions AFTER stepping
            if has_moving_mods:
                dyn_shape, dyn_color, dyn_rot = get_moving_modifier_grid_effects(
                    moving_mods, new_mod_states)
            else:
                dyn_shape, dyn_color, dyn_rot = set(), set(), set()

            new_shape = shape
            new_col = col_idx
            new_rot = rot_idx
            new_goals = goals_mask
            new_refills = refills_mask
            refill_happened = False
            blocked = False

            # Apply modifiers at initial destination
            new_shape, new_col, new_rot, new_goals, new_refills, rh, blocked = \
                apply_modifiers((nx, ny), new_shape, new_col, new_rot, new_goals, new_refills,
                               info, goal_shapes, goal_colors, goal_rots,
                               dyn_shape, dyn_color, dyn_rot)
            if rh:
                refill_happened = True

            if blocked:
                # Player blocked at goal - modifiers undo (revert to old state)
                continue

            # Check pushable wall
            final_x, final_y = nx, ny
            if (nx, ny) in pushable_map:
                final_x, final_y = pushable_map[(nx, ny)]
                new_shape, new_col, new_rot, new_goals, new_refills, rh, blocked = \
                    apply_modifiers((final_x, final_y), new_shape, new_col, new_rot,
                                   new_goals, new_refills, info, goal_shapes, goal_colors,
                                   goal_rots, dyn_shape, dyn_color, dyn_rot)
                if rh:
                    refill_happened = True
                if blocked:
                    continue

            # Steps management
            new_steps = steps - steps_decrement
            if refill_happened:
                new_steps = step_counter
            if new_steps < 0:
                continue

            new_actions = actions + [action_id]

            # Win check
            if new_goals == all_goals_mask:
                if best_solution is None or len(new_actions) < len(best_solution):
                    best_solution = new_actions
                    print(f"  BFS L{level_num}: Solution len={len(new_actions)} at iter={iterations}")
                continue

            new_state = (final_x, final_y, new_shape, new_col, new_rot, new_goals, new_refills, new_mod_states)

            if new_state in visited and visited[new_state] >= new_steps:
                continue
            visited[new_state] = new_steps

            queue.append((new_state, new_steps, new_actions))

    print(f"  BFS L{level_num}: Explored {iterations} states, visited={len(visited)}")
    return best_solution


def engine_bfs(arc_inst, prev_solutions, level_num, max_depth=55):
    """BFS using actual game engine for simulation.

    Optimized: replay only current level actions from saved checkpoint.
    """
    nonlocal_env = [None]
    nonlocal_game = [None]

    def replay_to_level():
        """Recreate env and replay to the start of current level."""
        new_env = arc_inst.make('ls20')
        obs = new_env.reset()
        new_game = new_env._game
        obs = new_env.step(6)
        for lv in sorted(prev_solutions.keys()):
            for a in prev_solutions[lv]:
                obs = new_env.step(a)
                safety = 0
                while safety < 50 and (new_game.euemavvxz or new_game.ebfuxzbvn > 0 or new_game.akoadfsur > 0):
                    obs = new_env.step(0)
                    safety += 1
        nonlocal_env[0] = new_env
        nonlocal_game[0] = new_game
        return obs

    def execute_actions(actions):
        """Replay to level start, then execute actions with animation handling."""
        obs = replay_to_level()
        e = nonlocal_env[0]
        g = nonlocal_game[0]
        init_completed = obs.levels_completed
        for a in actions:
            obs = e.step(a)
            safety = 0
            while safety < 100 and (g.euemavvxz or g.ebfuxzbvn > 0 or g.akoadfsur > 0):
                obs = e.step(0)
                safety += 1
            if obs.state.name != "NOT_FINISHED":
                return obs, None, obs.levels_completed > init_completed

        p = g.current_level.get_sprites_by_tag("sfqyzhzkij")[0]
        steps = g._step_counter_ui.current_steps
        goals_rem = tuple(sorted((s.x, s.y) for s in g.current_level.get_sprites_by_tag("rjlbuycveu")))
        refills_rem = tuple(sorted((s.x, s.y) for s in g.current_level.get_sprites_by_tag("npxgalaybz")))
        # Include moving modifier state
        mod_state = tuple((ws._sprite.x, ws._sprite.y, ws._dir) for ws in g.wsoslqeku)
        state = (p.x, p.y, g.fwckfzsyc, g.hiaauhahz, g.cklxociuu, goals_rem, refills_rem, steps, mod_state)

        return obs, state, obs.levels_completed > init_completed

    obs, init_state, _ = execute_actions([])
    print(f"  Engine init: state={init_state}, completed={obs.levels_completed}")
    if init_state is None:
        return None

    visited = {init_state}
    queue = deque()
    queue.append([])

    iterations = 0

    while queue:
        actions = queue.popleft()
        iterations += 1

        if iterations % 2000 == 0:
            print(f"  Engine BFS L{level_num}: {iterations} states, q={len(queue)}, depth={len(actions)}")

        if iterations > 100000:
            break

        if len(actions) >= max_depth:
            continue

        for action_id in [1, 2, 3, 4]:
            new_actions = actions + [action_id]
            obs, new_state, solved = execute_actions(new_actions)

            if solved:
                print(f"  Engine BFS L{level_num}: Solution len={len(new_actions)} at iter={iterations}")
                return new_actions

            if new_state is None:
                continue
            if obs.state.name != "NOT_FINISHED":
                continue
            if new_state in visited:
                continue
            visited.add(new_state)

            queue.append(new_actions)

    print(f"  Engine BFS L{level_num}: Explored {iterations} states, no solution")
    return None


LEVEL_DATA = {
    1: {
        'start_shape': 5, 'start_color': 9, 'start_rotation': 270,
        'goal_shapes': [5], 'goal_colors': [9], 'goal_rotations': [0],
        'step_counter': 42, 'steps_decrement': 1,
    },
    2: {
        'start_shape': 5, 'start_color': 9, 'start_rotation': 0,
        'goal_shapes': [5], 'goal_colors': [9], 'goal_rotations': [270],
        'step_counter': 42, 'steps_decrement': 2,
    },
    3: {
        'start_shape': 5, 'start_color': 12, 'start_rotation': 0,
        'goal_shapes': [5], 'goal_colors': [9], 'goal_rotations': [180],
        'step_counter': 42, 'steps_decrement': 2,
    },
    4: {
        'start_shape': 4, 'start_color': 14, 'start_rotation': 0,
        'goal_shapes': [5], 'goal_colors': [9], 'goal_rotations': [0],
        'step_counter': 42, 'steps_decrement': 1,
    },
    5: {
        'start_shape': 4, 'start_color': 12, 'start_rotation': 0,
        'goal_shapes': [0], 'goal_colors': [8], 'goal_rotations': [180],
        'step_counter': 42, 'steps_decrement': 2,
    },
    6: {
        'start_shape': 0, 'start_color': 14, 'start_rotation': 0,
        'goal_shapes': [5, 0], 'goal_colors': [9, 8], 'goal_rotations': [90, 180],
        'step_counter': 42, 'steps_decrement': 1,
    },
    7: {
        'start_shape': 1, 'start_color': 12, 'start_rotation': 0,
        'goal_shapes': [0], 'goal_colors': [8], 'goal_rotations': [180],
        'step_counter': 42, 'steps_decrement': 2,
    },
}


def execute_and_verify(env, game, level_solutions, level_num, solution):
    """Execute solution via reset+replay, verify it works."""
    obs = env.reset()
    obs = env.step(6)
    for lv in sorted(level_solutions.keys()):
        for a in level_solutions[lv]:
            obs = env.step(a)

    init_completed = obs.levels_completed
    for a in solution:
        obs = env.step(a)
        safety = 0
        while safety < 100 and (game.euemavvxz or game.ebfuxzbvn > 0 or game.akoadfsur > 0):
            obs = env.step(0)
            safety += 1
        if obs.state.name != "NOT_FINISHED":
            break

    return obs, obs.levels_completed > init_completed


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('ls20')
    obs = env.reset()
    game = env._game

    print(f"ls20: {obs.win_levels} levels")
    obs = env.step(6)

    total_solved = 0
    level_solutions = {}

    for level_num in range(1, 8):
        if obs.state.name != "NOT_FINISHED":
            break

        print(f"\n--- Level {level_num} ---")

        info = extract_level_info(game)
        ld = LEVEL_DATA[level_num]

        print(f"  Start: {info['start']}")
        print(f"  Goals: {info['goals']}")
        print(f"  Walkable: {len(info['walkable'])}")
        print(f"  Pushable: {len(info['pushable_map'])} entries")
        print(f"  Moving modifiers: {len(info['moving_modifiers'])}")
        for i, mm in enumerate(info['moving_modifiers']):
            print(f"    MM{i}: type={mm.mod_type}, start=({mm.start_x},{mm.start_y}), bnd=({mm.bnd_x},{mm.bnd_y},{mm.bnd_w}x{mm.bnd_h})")
        print(f"  Need: shape {ld['start_shape']}->{ld['goal_shapes']}, color {ld['start_color']}->{ld['goal_colors']}, rot {ld['start_rotation']}->{ld['goal_rotations']}")

        solution = bfs_solve_level(level_num, info, ld)

        if solution is None:
            print(f"  Level {level_num}: Pure BFS NO SOLUTION, trying engine BFS...")
            solution = engine_bfs(arc_inst, level_solutions, level_num, max_depth=55)
            if solution:
                level_solutions[level_num] = solution
            else:
                print(f"  ENGINE BFS ALSO FAILED")
                break
        else:
            print(f"  BFS solution len={len(solution)}, verifying...")
            obs, verified = execute_and_verify(env, game, level_solutions, level_num, solution)

            if verified:
                print(f"  VERIFIED!")
                level_solutions[level_num] = solution
            else:
                print(f"  VERIFICATION FAILED, trying engine-based BFS...")
                solution = engine_bfs(arc_inst, level_solutions, level_num, max_depth=55)
                if solution:
                    level_solutions[level_num] = solution
                else:
                    print(f"  ENGINE BFS ALSO FAILED")
                    break

        # Ensure clean state - fast replay
        obs = env.reset()
        obs = env.step(6)
        for lv in sorted(level_solutions.keys()):
            for a in level_solutions[lv]:
                obs = env.step(a)

        print(f"  completed={obs.levels_completed}, state={obs.state.name}")
        total_solved = obs.levels_completed

        if obs.state.name == "WIN":
            break

    if obs.state.name == "WIN":
        print(f"\nls20 RESULT: 7/7 (WIN)")
    else:
        print(f"\nls20 RESULT: {total_solved}/7")

    print(f"\nGAME_ID: ls20")
    print(f"LEVELS_SOLVED: {total_solved}")
    print(f"TOTAL_LEVELS: 7")
    print(f"MECHANICS: Grid puzzle with shape/color/rotation matching. Moving modifiers change position each step. Pushable walls teleport player. Fog in L7 (rendering only).")
    print(f"KEY_LESSONS: Moving modifiers (dboxixicic) require modifier position+direction in BFS state. Modifier movement undone when player is blocked. Boundary sprites define modifier paths via pixel validation. Pure sim BFS 500x faster than engine replay.")

    return total_solved


if __name__ == "__main__":
    solve()
