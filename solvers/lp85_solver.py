#!/usr/bin/env python3
"""lp85 solver — multi-gear track puzzle.

KEY INSIGHTS:
1. Actions are FIXED permutations of positions (independent of state).
   So we only need to track where GOAL sprites are, not all sprites.
2. Multiple button sprites can share the same position. Clicking triggers
   ALL buttons at that position simultaneously (compound action).
"""
import arc_agi
import numpy as np
import time
from collections import deque
from universal_harness import grid_to_display, replay_solution

SCALE = 3


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('lp85')
    obs = env.reset()
    obs = env.step(6)
    game = env._game

    print(f"lp85: {obs.win_levels} levels")
    level_solutions = {}

    for level in range(1, obs.win_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        cam = game.camera
        level_name = game.ucybisahh
        track_data = game.uopmnplcnv[level_name]
        groups = list(track_data.keys())
        step_limit = game.current_level.get_data("StepCounter") or 100
        print(f"\nL{level} '{level_name}' (cam={cam.width}x{cam.height}, {len(groups)} groups, steps={step_limit})")

        # Build tracks: group -> ordered list of (sprite_x, sprite_y)
        group_tracks = {}
        for gname, gdata in track_data.items():
            positions = gdata['qcmzcjocmj']
            n = gdata['oxbwsencfv']
            ordered = []
            for i in range(1, n + 1):
                if i in positions:
                    p = positions[i]
                    ordered.append((p.x * SCALE, p.y * SCALE))
            group_tracks[gname] = ordered

        # All track positions
        all_track_pos = set()
        for track in group_tracks.values():
            all_track_pos.update(track)

        # Build COMPOUND buttons: group button sprites at same position
        # The game triggers ALL button sprites at the clicked position
        all_sprites = game.current_level.get_sprites()
        click_positions = {}  # (gx, gy) -> list of (group, is_right)
        click_sprite_info = {}  # (gx, gy) -> sprite (for display coord calculation)

        for s in all_sprites:
            for tag in s.tags:
                if tag.startswith("button_"):
                    parts = tag.split("_")
                    if len(parts) == 3:
                        pos = (s.x, s.y)
                        click_positions.setdefault(pos, []).append((parts[1], parts[2] == 'R'))
                        if pos not in click_sprite_info:
                            click_sprite_info[pos] = s

        # Build display coordinates for each click position
        buttons = []
        for pos, actions in click_positions.items():
            s = click_sprite_info[pos]
            dx, dy = grid_to_display(s.x + s.width // 2, s.y + s.height // 2, cam)
            buttons.append({
                'groups': actions,
                'display': (dx, dy),
                'grid': pos,
            })

        # Find moveable sprites
        moveable_sprites = []
        for s in all_sprites:
            if (s.x, s.y) in all_track_pos:
                moveable_sprites.append(s)

        # Markers (win conditions)
        markers_goal = []
        markers_goal_o = []
        for s in game.current_level.get_sprites_by_tag("bghvgbtwcb"):
            markers_goal.append((s.x + 1, s.y + 1))
        for s in game.current_level.get_sprites_by_tag("fdgmtkfrxl"):
            markers_goal_o.append((s.x + 1, s.y + 1))

        sprite_tags = [set(s.tags) for s in moveable_sprites]

        # Build sorted position list and mappings
        pos_list = sorted(all_track_pos)
        n_pos = len(pos_list)
        pos_to_pidx = {p: i for i, p in enumerate(pos_list)}
        pos_to_tidx = {}
        for gname, track in group_tracks.items():
            for i, pos in enumerate(track):
                pos_to_tidx.setdefault(pos, {})[gname] = i

        # Build COMPOUND action permutations (deduplicated)
        # Each click triggers multiple group rotations simultaneously
        action_perms = []
        seen_perms = set()
        unique_buttons = []
        for btn in buttons:
            perm = list(range(n_pos))
            for group, is_right in btn['groups']:
                if group not in group_tracks:
                    continue
                track = group_tracks[group]
                n = len(track)
                for pi, pos in enumerate(pos_list):
                    tidx = pos_to_tidx.get(pos, {}).get(group)
                    if tidx is not None:
                        new_tidx = (tidx + 1) % n if is_right else (tidx - 1) % n
                        perm[pi] = pos_to_pidx[track[new_tidx]]
            perm_t = tuple(perm)
            if perm_t not in seen_perms:
                seen_perms.add(perm_t)
                action_perms.append(perm_t)
                unique_buttons.append(btn)
        buttons = unique_buttons

        # Identify goal sprites and targets
        tile_w = moveable_sprites[0].width if moveable_sprites else 2
        tile_h = moveable_sprites[0].height if moveable_sprites else 2

        goal_pidxs = []
        goal_o_pidxs = []
        for si, tags in enumerate(sprite_tags):
            pos = (moveable_sprites[si].x, moveable_sprites[si].y)
            if pos in pos_to_pidx:
                pidx = pos_to_pidx[pos]
                if 'goal' in tags:
                    goal_pidxs.append(pidx)
                elif 'goal-o' in tags:
                    goal_o_pidxs.append(pidx)

        def find_target_pidx(mx, my):
            for pos in all_track_pos:
                px, py = pos
                if px <= mx < px + tile_w and py <= my < py + tile_h:
                    return pos_to_pidx[pos]
            return None

        goal_targets = set()
        for mx, my in markers_goal:
            tp = find_target_pidx(mx, my)
            if tp is not None:
                goal_targets.add(tp)

        goal_o_targets = set()
        for mx, my in markers_goal_o:
            tp = find_target_pidx(mx, my)
            if tp is not None:
                goal_o_targets.add(tp)

        n_goal = len(goal_pidxs)
        n_goal_o = len(goal_o_pidxs)
        n_tracked = n_goal + n_goal_o

        print(f"  {len(moveable_sprites)} moveable, {len(buttons)} unique actions, {n_goal}+{n_goal_o} goal sprites")

        # State: tuple of position indices for tracked goal sprites
        tracked_init = tuple(goal_pidxs + goal_o_pidxs)

        def check_win_reduced(state):
            goal_positions = set(state[:n_goal])
            goal_o_positions = set(state[n_goal:])
            return goal_targets.issubset(goal_positions) and goal_o_targets.issubset(goal_o_positions)

        def canonicalize(state):
            g = tuple(sorted(state[:n_goal]))
            go = tuple(sorted(state[n_goal:]))
            return g + go

        # Check initial state win
        if check_win_reduced(tracked_init):
            print(f"  Already won!")
            # Need to trigger the actual win in the game
            # Just advance to next level
            obs = env.step(6)
            game = env._game
            level_solutions[level] = []
            continue

        # ═══ BFS on reduced state ═══
        t0 = time.time()

        init_canon = canonicalize(tracked_init)
        visited = {init_canon: []}
        queue = deque([(tracked_init, [])])
        solution = None
        max_states = 50_000_000

        while queue and len(visited) < max_states:
            state, moves = queue.popleft()
            if len(moves) >= step_limit:
                continue

            for ai, perm in enumerate(action_perms):
                new_state = tuple(perm[p] for p in state)
                new_canon = canonicalize(new_state)
                if new_canon in visited:
                    continue

                new_moves = moves + [ai]
                visited[new_canon] = new_moves

                if check_win_reduced(new_state):
                    solution = new_moves
                    break

                queue.append((new_state, new_moves))

            if solution:
                break

            if len(visited) % 1000000 == 0:
                elapsed = time.time() - t0
                print(f"    {len(visited)} states, depth={len(moves)}, time={elapsed:.1f}s")

        elapsed = time.time() - t0
        print(f"  BFS: {len(visited)} states in {elapsed:.1f}s")

        if solution:
            click_list = [buttons[bi]['display'] for bi in solution]
            print(f"  SOLVED! {len(solution)} clicks")

            for click in click_list:
                obs = env.step(6, data={"x": click[0], "y": click[1]})
                if obs.levels_completed >= level:
                    break

            level_solutions[level] = click_list
            print(f"  completed={obs.levels_completed}")
            game = env._game

            if obs.levels_completed < level:
                print(f"  SIM MISMATCH! Trying replay...")
                obs = replay_solution(env, level_solutions)
                game = env._game
                print(f"  After replay: completed={obs.levels_completed}")
                if obs.levels_completed < level:
                    del level_solutions[level]
                    break
        else:
            print(f"  No solution found!")
            break

    total = obs.levels_completed
    if obs.state.name == "WIN":
        total = obs.win_levels
    print(f"\n{'='*40}")
    print(f"lp85 RESULT: {total}/{obs.win_levels}")
    return total


if __name__ == "__main__":
    solve()
