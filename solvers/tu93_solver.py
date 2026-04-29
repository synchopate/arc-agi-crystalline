#!/usr/bin/env python3
"""TU93 Solver — Maze with enemy avoidance via BFS.

Mechanics:
- Graph nodes at 6px intervals on board sprite, edges = pixel value 2
- Actions: 1=up, 2=down, 3=left, 4=right
- Player moves to adjacent node. Eats enemies at destination (they grow, not player).
- Then enemies move. Type1: activated when player is exactly 6px ahead in facing dir.
  Type2: always moves, bounces off dead ends. Type3: activated at 12px dist, with delay.
- If ANY enemy reaches player's node after their move: player dies.
- Win: reach exit. Lose: step counter depleted or death.
"""

import sys
import logging
logging.disable(logging.WARNING)

import numpy as np
from collections import deque

from arc_agi import Arcade


def extract_graph(board):
    """Extract adjacency graph from board sprite."""
    h, w = board.pixels.shape
    nodes = set()
    adj = {}

    for i in range(0, h, 6):
        for j in range(0, w, 6):
            if i < h and j < w and board.pixels[i, j] >= 0:
                nodes.add((j + board.x, i + board.y))

    for (x, y) in nodes:
        i, j = y - board.y, x - board.x
        neighbors = {}
        if i - 3 >= 0 and board.pixels[i - 3, j] == 2:
            d = (x, y - 6)
            if d in nodes: neighbors[1] = d
        if i + 3 < h and board.pixels[i + 3, j] == 2:
            d = (x, y + 6)
            if d in nodes: neighbors[2] = d
        if j - 3 >= 0 and board.pixels[i, j - 3] == 2:
            d = (x - 6, y)
            if d in nodes: neighbors[3] = d
        if j + 3 < w and board.pixels[i, j + 3] == 2:
            d = (x + 6, y)
            if d in nodes: neighbors[4] = d
        adj[(x, y)] = neighbors

    return nodes, adj


REVERSE = {0: 180, 180: 0, 90: 270, 270: 90}
ROT_TO_ACTION = {0: 1, 180: 2, 270: 3, 90: 4}
ACTION_TO_ROT = {1: 0, 2: 180, 3: 270, 4: 90}


def simulate_step(adj, player_pos, action, enemies, nodes):
    """Simulate one player move + enemy response.

    enemies: list of (type, x, y, rot, activated, delay_queue)
      type: 1, 2, or 3
      activated: bool (for type1 and type3)
      delay_queue: tuple of rotations for type3 delay mechanism

    Returns: (new_player_pos, new_enemies, alive, won_check_pos)
    alive=False means player died
    """
    dest = adj.get(player_pos, {}).get(action)
    if dest is None:
        return player_pos, enemies, True, player_pos

    player_pos = dest
    player_rot = ACTION_TO_ROT[action]

    # Step 0: Append player_rot to ALL activated type3 delay queues
    # (In the actual code this happens in phase 0 before any sliding)
    step0 = []
    for (etype, ex, ey, erot, eact, delay) in enemies:
        if etype == 3 and eact:
            new_delay = delay + (player_rot,)
            step0.append((etype, ex, ey, erot, eact, new_delay))
        else:
            step0.append((etype, ex, ey, erot, eact, delay))

    # Step 2: Player eats enemies at destination node
    step2 = []
    for e in step0:
        if (e[1], e[2]) == player_pos:
            continue  # Enemy consumed
        step2.append(e)

    # Step 3: Activate type1 enemies adjacent to player (dist 6)
    step3 = []
    for (etype, ex, ey, erot, eact, delay) in step2:
        if etype == 1 and not eact:
            px, py = player_pos
            if (erot == 90 and ex == px - 6 and ey == py) or \
               (erot == 270 and ex == px + 6 and ey == py) or \
               (erot == 180 and ey == py - 6 and ex == px) or \
               (erot == 0 and ey == py + 6 and ex == px):
                act = ROT_TO_ACTION.get(erot)
                ndest = adj.get((ex, ey), {}).get(act)
                if ndest:
                    step3.append((etype, ndest[0], ndest[1], erot, True, delay))
                else:
                    step3.append((etype, ex, ey, erot, True, delay))
                continue
        step3.append((etype, ex, ey, erot, eact, delay))

    # Step 4: Type2 move 1 node
    step4 = []
    for (etype, ex, ey, erot, eact, delay) in step3:
        if etype == 2:
            act = ROT_TO_ACTION.get(erot)
            ndest = adj.get((ex, ey), {}).get(act)
            if ndest:
                step4.append((etype, ndest[0], ndest[1], erot, eact, delay))
            else:
                step4.append((etype, ex, ey, erot, eact, delay))
        else:
            step4.append((etype, ex, ey, erot, eact, delay))

    # Step 5: Activated type3 move 1 node (uses CURRENT rotation, before delay pop)
    step5 = []
    for (etype, ex, ey, erot, eact, delay) in step4:
        if etype == 3 and eact:
            act = ROT_TO_ACTION.get(erot)
            ndest = adj.get((ex, ey), {}).get(act)
            if ndest:
                step5.append((etype, ndest[0], ndest[1], erot, eact, delay))
            else:
                step5.append((etype, ex, ey, erot, eact, delay))
        else:
            step5.append((etype, ex, ey, erot, eact, delay))

    # Step 6: Death check
    for e in step5:
        if (e[1], e[2]) == player_pos:
            return player_pos, step5, False, player_pos

    # Step 7: Type2 bounce
    step7 = []
    for (etype, ex, ey, erot, eact, delay) in step5:
        if etype == 2:
            act = ROT_TO_ACTION.get(erot)
            if act not in adj.get((ex, ey), {}):
                step7.append((etype, ex, ey, REVERSE[erot], eact, delay))
            else:
                step7.append((etype, ex, ey, erot, eact, delay))
        else:
            step7.append((etype, ex, ey, erot, eact, delay))

    # Step 8: Type3 activation (new) + delay pop (existing)
    step8 = []
    for (etype, ex, ey, erot, eact, delay) in step7:
        if etype == 3:
            if not eact:
                # Check activation at distance 12
                px, py = player_pos
                if (erot == 90 and ex == px - 12 and ey == py) or \
                   (erot == 270 and ex == px + 12 and ey == py) or \
                   (erot == 180 and ey == py - 12 and ex == px) or \
                   (erot == 0 and ey == py + 12 and ex == px):
                    # Activate: set delay = [rot, rot], then immediately pop first
                    # gmwsemdsae sets ylmdnwbdyy[sprite] = [rot, rot]
                    # then pops first element -> sprite.rotation = rot, delay = [rot]
                    new_delay = (erot,)
                    step8.append((etype, ex, ey, erot, True, new_delay))
                    continue
                step8.append((etype, ex, ey, erot, eact, delay))
            else:
                # Already activated - pop first from delay queue, set as rotation
                if delay:
                    new_rot = delay[0]
                    new_delay = delay[1:]
                    step8.append((etype, ex, ey, new_rot, eact, new_delay))
                else:
                    step8.append((etype, ex, ey, erot, eact, ()))
        else:
            step8.append((etype, ex, ey, erot, eact, delay))

    return player_pos, step8, True, player_pos


def state_key(player_pos, enemies):
    """Create hashable state key."""
    return (player_pos, tuple(sorted(enemies)))


def solve_level(adj, nodes, player_pos, exit_pos, enemies, max_steps):
    """BFS to find action sequence from player to exit avoiding enemies."""
    init_state = state_key(player_pos, enemies)
    queue = deque()
    queue.append((player_pos, enemies, [], 0))
    visited = {init_state}

    while queue:
        ppos, enemies_list, actions, steps = queue.popleft()

        if steps >= max_steps:
            continue

        for action in [1, 2, 3, 4]:
            if action not in adj.get(ppos, {}):
                continue

            new_ppos, new_enemies, alive, _ = simulate_step(
                adj, ppos, action, enemies_list, nodes
            )

            if not alive:
                continue

            new_actions = actions + [action]

            if new_ppos == exit_pos:
                return new_actions

            sk = state_key(new_ppos, new_enemies)
            if sk not in visited:
                visited.add(sk)
                queue.append((new_ppos, new_enemies, new_actions, steps + 1))

    return None


def solve_level_simple(adj, player_pos, exit_pos, max_steps):
    """Simple BFS without enemies."""
    queue = deque([(player_pos, [])])
    visited = {player_pos}
    while queue:
        pos, actions = queue.popleft()
        if len(actions) >= max_steps:
            continue
        if pos == exit_pos:
            return actions
        for action, dest in adj.get(pos, {}).items():
            if dest not in visited:
                visited.add(dest)
                queue.append((dest, actions + [action]))
    return None


def get_enemies(game):
    """Extract enemy info from game state."""
    enemies = []
    for s in game.current_level.get_sprites_by_tag("0001haidilggfh"):
        activated = bool(s.pixels[0, 1] == 11)
        enemies.append((1, s.x, s.y, s.rotation, activated, ()))
    for s in game.current_level.get_sprites_by_tag("0020npxxteirsg"):
        enemies.append((2, s.x, s.y, s.rotation, False, ()))
    for s in game.current_level.get_sprites_by_tag("0023otenflmryc"):
        activated = bool(s.pixels[0, 1] == 11)
        enemies.append((3, s.x, s.y, s.rotation, activated, ()))
    return enemies


def verify_with_game(arc, prefix_actions, level_actions):
    """Verify a solution by replaying on actual game."""
    env = arc.make("tu93")
    obs = env.reset()
    for a in prefix_actions:
        obs = env.step(a)
        if obs.state.name not in ("NOT_FINISHED",):
            return False

    for a in level_actions:
        obs = env.step(a)
        if obs.state.name in ("WON", "WIN"):
            return True
        if obs.state.name not in ("NOT_FINISHED",):
            return False

    # Level might have advanced (state still NOT_FINISHED but different level)
    return True


def solve_level_with_fallback(arc, prefix_actions, adj, nodes, player_pos, exit_pos, enemies, max_steps, level_num):
    """Try simulation BFS first, fall back to replay BFS if needed."""
    # Try simulation BFS
    print(f"  Trying simulation BFS (max_steps={max_steps})...")
    solution = solve_level(adj, nodes, player_pos, exit_pos, enemies, max_steps)

    if solution:
        print(f"  Simulation found: {len(solution)} actions: {solution}")
        # Verify with actual game
        if verify_with_game(arc, prefix_actions, solution):
            print(f"  Verified OK!")
            return solution
        else:
            print(f"  Verification FAILED! Falling back to replay BFS...")

    if solution is None:
        print(f"  Simulation BFS found no solution, trying replay BFS...")

    # Replay BFS - slower but accurate
    return replay_bfs(arc, prefix_actions, adj, max_steps)


def replay_bfs(arc, prefix_actions, adj, max_steps):
    """BFS using actual game replay for accuracy.

    Uses incremental approach: maintain a pool of (env, actions) pairs
    and extend each by one action, avoiding full replay from scratch.
    """
    def make_env_at_level():
        e = arc.make("tu93")
        o = e.reset()
        for a in prefix_actions:
            o = e.step(a)
        return e, o

    def get_state(g):
        p = g.current_level.get_sprites_by_tag("0017unajnymcki")
        if not p: return None
        parts = [p[0].x, p[0].y]
        for tag in ["0001haidilggfh", "0020npxxteirsg", "0023otenflmryc"]:
            for s in sorted(g.current_level.get_sprites_by_tag(tag), key=lambda s: s.name):
                parts.extend([s.x, s.y, s.rotation, s.pixels.shape[0]])
        return tuple(parts)

    ref_env, _ = make_env_at_level()
    game = ref_env._game
    player = game.current_level.get_sprites_by_tag("0017unajnymcki")[0]
    init_ppos = (player.x, player.y)
    init_state = get_state(game)

    # BFS with full replay from scratch (expensive but correct)
    # Limit depth to keep it manageable
    max_depth = min(max_steps, 25)  # Don't search too deep
    queue = deque([([], init_state, init_ppos)])
    visited = {init_state}
    iterations = 0

    while queue:
        iterations += 1
        if iterations % 500 == 0:
            print(f"    Replay BFS: {iterations} iters, {len(visited)} visited, queue={len(queue)}")
        if iterations > 100000:
            print(f"    Replay BFS limit reached at {iterations}")
            break

        actions, _, ppos = queue.popleft()
        if len(actions) >= max_depth:
            continue

        possible = list(adj.get(ppos, {}).keys())

        for action in possible:
            new_actions = actions + [action]

            test_env, _ = make_env_at_level()

            dead = False
            won = False
            for a in new_actions:
                obs = test_env.step(a)
                if obs.state.name in ("WON", "WIN"):
                    won = True
                    break
                if obs.state.name not in ("NOT_FINISHED",):
                    dead = True
                    break

            if won:
                print(f"    Replay BFS found: {len(new_actions)} actions: {new_actions}")
                return new_actions

            if dead:
                continue

            state = get_state(test_env._game)
            if state is None:
                continue

            p = test_env._game.current_level.get_sprites_by_tag("0017unajnymcki")
            if not p:
                continue
            new_ppos = (p[0].x, p[0].y)

            if state not in visited:
                visited.add(state)
                queue.append((new_actions, state, new_ppos))

    return None


def execute_actions(env, actions):
    """Execute actions on environment."""
    obs = None
    for i, action in enumerate(actions):
        obs = env.step(action)
        if obs.state.name in ("WON", "WIN", "GAME_OVER"):
            return obs, i + 1
    return obs, len(actions)


def main():
    arc = Arcade()
    env = arc.make("tu93")
    obs = env.reset()
    game = env._game

    total_levels = obs.win_levels
    solved = 0
    total_actions = 0
    all_prefix = []

    print(f"GAME: tu93, LEVELS: {total_levels}")
    print(f"Baselines: [19, 16, 34, 42, 123, 80, 14, 23, 111]")
    print()

    for level in range(1, total_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        print(f"{'=' * 60}")
        print(f"LEVEL {level}/{total_levels}")
        print(f"{'=' * 60}")

        board = game.current_level.get_sprites_by_tag("0005uvnhiglpvh")[0]
        player = game.current_level.get_sprites_by_tag("0017unajnymcki")[0]
        exit_s = game.current_level.get_sprites_by_tag("0015msvpvzxhqf")[0]
        nodes, adj = extract_graph(board)
        player_pos = (player.x, player.y)
        exit_pos = (exit_s.x, exit_s.y)
        max_steps = game.ksulgrfyqx.yhzmaedply
        enemies = get_enemies(game)

        print(f"  Player: {player_pos}, Exit: {exit_pos}, Steps: {max_steps}")
        print(f"  Nodes: {len(nodes)}, Enemies: {len(enemies)}")
        for e in enemies:
            enames = {1: "type1", 2: "type2", 3: "type3"}
            print(f"    {enames[e[0]]}@({e[1]},{e[2]}) rot={e[3]}")

        # Simple path first
        simple = solve_level_simple(adj, player_pos, exit_pos, max_steps)
        if simple is None:
            print(f"  No path on graph!")
            break
        print(f"  Shortest path (no enemies): {len(simple)} steps")

        if not enemies:
            actions = simple
        else:
            actions = solve_level_with_fallback(
                arc, list(all_prefix), adj, nodes,
                player_pos, exit_pos, enemies, max_steps, level
            )

        if actions is None:
            print(f"  FAILED to solve level {level}")
            break

        print(f"  Executing {len(actions)} actions...")
        obs, used = execute_actions(env, actions)
        total_actions += used
        all_prefix.extend(actions[:used])

        if obs.state.name in ("WON", "WIN"):
            solved = total_levels
            print(f"  GAME WON! Total actions: {total_actions}")
            break
        elif obs.state.name in ("GAME_OVER", "LOST"):
            print(f"  DIED at level {level}")
            break
        else:
            solved = level
            print(f"  Level {level} done ({used} actions, total: {total_actions})")

    print()
    print("=" * 60)
    print(f"GAME_ID: tu93")
    print(f"LEVELS_SOLVED: {solved}")
    print(f"TOTAL_LEVELS: {total_levels}")
    print(f"MECHANICS: Maze on node graph (6px intervals). Edges = pixel value 2 in board sprite. Actions 1-4 = up/down/left/right. 3 enemy types: type1 (chase on proximity d=6), type2 (bounce patrol), type3 (delayed chase d=12). Player eats enemies when walking into them. Enemies kill player when walking into player (triple growth = instant death). Step counter limits moves.")
    print(f"KEY_LESSONS: 1) Player walking into enemy = eat enemy (safe). Enemy walking into player = death. 2) BFS with enemy state simulation. 3) Verify solutions with actual game replay. 4) Type2 enemies bounce off dead ends. 5) Graph extracted from board sprite pixel value 2 at 3px offsets.")


if __name__ == "__main__":
    main()
