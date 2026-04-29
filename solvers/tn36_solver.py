#!/usr/bin/env python3
"""
tn36 solver — programming puzzle game.

Game mechanics:
- Two panels: LEFT (reference, reooao tagged) and RIGHT (editable)
- RIGHT panel has a bltjrl block that must reach a target position/rotation/scale/color
- Each row of buttons encodes an opcode (bit pattern)
- Clicking sucqgk executes the program
- Opcodes move/rotate/scale/recolor the block
- Timer bar decreases with each click -> loss if exhausted
- Checkpoints (chrccc) save block position; after failed execution, block resets to last checkpoint
- Multi-execution: for levels where direct BFS fails, use checkpoints as intermediate waypoints

Opcode table (value -> action):
  0:  no-op              1:  move left  (-4, 0)
  2:  move right (+4, 0)  3:  move down  (0, +4)
  5:  rotate +90          6:  rotate -90
  7:  rotate 180          8:  scale +1
  9:  scale -1           10:  move right*2 (+8, 0)
 12:  move left*2 (-8, 0) 14:  recolor to 9
 15:  recolor to 8        16:  rotate 270
 33:  move up   (0, -4)   34:  move left (-4, 0)
 63:  recolor to 15
"""

import arc_agi
from collections import deque
from universal_harness import grid_to_display, get_clickables

CSPOIQWER = 4

# Opcode effects: (dx, dy, drot, dscale, new_color_or_None)
OPCODE_EFFECTS = {
    0:  (0, 0, 0, 0, None),
    1:  (-CSPOIQWER, 0, 0, 0, None),
    2:  (CSPOIQWER, 0, 0, 0, None),
    3:  (0, CSPOIQWER, 0, 0, None),
    5:  (0, 0, 90, 0, None),
    6:  (0, 0, -90, 0, None),
    7:  (0, 0, 180, 0, None),
    8:  (0, 0, 0, 1, None),
    9:  (0, 0, 0, -1, None),
    10: (CSPOIQWER*2, 0, 0, 0, None),
    11: (CSPOIQWER*2, 0, 0, 0, None),
    12: (-CSPOIQWER*2, 0, 0, 0, None),
    13: (-CSPOIQWER*2, 0, 0, 0, None),
    14: (0, 0, 0, 0, 9),
    15: (0, 0, 0, 0, 8),
    16: (0, 0, 270, 0, None),
    33: (0, -CSPOIQWER, 0, 0, None),
    34: (-CSPOIQWER, 0, 0, 0, None),
    63: (0, 0, 0, 0, 15),
}


def build_wall_collision_fn(game):
    """Build a collision check function using the actual game engine's collides_with."""
    gobj = game.fdksqlmpki
    right = gobj.bzirenxmrg
    bltjrl_sprite = right.htntnzkbzu.axbjgpzkyi
    wall_sprites = [w.axbjgpzkyi for w in right.bizgpiltwm]

    if not wall_sprites:
        return lambda x, y, scale: False, lambda: None

    orig_x = bltjrl_sprite.x
    orig_y = bltjrl_sprite.y
    orig_scale = bltjrl_sprite.scale

    cache = {}

    def check_blocked(x, y, scale):
        key = (x, y, scale)
        if key in cache:
            return cache[key]
        bltjrl_sprite.set_position(x, y)
        bltjrl_sprite.set_scale(scale)
        blocked = False
        for ws in wall_sprites:
            if ws.collides_with(bltjrl_sprite):
                blocked = True
                break
        cache[key] = blocked
        return blocked

    def restore():
        bltjrl_sprite.set_position(orig_x, orig_y)
        bltjrl_sprite.set_scale(orig_scale)

    return check_blocked, restore


def build_hazard_collision_fn(game):
    """Build hazard collision check using the game engine.

    Hazards have two collision modes:
    - When invisible: use linked laycmuofkkgm sprite for collision
    - When visible: use own laycmuommm sprite for collision

    Returns: check_hazard(x, y, scale, hazards_visible) -> bool, restore_fn
    """
    gobj = game.fdksqlmpki
    right = gobj.bzirenxmrg
    bltjrl_sprite = right.htntnzkbzu.axbjgpzkyi
    hazards = right.ekdwmirldx

    if not hazards:
        return lambda x, y, scale, hv: False, lambda: None

    orig_x = bltjrl_sprite.x
    orig_y = bltjrl_sprite.y
    orig_scale = bltjrl_sprite.scale

    # Collect both body and sensor sprites for each hazard
    hazard_info = []
    for h in hazards:
        body_sprite = h.axbjgpzkyi  # laycmuommm (visible collision)
        sensor_sprite = h.olbuwgbgyz  # laycmuofkkgm (invisible collision)
        hazard_info.append((body_sprite, sensor_sprite))

    cache = {}

    def check_hazard(x, y, scale, hazards_visible):
        key = (x, y, scale, hazards_visible)
        if key in cache:
            return cache[key]
        bltjrl_sprite.set_position(x, y)
        bltjrl_sprite.set_scale(scale)
        hit = False
        for body_sprite, sensor_sprite in hazard_info:
            if hazards_visible:
                if body_sprite.collides_with(bltjrl_sprite):
                    hit = True
                    break
            else:
                if sensor_sprite.collides_with(bltjrl_sprite):
                    hit = True
                    break
        cache[key] = hit
        return hit

    def restore():
        bltjrl_sprite.set_position(orig_x, orig_y)
        bltjrl_sprite.set_scale(orig_scale)

    return check_hazard, restore


def sim_step(state, op, check_blocked, check_hazard=None, step_idx=0, hazards_visible=False):
    """Simulate one opcode step.

    Returns (new_state, alive) where alive=False if block hit a hazard.
    """
    x, y, rot, scale, color = state
    effect = OPCODE_EFFECTS.get(op)
    if effect is None:
        return state, True
    dx, dy, drot, dscale, new_color = effect

    if dx != 0 or dy != 0:
        nx, ny = x + dx, y + dy
        if not check_blocked(nx, ny, scale):
            x, y = nx, ny
            # Check hazard collision after movement
            if check_hazard and check_hazard(x, y, scale, hazards_visible):
                return (x, y, rot, scale, color), False

    if drot != 0:
        rot = (rot + drot) % 360

    if dscale != 0:
        ns = scale + dscale
        if ns >= 1 and not check_blocked(x, y, ns):
            scale = ns
            # Check hazard after scale change
            if check_hazard and check_hazard(x, y, scale, hazards_visible):
                return (x, y, rot, scale, color), False

    if new_color is not None:
        color = new_color

    return (x, y, rot, scale, color), True


def bfs_find_program(n_rows, target_state, start_state, check_blocked, max_opcode=63,
                     check_hazard=None, initial_hazard_visible=False):
    """BFS using engine-based collision checking with hazard awareness.

    Hazards toggle visibility when step_idx % 3 == 2 (and step_idx < n_rows-1).
    """
    if start_state == target_state:
        return [0] * n_rows

    useful_opcodes = [op for op in sorted(OPCODE_EFFECTS.keys()) if op <= max_opcode]
    has_hazards = check_hazard is not None

    # State includes hazard visibility if hazards exist
    if has_hazards:
        current = {(start_state, initial_hazard_visible): []}
    else:
        current = {start_state: []}

    for row_idx in range(n_rows):
        nxt = {}
        is_last = (row_idx == n_rows - 1)

        for full_state, program in current.items():
            if has_hazards:
                state, hv = full_state
            else:
                state = full_state
                hv = False

            for op in useful_opcodes:
                ns, alive = sim_step(state, op, check_blocked, check_hazard, row_idx, hv)
                if not alive:
                    continue  # Block killed by hazard

                # Check hazard toggle: after executing opcode, if step_idx % 3 == 2
                # and not last step, hazards toggle
                new_hv = hv
                if has_hazards and not is_last and row_idx % 3 == 2:
                    new_hv = not hv
                    # After toggle, if hazard is now visible and collides, block dies
                    if new_hv and check_hazard(ns[0], ns[1], ns[3], new_hv):
                        continue  # Block killed by newly visible hazard

                np_ = program + [op]

                if has_hazards:
                    nxt_key = (ns, new_hv)
                else:
                    nxt_key = ns

                if is_last:
                    if ns == target_state:
                        return np_
                else:
                    if nxt_key not in nxt:
                        nxt[nxt_key] = np_

        if not nxt and not is_last:
            print(f"    BFS: no states at step {row_idx}")
            return None
        if not is_last:
            current = nxt
            if row_idx % 2 == 0:
                print(f"    BFS step {row_idx}: {len(current)} states")

    print(f"    BFS: no solution ({len(current)} final states)")
    return None


def bfs_to_goals(n_rows, start_state, goal_positions, check_blocked, max_opcode=63,
                 check_hazard=None, initial_hazard_visible=False):
    """BFS for n_rows steps reaching any of goal_positions (x,y matching).
    Returns (program, end_state) or (None, None)."""
    useful_opcodes = [op for op in sorted(OPCODE_EFFECTS.keys()) if op <= max_opcode]
    has_hazards = check_hazard is not None

    if has_hazards:
        current = {(start_state, initial_hazard_visible): []}
    else:
        current = {start_state: []}

    for row_idx in range(n_rows):
        nxt = {}
        is_last = (row_idx == n_rows - 1)

        for full_state, program in current.items():
            if has_hazards:
                state, hv = full_state
            else:
                state = full_state
                hv = False

            for op in useful_opcodes:
                ns, alive = sim_step(state, op, check_blocked, check_hazard, row_idx, hv)
                if not alive:
                    continue

                new_hv = hv
                if has_hazards and not is_last and row_idx % 3 == 2:
                    new_hv = not hv
                    if new_hv and check_hazard(ns[0], ns[1], ns[3], new_hv):
                        continue

                np_ = program + [op]

                if has_hazards:
                    nxt_key = (ns, new_hv)
                else:
                    nxt_key = ns

                if is_last:
                    if (ns[0], ns[1]) in goal_positions:
                        return np_, ns
                else:
                    if nxt_key not in nxt:
                        nxt[nxt_key] = np_

        if not nxt and not is_last:
            return None, None
        if not is_last:
            current = nxt

    return None, None


def find_multi_exec_plan(n_rows, start_state, target_state, checkpoints, check_blocked,
                         max_opcode=63, check_hazard=None, initial_hazard_visible=False):
    """Find multi-execution plan using checkpoints as waypoints.
    Returns list of (program, end_state) tuples, or None."""

    # Try direct first
    program = bfs_find_program(n_rows, target_state, start_state, check_blocked, max_opcode,
                                check_hazard=check_hazard, initial_hazard_visible=initial_hazard_visible)
    if program:
        return [(program, target_state)]

    target_pos = (target_state[0], target_state[1])
    checkpoint_positions = {}
    for cp in checkpoints:
        checkpoint_positions[(cp[0], cp[1])] = cp

    # Try 2-execution: start -> checkpoint -> target
    # After execution, hazards toggle back (they toggle at end of execution too)
    # Actually: at end of execution (olsmwehruj line 2383-2384), hazards toggle again
    # So hazard state resets between executions
    for cp_pos in checkpoint_positions:
        prog1, end1 = bfs_to_goals(n_rows, start_state, {cp_pos}, check_blocked, max_opcode,
                                    check_hazard=check_hazard, initial_hazard_visible=initial_hazard_visible)
        if prog1 is None:
            continue
        # After execution ends, hazards toggle again (olrpupaury path), reset to initial
        prog2 = bfs_find_program(n_rows, target_state, end1, check_blocked, max_opcode,
                                  check_hazard=check_hazard, initial_hazard_visible=initial_hazard_visible)
        if prog2:
            print(f"    2-exec plan: -> {cp_pos} -> target")
            return [(prog1, end1), (prog2, target_state)]

    # Try 3-execution: start -> cp1 -> cp2 -> target
    for cp1_pos in checkpoint_positions:
        prog1, end1 = bfs_to_goals(n_rows, start_state, {cp1_pos}, check_blocked, max_opcode,
                                    check_hazard=check_hazard, initial_hazard_visible=initial_hazard_visible)
        if prog1 is None:
            continue
        for cp2_pos in checkpoint_positions:
            if cp2_pos == cp1_pos:
                continue
            prog2, end2 = bfs_to_goals(n_rows, end1, {cp2_pos}, check_blocked, max_opcode,
                                        check_hazard=check_hazard, initial_hazard_visible=initial_hazard_visible)
            if prog2 is None:
                continue
            prog3 = bfs_find_program(n_rows, target_state, end2, check_blocked, max_opcode,
                                      check_hazard=check_hazard, initial_hazard_visible=initial_hazard_visible)
            if prog3:
                print(f"    3-exec plan: -> {cp1_pos} -> {cp2_pos} -> target")
                return [(prog1, end1), (prog2, end2), (prog3, target_state)]

    return None


def extract_level_info(game):
    """Extract puzzle parameters from the current game state."""
    gobj = game.fdksqlmpki
    right = gobj.bzirenxmrg
    cam = game.camera

    bltjrl = right.htntnzkbzu
    target = right.aqszntqeae
    dp = right.vupcwzjtxu

    info = {
        'start': (bltjrl.x, bltjrl.y, bltjrl.rotation, bltjrl.scale, bltjrl.sjmtdfxdrc),
        'target': (target.x, target.y, target.rotation, target.scale, target.sjmtdfxdrc) if target else None,
        'n_rows': len(dp.rzmeklhluf),
        'n_bits': len(dp.rzmeklhluf[0].sonocxtjtj) if dp.rzmeklhluf else 0,
        'current_values': dp.vkuvtkaerv,
        'initial_values': list(dp.dzhrsuxbcw),
        'walls': [],
        'hazards': [],
    }

    for w in right.bizgpiltwm:
        info['walls'].append((w.x, w.y, w.width, w.height))

    for h in right.ekdwmirldx:
        info['hazards'].append((h.x, h.y, h.width, h.height, h.is_visible))

    info['bit_coords'] = []
    for i, row in enumerate(dp.rzmeklhluf):
        row_coords = []
        for j, bit in enumerate(row.sonocxtjtj):
            dx, dy = grid_to_display(bit.x + bit.width // 2, bit.y + bit.height // 2, cam)
            row_coords.append((dx, dy, bit.yliktcpsfp))
        info['bit_coords'].append(row_coords)

    for c in get_clickables(game):
        if 'sucqgk' in c['name']:
            info['sucqgk'] = c['display']

    info['tabs'] = []
    for c in get_clickables(game):
        if 'tozzsf' in c['name']:
            info['tabs'].append(c['display'])

    timer = game.lmkazecqdh
    info['clicks_remaining'] = timer.axbjgpzkyi.x + timer.axbjgpzkyi.width - timer._background.x

    return info


def get_checkpoints(game):
    """Get checkpoint positions from game state."""
    gobj = game.fdksqlmpki
    right = gobj.bzirenxmrg
    checkpoints = []
    for c in right.wgzwawbgew:
        checkpoints.append((c.x, c.y, c.scale))
    return checkpoints


def compute_clicks_for_program(target_opcodes, info):
    """Given target opcodes, compute the display clicks needed to set them."""
    clicks = []
    bit_coords = info['bit_coords']
    current_values = info['current_values']

    for row_idx, target_op in enumerate(target_opcodes):
        current_val = current_values[row_idx]
        n_bits = len(bit_coords[row_idx])

        for bit_idx in range(n_bits):
            current_bit = bool(current_val & (1 << bit_idx))
            target_bit = bool(target_op & (1 << bit_idx))

            if current_bit != target_bit:
                dx, dy, _ = bit_coords[row_idx][bit_idx]
                clicks.append((dx, dy))

    clicks.append(info['sucqgk'])
    return clicks


def execute_clicks(env, clicks, obs):
    """Execute a list of clicks and return updated obs."""
    for x, y in clicks:
        obs = env.step(6, data={"x": x, "y": y})
    return obs


def wait_for_animation(env, obs, max_attempts=50):
    """Wait for animation to complete (busy state to clear)."""
    game = env._game
    attempts = 0
    while game.fdksqlmpki.deredwcqze and obs.state.name == "NOT_FINISHED" and attempts < max_attempts:
        obs = env.step(6, data={"x": 0, "y": 0})
        attempts += 1
    return obs


def solve_level(game, env, obs, level_solutions, level):
    """Solve a level using engine-based collision BFS."""
    info = extract_level_info(game)

    if info['target'] is None:
        print(f"  L{level}: No target, skipping")
        return None

    print(f"  L{level}: {info['n_rows']} rows x {info['n_bits']} bits")
    print(f"    Start: {info['start']}")
    print(f"    Target: {info['target']}")
    print(f"    Walls: {len(info['walls'])}")
    print(f"    Clicks remaining: {info['clicks_remaining']}")

    start_state = tuple(int(v) for v in info['start'])
    target_state = tuple(int(v) for v in info['target'])
    max_opcode = (1 << info['n_bits']) - 1

    check_blocked, restore_wall = build_wall_collision_fn(game)

    # Build hazard collision if hazards exist
    check_hazard, restore_hazard = build_hazard_collision_fn(game)
    has_hazards = bool(info['hazards'])
    # Determine initial hazard visibility
    initial_hv = False
    if has_hazards:
        # Check if any hazard is initially visible
        gobj = game.fdksqlmpki
        right = gobj.bzirenxmrg
        initial_hv = any(h.is_visible for h in right.ekdwmirldx)

    if has_hazards:
        print(f"    Hazards: {len(info['hazards'])}, initially_visible={initial_hv}")

    # Try direct BFS first
    program = bfs_find_program(
        info['n_rows'], target_state, start_state,
        check_blocked, max_opcode=max_opcode,
        check_hazard=check_hazard if has_hazards else None,
        initial_hazard_visible=initial_hv
    )

    restore_wall()
    restore_hazard()

    if program is not None:
        print(f"    Found program: {program}")
        clicks = compute_clicks_for_program(program, info)
        print(f"    Clicks needed: {len(clicks)} (budget: {info['clicks_remaining']})")
        return clicks

    # Direct BFS failed — try multi-execution with checkpoints
    print(f"    Direct BFS failed, trying multi-execution...")
    checkpoint_data = get_checkpoints(game)
    if not checkpoint_data:
        print(f"    No checkpoints available!")
        return None

    checkpoints = []
    for cx, cy, cs in checkpoint_data:
        checkpoints.append((cx, cy))
    print(f"    Checkpoints: {checkpoints}")

    check_blocked2, restore2 = build_wall_collision_fn(game)
    check_hazard2, restore_h2 = build_hazard_collision_fn(game)
    plan = find_multi_exec_plan(
        info['n_rows'], start_state, target_state, checkpoints,
        check_blocked2, max_opcode=max_opcode,
        check_hazard=check_hazard2 if has_hazards else None,
        initial_hazard_visible=initial_hv
    )
    restore2()
    restore_h2()

    if plan is None:
        print(f"    Multi-exec plan failed!")
        return None

    print(f"    Multi-exec plan: {len(plan)} executions")
    return ('multi', plan, info)


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('tn36')
    obs = env.reset()
    obs = env.step(6, data={"x": 0, "y": 0})
    game = env._game

    print(f"tn36: {obs.win_levels} levels")
    level_solutions = {}

    for level in range(1, obs.win_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        game = env._game
        print(f"\nL{level} (completed={obs.levels_completed})")

        result = solve_level(game, env, obs, level_solutions, level)

        if result is None:
            print(f"  L{level} FAILED")
            break

        if isinstance(result, tuple) and result[0] == 'multi':
            # Multi-execution plan
            _, plan, info = result
            print(f"  Executing multi-exec plan ({len(plan)} runs)...")

            for exec_idx, (program, end_state) in enumerate(plan):
                # Re-read game state for current bit values
                game = env._game
                info = extract_level_info(game)

                print(f"    Exec {exec_idx+1}: program={program}")
                clicks = compute_clicks_for_program(program, info)
                print(f"      Clicks: {len(clicks)} (budget: {info['clicks_remaining']})")

                # Execute the bit clicks and sucqgk
                obs = execute_clicks(env, clicks, obs)

                # Wait for program animation to complete
                obs = wait_for_animation(env, obs)

                if obs.levels_completed >= level:
                    print(f"    Level completed after exec {exec_idx+1}!")
                    break

                if obs.state.name != "NOT_FINISHED":
                    print(f"    Game state: {obs.state.name}")
                    break

                # Small extra wait to ensure state settles
                for _ in range(5):
                    obs = env.step(6, data={"x": 0, "y": 0})

        else:
            # Single execution
            clicks = result
            for x, y in clicks:
                obs = env.step(6, data={"x": x, "y": y})
                if obs.levels_completed >= level:
                    break

            # Wait for animation
            attempts = 0
            while obs.levels_completed < level and obs.state.name == "NOT_FINISHED" and attempts < 30:
                obs = env.step(6, data={"x": 0, "y": 0})
                attempts += 1

        if obs.levels_completed >= level:
            print(f"  L{level} SOLVED!")
            level_solutions[level] = True
        else:
            print(f"  L{level} execution FAILED (completed={obs.levels_completed})")
            break

    total = obs.levels_completed
    if obs.state.name == "WIN":
        total = obs.win_levels

    print(f"\n{'='*40}")
    print(f"tn36 RESULT: {total}/{obs.win_levels}")
    print(f"{'='*40}")
    return total


if __name__ == "__main__":
    solve()
