#!/usr/bin/env python3
"""Record action sequences for all 25 ARC-AGI-3 solvers.

Monkey-patches env.step() on the MAIN environment to capture all actions.
Handles the variety of solver patterns (direct actions, clicks, GameAction enums).

Solver categories:
  DIRECT: Actions executed sequentially, no BFS via env.step. Simple patching works.
  REPLAY: Solver uses replay_solution/replay_actions with env.reset().
          Use reset_on_reset=True to capture only the last replay.
  GAME_SWAP: Solver swaps env._game with deepcopy for BFS.
          Use track_game=True to ignore deepcopy'd games.
  BFS_ENV: Solver does BFS using env.step with save/restore on same game.
          Need custom handling (final replay from reset).
"""

import sys
import os
import json
import importlib
import traceback
import logging

logging.disable(logging.WARNING)
sys.setrecursionlimit(10000)

sys.path.insert(0, '/home/paolo/arc-agi/solver')
os.chdir('/home/paolo/arc-agi/solver')

# Global recording state
_recorded_actions = []


def patch_env_step(env, track_game=False, reset_on_reset=False):
    """Monkey-patch env.step to record actions.

    track_game: only record when env._game is the original (not deepcopy'd)
    reset_on_reset: patch env.reset() to clear recording on each reset
    """
    global _recorded_actions
    _recorded_actions = []
    original_step = env.step
    original_reset = env.reset
    seen_games = set()
    if track_game and hasattr(env, '_game') and env._game is not None:
        seen_games.add(id(env._game))

    def recording_step(action, data=None, reasoning=None, **kwargs):
        global _recorded_actions
        # Skip recording on deepcopy'd games
        if track_game and hasattr(env, '_game') and env._game is not None:
            if id(env._game) not in seen_games:
                return original_step(action, data=data, reasoning=reasoning, **kwargs)

        # Convert action to int
        if hasattr(action, 'value'):
            action_id = action.value if isinstance(action.value, int) else action.value[0]
        else:
            action_id = int(action)

        # Build data for recording
        rec_data = {"x": int(data['x']), "y": int(data['y'])} if (data and 'x' in data and 'y' in data) else None
        _recorded_actions.append([action_id, rec_data])

        result = original_step(action, data=data, reasoning=reasoning, **kwargs)

        # Track new games after level transitions
        if track_game and hasattr(env, '_game') and env._game is not None:
            seen_games.add(id(env._game))

        return result

    def recording_reset():
        global _recorded_actions
        _recorded_actions = []
        return original_reset()

    env.step = recording_step
    if reset_on_reset:
        env.reset = recording_reset
    return env


def make_recorder(module_name, fn_name, track_game=False, reset_on_reset=False):
    """Create a recorder function for a solver module."""
    def recorder():
        import arc_agi
        original_make = arc_agi.Arcade.make
        call_count = [0]

        def patched_make(self, gid, **kwargs):
            env = original_make(self, gid, **kwargs)
            call_count[0] += 1
            if call_count[0] == 1:
                patch_env_step(env, track_game=track_game, reset_on_reset=reset_on_reset)
            return env

        arc_agi.Arcade.make = patched_make
        saved_stdout = sys.stdout
        # Prevent modules from corrupting stdout via fdopen
        original_fdopen = os.fdopen
        os.fdopen = lambda *a, **kw: saved_stdout
        try:
            # Remove module from cache to avoid reload issues
            # (some modules redefine builtins like print, causing circular refs on reload)
            if module_name in sys.modules:
                del sys.modules[module_name]
            mod = importlib.import_module(module_name)
            getattr(mod, fn_name)()
        finally:
            arc_agi.Arcade.make = original_make
            os.fdopen = original_fdopen
            sys.stdout = saved_stdout

        return list(_recorded_actions)
    return recorder


def record_sc25():
    """sc25: Solver class wraps env.step with _counting_step."""
    import arc_agi
    original_make = arc_agi.Arcade.make

    def patched_make(self, gid, **kwargs):
        env = original_make(self, gid, **kwargs)
        patch_env_step(env)
        return env

    arc_agi.Arcade.make = patched_make
    try:
        import sc25_solver
        importlib.reload(sc25_solver)
        s = sc25_solver.Solver()
        s.solve()
    finally:
        arc_agi.Arcade.make = original_make

    return list(_recorded_actions)


def _old_record_dc22():
    """OLD dc22 recorder - REPLACED.

    The original dc22_solver.solve() is called, but env.step is patched
    with a global suppress flag that gets toggled during BFS search.
    """
    global _recorded_actions
    _recorded_actions = []

    import arc_agi
    import builtins

    # Create a global suppress flag accessible from the solver
    builtins._dc22_suppress_recording = False

    original_make = arc_agi.Arcade.make

    def patched_make(self, gid, **kwargs):
        env = original_make(self, gid, **kwargs)
        original_step = env.step

        def recording_step(action, data=None, reasoning=None, **kwargs2):
            if not builtins._dc22_suppress_recording:
                if hasattr(action, 'value'):
                    action_id = action.value if isinstance(action.value, int) else action.value[0]
                else:
                    action_id = int(action)
                rec_data = {"x": int(data['x']), "y": int(data['y'])} if (data and 'x' in data and 'y' in data) else None
                _recorded_actions.append([action_id, rec_data])
            return original_step(action, data=data, reasoning=reasoning, **kwargs2)

        env.step = recording_step
        return env

    arc_agi.Arcade.make = patched_make

    # Patch dc22_solver's solve_level_bfs to suppress recording during BFS
    if 'dc22_solver' in sys.modules:
        del sys.modules['dc22_solver']

    import dc22_solver

    # The original solve() defines solve_level_bfs as a closure.
    # We can't patch it directly, but we CAN patch the global variable
    # that the BFS references.

    # Alternative: patch solve() to wrap solve_level_bfs
    original_solve = dc22_solver.solve

    def patched_solve():
        # We'll monkey-patch the env.step within solve to toggle suppression
        # But since solve_level_bfs is a nested function, we can't access it.
        # Instead, we'll use a global flag checked by env.step.

        # The BFS calls env.step(act) and env.step(6, data=...) during search.
        # The execute_solution calls env.step(act) and env.step(6) for final execution.
        # The manual levels call env.step(act) and env.step(6) directly.

        # We need to suppress during BFS but not during execute_solution or manual.

        # Approach: set suppress=True when _skip_render[0] is True (BFS mode).
        # But we can't access _skip_render from outside the closure.

        # Simplest: just call original solve() and let ALL actions record,
        # then filter out the BFS search actions.
        # BFS search actions have a pattern: they're followed by restore_state
        # which means the game state resets. But we can't detect that from env.step.

        # Actually, let's just run the original solver and accept ALL actions.
        # dc22 solves 4/6 levels. The BFS search adds extra actions but
        # since we save/restore, the final game state is correct.
        # The issue: the recording will have BFS search actions mixed in.

        # But wait - the recording is just for replay. If we replay ALL recorded
        # actions, the BFS search actions will execute on the game and mess up
        # the state. We need ONLY the final solution actions.

        # Final approach: run the solver, but intercept the solution after BFS.
        # We'll just accept that dc22 needs its own approach.
        pass

    # OK, let me just use the simplest possible approach:
    # Run dc22 solver, extract solutions by intercepting execute_solution,
    # then replay them on a fresh env with recording.

    level_solutions = {}  # level_num -> list of (action_or_click_tuple)

    # Patch execute_solution to capture solutions
    # But execute_solution is a closure inside solve(), so we can't patch it.

    # Let me just hardcode the approach differently.
    # Run the solver WITHOUT recording, let it print results.
    # Then build solutions from known structure.

    arc_agi.Arcade.make = original_make  # restore
    del builtins._dc22_suppress_recording

    # Run original solver (no recording) and capture internal state
    import dc22_solver as dc22
    if hasattr(dc22, '_cached_solutions'):
        del dc22._cached_solutions

    # Add a hook to the solver to export solutions
    original_solve_fn = dc22.solve

    _dc22_solutions = []  # list of level solutions

    def solve_with_capture():
        import numpy as np
        from collections import deque

        arc_inst = arc_agi.Arcade()
        env = arc_inst.make('dc22')
        obs = env.reset()
        game = env._game

        _dummy_frame = np.zeros((64, 64), dtype=np.int8)
        _real_render = game.camera.render
        _skip_render = [False]
        def _patched_render(sprites):
            return _dummy_frame if _skip_render[0] else _real_render(sprites)
        game.camera.render = _patched_render

        def doff():
            return (64 - game.vgrdxwayb) // 2

        def wait_anim():
            for _ in range(60):
                if not (game.guspipewt or game.fadccmsnb or game.fjiyimenq):
                    break
                env.step(1)

        # Use the ORIGINAL solver's save_state/restore_state/solve_level_bfs
        # by calling solve() but intercepting the solutions

        # Actually, let me just duplicate the minimal solver logic
        # and capture execute_solution inputs

        # Level 0 manual
        off0 = doff()
        btn0 = {'click_a': (48, 9+off0), 'click_b': (48, 26+off0)}
        l0_raw = [1, 'click_b', 1, 1, 1, 1, 4, 4, 4, 4, 4, 'click_a', 1, 1, 1, 'click_b', 1, 1, 4, 4]
        l0_sol = []
        for act in l0_raw:
            if isinstance(act, str):
                x, y = btn0[act]
                l0_sol.append(('click', x, y))
                obs = env.step(6, data={'x': x, 'y': y})
            else:
                l0_sol.append(act)
                obs = env.step(act)
            wait_anim()
        _dc22_solutions.append(l0_sol)
        print(f"dc22 L0: completed={obs.levels_completed}")

        if obs.state.name != 'NOT_FINISHED':
            return

        # Level 1 manual
        off1 = doff()
        btn1 = {'click_b': (52, 32+off1), 'click_c': (52, 14+off1), 'click_a': (52, 23+off1)}
        l1_raw = ['click_b'] + [2]*6 + [4]*5 + ['click_c'] + [2]*5 + ['click_a'] + [1]*10 + [4]*2 + [1]*10 + [4]
        l1_sol = []
        for act in l1_raw:
            if isinstance(act, str):
                x, y = btn1[act]
                l1_sol.append(('click', x, y))
                obs = env.step(6, data={'x': x, 'y': y})
            else:
                l1_sol.append(act)
                obs = env.step(act)
            wait_anim()
        _dc22_solutions.append(l1_sol)
        print(f"dc22 L1: completed={obs.levels_completed}")

        # Levels 2-5: use original solver's BFS
        # Call the original solve() closure's BFS.
        # Since we can't, let's use a fresh import of the module.
        # The trick: dc22_solver.solve() creates everything inside solve().
        # We need to call it and capture the BFS results.

        # Actually the simplest: just call the original dc22 solver for L2+
        # but patch execute_solution to capture solutions.

        # Since solve_level_bfs and execute_solution are closures inside solve(),
        # we can't patch them. Instead, let me just run solve() and capture
        # env.step calls ONLY during execute_solution and wait_anim after restore.

        # I give up trying to be elegant. Let me just call dc22 from subprocess
        # and parse its output... or better: let me just NOT record dc22's BFS
        # levels and record only L0+L1 (2 out of 4 levels solved).

        # Wait, dc22 solves 4/6 levels. L0 and L1 are manual, L2 and L3 are BFS.
        # For L2 and L3, the original solver's BFS uses game engine save/restore
        # which is more complete than my inline version.

        # Let me just run the full dc22 solver with env.step patched, but
        # capture ONLY the last 'execute_solution' call's actions.
        pass

    # OK, absolutely simplest approach: run dc22 solver via subprocess,
    # patch it to write solutions to a file, then read and replay.

    # Actually wait - let me check the memory for dc22's win state.
    # It's listed as dc22(4/6) partial. So we need 4 levels.

    # Let me write a tiny wrapper that adds solution export to dc22_solver:
    solve_with_capture()

    # If we only got L0+L1, that's fine - the BFS levels are too slow anyway.
    # For competition, 2/6 is what dc22 managed in some runs.

    if len(_dc22_solutions) >= 2:
        # Replay L0+L1 with recording on fresh env
        _recorded_actions = []
        arc_inst2 = arc_agi.Arcade()
        env2 = arc_inst2.make('dc22')
        patch_env_step(env2)
        obs2 = env2.reset()

        def wait_anim2():
            game2 = env2._game
            for _ in range(60):
                if not (game2.guspipewt or game2.fadccmsnb or game2.fjiyimenq):
                    break
                env2.step(1)

        for sol in _dc22_solutions:
            for act in sol:
                if isinstance(act, tuple) and act[0] == 'click':
                    env2.step(6, data={'x': act[1], 'y': act[2]})
                else:
                    env2.step(act)
                wait_anim2()

        obs2 = env2._last_response
        print(f"dc22 replay: completed={obs2.levels_completed}")

    return list(_recorded_actions)



def record_dc22():
    """dc22: Run original solver (exports solutions), then replay with recording."""
    global _recorded_actions
    _recorded_actions = []

    if 'dc22_solver' in sys.modules:
        del sys.modules['dc22_solver']
    import dc22_solver

    # Run solver (no recording) - it now exports _exported_solutions
    dc22_solver.solve()

    solutions = getattr(dc22_solver, '_exported_solutions', [])
    print(f"dc22: got {len(solutions)} level solutions")

    if not solutions:
        return []

    # Replay on fresh env with recording
    import arc_agi
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('dc22')
    patch_env_step(env)
    obs = env.reset()
    game = env._game

    def wait_anim():
        for _ in range(60):
            if not (game.guspipewt or game.fadccmsnb or game.fjiyimenq):
                break
            env.step(1)

    for sol in solutions:
        for act in sol:
            if isinstance(act, tuple) and act[0] == 'click':
                env.step(6, data={'x': act[1], 'y': act[2]})
            else:
                env.step(act)
            wait_anim()

    obs = env._last_response
    print(f"dc22 replay: completed={obs.levels_completed}, state={obs.state.name}")
    return list(_recorded_actions)


def record_vc33():
    """vc33: BFS uses env.step. Extract level_solutions and do clean replay."""
    global _recorded_actions
    import arc_agi

    # First run solver without recording to get level_solutions
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('vc33')
    obs = env.reset()
    obs = env.step(6)
    game = env._game

    import vc33_solver
    importlib.reload(vc33_solver)

    level_solutions = {}
    for level in range(1, obs.win_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break
        cam = game.camera
        if level <= 3:
            sol, obs2 = vc33_solver.solve_bfs_replay(env, game, level, level_solutions)
            if sol:
                level_solutions[level] = sol
                obs = obs2
                game = env._game
        elif level == 4:
            clicks = vc33_solver.get_manual_l4(game, cam)
            level_solutions[level] = clicks
            obs2 = env.reset()
            obs2 = env.step(6)
            for prev_l in sorted(level_solutions.keys()):
                for click in level_solutions[prev_l]:
                    obs2 = env.step(6, data={"x": click[0], "y": click[1]})
            obs = obs2
            game = env._game
        elif level == 5:
            clicks = vc33_solver.get_manual_l5(game, cam)
            level_solutions[level] = clicks
            obs2 = env.reset()
            obs2 = env.step(6)
            for prev_l in sorted(level_solutions.keys()):
                for click in level_solutions[prev_l]:
                    obs2 = env.step(6, data={"x": click[0], "y": click[1]})
            obs = obs2
            game = env._game
        elif level == 6:
            sol, obs2 = vc33_solver.solve_bfs_saverestore(env, game, level, level_solutions, max_states=100000)
            if sol:
                level_solutions[level] = sol
                obs = obs2
                game = env._game
        elif level == 7:
            click_log, obs2 = vc33_solver.solve_l7_interactive(env, game, level_solutions)
            if obs2 and (obs2.state.name == "WIN" or game.ielczunthe()):
                level_solutions[level] = click_log
                obs = obs2
                game = env._game

    print(f"vc33: solved {len(level_solutions)} levels, now replaying...")

    # Now do a clean replay with recording
    env2 = arc_inst.make('vc33')
    patch_env_step(env2)
    obs2 = env2.reset()
    obs2 = env2.step(6)
    for lv in sorted(level_solutions.keys()):
        for click in level_solutions[lv]:
            obs2 = env2.step(6, data={"x": click[0], "y": click[1]})
    print(f"vc33 replay: completed={obs2.levels_completed}, state={obs2.state.name}")

    return list(_recorded_actions)


def record_wa30():
    """wa30: reactive solver executes actions directly on env.
    Extract level_solutions and do clean replay."""
    global _recorded_actions
    import arc_agi
    import wa30_solver
    importlib.reload(wa30_solver)

    # Run solver without recording to get level_solutions
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('wa30')
    obs = env.reset()
    obs = env.step(6)
    game = env._game

    total_levels = obs.win_levels
    level_solutions = {}

    for level_num in range(1, total_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break
        wa30_solver.replay_actions(env, level_solutions)
        game = env._game

        if level_num in wa30_solver.MANUAL_SOLUTIONS:
            solution = wa30_solver.MANUAL_SOLUTIONS[level_num]
            for a in solution:
                obs = env.step(a)
            if obs.levels_completed >= level_num:
                level_solutions[level_num] = solution
                obs = wa30_solver.replay_actions(env, level_solutions)
                game = env._game
                continue
            else:
                wa30_solver.replay_actions(env, level_solutions)
                game = env._game
                solution = wa30_solver.solve_level(env, game, level_num, level_solutions)
        else:
            solution = wa30_solver.solve_level(env, game, level_num, level_solutions)

        if solution is not None:
            level_solutions[level_num] = solution
            obs = wa30_solver.replay_actions(env, level_solutions)
            game = env._game
        else:
            break

    print(f"wa30: solved {len(level_solutions)} levels, now replaying...")

    # Clean replay with recording
    env2 = arc_inst.make('wa30')
    patch_env_step(env2)
    obs2 = env2.reset()
    obs2 = env2.step(6)
    for lv in sorted(level_solutions.keys()):
        for action in level_solutions[lv]:
            obs2 = env2.step(action)
    print(f"wa30 replay: completed={obs2.levels_completed}, state={obs2.state.name}")

    return list(_recorded_actions)


# ─── SOLVER REGISTRY ────────────────────────────────────────────────────

SOLVERS = {
    # DIRECT execution solvers (no BFS via env.step)
    'tu93': make_recorder('tu93_solver', 'main'),  # BFS creates separate envs
    'm0r0': make_recorder('m0r0_solver', 'solve'),
    'tr87': make_recorder('tr87_solver', 'solve_all_levels', reset_on_reset=True),
    'sb26': make_recorder('sb26_solver', 'main'),
    'cd82': make_recorder('cd82_solver', 'solve'),
    'sc25': record_sc25,
    'tn36': make_recorder('tn36_solver', 'solve'),
    'cn04': make_recorder('cn04_solver', 'solve'),
    'sp80': make_recorder('sp80_solver', 'main'),
    'bp35': make_recorder('bp35_solver', 'solve_all', reset_on_reset=True),

    # REPLAY-based solvers (use replay_solution/replay_actions with env.reset)
    'su15': make_recorder('su15_solver', 'solve', reset_on_reset=True),
    's5i5': make_recorder('s5i5_solver', 'solve', reset_on_reset=True),
    'lp85': make_recorder('lp85_solver', 'solve', reset_on_reset=True),
    'ft09': make_recorder('ft09_solver', 'solve_all', reset_on_reset=True),
    'ls20': make_recorder('ls20_solver', 'solve', reset_on_reset=True),
    'vc33': record_vc33,
    'wa30': record_wa30,
    'sk48': make_recorder('sk48_solver', 'solve', reset_on_reset=True),

    # GAME_SWAP solvers (env._game swapped with deepcopy)
    'ka59': make_recorder('ka59_solver', 'solve', track_game=True),

    # BFS_ENV solvers (BFS uses env.step, need custom handling)
    'dc22': record_dc22,

    # GameAction-based solvers
    'g50t': make_recorder('g50t_solver', 'solve', reset_on_reset=True),
    'r11l': make_recorder('agi3_solver_v2', 'solve'),
}

OUTPUT_FILE = '/home/paolo/arc-agi/solver/recorded_solutions.json'


def main():
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE) as f:
            solutions = json.load(f)
    else:
        solutions = {}

    if len(sys.argv) > 1:
        games = sys.argv[1:]
    else:
        games = [g for g in SOLVERS if g not in solutions]

    print(f"Games to record: {games}")
    print(f"Already have: {list(solutions.keys())}")
    print()

    for game_id in games:
        if game_id not in SOLVERS:
            print(f"SKIP {game_id}: no recorder defined")
            continue

        print(f"\n{'='*60}")
        print(f"RECORDING: {game_id}")
        print(f"{'='*60}")

        global _recorded_actions
        _recorded_actions = []

        try:
            actions = SOLVERS[game_id]()
            if actions and len(actions) > 0:
                solutions[game_id] = actions
                print(f"\n  >> {game_id}: {len(actions)} actions recorded")

                with open(OUTPUT_FILE, 'w') as f:
                    json.dump(solutions, f)
                print(f"  >> Saved to {OUTPUT_FILE}")
            else:
                print(f"\n  >> {game_id}: NO actions recorded!")
        except Exception as e:
            print(f"\n  >> {game_id}: FAILED: {e}")
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"DONE. Total games: {len(solutions)}")
    for g in sorted(solutions.keys()):
        print(f"  {g}: {len(solutions[g])} actions")


if __name__ == "__main__":
    main()
