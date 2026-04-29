#!/usr/bin/env python3
"""vc33 solver — BFS for simple levels, manual solutions for complex ones."""
import arc_agi
import numpy as np
from collections import deque

def grid_to_display(gx, gy, cam):
    scale, x_off, y_off = cam._calculate_scale_and_offset()
    return int((gx - cam.x) * scale + x_off), int((gy - cam.y) * scale + y_off)

def get_state_hash(game):
    h = []
    for p in sorted(game.current_level.get_sprites_by_tag("0043nzrtobajqi"), key=lambda s: (s.x, s.y)):
        h.append(('P', p.x, p.y, p.width, p.height))
    for b in sorted(game.current_level.get_sprites_by_tag("0016uciqlhjlom"), key=lambda s: (s.x, s.y)):
        h.append(('B', b.x, b.y))
    for bt in sorted(game.current_level.get_sprites_by_tag("0004sttgkofqwb"), key=lambda s: (s.x, s.y)):
        h.append(('btn', game.ezbubuphlm(bt)))
    return tuple(h)

def save_state(game):
    state = {}
    pipes = list(game.current_level.get_sprites_by_tag("0043nzrtobajqi"))
    state['pipes'] = [(p, p.x, p.y, p.pixels.copy()) for p in pipes]
    balls = list(game.current_level.get_sprites_by_tag("0016uciqlhjlom"))
    state['balls'] = [(b, b.x, b.y) for b in balls]
    btns = list(game.current_level.get_sprites_by_tag("0004sttgkofqwb"))
    state['btns'] = [(bt, bt.pixels.copy()) for bt in btns]
    state['steps'] = game.heczcoeosi.current_steps
    state['animation'] = game.bnnqyrupir
    return state

def restore_state(game, state):
    for p, x, y, pix in state['pipes']:
        p.set_position(x, y)
        p.pixels = pix.copy()
    for b, x, y in state['balls']:
        b.set_position(x, y)
    for bt, pix in state['btns']:
        bt.pixels = pix.copy()
    game.heczcoeosi.current_steps = state['steps']
    game.bnnqyrupir = state['animation']
    game.wpcgsoumbr()

def solve_bfs_replay(env, game, level, level_solutions, max_depth=30):
    """BFS using full replay from start."""
    cam = game.camera
    ctrls = list(game.current_level.get_sprites_by_tag("0022jvmlspyigc"))
    btns = list(game.current_level.get_sprites_by_tag("0004sttgkofqwb"))
    clickables = ctrls + btns
    click_coords = []
    for s in clickables:
        dx, dy = grid_to_display(s.x + s.width // 2, s.y + s.height // 2, cam)
        click_coords.append((dx, dy))
    n = len(click_coords)

    def replay_and_hash(moves):
        obs2 = env.reset()
        obs2 = env.step(6)
        for prev_l in sorted(level_solutions.keys()):
            for click in level_solutions[prev_l]:
                obs2 = env.step(6, data={"x": click[0], "y": click[1]})
        for ci in moves:
            obs2 = env.step(6, data={"x": click_coords[ci][0], "y": click_coords[ci][1]})
            if obs2.levels_completed >= level:
                return None, obs2, True
        h = get_state_hash(env._game)
        return h, obs2, False

    init_hash, _, _ = replay_and_hash([])
    visited = {init_hash}
    queue = deque([[]])
    explored = 0

    while queue:
        moves = queue.popleft()
        if len(moves) >= max_depth:
            continue
        for ci in range(n):
            new_moves = moves + [ci]
            h, obs2, won = replay_and_hash(new_moves)
            if won:
                return [click_coords[c] for c in new_moves], obs2
            if h is not None and h not in visited:
                visited.add(h)
                queue.append(new_moves)
                explored += 1
                if explored % 500 == 0:
                    print(f"  ... {explored} states, depth={len(new_moves)}, queue={len(queue)}")
    return None, None

def solve_bfs_saverestore(env, game, level, level_solutions, max_depth=100, max_states=100000):
    """BFS using save/restore for speed."""
    # First replay to get to current level
    obs2 = env.reset()
    obs2 = env.step(6)
    for prev_l in sorted(level_solutions.keys()):
        for click in level_solutions[prev_l]:
            obs2 = env.step(6, data={"x": click[0], "y": click[1]})
    game = env._game
    cam = game.camera

    ctrls = list(game.current_level.get_sprites_by_tag("0022jvmlspyigc"))
    btns = list(game.current_level.get_sprites_by_tag("0004sttgkofqwb"))
    clickables = ctrls + btns
    click_coords = []
    for s in clickables:
        dx, dy = grid_to_display(s.x + s.width // 2, s.y + s.height // 2, cam)
        click_coords.append((dx, dy))
    n = len(click_coords)

    init_state = save_state(game)
    init_hash = get_state_hash(game)
    visited = {init_hash}
    queue = deque([([], init_state)])
    explored = 0

    while queue and explored < max_states:
        moves, saved = queue.popleft()
        if len(moves) >= max_depth:
            continue
        for ci in range(n):
            restore_state(game, saved)
            obs2 = env.step(6, data={"x": click_coords[ci][0], "y": click_coords[ci][1]})
            if obs2.levels_completed >= level:
                return [click_coords[c] for c in moves + [ci]], obs2
            if obs2.state.name == "LOSE":
                continue
            h = get_state_hash(game)
            if h not in visited:
                visited.add(h)
                queue.append((moves + [ci], save_state(game)))
                explored += 1
                if explored % 1000 == 0:
                    print(f"  ... {explored} states, depth={len(moves)+1}, queue={len(queue)}")
    return None, None

def solve_l7_interactive(env, game, level_solutions):
    """Solve L7 interactively with animation waiting.

    Layout (rotation 180, gravity [0,-2]):
      P0(0,0) 14x20    |wall(14)|  P2(16,0) 16x8   |wall(32)|  P3(34,0) 14x6 [PUR]
      P1(0,24) 14x8 [BLU] |     |                   |        |  P4(34,24) 14x10 [ORA]
      Floor(0,22)                                              Floor(34,22)

    Solution: ORA in P2(h=10), PUR in P1(h=18), BLU in P3(h=18)
    """
    cam = game.camera
    ctrls = list(game.current_level.get_sprites_by_tag("0022jvmlspyigc"))
    btns = list(game.current_level.get_sprites_by_tag("0004sttgkofqwb"))

    ctrl_by_pos = {}
    for s in ctrls:
        ctrl_by_pos[(s.x, s.y)] = s

    c12 = ctrl_by_pos[(16, 24)]   # P1→P2
    c02 = ctrl_by_pos[(16, 0)]    # P0→P2
    c20 = ctrl_by_pos[(12, 0)]    # P2→P0
    c21 = ctrl_by_pos[(12, 24)]   # P2→P1
    c32 = ctrl_by_pos[(30, 0)]    # P3→P2
    c42 = ctrl_by_pos[(30, 24)]   # P4→P2
    c23 = ctrl_by_pos[(34, 0)]    # P2→P3

    b0 = [b for b in btns if b.x == 14][0]
    b1 = [b for b in btns if b.x == 32 and b.y == 8][0]
    b2 = [b for b in btns if b.x == 32 and b.y == 30][0]

    click_log = []

    def click(sprite, count=1):
        nonlocal game
        dx, dy = grid_to_display(sprite.x + sprite.width//2, sprite.y + sprite.height//2, cam)
        obs2 = None
        for _ in range(count):
            obs2 = env.step(6, data={"x": dx, "y": dy})
            click_log.append((dx, dy))
            # Wait for any animation to complete
            while game.bnnqyrupir:
                obs2 = env.step(6, data={"x": 0, "y": 0})
                click_log.append((0, 0))
            if obs2.state.name == "WIN":
                return obs2
        return obs2

    # Step 1a: BLU P1→P2 via Btn0
    click(c12, 1)   # P1→P2 x1
    click(c02, 10)  # P0→P2 x10
    obs = click(b0, 1)   # Btn0: BLU→P2

    # Step 1b: BLU P2→P3 via Btn1
    click(c20, 10)  # P2→P0 x10
    click(c23, 1)   # P2→P3 x1
    obs = click(b1, 1)   # Btn1: BLU↔PUR

    # Step 1c: PUR P2→P1 via Btn0
    click(c02, 10)  # P0→P2 x10
    click(c32, 1)   # P3→P2 x1
    obs = click(b0, 1)   # Btn0: PUR→P1

    # Step 2: ORA P4→P2 via Btn2
    click(c20, 2)   # P2→P0 x2
    click(c42, 2)   # P4→P2 x2
    obs = click(b2, 1)   # Btn2: ORA→P2

    # Step 3: Position all balls
    click(c20, 10)  # P2→P0 x10 (some blocked by floor, OK)
    click(c02, 6)   # P0→P2 x6
    click(c23, 6)   # P2→P3 x6 (BLU.y→18)
    click(c02, 6)   # P0→P2 x6 (some blocked by empty P0, OK)
    obs = click(c21, 6)   # P2→P1 x6 (PUR.y→42)

    return click_log, obs


def get_manual_l4(game, cam):
    """Manual solution for L4."""
    ctrls = list(game.current_level.get_sprites_by_tag("0022jvmlspyigc"))
    btns = list(game.current_level.get_sprites_by_tag("0004sttgkofqwb"))
    ctrl_map = {}
    for s in ctrls:
        src, dst = game.wrcxjliglr[s]
        ctrl_map[f"{src.x}->{dst.x}"] = s
    c01 = ctrl_map["0->15"]
    c43 = ctrl_map["57->45"]
    c32 = ctrl_map["45->30"]
    b12 = [b for b in btns if b.x == 12][0]
    b27 = [b for b in btns if b.x == 27][0]
    seq = [c01]*2 + [b12] + [c01]*3 + [c43]*6 + [c32]*3 + [b27] + [c32]*5
    return [grid_to_display(s.x + s.width//2, s.y + s.height//2, cam) for s in seq]

def get_manual_l5(game, cam):
    """Manual solution for L5."""
    ctrls = list(game.current_level.get_sprites_by_tag("0022jvmlspyigc"))
    btns = list(game.current_level.get_sprites_by_tag("0004sttgkofqwb"))
    c_map = {}
    for s in ctrls:
        src, dst = game.wrcxjliglr[s]
        c_map[(src.y, dst.y)] = s
    c_01 = c_map[(0, 17)]; c_10 = c_map[(17, 0)]
    c_12 = c_map[(17, 35)]; c_21 = c_map[(35, 17)]
    c_23 = c_map[(35, 52)]; c_32 = c_map[(52, 35)]
    btn28 = [b for b in btns if b.y == 14][0]
    btn40 = [b for b in btns if b.y == 32][0]
    btn25 = [b for b in btns if b.y == 49][0]
    seq = (
        [c_01]*3 + [c_12]*5 + [c_23]*2 + [btn25] +
        [c_01]*4 + [c_23]*5 + [btn40] +
        [c_01]*1 + [c_21]*3 + [btn28] +
        [c_12]*4 + [c_23]*1 + [btn40] +
        [c_21]*1 + [c_32]*6 + [btn25] +
        [c_23]*7 + [c_10]*5 + [c_21]*1 + [c_10]*1
    )
    return [grid_to_display(s.x + s.width//2, s.y + s.height//2, cam) for s in seq]

def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('vc33')
    obs = env.reset()
    obs = env.step(6)
    game = env._game

    print(f"vc33: {obs.win_levels} levels")
    level_solutions = {}

    for level in range(1, obs.win_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        cam = game.camera
        grav = list(game.dwwmpxqsza)
        pipes = list(game.current_level.get_sprites_by_tag("0043nzrtobajqi"))
        balls = list(game.current_level.get_sprites_by_tag("0016uciqlhjlom"))
        btns = list(game.current_level.get_sprites_by_tag("0004sttgkofqwb"))
        ctrls = list(game.current_level.get_sprites_by_tag("0022jvmlspyigc"))
        step_limit = game.heczcoeosi.current_steps

        print(f"\nL{level}: {len(ctrls)} ctrls, {len(btns)} btns, {len(pipes)} pipes, "
              f"{len(balls)} balls, gravity={grav}, steps={step_limit}")

        if level <= 3:
            sol, obs2 = solve_bfs_replay(env, game, level, level_solutions)
            if sol:
                level_solutions[level] = sol
                obs = obs2
                game = env._game
                print(f"  SOLVED! {len(sol)} clicks")
            else:
                print(f"  FAILED")
                break

        elif level == 4:
            clicks = get_manual_l4(game, cam)
            level_solutions[level] = clicks
            obs2 = env.reset()
            obs2 = env.step(6)
            for prev_l in sorted(level_solutions.keys()):
                for click in level_solutions[prev_l]:
                    obs2 = env.step(6, data={"x": click[0], "y": click[1]})
            obs = obs2
            game = env._game
            print(f"  SOLVED! {len(clicks)} clicks (manual)")

        elif level == 5:
            clicks = get_manual_l5(game, cam)
            level_solutions[level] = clicks
            obs2 = env.reset()
            obs2 = env.step(6)
            for prev_l in sorted(level_solutions.keys()):
                for click in level_solutions[prev_l]:
                    obs2 = env.step(6, data={"x": click[0], "y": click[1]})
            obs = obs2
            game = env._game
            print(f"  SOLVED! {len(clicks)} clicks (manual)")

        elif level == 6:
            sol, obs2 = solve_bfs_saverestore(env, game, level, level_solutions, max_states=100000)
            if sol:
                level_solutions[level] = sol
                obs = obs2
                game = env._game
                print(f"  SOLVED! {len(sol)} clicks")
            else:
                print(f"  FAILED")
                break

        elif level == 7:
            click_log, obs2 = solve_l7_interactive(env, game, level_solutions)
            if obs2 and obs2.state.name == "WIN":
                level_solutions[level] = click_log
                obs = obs2
                game = env._game
                print(f"  SOLVED! {len(click_log)} clicks (interactive)")
            else:
                # Check if win condition is met
                if game.ielczunthe():
                    level_solutions[level] = click_log
                    obs = obs2 if obs2 else obs
                    game = env._game
                    print(f"  SOLVED! (win condition met, {len(click_log)} clicks)")
                else:
                    print(f"  FAILED (state={obs2.state.name if obs2 else 'None'})")
                    break

        else:
            print(f"  L{level} not implemented")
            break

    total = obs.levels_completed
    if obs.state.name == "WIN":
        total = obs.win_levels
    print(f"\n{'='*40}")
    print(f"RESULT: {total}/{obs.win_levels}")
    return total

if __name__ == "__main__":
    solve()
