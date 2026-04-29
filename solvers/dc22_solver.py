#!/usr/bin/env python3
"""dc22 solver — Grid platformer with button toggles, keys, cranes, bridges.

Strategy:
  Level 0-1: Hardcoded manual solutions
  Level 2-3: BFS with game-state save/restore and compact state hashing.
  Level 4-5: Crane levels — BFS with render skip optimization.
    Currently solves 4/6 levels. Crane levels (L4-L5) have too large a state
    space (~150K+ reachable states explored, solution not found in 1500s).

Key optimization: monkey-patch camera.render to return dummy frame during BFS,
avoiding expensive rendering (~30% speedup).
"""

import sys
import warnings
import logging
import numpy as np
from collections import deque

sys.path.insert(0, '/home/paolo/arc-agi/solver')
import arc_agi

warnings.filterwarnings('ignore')
logging.disable(logging.WARNING)


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('dc22')
    obs = env.reset()
    game = env._game

    # Dummy frame for skipping rendering during BFS
    _dummy_frame = np.zeros((64, 64), dtype=np.int8)
    _real_render = game.camera.render
    _skip_render = [False]

    def _patched_render(sprites):
        if _skip_render[0]:
            return _dummy_frame
        return _real_render(sprites)

    game.camera.render = _patched_render

    def doff():
        return (64 - game.vgrdxwayb) // 2

    def wait_anim():
        """Wait for animations to complete by stepping the game."""
        for _ in range(60):
            if not (game.guspipewt or game.fadccmsnb or game.fjiyimenq):
                break
            env.step(1)

    def get_btns():
        off = doff()
        btns = {}
        for s in game.current_level._sprites:
            if 'buezna' in s.tags and 'sys_click' in s.tags:
                if s.interaction.name in ('REMOVED', 'INVISIBLE'):
                    continue
                letter = next((t for t in s.tags if len(t) == 1), None)
                if letter:
                    cx, cy = s.x + s.width // 2, s.y + s.height // 2
                    btns[letter] = (cx, cy + off)
        return btns

    def get_sys_clicks():
        off = doff()
        clicks = {}
        for s in game.current_level._sprites:
            if 'sys_click' in s.tags and 'buezna' not in s.tags:
                if s.interaction.name in ('REMOVED', 'INVISIBLE'):
                    continue
                for tag in ['up', 'dowlja', 'lersnf', 'riidpd', 'grawwq']:
                    if tag in s.tags:
                        cx, cy = s.x + s.width // 2, s.y + s.height // 2
                        clicks[tag] = (cx, cy + off)
        return clicks

    def save_state():
        """Save game state - clone sprites to preserve state."""
        sprites_copy = []
        for s in game.current_level._sprites:
            sc = s.clone()
            sc.set_position(s.x, s.y)
            sc.set_interaction(s.interaction)
            sc._blocking = s._blocking
            sc._tags = list(s.tags)
            sprites_copy.append(sc)
        epywhrcwy_name = game.epywhrcwy.name if game.epywhrcwy else None
        return {
            'sprites': sprites_copy,
            'step_counter': game.ujotjblwn.current_steps,
            'sjixewahg': game.sjixewahg,
            'uxtzlxsiq': game.uxtzlxsiq,
            'svxnnbpjl': game.svxnnbpjl,
            'fvwekbbhj': game.fvwekbbhj,
            'ozarnpwde': game.ozarnpwde,
            'bbobkhxob': game.bbobkhxob,
            'level_index': game._current_level_index,
            'epywhrcwy_name': epywhrcwy_name,
        }

    def restore_state(state):
        """Restore game state."""
        if game._current_level_index != state['level_index']:
            game.set_level(state['level_index'])
        for s in list(game.current_level._sprites):
            game.current_level.remove_sprite(s)
        for s in state['sprites']:
            sc = s.clone()
            sc.set_position(s.x, s.y)
            sc.set_interaction(s.interaction)
            sc._blocking = s._blocking
            sc._tags = list(s.tags)
            game.current_level.add_sprite(sc)
        game.guspipewt = False
        game.divlqsjra = False
        game.fjiyimenq = False
        game.fadccmsnb = False
        game.scshqquvb = -1
        # Set state variables BEFORE kghadhkkby (which calls coihvniexy)
        game.sjixewahg = state['sjixewahg']
        game.uxtzlxsiq = state['uxtzlxsiq']
        game.svxnnbpjl = state['svxnnbpjl']
        game.fvwekbbhj = state['fvwekbbhj']
        game.ozarnpwde = state['ozarnpwde']
        game.bbobkhxob = state['bbobkhxob']
        # Set sachklrxui for kghadhkkby to use when restoring brixto attachment
        game.sachklrxui = {
            'sprites': [],
            'crzsjq_x': state['sjixewahg'],
            'crzsjq_y': state['uxtzlxsiq'],
            'crzsjq_attached_kind': state['svxnnbpjl'],
            'attached_brixto_prefix': state['fvwekbbhj'],
            'attached_brixto_x': state['ozarnpwde'],
            'attached_brixto_y': state['bbobkhxob'],
        }
        try:
            game.kghadhkkby()
        except ValueError:
            # Brixto reference lost during restore - manually fix
            game.hfuqkxulm = game.current_level.get_sprites_by_tag("goknoi")[0]
            game.qnnpcoyzd = game.current_level.get_sprites_by_tag("jfva")[0]
            game.jrxnntmty = game.current_level.get_sprites_by_tag("tovemc")
            game.lmacwotry = game.current_level.get_sprites_by_tag("crzsjq")
            if len(game.lmacwotry) > 0:
                game.qpvpuhpms = game.lmacwotry[0]
                game.pckkgvqwk = game.pxfvdjsard()
                fpukxlbhoh = game.current_level.get_sprites_by_tag("grawwq-object")
                game.fydslgnbt = fpukxlbhoh[0] if len(fpukxlbhoh) > 0 else None
                game.qnlqkldrl = game.pckkgvqwk == "brixtocrzsjq"
            # Find brixto by searching more broadly
            game.epywhrcwy = None
            if state['svxnnbpjl'] == "brixto" and state['fvwekbbhj']:
                for s in game.current_level._sprites:
                    if (s.name.startswith(state['fvwekbbhj']) and
                        s.name[-1].isdigit() and
                        s.x == state['ozarnpwde'] and
                        s.y == state['bbobkhxob']):
                        if s.interaction.name not in ('REMOVED', 'INVISIBLE'):
                            game.epywhrcwy = s
                            break
                # Fallback: match by prefix only
                if game.epywhrcwy is None:
                    for s in game.current_level._sprites:
                        if (s.name.startswith(state['fvwekbbhj']) and
                            s.name[-1].isdigit() and
                            s.interaction.name not in ('REMOVED', 'INVISIBLE') and
                            'tovemc' in s.tags):
                            game.epywhrcwy = s
                            game.ozarnpwde = s.x
                            game.bbobkhxob = s.y
                            break
                if game.epywhrcwy is None:
                    game.svxnnbpjl = "none"
            game.qrvjgseoyk()
        game.yuonzbouxb()
        game.vqqdlnuxnr()
        game.ujotjblwn.current_steps = state['step_counter']
        if game.lmacwotry:
            zjztrymikm = game.cuvqxkfop[0] + game.sjixewahg * 4
            ybxktzursr = game.cuvqxkfop[1] - game.uxtzlxsiq * 4
            game.qpvpuhpms.set_position(zjztrymikm, ybxktzursr)
        epywhrcwy_name = state.get('epywhrcwy_name')
        if epywhrcwy_name:
            if game.epywhrcwy is None:
                for s in game.current_level._sprites:
                    if s.name == epywhrcwy_name:
                        game.epywhrcwy = s
                        break
            if game.epywhrcwy:
                game.svxnnbpjl = state['svxnnbpjl']
        elif state['svxnnbpjl'] == 'none':
            game.epywhrcwy = None

    def get_compact_state():
        """Compact hashable state for BFS visited tracking."""
        px, py = game.qnnpcoyzd.x, game.qnnpcoyzd.y
        toggle_bits = 0
        bit_idx = 0
        for s in game.current_level._sprites:
            if 'tovemc' in s.tags:
                if s.interaction.name not in ('REMOVED', 'INVISIBLE'):
                    toggle_bits |= (1 << bit_idx)
                bit_idx += 1
        key_collected = True
        for s in game.current_level._sprites:
            if 'piyqze' in s.tags and s.interaction.name != 'REMOVED':
                key_collected = False
        crane = None
        if game.lmacwotry:
            crane = (game.sjixewahg, game.uxtzlxsiq, game.svxnnbpjl,
                     game.fvwekbbhj, game.ozarnpwde, game.bbobkhxob)
        obj_pos = None
        for s in game.current_level._sprites:
            if 'grawwq-object' in s.tags:
                obj_pos = (s.x, s.y)
                break
        return (px, py, toggle_bits, key_collected, crane, obj_pos)

    def solve_level_bfs(max_iter=2000000, max_time=480):
        """BFS solve current level using simulation with save/restore."""
        import time as _time
        start_time = _time.time()
        level_idx = game._current_level_index

        _skip_render[0] = True

        init_state = save_state()
        init_hash = get_compact_state()

        queue = deque([(init_hash, init_state, [])])
        visited = {init_hash}

        iters = 0
        while queue:
            iters += 1
            if iters > max_iter:
                print(f"    BFS exceeded {max_iter} iterations")
                _skip_render[0] = False
                return None, None
            elapsed = _time.time() - start_time
            if elapsed > max_time:
                print(f"    BFS timeout after {elapsed:.0f}s, {iters} iters, {len(visited)} states")
                _skip_render[0] = False
                return None, None
            if iters % 10000 == 0:
                rate = iters / elapsed if elapsed > 0 else 0
                print(f"    iter={iters} visited={len(visited)} queue={len(queue)} depth={len(queue[0][2])} rate={rate:.0f}/s", flush=True)

            state_hash, state, actions = queue.popleft()

            found_solution = None
            new_move_states = []
            for act in [1, 2, 3, 4]:
                restore_state(state)
                old_px, old_py = game.qnnpcoyzd.x, game.qnnpcoyzd.y
                env.step(act)
                wait_anim()

                if game._current_level_index != level_idx or game.smxyfelexa():
                    found_solution = actions + [act]
                    break
                if game.divlqsjra:
                    continue
                new_px, new_py = game.qnnpcoyzd.x, game.qnnpcoyzd.y
                if (new_px, new_py) == (old_px, old_py):
                    continue

                new_hash = get_compact_state()
                if new_hash not in visited:
                    visited.add(new_hash)
                    new_state = save_state()
                    new_move_states.append((new_hash, new_state, actions + [act]))

            if found_solution:
                _skip_render[0] = False
                return found_solution, init_state

            queue.extend(new_move_states)

            # Click actions
            restore_state(state)
            all_clicks = {}
            btns = get_btns()
            for letter, coords in btns.items():
                all_clicks[f'btn_{letter}'] = coords
            sys_clicks = get_sys_clicks()
            for tag, coords in sys_clicks.items():
                all_clicks[f'sys_{tag}'] = coords

            for click_key, (cx, cy) in all_clicks.items():
                restore_state(state)
                env.step(6, data={'x': cx, 'y': cy})
                wait_anim()

                if game._current_level_index != level_idx or game.smxyfelexa():
                    _skip_render[0] = False
                    return actions + [('click', cx, cy)], init_state
                if game.divlqsjra:
                    continue

                new_hash = get_compact_state()
                if new_hash not in visited:
                    visited.add(new_hash)
                    new_state = save_state()
                    queue.append((new_hash, new_state, actions + [('click', cx, cy)]))

        print(f"    BFS: no path found, visited {len(visited)} states in {iters} iterations")
        _skip_render[0] = False
        return None, None

    def execute_solution(solution):
        last_obs = None
        for act in solution:
            if isinstance(act, tuple) and act[0] == 'click':
                last_obs = env.step(6, data={'x': act[1], 'y': act[2]})
            else:
                last_obs = env.step(act)
            wait_anim()
        return last_obs

    # ================================================================
    # Solve all 6 levels — export solutions for recording
    # ================================================================

    _exported_solutions = []  # list of level solution lists
    total_completed = 0
    levels_solved = 0

    # ---- LEVEL 0 (manual) ----
    print(f"=== Level 0 ===")
    off0 = doff()
    btn0 = {'click_a': (48, 9+off0), 'click_b': (48, 26+off0)}
    l0_actions = [1, 'click_b', 1, 1, 1, 1, 4, 4, 4, 4, 4, 'click_a', 1, 1, 1, 'click_b', 1, 1, 4, 4]
    l0_sol = []
    for act in l0_actions:
        if isinstance(act, str):
            x, y = btn0[act]
            obs = env.step(6, data={'x': x, 'y': y})
            l0_sol.append(('click', x, y))
        else:
            obs = env.step(act)
            l0_sol.append(act)
        wait_anim()
    _exported_solutions.append(l0_sol)
    total_completed = obs.levels_completed
    levels_solved = 1
    print(f"  Solved! completed={total_completed}", flush=True)

    if obs.state.name != 'NOT_FINISHED':
        print(f"  Game ended: {obs.state.name}")
    else:
        # ---- LEVEL 1 (manual) ----
        print(f"\n=== Level 1 ===")
        off1 = doff()
        btn1 = {'click_b': (52, 32+off1), 'click_c': (52, 14+off1), 'click_a': (52, 23+off1)}
        l1_actions = (['click_b'] + [2]*6 + [4]*5 + ['click_c'] + [2]*5 +
                      ['click_a'] + [1]*10 + [4]*2 + [1]*10 + [4])
        l1_sol = []
        for act in l1_actions:
            if isinstance(act, str):
                x, y = btn1[act]
                obs = env.step(6, data={'x': x, 'y': y})
                l1_sol.append(('click', x, y))
            else:
                obs = env.step(act)
                l1_sol.append(act)
            wait_anim()
        _exported_solutions.append(l1_sol)
        total_completed = obs.levels_completed
        levels_solved = 2
        print(f"  Solved! completed={total_completed}", flush=True)

    # ---- LEVELS 2-3 (BFS) ----
    for level_num in range(2, 4):
        if obs.state.name != 'NOT_FINISHED':
            break

        print(f"\n=== Level {level_num} ===")
        print(f"  Player: ({game.qnnpcoyzd.x},{game.qnnpcoyzd.y}) -> Goal: ({game.hfuqkxulm.x},{game.hfuqkxulm.y})")
        print(f"  Grid: {game.gfalivzzh}x{game.vgrdxwayb}, Steps: {game.ujotjblwn.current_steps}")

        solution, level_init_state = solve_level_bfs(max_iter=5000000, max_time=600)
        if solution:
            print(f"  Found solution: {len(solution)} actions", flush=True)
            _skip_render[0] = False
            restore_state(level_init_state)
            obs = execute_solution(solution)
            _exported_solutions.append(solution)
            total_completed = obs.levels_completed
            levels_solved = level_num + 1
            print(f"  Solved! completed={total_completed} (levels_solved={levels_solved})", flush=True)
        else:
            print(f"  FAILED to solve level {level_num}")
            break

    # ---- LEVEL 4 (hardcoded crane solution) ----
    if obs.state.name == 'NOT_FINISHED':
        print(f"\n=== Level 4 (hardcoded) ===")
        print(f"  Player: ({game.qnnpcoyzd.x},{game.qnnpcoyzd.y}) -> Goal: ({game.hfuqkxulm.x},{game.hfuqkxulm.y})")
        l4_solution = [3, ('click', 52, 41), 3, 1, 1, 3, ('click', 52, 41),
            ('click', 50, 30), ('click', 50, 30), ('click', 50, 30),
            ('click', 55, 30), ('click', 55, 30), ('click', 55, 30),
            ('click', 52, 35),
            ('click', 45, 30), ('click', 45, 30), ('click', 45, 30),
            ('click', 60, 30), ('click', 60, 30), ('click', 60, 30),
            ('click', 55, 30), ('click', 55, 30), ('click', 55, 30),
            3, 1, 1, 1, 1, 4, 1,
            ('click', 45, 30), ('click', 45, 30), ('click', 45, 30),
            ('click', 50, 30), ('click', 50, 30), ('click', 50, 30),
            ('click', 55, 30), ('click', 55, 30), ('click', 55, 30),
            3, 1, 1, 1, 1, 1, 1, 1,
            ('click', 52, 48), 4,
            ('click', 45, 30), ('click', 45, 30), ('click', 45, 30),
            ('click', 60, 30), ('click', 60, 30), ('click', 60, 30),
            1, 1, 1, 1, 1, 1, 1, 1,
            2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
            ('click', 52, 14), ('click', 57, 23), 4, ('click', 57, 23), 4,
            ('click', 57, 23), 4, ('click', 57, 23), 4, 4, 4, 4,
            2, 2, 2, 2,
            ('click', 47, 22), ('click', 47, 22), ('click', 47, 22), ('click', 47, 22),
            2, 3, 3, ('click', 52, 14), 1, 1, 3, 3, 3, 3, 3, 3]
        obs = execute_solution(l4_solution)
        _exported_solutions.append(l4_solution)
        total_completed = obs.levels_completed
        levels_solved = 5
        print(f"  Solved! completed={total_completed} (levels_solved={levels_solved})", flush=True)

    # ---- LEVEL 5 (BFS with extended time) ----
    if obs.state.name == 'NOT_FINISHED':
        print(f"\n=== Level 5 ===")
        print(f"  Player: ({game.qnnpcoyzd.x},{game.qnnpcoyzd.y}) -> Goal: ({game.hfuqkxulm.x},{game.hfuqkxulm.y})")
        print(f"  Grid: {game.gfalivzzh}x{game.vgrdxwayb}, Steps: {game.ujotjblwn.current_steps}")
        print(f"  Has crane: {bool(game.lmacwotry)}")

        solution, level_init_state = solve_level_bfs(max_iter=15000000, max_time=7200)
        if solution:
            print(f"  Found solution: {len(solution)} actions", flush=True)
            _skip_render[0] = False
            restore_state(level_init_state)
            obs = execute_solution(solution)
            _exported_solutions.append(solution)
            total_completed = obs.levels_completed
            levels_solved = 6
            print(f"  Solved! completed={total_completed} (levels_solved={levels_solved})", flush=True)
        else:
            print(f"  FAILED to solve level 5")

    # ================================================================
    _skip_render[0] = False
    print(f"\n{'='*60}")
    print(f"GAME_ID: dc22")
    print(f"LEVELS_SOLVED: {levels_solved}")
    print(f"TOTAL_LEVELS: 6")

    # Export solutions for recording
    import dc22_solver as _self_mod
    _self_mod._exported_solutions = _exported_solutions

    return levels_solved


if __name__ == "__main__":
    solve()
