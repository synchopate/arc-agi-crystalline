#!/usr/bin/env python3
"""su15 solver - Merge/matching physics game.

Strategy: gather-then-merge with enemy awareness.
- Pre-check all clicks for different-value collision risk
- Move individual fruits toward merge partners when far apart
- Merge only when fruits are close enough for 1-click merge
- Undo sparingly (penalty escalates: 2+2n steps per undo)
- L8/L9: dedicated phase-based solvers with simulation
"""
import arc_agi
import math
import copy
from collections import Counter
from universal_harness import grid_to_display, replay_solution

RADIUS = 8
MOVE_SPEED = 4
ANIM_STEPS = 4
MIN_Y = 10
MAX_Y = 63
ENEMY_TYPE_1 = "0030xjmmfvfpqm"
ENEMY_TYPE_2 = "0031xcwudgivus"
ENEMY_TYPE_3 = "0032qekmtelwqi"


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('su15')
    obs = env.reset()
    obs = env.step(6, data={"x": 0, "y": 0})
    level_solutions = {}

    print(f"su15: {obs.win_levels} levels")

    for level in range(1, obs.win_levels + 1):
        if obs.state.name != "NOT_FINISHED":
            break

        game = env._game
        print(f"\nL{level} (completed={obs.levels_completed})")

        fruits = game.lkujttxgs
        enemies = game.fezhhzhih
        win_cond = game.dsqlbvwaj
        steps = game.step_counter_ui.ccgddjelir

        fruit_vals = [game.kqywaxhmsb.get(s, 0) for s in fruits]
        print(f"  Fruits: {len(fruits)} vals={fruit_vals}")
        print(f"  Enemies: {len(enemies)}, Steps: {steps}")
        print(f"  Win cond: {win_cond}")

        if level == 8:
            solution = solve_level_8(env, game, level, level_solutions)
        elif level == 9:
            solution = solve_level_9(env, game, level, level_solutions)
        else:
            solution = solve_level(env, game, level)

        if solution is not None:
            level_solutions[level] = solution
            obs = replay_solution(env, level_solutions)
            game = env._game
            print(f"  L{level} SOLVED ({len(solution)} clicks)")
        else:
            print(f"  L{level} FAILED")
            break

    total = obs.levels_completed
    if obs.state.name == "WIN":
        total = obs.win_levels

    print(f"\n{'='*40}")
    print(f"su15 RESULT: {total}/{obs.win_levels}")
    print(f"{'='*40}")
    return total


# ─── Utilities ───────────────────────────────────────────
def sc(game, sprite):
    """Sprite center."""
    return game.jdeyppambj(sprite)

def sv(game, sprite):
    """Sprite value."""
    return game.kqywaxhmsb.get(sprite, 0)

def dist2d(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)

def total_fruit_value(game):
    return sum(2 ** sv(game, s) for s in game.lkujttxgs)

def enemy_type(game, e):
    return game.kcuphgwar.get(e, ENEMY_TYPE_1)

def click_toward(cx, cy, tx, ty, max_dist=7):
    dx, dy = tx - cx, ty - cy
    d = math.sqrt(dx*dx + dy*dy)
    if d < 0.5:
        return None
    cd = min(max_dist, d)
    return (int(cx + cd * dx / d), max(MIN_Y, min(MAX_Y - 1, int(cy + cd * dy / d))))

def parse_win_condition(win_cond):
    fruit_needs, enemy_needs = {}, {}
    if win_cond is None:
        return fruit_needs, enemy_needs
    first = win_cond[0]
    if isinstance(first, (list, tuple)):
        entries = [(str(t), int(c)) for t, c in win_cond]
    else:
        entries = [(str(first), int(win_cond[1]))]
    for ts, cnt in entries:
        if ts in (ENEMY_TYPE_1, ENEMY_TYPE_2, ENEMY_TYPE_3):
            enemy_needs[ts] = cnt
        else:
            try:
                fruit_needs[int(ts)] = cnt
            except ValueError:
                enemy_needs[ts] = cnt
    return fruit_needs, enemy_needs

def should_merge(game, fruit_needs):
    vals = Counter(sv(game, s) for s in game.lkujttxgs)
    return any(vals.get(v, 0) < c for v, c in fruit_needs.items())

def fruits_in_radius(game, cx, cy):
    """Return list of (sprite, value) within click radius of (cx,cy)."""
    result = []
    for f in game.lkujttxgs:
        if game.kcqeohsztd(cx, cy, RADIUS, f):
            result.append((f, sv(game, f)))
    return result

def is_safe_click(game, cx, cy):
    """Check if clicking at (cx,cy) won't cause different-value fruit collision."""
    attracted = fruits_in_radius(game, cx, cy)
    vals = set(v for _, v in attracted)
    return len(vals) <= 1

def find_safe_pull_point(game, fruit, target_x, target_y):
    """Find a click point that pulls 'fruit' toward (target_x, target_y)
    without attracting fruits of different values.

    Returns (click_x, click_y) or None.
    """
    fc = sc(game, fruit)
    fv = sv(game, fruit)

    # Try clicking between fruit and target at various positions
    for frac in [0.3, 0.5, 0.7, 0.2, 0.8, 0.1, 0.9]:
        cx = int(fc[0] + frac * (target_x - fc[0]))
        cy = int(fc[1] + frac * (target_y - fc[1]))
        cy = max(MIN_Y, min(MAX_Y - 1, cy))
        cx = max(0, min(63, cx))

        if not game.kcqeohsztd(cx, cy, RADIUS, fruit):
            continue

        attracted = fruits_in_radius(game, cx, cy)
        vals = set(v for _, v in attracted)
        if len(vals) <= 1:
            return (cx, cy)

    # Try clicking on the FAR side of the fruit from other fruits
    # This maximizes the chance of only catching the target fruit
    other_fruits = [f for f in game.lkujttxgs if f is not fruit and sv(game, f) != fv]
    if other_fruits:
        # Direction away from nearest different-value fruit
        nearest_other = min(other_fruits, key=lambda f: dist2d(fc, sc(game, f)))
        oc = sc(game, nearest_other)
        # Click on opposite side of fruit from the other
        dx = fc[0] - oc[0]
        dy = fc[1] - oc[1]
        dd = max(1, math.sqrt(dx*dx + dy*dy))
        for r in [6, 5, 4, 3]:
            cx = int(fc[0] + r * dx / dd)
            cy = int(fc[1] + r * dy / dd)
            cy = max(MIN_Y, min(MAX_Y - 1, cy))
            cx = max(0, min(63, cx))
            if not game.kcqeohsztd(cx, cy, RADIUS, fruit):
                continue
            attracted = fruits_in_radius(game, cx, cy)
            vals = set(v for _, v in attracted)
            if len(vals) <= 1:
                return (cx, cy)

    # Try a grid of points around the fruit
    for dx in range(-7, 8, 2):
        for dy in range(-7, 8, 2):
            cx = fc[0] + dx
            cy = fc[1] + dy
            cy = max(MIN_Y, min(MAX_Y - 1, cy))
            cx = max(0, min(63, cx))
            if not game.kcqeohsztd(cx, cy, RADIUS, fruit):
                continue
            attracted = fruits_in_radius(game, cx, cy)
            vals = set(v for _, v in attracted)
            if len(vals) <= 1:
                # Check that this click moves fruit in roughly the right direction
                dir_to_target = (target_x - fc[0], target_y - fc[1])
                dir_of_pull = (cx - fc[0], cy - fc[1])
                # Dot product should be positive
                dot = dir_to_target[0] * dir_of_pull[0] + dir_to_target[1] * dir_of_pull[1]
                if dot > 0:
                    return (cx, cy)

    return None


def estimate_enemy_threat(game):
    """How many clicks until an enemy reaches a fruit."""
    enemies = game.fezhhzhih
    fruits = game.lkujttxgs
    if not enemies or not fruits:
        return float('inf')
    min_c = float('inf')
    for e in enemies:
        ec = sc(game, e)
        et = enemy_type(game, e)
        spd = 2 if et == ENEMY_TYPE_3 else 1
        for f in fruits:
            fc = sc(game, f)
            d = dist2d(ec, fc)
            min_c = min(min_c, d / (spd * 4))
    return min_c


def compute_safe_lure(game):
    """Find a click that lures the most threatening enemy away from fruits.
    Must be in radius of enemy but NOT in radius of any fruit."""
    enemies = game.fezhhzhih
    fruits = game.lkujttxgs
    if not enemies or not fruits:
        return None

    # Find most threatening enemy
    threat_list = []
    for e in enemies:
        et = enemy_type(game, e)
        if game.dfqhmningy(et) != 1:
            continue
        ec = sc(game, e)
        nearest = min(fruits, key=lambda f: dist2d(ec, sc(game, f)))
        nfc = sc(game, nearest)
        d = dist2d(ec, nfc)
        threat_list.append((d, e, ec, nfc))
    threat_list.sort()

    for _, e, ec, nfc in threat_list:
        # Direction away from nearest fruit
        dx = ec[0] - nfc[0]
        dy = ec[1] - nfc[1]
        dd = max(1, math.sqrt(dx*dx + dy*dy))
        for r in [6, 5, 4, 3]:
            lx = int(ec[0] + r * dx / dd)
            ly = int(ec[1] + r * dy / dd)
            ly = max(MIN_Y, min(MAX_Y - 1, ly))
            lx = max(0, min(63, lx))
            if not game.kcqeohsztd(lx, ly, RADIUS, e):
                continue
            # Check no fruit in radius
            if any(game.kcqeohsztd(lx, ly, RADIUS, f) for f in fruits):
                continue
            return (lx, ly)

        # Try other directions
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            for r in [6, 5, 4]:
                lx = int(ec[0] + r * math.cos(rad))
                ly = int(ec[1] + r * math.sin(rad))
                ly = max(MIN_Y, min(MAX_Y - 1, ly))
                lx = max(0, min(63, lx))
                if not game.kcqeohsztd(lx, ly, RADIUS, e):
                    continue
                if any(game.kcqeohsztd(lx, ly, RADIUS, f) for f in fruits):
                    continue
                # Verify click moves enemy away from nearest fruit
                new_ex = ec[0] + (lx - ec[0]) * 0.5
                new_ey = ec[1] + (ly - ec[1]) * 0.5
                if dist2d((new_ex, new_ey), nfc) > dist2d(ec, nfc):
                    return (lx, ly)

    return None


def compute_lure_toward(game, enemy, target_x, target_y):
    """Find a click that lures an enemy TOWARD a specific point.
    Must be in radius of enemy, click on the side toward target."""
    ec = sc(game, enemy)
    et = enemy_type(game, enemy)
    if game.dfqhmningy(et) != 1:
        return None  # Can only lure type-1

    dx = target_x - ec[0]
    dy = target_y - ec[1]
    dd = max(1, math.sqrt(dx*dx + dy*dy))

    # Click on the side of the enemy toward the target
    for r in [6, 5, 4, 3, 7]:
        lx = int(ec[0] + r * dx / dd)
        ly = int(ec[1] + r * dy / dd)
        ly = max(MIN_Y, min(MAX_Y - 1, ly))
        lx = max(0, min(63, lx))
        if game.kcqeohsztd(lx, ly, RADIUS, enemy):
            # Check no fruit in radius
            if not any(game.kcqeohsztd(lx, ly, RADIUS, f) for f in game.lkujttxgs):
                return (lx, ly)

    # Try other angles near the target direction
    base_angle = math.atan2(dy, dx)
    for delta in [0.3, -0.3, 0.6, -0.6]:
        angle = base_angle + delta
        for r in [6, 5, 4, 3]:
            lx = int(ec[0] + r * math.cos(angle))
            ly = int(ec[1] + r * math.sin(angle))
            ly = max(MIN_Y, min(MAX_Y - 1, ly))
            lx = max(0, min(63, lx))
            if game.kcqeohsztd(lx, ly, RADIUS, enemy):
                if not any(game.kcqeohsztd(lx, ly, RADIUS, f) for f in game.lkujttxgs):
                    return (lx, ly)

    return None


def compute_lure_between_enemies(game, e1, e2):
    """Find a click that lures BOTH enemies toward each other.
    Click near midpoint. Both must be type-1 and within radius."""
    ec1 = sc(game, e1)
    ec2 = sc(game, e2)

    mid_x = (ec1[0] + ec2[0]) // 2
    mid_y = (ec1[1] + ec2[1]) // 2
    mid_y = max(MIN_Y, min(MAX_Y - 1, mid_y))

    # Check if midpoint is in radius of both
    if (game.kcqeohsztd(mid_x, mid_y, RADIUS, e1) and
        game.kcqeohsztd(mid_x, mid_y, RADIUS, e2)):
        if not any(game.kcqeohsztd(mid_x, mid_y, RADIUS, f) for f in game.lkujttxgs):
            return (mid_x, mid_y)

    # If not, try clicking near each enemy to pull toward the other
    return None


def find_neutral_click(game):
    """Find a click point that doesn't attract any fruit or enemy.
    Used when we just want to 'pass' a turn to let enemies move naturally."""
    fruits = game.lkujttxgs
    enemies = game.fezhhzhih

    # Try corners and edges first - far from everything
    candidates = [
        (3, 11), (60, 11), (3, 60), (60, 60),
        (32, 11), (3, 35), (60, 35), (32, 60),
        (16, 11), (48, 11), (16, 60), (48, 60),
    ]

    for cx, cy in candidates:
        # Check no fruit in radius
        in_fruit_radius = any(game.kcqeohsztd(cx, cy, RADIUS, f) for f in fruits)
        in_enemy_radius = any(game.kcqeohsztd(cx, cy, RADIUS, e) for e in enemies)
        if not in_fruit_radius and not in_enemy_radius:
            return (cx, cy)

    # If that fails, try a grid
    for cx in range(3, 61, 4):
        for cy in range(11, 61, 4):
            in_fruit_radius = any(game.kcqeohsztd(cx, cy, RADIUS, f) for f in fruits)
            if not in_fruit_radius:
                return (cx, cy)

    # Last resort
    return (3, 11)


def get_game_state(game):
    """Get compact state representation for hashing."""
    fruits = []
    for f in game.lkujttxgs:
        c = sc(game, f)
        v = sv(game, f)
        fruits.append((c[0], c[1], v))
    enemies = []
    for e in game.fezhhzhih:
        c = sc(game, e)
        et = enemy_type(game, e)
        enemies.append((c[0], c[1], et))
    return (tuple(sorted(fruits)), tuple(sorted(enemies)),
            game.step_counter_ui.current_steps)


def get_game_state_coarse(game):
    """Get coarse state representation (quantized positions) for hashing."""
    fruits = []
    for f in game.lkujttxgs:
        c = sc(game, f)
        v = sv(game, f)
        fruits.append((c[0]//4, c[1]//4, v))
    enemies = []
    for e in game.fezhhzhih:
        c = sc(game, e)
        et = enemy_type(game, e)
        enemies.append((c[0]//4, c[1]//4, et))
    return (tuple(sorted(fruits)), tuple(sorted(enemies)))


# ─── Level 8 dedicated solver ──────────────────────────────
def solve_level_8(env, game, level_num, level_solutions):
    """Level 8: 2x val-3 + val-5, 3 enemies. Need: 2x val-4 + type-2 enemy.

    Strategy phases:
    1. Lure enemies away from fruits immediately
    2. Merge 2x val-3 -> val-4 (they're close together at bottom-left)
    3. Merge two enemies into type-2 (lure them together)
    4. Let remaining enemy hit val-5 once -> val-4
    5. Move fruits and type-2 enemy to targets
    """
    print("  === L8 dedicated solver ===")

    # Use greedy simulation approach
    from collections import deque

    # Try strategy 0 (merge first, then enemy merge, then hit, then place)
    solution = l8_strategy_merge_first(env, game, level_num)
    if solution is not None:
        return solution

    # Fallback strategies
    for strategy_id in [1, 2, 3]:
        obs = replay_solution(env, level_solutions)
        game = env._game

        try:
            if strategy_id == 1:
                solution = l8_strategy_lure_first(env, game, level_num)
            elif strategy_id == 2:
                solution = l8_strategy_enemy_merge_first(env, game, level_num)
            elif strategy_id == 3:
                solution = l8_strategy_aggressive(env, game, level_num)
        except Exception as e:
            print(f"  Strategy {strategy_id} error: {e}")
            solution = None

        if solution is not None:
            print(f"  Strategy {strategy_id} succeeded: {len(solution)} clicks")
            return solution

    # Fallback: BFS with coarse grid
    print("  Trying BFS fallback for L8...")
    obs = replay_solution(env, level_solutions)
    game = env._game
    return l8_bfs(env, game, level_num, level_solutions)


def l8_do_click(env, game, clicks, x, y, level_num):
    """Execute click and return (obs, game, won)."""
    clicks.append((x, y))
    obs = env.step(6, data={"x": x, "y": y})
    game = env._game
    won = obs.levels_completed >= level_num
    return obs, game, won


def l8_strategy_merge_first(env, game, level_num):
    """Strategy: lure ALL enemies to safe corners first, then merge val-3 pair.

    L8 layout:
    - Fruits: val-3 at (15,44), val-3 at (5,42), val-5 at (23,27)
    - Enemies at: (45,33), (31,55), (49,50) - all type-1
    - Targets at: (56,19), (7,19), (56,55), (7,55) (9x9 circles)
    - Need: 2x val-4 in targets + 1 type-2 enemy in target

    Phase 1: Lure all 3 enemies away from fruits (to top corners)
    Phase 2: Merge val-3 pair -> val-4
    Phase 3: Merge 2 enemies -> type-2 (lure toward each other)
    Phase 4: Let remaining enemy hit val-5 once -> val-4
    Phase 5: Move fruits + type-2 enemy to targets
    """
    clicks = []
    max_clicks = 45

    for step in range(max_clicks):
        game = env._game
        fruits = game.lkujttxgs
        enemies = game.fezhhzhih
        remaining = game.step_counter_ui.current_steps

        if remaining <= 0 or not fruits:
            return None
        if game.cbdhpcilgb():
            return clicks

        fruit_vals = {f: sv(game, f) for f in fruits}
        val_list = list(fruit_vals.values())
        enemy_types_map = {e: enemy_type(game, e) for e in enemies}

        fruit_needs, enemy_needs = parse_win_condition(game.dsqlbvwaj)
        targets = game.powykypsm

        if step < 5 or step % 5 == 0:
            et_counts = Counter(enemy_types_map.values())
            print(f"    s{step}: vals={val_list} enemies={dict(et_counts)} steps={remaining}")

        val_counts = Counter(val_list)

        # Determine what's still needed
        fruits_satisfied = all(val_counts.get(v, 0) >= c for v, c in fruit_needs.items())
        need_merge = should_merge(game, fruit_needs)

        type2_enemies = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_2]
        type1_enemies = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_1]
        need_type2 = ENEMY_TYPE_2 in enemy_needs and len(type2_enemies) < enemy_needs.get(ENEMY_TYPE_2, 0)

        # Check if we need enemy hit on val-5
        need_hit = False
        for needed_val, cnt in fruit_needs.items():
            if val_counts.get(needed_val, 0) < cnt:
                higher = [f for f in fruits if fruit_vals[f] > needed_val]
                if higher:
                    need_hit = True

        # PHASE 1: Early game - lure enemies away from fruits before any merging
        if step < 6 and enemies:
            threat = estimate_enemy_threat(game)
            if threat < 15:
                lure = compute_safe_lure(game)
                if lure:
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

        # PHASE 2: Merge val-3 pair -> val-4 (check for collision protection)
        if need_merge:
            pairs = find_pairs(game)
            if pairs:
                # Check if enemies are threatening - if so, undo and lure first
                click = pick_best_action(game, pairs, fruit_needs, len(enemies) > 0, targets)
                if click:
                    prev_total = total_fruit_value(game)
                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                    if won: return clicks
                    # Check for collateral damage
                    new_total = total_fruit_value(env._game)
                    if new_total < prev_total and remaining > 8:
                        # Undo and try luring first
                        env.step(7)
                        clicks.pop()
                        game = env._game
                        lure = compute_safe_lure(game)
                        if lure:
                            obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                            if won: return clicks
                    continue
            # need_merge is True but no pairs - need enemy hit to get val down
            # Fall through to Phase 3/4

        # PHASE 3: Enemy merging for type-2
        if need_type2 and len(type1_enemies) >= 2:
            # Pick the two closest type-1 enemies
            best_pair = None
            best_d = float('inf')
            for i in range(len(type1_enemies)):
                for j in range(i+1, len(type1_enemies)):
                    d = dist2d(sc(game, type1_enemies[i]), sc(game, type1_enemies[j]))
                    if d < best_d:
                        best_d = d
                        best_pair = (type1_enemies[i], type1_enemies[j])

            if best_pair:
                e1, e2 = best_pair
                ec1, ec2 = sc(game, e1), sc(game, e2)
                print(f"    Merging enemies: d={dist2d(ec1, ec2):.0f} at {ec1}, {ec2}")

                mid = compute_lure_between_enemies(game, e1, e2)
                if mid:
                    print(f"    -> midpoint lure at {mid}")
                    obs, game, won = l8_do_click(env, game, clicks, mid[0], mid[1], level_num)
                    if won: return clicks
                    continue

                lure = compute_lure_toward(game, e1, ec2[0], ec2[1])
                if lure:
                    print(f"    -> lure e1 toward e2 at {lure}")
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

                lure = compute_lure_toward(game, e2, ec1[0], ec1[1])
                if lure:
                    print(f"    -> lure e2 toward e1 at {lure}")
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

                # Can't lure directly, enemies chasing fruits.
                # Click on the ENEMY itself (within its sprite bounds)
                # to attract it toward the click direction
                print(f"    -> no safe lure found, trying direct enemy click")
                # Try clicking at a point near the enemy, even if it's in fruit radius
                for e, other_e in [(e1, e2), (e2, e1)]:
                    ec = sc(game, e)
                    oec = sc(game, other_e)
                    dx = oec[0] - ec[0]
                    dy = oec[1] - ec[1]
                    dd = max(1, math.sqrt(dx*dx + dy*dy))
                    for r in [6, 5, 4, 3, 7]:
                        lx = int(ec[0] + r * dx / dd)
                        ly = int(ec[1] + r * dy / dd)
                        ly = max(MIN_Y, min(MAX_Y - 1, ly))
                        lx = max(0, min(63, lx))
                        if game.kcqeohsztd(lx, ly, RADIUS, e):
                            obs, game, won = l8_do_click(env, game, clicks, lx, ly, level_num)
                            if won: return clicks
                            break
                    else:
                        continue
                    break
                else:
                    # Last resort: neutral click to let enemies chase naturally
                    obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                    if won: return clicks
            else:
                obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                if won: return clicks
            continue

        # PHASE 3b: Fruits are ready - URGENTLY move to targets
        # The type-2 enemy will chase into target naturally (win via same-frame trick)
        if not need_merge and not need_hit:
            # Lure type-1 enemy away from fruits first if threatening (max 2 lures)
            did_lure = False
            if type1_enemies and step < 20:
                for e in type1_enemies:
                    et = enemy_types_map.get(e)
                    if game.dfqhmningy(et) == 1:
                        ec = sc(game, e)
                        min_fd = min(dist2d(ec, sc(game, f)) for f in fruits)
                        if min_fd < 10:
                            lure = compute_safe_lure(game)
                            if lure:
                                print(f"    -> protective lure type-1 at {lure}")
                                obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                                if won: return clicks
                                did_lure = True
                                break
            if did_lure:
                continue

            # Check: which targets are closest to the type-2 enemy?
            # Move one val-4 fruit to a target NEAR the type-2 enemy (bait)
            # Move the other val-4 fruit to a target FAR from enemies
            val4_fruits = [f for f in fruits if sv(game, f) == 4]

            if type2_enemies and val4_fruits:
                e2 = type2_enemies[0]
                e2c = sc(game, e2)

                # Sort targets by distance to type-2 enemy
                sorted_targets = sorted(targets, key=lambda t: dist2d(e2c, (t.x + t.width//2, t.y + t.height//2)))
                bait_target = sorted_targets[0]  # Nearest to type-2
                safe_targets = sorted_targets[1:]  # Far from type-2

                # Check which fruits are already in targets
                for f in val4_fruits:
                    fc = sc(game, f)
                    in_bait = (bait_target.x <= fc[0] < bait_target.x + bait_target.width and
                              bait_target.y <= fc[1] < bait_target.y + bait_target.height)
                    in_safe = any(t.x <= fc[0] < t.x + t.width and t.y <= fc[1] < t.y + t.height for t in safe_targets)

                # Assign: one fruit to bait target, one to safe target
                # Move the one closest to the safe target there first
                f_bait = min(val4_fruits, key=lambda f: dist2d(sc(game, f), (bait_target.x + bait_target.width//2, bait_target.y + bait_target.height//2)))
                f_safe = [f for f in val4_fruits if f is not f_bait]
                if f_safe:
                    f_safe = f_safe[0]
                    fsc = sc(game, f_safe)
                    # Move safe fruit first (to a far target)
                    safe_t = min(safe_targets, key=lambda t: dist2d(fsc, (t.x + t.width//2, t.y + t.height//2)))
                    stc = (safe_t.x + safe_t.width//2, safe_t.y + safe_t.height//2)
                    in_safe = safe_t.x <= fsc[0] < safe_t.x + safe_t.width and safe_t.y <= fsc[1] < safe_t.y + safe_t.height

                    if not in_safe:
                        click = find_safe_pull_point(game, f_safe, stc[0], stc[1])
                        if not click:
                            click = click_toward(fsc[0], fsc[1], stc[0], stc[1])
                        if click:
                            print(f"    -> moving safe fruit to far target at {click}")
                            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                            if won: return clicks
                            continue

                # Now move bait fruit toward bait target (near type-2)
                fbc = sc(game, f_bait)
                btc = (bait_target.x + bait_target.width//2, bait_target.y + bait_target.height//2)
                in_bait = bait_target.x <= fbc[0] < bait_target.x + bait_target.width and bait_target.y <= fbc[1] < bait_target.y + bait_target.height
                if not in_bait:
                    click = find_safe_pull_point(game, f_bait, btc[0], btc[1])
                    if not click:
                        click = click_toward(fbc[0], fbc[1], btc[0], btc[1])
                    if click:
                        print(f"    -> moving bait fruit to near target at {click}")
                        obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                        if won: return clicks
                        continue

            # Generic fallback
            click = move_needed_to_target(game, fruit_needs, targets)
            if click:
                obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                if won: return clicks
                continue

            click = move_highest_to_target(game, targets)
            if click:
                obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                if won: return clicks
            else:
                obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                if won: return clicks
            continue

        # PHASE 4: Need enemy to hit val-5 -> val-4
        if need_hit:
            for needed_val, cnt in fruit_needs.items():
                if val_counts.get(needed_val, 0) >= cnt:
                    continue
                higher = [f for f in fruits if fruit_vals[f] > needed_val]
                if higher and enemies:
                    hf = min(higher, key=lambda f: fruit_vals[f])
                    hc = sc(game, hf)
                    # Pick a type-1 enemy if possible (we can lure it)
                    lurable = [e for e in enemies if game.dfqhmningy(enemy_types_map.get(e, ENEMY_TYPE_1)) == 1]
                    if lurable:
                        ne = min(lurable, key=lambda e: dist2d(sc(game, e), hc))
                    else:
                        ne = min(enemies, key=lambda e: dist2d(sc(game, e), hc))
                    nec = sc(game, ne)
                    d = dist2d(nec, hc)
                    print(f"    Hit phase: fruit val={fruit_vals[hf]} at {hc}, enemy at {nec}, d={d:.1f}")

                    if d > 5:
                        lure = compute_lure_toward(game, ne, hc[0], hc[1])
                        if lure:
                            print(f"    -> luring enemy toward fruit at {lure}")
                            obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                        else:
                            print(f"    -> no lure, clicking safe neutral")
                            safe = find_neutral_click(game)
                            obs, game, won = l8_do_click(env, game, clicks, safe[0], safe[1], level_num)
                    else:
                        print(f"    -> enemy close, waiting")
                        safe = find_neutral_click(game)
                        obs, game, won = l8_do_click(env, game, clicks, safe[0], safe[1], level_num)
                    if won: return clicks
                    break
            continue

        # PHASE 5: Lure threatening enemies away while moving to targets
        threat = estimate_enemy_threat(game)
        if threat < 5 and remaining > 8:
            lure = compute_safe_lure(game)
            if lure:
                obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                if won: return clicks
                continue

        # Move type-2 enemy to target if needed
        if enemy_needs:
            for etype, cnt in enemy_needs.items():
                type_es = [e for e in enemies if enemy_types_map.get(e) == etype]
                if len(type_es) >= cnt:
                    for e in type_es[:cnt]:
                        ec = sc(game, e)
                        in_t = any(t.x <= ec[0] < t.x + t.width and t.y <= ec[1] < t.y + t.height for t in targets)
                        if not in_t:
                            et = enemy_types_map.get(e)
                            if game.dfqhmningy(et) == 1:
                                best_t = min(targets, key=lambda t: dist2d(ec, (t.x + t.width//2, t.y + t.height//2)))
                                tc = (best_t.x + best_t.width//2, best_t.y + best_t.height//2)
                                lure = compute_lure_toward(game, e, tc[0], tc[1])
                                if lure:
                                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                                    if won: return clicks
                                    break
                            else:
                                # Type-2+ can't be lured, use fruit bait
                                # Move a fruit toward the target center, enemy will chase
                                best_t = min(targets, key=lambda t: dist2d(ec, (t.x + t.width//2, t.y + t.height//2)))
                                tc = (best_t.x + best_t.width//2, best_t.y + best_t.height//2)
                                nf = min(fruits, key=lambda f: dist2d(sc(game, f), ec))
                                click = click_toward(sc(game, nf)[0], sc(game, nf)[1], tc[0], tc[1])
                                if click:
                                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                                    if won: return clicks
                                    break

        # Move fruits to targets
        click = move_needed_to_target(game, fruit_needs, targets)
        if click:
            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
            if won: return clicks
            continue

        # Fallback
        click = move_highest_to_target(game, targets)
        if click:
            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
            if won: return clicks
        else:
            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
            if won: return clicks

    return None


def l8_strategy_lure_first(env, game, level_num):
    """Strategy: lure enemies away first, then merge safely."""
    clicks = []

    # First lure all enemies to corners
    for lure_round in range(4):
        game = env._game
        fruits = game.lkujttxgs
        enemies = game.fezhhzhih
        if not enemies:
            break

        lure = compute_safe_lure(game)
        if lure:
            obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
            if won: return clicks
        else:
            break

    # Now run merge_first strategy
    remaining_clicks = l8_strategy_merge_first(env, env._game, level_num)
    if remaining_clicks is not None:
        return clicks + remaining_clicks
    return None


def l8_strategy_enemy_merge_first(env, game, level_num):
    """Strategy: merge enemies first (to get type-2), then handle fruits."""
    clicks = []
    max_clicks = 45

    for step in range(max_clicks):
        game = env._game
        fruits = game.lkujttxgs
        enemies = game.fezhhzhih
        remaining = game.step_counter_ui.current_steps

        if remaining <= 0 or not fruits:
            return None
        if game.cbdhpcilgb():
            return clicks

        fruit_needs, enemy_needs = parse_win_condition(game.dsqlbvwaj)
        targets = game.powykypsm
        enemy_types_map = {e: enemy_type(game, e) for e in enemies}

        # Priority: get the type-2 enemy first
        type2_enemies = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_2]
        type1_enemies = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_1]

        if ENEMY_TYPE_2 in enemy_needs and len(type2_enemies) < enemy_needs[ENEMY_TYPE_2]:
            # Need to merge type-1 enemies
            if len(type1_enemies) >= 2:
                e1, e2 = type1_enemies[0], type1_enemies[1]
                ec1, ec2 = sc(game, e1), sc(game, e2)
                d = dist2d(ec1, ec2)

                # Try midpoint click
                mid = compute_lure_between_enemies(game, e1, e2)
                if mid:
                    obs, game, won = l8_do_click(env, game, clicks, mid[0], mid[1], level_num)
                    if won: return clicks
                    continue

                # Lure one toward the other
                lure = compute_lure_toward(game, e1, ec2[0], ec2[1])
                if lure:
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

                lure = compute_lure_toward(game, e2, ec1[0], ec1[1])
                if lure:
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

                # Click neutral
                obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                if won: return clicks
                continue

        # Once we have type-2, continue with normal strategy
        return _finish_l8_fruits(env, game, clicks, level_num, fruit_needs, enemy_needs, targets)

    return None


def _finish_l8_fruits(env, game, clicks, level_num, fruit_needs, enemy_needs, targets):
    """After enemy is handled, do fruit merging and placement."""
    max_clicks = 45 - len(clicks)

    for step in range(max_clicks):
        game = env._game
        fruits = game.lkujttxgs
        enemies = game.fezhhzhih
        remaining = game.step_counter_ui.current_steps

        if remaining <= 0 or not fruits:
            return None
        if game.cbdhpcilgb():
            return clicks

        fruit_needs, enemy_needs = parse_win_condition(game.dsqlbvwaj)
        targets = game.powykypsm
        val_list = [sv(game, f) for f in fruits]

        # Check if we still need merging
        need_merge = should_merge(game, fruit_needs)

        if need_merge:
            pairs = find_pairs(game)
            if pairs:
                click = pick_best_action(game, pairs, fruit_needs, len(enemies) > 0, targets)
                if click:
                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                    if won: return clicks
                    continue

        # Check if enemy needs to hit a fruit
        for needed_val, cnt in fruit_needs.items():
            current = sum(1 for v in val_list if v == needed_val)
            if current < cnt:
                higher = [f for f in fruits if sv(game, f) > needed_val]
                if higher and enemies:
                    hf = min(higher, key=lambda f: sv(game, f))
                    hc = sc(game, hf)
                    ne = min(enemies, key=lambda e: dist2d(sc(game, e), hc))
                    nec = sc(game, ne)
                    d = dist2d(nec, hc)

                    if d > 3:
                        lure = compute_lure_toward(game, ne, hc[0], hc[1])
                        if lure:
                            obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                            if won: return clicks
                        else:
                            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                            if won: return clicks
                    else:
                        obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                        if won: return clicks
                    break

        # Move stuff to targets
        # Move needed enemy to target first if we have it
        if enemy_needs:
            for etype, cnt in enemy_needs.items():
                type_enemies = [e for e in enemies if enemy_type(game, e) == etype]
                if len(type_enemies) >= cnt:
                    for e in type_enemies:
                        ec = sc(game, e)
                        in_t = any(t.x <= ec[0] < t.x + t.width and t.y <= ec[1] < t.y + t.height for t in targets)
                        if not in_t:
                            et = enemy_type(game, e)
                            if game.dfqhmningy(et) == 1:
                                best_t = min(targets, key=lambda t: dist2d(ec, (t.x + t.width//2, t.y + t.height//2)))
                                tc = (best_t.x + best_t.width//2, best_t.y + best_t.height//2)
                                lure = compute_lure_toward(game, e, tc[0], tc[1])
                                if lure:
                                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                                    if won: return clicks
                                    break

        # Move fruits to targets
        click = move_needed_to_target(game, fruit_needs, targets)
        if click:
            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
            if won: return clicks
            continue

        click = move_highest_to_target(game, targets)
        if click:
            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
            if won: return clicks
        else:
            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
            if won: return clicks

    return None


def l8_strategy_aggressive(env, game, level_num):
    """Strategy: try to do everything in parallel, accept some risk."""
    clicks = []
    max_clicks = 45

    for step in range(max_clicks):
        game = env._game
        fruits = game.lkujttxgs
        enemies = game.fezhhzhih
        remaining = game.step_counter_ui.current_steps

        if remaining <= 0 or not fruits:
            return None
        if game.cbdhpcilgb():
            return clicks

        fruit_needs, enemy_needs = parse_win_condition(game.dsqlbvwaj)
        targets = game.powykypsm
        val_list = [sv(game, f) for f in fruits]
        enemy_types_map = {e: enemy_type(game, e) for e in enemies}

        if step < 3 or step % 5 == 0:
            et_counts = Counter(enemy_types_map.values())
            print(f"    agg s{step}: vals={val_list} enemy_types={dict(et_counts)} steps={remaining}")

        # Determine what's still needed
        val_counts = Counter(val_list)
        fruits_done = all(val_counts.get(v, 0) >= c for v, c in fruit_needs.items())

        type2_enemies = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_2]
        need_type2 = ENEMY_TYPE_2 in enemy_needs and len(type2_enemies) < enemy_needs.get(ENEMY_TYPE_2, 0)

        need_hit = not fruits_done and any(
            val_counts.get(v, 0) < c and any(sv(game, f) > v for f in fruits)
            for v, c in fruit_needs.items()
        )

        need_merge = not fruits_done and should_merge(game, fruit_needs)

        # Priority actions
        if need_merge:
            pairs = find_pairs(game)
            if pairs:
                click = pick_best_action(game, pairs, fruit_needs, len(enemies) > 0, targets)
                if click:
                    prev_total = total_fruit_value(game)
                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                    if won: return clicks
                    # Check for enemy damage
                    new_total = total_fruit_value(env._game)
                    if new_total < prev_total and remaining > 6:
                        # Undo
                        env.step(7)
                        clicks.pop()
                        # Try luring enemy away first
                        game = env._game
                        lure = compute_safe_lure(game)
                        if lure:
                            obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                            if won: return clicks
                    continue

        if need_hit:
            for needed_val, cnt in fruit_needs.items():
                if val_counts.get(needed_val, 0) >= cnt:
                    continue
                higher = [f for f in fruits if sv(game, f) > needed_val]
                if higher and enemies:
                    hf = min(higher, key=lambda f: sv(game, f))
                    hc = sc(game, hf)
                    ne = min(enemies, key=lambda e: dist2d(sc(game, e), hc))
                    nec = sc(game, ne)
                    d = dist2d(nec, hc)

                    if d > 5:
                        lure = compute_lure_toward(game, ne, hc[0], hc[1])
                        if lure:
                            obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                            if won: return clicks
                        else:
                            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                            if won: return clicks
                    else:
                        obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                        if won: return clicks
                    break
            continue

        if need_type2:
            type1_enemies = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_1]
            if len(type1_enemies) >= 2:
                e1, e2 = type1_enemies[0], type1_enemies[1]
                ec1, ec2 = sc(game, e1), sc(game, e2)

                mid = compute_lure_between_enemies(game, e1, e2)
                if mid:
                    obs, game, won = l8_do_click(env, game, clicks, mid[0], mid[1], level_num)
                    if won: return clicks
                    continue

                lure = compute_lure_toward(game, e1, ec2[0], ec2[1])
                if lure:
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

                lure = compute_lure_toward(game, e2, ec1[0], ec1[1])
                if lure:
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

                obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                if won: return clicks
                continue

        # Everything is prepared, just move to targets
        # Lure enemies away from fruits if threatening
        threat = estimate_enemy_threat(game)
        if threat < 5 and remaining > 10:
            lure = compute_safe_lure(game)
            if lure:
                obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                if won: return clicks
                continue

        # Move enemy to target if needed
        if enemy_needs:
            for etype, cnt in enemy_needs.items():
                type_enemies = [e for e in enemies if enemy_types_map.get(e) == etype]
                if len(type_enemies) >= cnt:
                    for e in type_enemies[:cnt]:
                        ec = sc(game, e)
                        in_t = any(t.x <= ec[0] < t.x + t.width and t.y <= ec[1] < t.y + t.height for t in targets)
                        if not in_t:
                            et = enemy_type(game, e)
                            if game.dfqhmningy(et) == 1:
                                best_t = min(targets, key=lambda t: dist2d(ec, (t.x + t.width//2, t.y + t.height//2)))
                                tc = (best_t.x + best_t.width//2, best_t.y + best_t.height//2)
                                lure = compute_lure_toward(game, e, tc[0], tc[1])
                                if lure:
                                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                                    if won: return clicks
                                    break
                            else:
                                # Type 2+ can't be lured, need to use fruit as bait
                                # Move a fruit toward the target so enemy follows
                                if fruits:
                                    # Pick a fruit we DON'T need or one that's expendable
                                    expendable = [f for f in fruits if sv(game, f) not in fruit_needs]
                                    if not expendable:
                                        expendable = list(fruits)
                                    nf = min(expendable, key=lambda f: dist2d(sc(game, f), ec))
                                    best_t = min(targets, key=lambda t: dist2d(ec, (t.x + t.width//2, t.y + t.height//2)))
                                    click = move_to_target(game, nf, [best_t])
                                    if click:
                                        obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                                        if won: return clicks
                                        break
                    continue

        # Move fruits to targets
        click = move_needed_to_target(game, fruit_needs, targets)
        if click:
            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
            if won: return clicks
            continue

        click = move_highest_to_target(game, targets)
        if click:
            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
            if won: return clicks
        else:
            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
            if won: return clicks

    return None


def l8_bfs(env, game, level_num, level_solutions):
    """BFS fallback for L8 with coarse click grid."""
    from collections import deque

    # Generate click coordinates - coarse 8x8 grid in the play area
    click_coords = []
    for x in range(4, 64, 8):
        for y in range(12, 60, 8):
            click_coords.append((x, y))

    print(f"  BFS with {len(click_coords)} click positions")

    solution, obs = bfs_solve_custom(env, level_solutions, click_coords, level_num,
                                      max_depth=20, max_states=50000)
    return solution


def bfs_solve_custom(env, level_solutions, click_coords, level, max_depth=20, max_states=50000):
    """Custom BFS with state hashing."""
    from collections import deque

    n = len(click_coords)
    replay_solution(env, level_solutions)
    game = env._game
    init_hash = get_game_state_coarse(game)

    visited = {init_hash}
    queue = deque([[]])
    explored = 0

    while queue:
        moves = queue.popleft()
        if len(moves) >= max_depth:
            continue

        for ci in range(n):
            new_moves = moves + [ci]

            replay_solution(env, level_solutions)
            obs = None
            for c in new_moves:
                obs = env.step(6, data={"x": click_coords[c][0], "y": click_coords[c][1]})
                if obs.levels_completed >= level:
                    solution = [click_coords[m] for m in new_moves]
                    print(f"  BFS SOLVED! {len(new_moves)} clicks ({explored} states)")
                    return solution, obs

            game = env._game
            h = get_game_state_coarse(game)
            if h not in visited:
                visited.add(h)
                queue.append(new_moves)
                explored += 1

                if explored % 1000 == 0:
                    print(f"  ... {explored} states, depth={len(new_moves)}, queue={len(queue)}")

                if explored >= max_states:
                    print(f"  BFS limit reached ({max_states} states)")
                    return None, None

    print(f"  BFS FAILED ({explored} states)")
    return None, None


# ─── Level 9 dedicated solver ──────────────────────────────
def solve_level_9(env, game, level_num, level_solutions):
    """Level 9: 2x val-1 + val-5, 4 enemies. Need: val-4 + type-3 enemy + val-2.

    Strategy:
    1. Merge val-1 pair -> val-2
    2. Merge 2 type-1 enemies -> type-2 (x2 pairs = 2x type-2)
    3. Merge 2 type-2 -> type-3
    4. Enemy hit val-5 -> val-4
    5. Place val-4, val-2, type-3 in targets
    """
    print("  === L9 dedicated solver ===")

    # Try strategies sequentially, return first success
    for strategy_id in range(4):
        if strategy_id > 0:
            obs = replay_solution(env, level_solutions)
            game = env._game

        try:
            if strategy_id == 0:
                solution = l9_strategy_fruits_then_enemies(env, game, level_num)
            elif strategy_id == 1:
                solution = l9_strategy_enemies_then_fruits(env, game, level_num)
            elif strategy_id == 2:
                solution = l9_strategy_parallel(env, game, level_num)
            elif strategy_id == 3:
                solution = l9_strategy_alt(env, game, level_num)
        except Exception as e:
            print(f"  L9 Strategy {strategy_id} error: {e}")
            import traceback
            traceback.print_exc()
            solution = None

        if solution is not None:
            print(f"  L9 Strategy {strategy_id} succeeded: {len(solution)} clicks")
            return solution

    return None


def l9_strategy_fruits_then_enemies(env, game, level_num):
    """L9: Merge fruits first, protect val-2, then enemy merging.

    L9 layout:
    - Fruits: val-1 at (19,47), val-1 at (24,53), val-5 at (38,51) - all bottom
    - Enemies at: (53,15), (16,14), (17,24), (56,35) - all type-1, mostly top
    - Targets at: (11,41), (53,55), (11,55) - 3 target zones
    - Need: 1x val-4, 1x type-3, 1x val-2

    Strategy:
    1. Merge val-1 pair -> val-2 FAST (they're close)
    2. Move val-2 to a safe target IMMEDIATELY (away from enemies)
    3. Merge enemy pairs: (16,14)+(17,24) = close pair, (53,15)+(56,35) = second pair
    4. Merge type-2 pair into type-3 (use val-5 as bait to lure them together)
    5. During merging, val-5 gets hit -> val-4 naturally
    6. Place everything in targets
    """
    clicks = []
    max_clicks = 45

    for step in range(max_clicks):
        game = env._game
        fruits = game.lkujttxgs
        enemies = game.fezhhzhih
        remaining = game.step_counter_ui.current_steps

        if remaining <= 0 or not fruits:
            return None
        if game.cbdhpcilgb():
            return clicks

        fruit_needs, enemy_needs = parse_win_condition(game.dsqlbvwaj)
        targets = game.powykypsm
        val_list = [sv(game, f) for f in fruits]
        enemy_types_map = {e: enemy_type(game, e) for e in enemies}
        val_counts = Counter(val_list)

        type1s = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_1]
        type2s = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_2]
        type3s = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_3]

        if step < 5 or step % 5 == 0:
            et_counts = Counter(enemy_types_map.values())
            print(f"    L9 s{step}: vals={val_list} t1={len(type1s)} t2={len(type2s)} t3={len(type3s)} steps={remaining}")

        need_merge = should_merge(game, fruit_needs)
        need_type3 = ENEMY_TYPE_3 in enemy_needs and len(type3s) < enemy_needs.get(ENEMY_TYPE_3, 0)

        # Check if we need enemy hit
        need_hit = False
        for needed_val, cnt in fruit_needs.items():
            if val_counts.get(needed_val, 0) < cnt:
                higher = [f for f in fruits if sv(game, f) > needed_val]
                if higher:
                    need_hit = True

        # Check fruits_ready (we have all needed fruit values)
        fruits_ready = all(val_counts.get(v, 0) >= c for v, c in fruit_needs.items())

        # PHASE 1: Merge val-1 pair -> val-2
        if need_merge:
            pairs = find_pairs(game)
            if pairs:
                click = pick_best_action(game, pairs, fruit_needs, len(enemies) > 0, targets)
                if click:
                    prev_total = total_fruit_value(game)
                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                    if won: return clicks
                    new_total = total_fruit_value(env._game)
                    if new_total < prev_total and remaining > 8:
                        env.step(7)
                        clicks.pop()
                        game = env._game
                        lure = compute_safe_lure(game)
                        if lure:
                            obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                            if won: return clicks
                    continue
            # Fall through if no pairs (need hit)

        # PHASE 2: Move val-2 to safety (a target far from enemies) if we have it
        val2_fruits = [f for f in fruits if sv(game, f) == 2]
        moved_val2 = False
        if val2_fruits and (need_type3 or need_hit):
            for f in val2_fruits:
                fc = sc(game, f)
                in_target = any(t.x <= fc[0] < t.x + t.width and t.y <= fc[1] < t.y + t.height for t in targets)
                if not in_target:
                    if enemies:
                        def target_safety(t):
                            tc = (t.x + t.width//2, t.y + t.height//2)
                            return min(dist2d(tc, sc(game, e)) for e in enemies)
                        safest = max(targets, key=target_safety)
                    else:
                        safest = targets[0]
                    stc = (safest.x + safest.width//2, safest.y + safest.height//2)
                    click = find_safe_pull_point(game, f, stc[0], stc[1])
                    if not click:
                        click = click_toward(fc[0], fc[1], stc[0], stc[1])
                    if click:
                        print(f"    -> moving val-2 to safe target at {click}")
                        obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                        if won: return clicks
                        moved_val2 = True
                        break
        if moved_val2:
            continue

        # PHASE 3: Enemy merging (type-1 -> type-2 -> type-3)
        if need_type3:
            if len(type1s) >= 2:
                # Pick closest pair
                best_pair = None
                best_d = float('inf')
                for i in range(len(type1s)):
                    for j in range(i+1, len(type1s)):
                        d = dist2d(sc(game, type1s[i]), sc(game, type1s[j]))
                        if d < best_d:
                            best_d = d
                            best_pair = (type1s[i], type1s[j])

                if best_pair:
                    e1, e2 = best_pair
                    ec1, ec2 = sc(game, e1), sc(game, e2)
                    print(f"    -> merge t1 pair d={best_d:.0f} at {ec1}, {ec2}")

                    mid = compute_lure_between_enemies(game, e1, e2)
                    if mid:
                        obs, game, won = l8_do_click(env, game, clicks, mid[0], mid[1], level_num)
                        if won: return clicks
                        continue

                    lure = compute_lure_toward(game, e1, ec2[0], ec2[1])
                    if lure:
                        obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                        if won: return clicks
                        continue

                    lure = compute_lure_toward(game, e2, ec1[0], ec1[1])
                    if lure:
                        obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                        if won: return clicks
                        continue

                    # Force: click on enemy even if in fruit radius
                    for e, oe in [(e1, e2), (e2, e1)]:
                        ec = sc(game, e)
                        oec = sc(game, oe)
                        dx = oec[0] - ec[0]
                        dy = oec[1] - ec[1]
                        dd = max(1, math.sqrt(dx*dx + dy*dy))
                        for r in [6, 5, 4, 3, 7]:
                            lx = int(ec[0] + r * dx / dd)
                            ly = int(ec[1] + r * dy / dd)
                            ly = max(MIN_Y, min(MAX_Y - 1, ly))
                            lx = max(0, min(63, lx))
                            if game.kcqeohsztd(lx, ly, RADIUS, e):
                                obs, game, won = l8_do_click(env, game, clicks, lx, ly, level_num)
                                if won: return clicks
                                break
                        else:
                            continue
                        break
                    else:
                        obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                        if won: return clicks
                    continue

            elif len(type2s) >= 2:
                # Merge type-2 pair -> type-3
                # Type-2 can't be lured, they chase nearest fruit
                e1, e2 = type2s[0], type2s[1]
                ec1, ec2 = sc(game, e1), sc(game, e2)
                d = dist2d(ec1, ec2)
                print(f"    -> merge t2 pair d={d:.0f} at {ec1}, {ec2}")

                if d < 8:
                    # Very close, just wait for them to overlap
                    obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                    if won: return clicks
                    continue

                # Use fruit as bait - move nearest fruit to midpoint
                mid_x = (ec1[0] + ec2[0]) // 2
                mid_y = max(MIN_Y, min(MAX_Y - 1, (ec1[1] + ec2[1]) // 2))

                # Use val-5/val-4 as bait (not val-2!)
                non_val2 = [f for f in fruits if sv(game, f) != 2]
                if non_val2:
                    bait = min(non_val2, key=lambda f: dist2d(sc(game, f), (mid_x, mid_y)))
                else:
                    bait = min(fruits, key=lambda f: dist2d(sc(game, f), (mid_x, mid_y)))
                bc = sc(game, bait)

                click = find_safe_pull_point(game, bait, mid_x, mid_y)
                if not click:
                    click = click_toward(bc[0], bc[1], mid_x, mid_y)
                if click:
                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                    if won: return clicks
                    continue

                obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                if won: return clicks
                continue

            elif len(type2s) == 1 and len(type1s) >= 2:
                # Need another type-2 from remaining type-1 pair
                e1, e2 = type1s[0], type1s[1]
                ec1, ec2 = sc(game, e1), sc(game, e2)
                print(f"    -> need 2nd type-2, merge t1 d={dist2d(ec1,ec2):.0f}")

                mid = compute_lure_between_enemies(game, e1, e2)
                if mid:
                    obs, game, won = l8_do_click(env, game, clicks, mid[0], mid[1], level_num)
                    if won: return clicks
                    continue

                lure = compute_lure_toward(game, e1, ec2[0], ec2[1])
                if not lure:
                    lure = compute_lure_toward(game, e2, ec1[0], ec1[1])
                if lure:
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

                obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                if won: return clicks
                continue

        # PHASE 4: Need enemy to hit val-5 -> val-4
        if need_hit and not need_merge:
            for needed_val, cnt in fruit_needs.items():
                if val_counts.get(needed_val, 0) >= cnt:
                    continue
                higher = [f for f in fruits if sv(game, f) > needed_val]
                if higher and enemies:
                    hf = min(higher, key=lambda f: sv(game, f))
                    hc = sc(game, hf)
                    ne = min(enemies, key=lambda e: dist2d(sc(game, e), hc))
                    nec = sc(game, ne)
                    d = dist2d(nec, hc)
                    print(f"    -> hit: fruit val={sv(game,hf)} at {hc}, enemy at {nec} d={d:.1f}")

                    if d > 5:
                        lure = compute_lure_toward(game, ne, hc[0], hc[1])
                        if lure:
                            obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                        else:
                            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                    else:
                        obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                    if won: return clicks
                    break
            continue

        # PHASE 5: Everything ready - move to targets
        if fruits_ready and not need_type3:
            # Lure threatening enemies
            threat = estimate_enemy_threat(game)
            if threat < 5 and remaining > 8:
                lure = compute_safe_lure(game)
                if lure:
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

            # Type-3 enemy needs to be in target
            # It chases nearest fruit, so move a fruit toward the nearest target to it
            if enemy_needs:
                for etype, cnt in enemy_needs.items():
                    type_es = [e for e in enemies if enemy_type(game, e) == etype]
                    if len(type_es) >= cnt:
                        for e in type_es[:cnt]:
                            ec = sc(game, e)
                            in_t = any(t.x <= ec[0] < t.x + t.width and t.y <= ec[1] < t.y + t.height for t in targets)
                            if not in_t:
                                # Move fruit (bait) toward target nearest to enemy
                                best_t = min(targets, key=lambda t: dist2d(ec, (t.x + t.width//2, t.y + t.height//2)))
                                tc = (best_t.x + best_t.width//2, best_t.y + best_t.height//2)
                                # Use val-4 as bait (same-frame trick: enemy enters target, hits val-4 but win check sees val-4)
                                val4_fruits = [f for f in fruits if sv(game, f) == 4]
                                if val4_fruits:
                                    bait = min(val4_fruits, key=lambda f: dist2d(sc(game, f), tc))
                                    bc = sc(game, bait)
                                    click = find_safe_pull_point(game, bait, tc[0], tc[1])
                                    if not click:
                                        click = click_toward(bc[0], bc[1], tc[0], tc[1])
                                    if click:
                                        print(f"    -> baiting type-3 with val-4 at {click}")
                                        obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                                        if won: return clicks
                                        break

            # Move fruits to targets
            click = move_needed_to_target(game, fruit_needs, targets)
            if click:
                obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                if won: return clicks
                continue

            click = move_highest_to_target(game, targets)
            if click:
                obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                if won: return clicks
            else:
                obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                if won: return clicks
            continue

        # Default: try moving to targets
        click = move_needed_to_target(game, fruit_needs, targets)
        if click:
            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
            if won: return clicks
        else:
            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
            if won: return clicks

    return None


def l9_strategy_enemies_then_fruits(env, game, level_num):
    """Start by merging enemies, then handle fruits."""
    clicks = []
    max_clicks = 45

    for step in range(max_clicks):
        game = env._game
        fruits = game.lkujttxgs
        enemies = game.fezhhzhih
        remaining = game.step_counter_ui.current_steps

        if remaining <= 0 or not fruits:
            return None
        if game.cbdhpcilgb():
            return clicks

        fruit_needs, enemy_needs = parse_win_condition(game.dsqlbvwaj)
        targets = game.powykypsm
        enemy_types_map = {e: enemy_type(game, e) for e in enemies}

        type1s = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_1]
        type2s = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_2]
        type3s = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_3]

        if step < 3 or step % 5 == 0:
            print(f"    L9e s{step}: t1={len(type1s)} t2={len(type2s)} t3={len(type3s)} steps={remaining}")

        need_type3 = ENEMY_TYPE_3 in enemy_needs and len(type3s) < enemy_needs.get(ENEMY_TYPE_3, 0)

        if need_type3:
            # First priority: merge type-1 pairs into type-2
            if len(type1s) >= 2:
                # Pick closest pair
                best_pair = None
                best_d = float('inf')
                for i in range(len(type1s)):
                    for j in range(i+1, len(type1s)):
                        d = dist2d(sc(game, type1s[i]), sc(game, type1s[j]))
                        if d < best_d:
                            best_d = d
                            best_pair = (type1s[i], type1s[j])

                if best_pair:
                    e1, e2 = best_pair
                    ec1, ec2 = sc(game, e1), sc(game, e2)

                    mid = compute_lure_between_enemies(game, e1, e2)
                    if mid:
                        obs, game, won = l8_do_click(env, game, clicks, mid[0], mid[1], level_num)
                        if won: return clicks
                        continue

                    lure = compute_lure_toward(game, e1, ec2[0], ec2[1])
                    if lure:
                        obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                        if won: return clicks
                        continue

                    lure = compute_lure_toward(game, e2, ec1[0], ec1[1])
                    if lure:
                        obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                        if won: return clicks
                        continue

            elif len(type2s) >= 2:
                # Merge type-2 pair into type-3
                # Type-2 enemies chase nearest fruit - position fruit between them
                e1, e2 = type2s[0], type2s[1]
                ec1, ec2 = sc(game, e1), sc(game, e2)
                d = dist2d(ec1, ec2)

                if d < 5:
                    # Very close, just wait
                    obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                    if won: return clicks
                    continue

                # Use fruit as bait - move fruit toward midpoint of enemies
                mid_x = (ec1[0] + ec2[0]) // 2
                mid_y = max(MIN_Y, min(MAX_Y - 1, (ec1[1] + ec2[1]) // 2))

                # Find nearest fruit to midpoint
                nf = min(fruits, key=lambda f: dist2d(sc(game, f), (mid_x, mid_y)))
                nfc = sc(game, nf)
                click = find_safe_pull_point(game, nf, mid_x, mid_y)
                if click:
                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                    if won: return clicks
                    continue
                click = click_toward(nfc[0], nfc[1], mid_x, mid_y)
                if click:
                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                    if won: return clicks
                    continue

            # Default: click neutral
            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
            if won: return clicks
            continue

        # Enemy merging done, handle fruits
        return _finish_l8_fruits(env, game, clicks, level_num, fruit_needs, enemy_needs, targets)

    return None


def l9_strategy_parallel(env, game, level_num):
    """Try to do everything simultaneously - merge fruits while enemies converge."""
    # Combine: merge val-1 pair (bottom area) while enemies at top converge naturally
    return l9_strategy_fruits_then_enemies(env, game, level_num)


def l9_strategy_alt(env, game, level_num):
    """Alternative: use fruit baiting aggressively to control enemy positions."""
    clicks = []
    max_clicks = 45

    for step in range(max_clicks):
        game = env._game
        fruits = game.lkujttxgs
        enemies = game.fezhhzhih
        remaining = game.step_counter_ui.current_steps

        if remaining <= 0 or not fruits:
            return None
        if game.cbdhpcilgb():
            return clicks

        fruit_needs, enemy_needs = parse_win_condition(game.dsqlbvwaj)
        targets = game.powykypsm
        val_list = [sv(game, f) for f in fruits]
        val_counts = Counter(val_list)
        enemy_types_map = {e: enemy_type(game, e) for e in enemies}
        type1s = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_1]
        type2s = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_2]
        type3s = [e for e in enemies if enemy_types_map.get(e) == ENEMY_TYPE_3]

        if step < 3 or step % 5 == 0:
            print(f"    L9alt s{step}: vals={val_list} t1={len(type1s)} t2={len(type2s)} t3={len(type3s)} steps={remaining}")

        need_type3 = ENEMY_TYPE_3 in enemy_needs and len(type3s) < enemy_needs.get(ENEMY_TYPE_3, 0)
        need_merge = should_merge(game, fruit_needs)
        need_hit = any(val_counts.get(v, 0) < c and any(sv(game, f) > v for f in fruits)
                      for v, c in fruit_needs.items())

        # Interleave: merge fruits when safe, work on enemies otherwise
        if need_merge and not need_type3:
            # Focus on fruit merging
            pairs = find_pairs(game)
            if pairs:
                click = pick_best_action(game, pairs, fruit_needs, len(enemies) > 0, targets)
                if click:
                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                    if won: return clicks
                    continue

        if need_type3:
            if len(type1s) >= 2:
                # Merge closest type-1 pair
                best_pair = min(
                    [(type1s[i], type1s[j])
                     for i in range(len(type1s)) for j in range(i+1, len(type1s))],
                    key=lambda p: dist2d(sc(game, p[0]), sc(game, p[1]))
                )
                e1, e2 = best_pair
                ec1, ec2 = sc(game, e1), sc(game, e2)

                mid = compute_lure_between_enemies(game, e1, e2)
                if mid:
                    obs, game, won = l8_do_click(env, game, clicks, mid[0], mid[1], level_num)
                    if won: return clicks
                    continue

                lure = compute_lure_toward(game, e1, ec2[0], ec2[1])
                if not lure:
                    lure = compute_lure_toward(game, e2, ec1[0], ec1[1])
                if lure:
                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                    if won: return clicks
                    continue

                # While waiting, try to merge fruits if possible
                if need_merge:
                    pairs = find_pairs(game)
                    if pairs:
                        click = pick_best_action(game, pairs, fruit_needs, True, targets)
                        if click:
                            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                            if won: return clicks
                            continue

            elif len(type2s) >= 2:
                # Move fruit between type-2 enemies as bait
                e1, e2 = type2s[0], type2s[1]
                ec1, ec2 = sc(game, e1), sc(game, e2)
                mid_x = (ec1[0] + ec2[0]) // 2
                mid_y = max(MIN_Y, min(MAX_Y - 1, (ec1[1] + ec2[1]) // 2))

                nf = min(fruits, key=lambda f: dist2d(sc(game, f), (mid_x, mid_y)))
                nfc = sc(game, nf)
                click = find_safe_pull_point(game, nf, mid_x, mid_y)
                if not click:
                    click = click_toward(nfc[0], nfc[1], mid_x, mid_y)
                if click:
                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                    if won: return clicks
                    continue

            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
            if won: return clicks
            continue

        if need_hit:
            for needed_val, cnt in fruit_needs.items():
                if val_counts.get(needed_val, 0) >= cnt:
                    continue
                higher = [f for f in fruits if sv(game, f) > needed_val]
                if higher and enemies:
                    hf = min(higher, key=lambda f: sv(game, f))
                    hc = sc(game, hf)
                    ne = min(enemies, key=lambda e: dist2d(sc(game, e), hc))
                    nec = sc(game, ne)
                    d = dist2d(nec, hc)
                    if d > 5:
                        lure = compute_lure_toward(game, ne, hc[0], hc[1])
                        if lure:
                            obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                        else:
                            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                    else:
                        obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
                    if won: return clicks
                    break
            continue

        # Move to targets (same as other strategies)
        # Handle enemy placement
        if enemy_needs:
            for etype, cnt in enemy_needs.items():
                type_enemies = [e for e in enemies if enemy_type(game, e) == etype]
                if len(type_enemies) >= cnt:
                    for e in type_enemies[:cnt]:
                        ec = sc(game, e)
                        in_t = any(t.x <= ec[0] < t.x + t.width and t.y <= ec[1] < t.y + t.height for t in targets)
                        if not in_t:
                            et = enemy_type(game, e)
                            if game.dfqhmningy(et) == 1:
                                best_t = min(targets, key=lambda t: dist2d(ec, (t.x + t.width//2, t.y + t.height//2)))
                                tc = (best_t.x + best_t.width//2, best_t.y + best_t.height//2)
                                lure = compute_lure_toward(game, e, tc[0], tc[1])
                                if lure:
                                    obs, game, won = l8_do_click(env, game, clicks, lure[0], lure[1], level_num)
                                    if won: return clicks
                                    break
                            else:
                                # Use bait
                                best_t = min(targets, key=lambda t: dist2d(ec, (t.x + t.width//2, t.y + t.height//2)))
                                tc = (best_t.x + best_t.width//2, best_t.y + best_t.height//2)
                                nf = min(fruits, key=lambda f: dist2d(sc(game, f), ec))
                                click = click_toward(sc(game, nf)[0], sc(game, nf)[1], tc[0], tc[1])
                                if click:
                                    obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
                                    if won: return clicks
                                    break

        click = move_needed_to_target(game, fruit_needs, targets)
        if click:
            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
            if won: return clicks
            continue

        click = move_highest_to_target(game, targets)
        if click:
            obs, game, won = l8_do_click(env, game, clicks, click[0], click[1], level_num)
            if won: return clicks
        else:
            obs, game, won = l8_do_click(env, game, clicks, *find_neutral_click(game), level_num)
            if won: return clicks

    return None


# ─── Main solver ─────────────────────────────────────────
def solve_level(env, game, level_num):
    clicks = []
    max_clicks = 50

    for step_num in range(max_clicks):
        game = env._game
        fruits = game.lkujttxgs

        if not fruits:
            print("    No fruits left!")
            return None

        remaining = game.step_counter_ui.current_steps
        if remaining <= 0:
            print("    Out of steps!")
            return None

        if game.cbdhpcilgb():
            return clicks

        fruit_needs, enemy_needs = parse_win_condition(game.dsqlbvwaj)
        targets = game.powykypsm
        has_enemies = len(game.fezhhzhih) > 0

        # Debug
        fv = [sv(game, s) for s in fruits]
        if step_num < 5 or step_num % 10 == 0:
            print(f"    s{step_num}: {fv} steps={remaining}")

        # Single fruit + no enemy needs: move to target
        if len(fruits) == 1 and not enemy_needs:
            click = move_to_target(game, fruits[0], targets)
            if click:
                clicks.append(click)
                obs = env.step(6, data={"x": click[0], "y": click[1]})
                if obs.levels_completed >= level_num:
                    return clicks
            continue

        need_merge = should_merge(game, fruit_needs)

        # Check if we need enemy to reduce fruit value (e.g., val-5 -> val-3)
        if has_enemies and fruit_needs:
            current_vals = Counter(sv(game, s) for s in fruits)
            for needed_val, needed_count in fruit_needs.items():
                if current_vals.get(needed_val, 0) >= needed_count:
                    continue
                # Check if any fruit has HIGHER value than needed
                high_fruits = [s for s in fruits if sv(game, s) > needed_val]
                if high_fruits:
                    hf = min(high_fruits, key=lambda s: sv(game, s))
                    hv = sv(game, hf)
                    hc = sc(game, hf)
                    hits_needed = hv - needed_val
                    print(f"    Need enemy to hit fruit (val {hv} -> {needed_val}, {hits_needed} hits)")

                    nearest_e = min(game.fezhhzhih, key=lambda e: dist2d(sc(game, e), hc))
                    ec = sc(game, nearest_e)
                    d = dist2d(hc, ec)

                    if d > 3:
                        safe_x = 32
                        safe_y = max(MIN_Y, min(MAX_Y-1, 50))
                        if not any(game.kcqeohsztd(safe_x, safe_y, RADIUS, f) for f in fruits):
                            clicks.append((safe_x, safe_y))
                            obs = env.step(6, data={"x": safe_x, "y": safe_y})
                        else:
                            click = click_toward(ec[0], ec[1], hc[0], hc[1])
                            if click:
                                clicks.append(click)
                                obs = env.step(6, data={"x": click[0], "y": click[1]})
                    else:
                        clicks.append((32, 50))
                        obs = env.step(6, data={"x": 32, "y": 50})

                    if obs.levels_completed >= level_num:
                        return clicks
                    continue

        if not need_merge and not enemy_needs:
            # If enemies are present and threatening, lure them away first
            if has_enemies and remaining > 10:
                threat = estimate_enemy_threat(game)
                if threat < 6:
                    lure = compute_safe_lure(game)
                    if lure:
                        clicks.append(lure)
                        obs = env.step(6, data={"x": lure[0], "y": lure[1]})
                        if obs.levels_completed >= level_num:
                            return clicks
                        continue

            click = move_needed_to_target(game, fruit_needs, targets)
            if click:
                clicks.append(click)
                obs = env.step(6, data={"x": click[0], "y": click[1]})
                if obs.levels_completed >= level_num:
                    return clicks
            else:
                # Can't find safe move - accept collision risk
                print(f"    s{step_num}: No safe move, trying unsafe")
                click = move_needed_to_target_unsafe(game, fruit_needs, targets)
                if click:
                    clicks.append(click)
                    obs = env.step(6, data={"x": click[0], "y": click[1]})
                    if obs.levels_completed >= level_num:
                        return clicks
            continue

        if not need_merge and enemy_needs:
            click = handle_enemy_win_cond(game, fruit_needs, enemy_needs, targets)
            if click:
                clicks.append(click)
                obs = env.step(6, data={"x": click[0], "y": click[1]})
                if obs.levels_completed >= level_num:
                    return clicks
            continue

        # Lure enemies away if they're threatening and we have budget
        if has_enemies and step_num == 0 and not enemy_needs and remaining >= 25:
            threat = estimate_enemy_threat(game)
            if threat < 12:
                lure_budget = min(2, remaining - 20)
                lured = 0
                while lured < lure_budget:
                    game = env._game
                    lure = compute_safe_lure(game)
                    if not lure:
                        break
                    clicks.append(lure)
                    obs = env.step(6, data={"x": lure[0], "y": lure[1]})
                    lured += 1
                    game = env._game
                    new_threat = estimate_enemy_threat(game)
                    print(f"    Lure {lured}: threat={new_threat:.1f}")
                    if new_threat > 20:
                        break
                    if obs.levels_completed >= level_num:
                        return clicks
                continue  # Re-evaluate after luring

        # Find same-value pairs
        pairs = find_pairs(game)

        if not pairs:
            click = move_highest_to_target(game, targets)
            if click:
                clicks.append(click)
                obs = env.step(6, data={"x": click[0], "y": click[1]})
                if obs.levels_completed >= level_num:
                    return clicks
            continue

        # Pick best action: merge if close & safe, or pull fruit closer
        click = pick_best_action(game, pairs, fruit_needs, has_enemies, targets)
        if click:
            prev_total = total_fruit_value(game) if has_enemies else 0
            clicks.append(click)
            obs = env.step(6, data={"x": click[0], "y": click[1]})
            if has_enemies:
                new_total = total_fruit_value(env._game)
                if new_total < prev_total and remaining > 4:
                    # Enemy damaged fruit - undo
                    env.step(7)
                    clicks.pop()
                    # Try a different approach next iteration
                    # Move fruit away from enemy
                    alt = move_threatened_fruit(game, pairs)
                    if alt:
                        clicks.append(alt)
                        obs = env.step(6, data={"x": alt[0], "y": alt[1]})
            if obs.levels_completed >= level_num:
                return clicks
        else:
            # No good action found
            click = move_highest_to_target(game, targets)
            if click:
                clicks.append(click)
                obs = env.step(6, data={"x": click[0], "y": click[1]})
                if obs.levels_completed >= level_num:
                    return clicks

    print(f"    Ran out of clicks ({max_clicks})")
    return None


def find_pairs(game):
    """Find all same-value fruit pairs, sorted by distance."""
    fruits = game.lkujttxgs
    n = len(fruits)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            vi, vj = sv(game, fruits[i]), sv(game, fruits[j])
            if vi != vj:
                continue
            ci, cj = sc(game, fruits[i]), sc(game, fruits[j])
            d = dist2d(ci, cj)
            pairs.append((d, i, j, ci, cj, vi))
    pairs.sort()
    return pairs


def pick_best_action(game, pairs, fruit_needs, has_enemies, targets):
    """Pick the best action: direct merge, pull closer, or move to target.

    Priority:
    1. Direct merge (close enough, safe from collision)
    2. Pull fruit toward merge partner (safe click)
    3. Move needed fruit toward target (if merging done for that value)
    """
    fruits = game.lkujttxgs
    val_counts = Counter(sv(game, s) for s in fruits)

    # 1. Try direct merges (d <= 16, so one click can merge)
    for d, i, j, ci, cj, val in pairs:
        if d > 16:
            break

        # Surplus check
        remaining = val_counts[val] - 2
        needed = fruit_needs.get(val, 0)
        if remaining < needed:
            continue

        # Merge click
        mx = (ci[0] + cj[0]) // 2
        my = max(MIN_Y, min(MAX_Y - 1, (ci[1] + cj[1]) // 2))

        if is_safe_click(game, mx, my):
            return (mx, my)

    # 2. Pull closest pair together
    for d, i, j, ci, cj, val in pairs:
        remaining = val_counts[val] - 2
        needed = fruit_needs.get(val, 0)
        if remaining < needed:
            continue

        # Pull fruit[i] toward fruit[j]
        click = find_safe_pull_point(game, fruits[i], cj[0], cj[1])
        if click:
            return click

        # Pull fruit[j] toward fruit[i]
        click = find_safe_pull_point(game, fruits[j], ci[0], ci[1])
        if click:
            return click

    # 3. Try any pair (ignore surplus check)
    for d, i, j, ci, cj, val in pairs:
        if d <= 16:
            mx = (ci[0] + cj[0]) // 2
            my = max(MIN_Y, min(MAX_Y - 1, (ci[1] + cj[1]) // 2))
            if is_safe_click(game, mx, my):
                return (mx, my)

        click = find_safe_pull_point(game, fruits[i], cj[0], cj[1])
        if click:
            return click

        click = find_safe_pull_point(game, fruits[j], ci[0], ci[1])
        if click:
            return click

    # 4. Fallback: try first pair with any click (even unsafe)
    if pairs:
        d, i, j, ci, cj, val = pairs[0]
        if d <= 16:
            mx = (ci[0] + cj[0]) // 2
            my = max(MIN_Y, min(MAX_Y - 1, (ci[1] + cj[1]) // 2))
            return (mx, my)
        return click_toward(ci[0], ci[1], cj[0], cj[1])

    return None


def move_threatened_fruit(game, pairs):
    """Move a fruit that's near an enemy away from danger."""
    fruits = game.lkujttxgs
    enemies = game.fezhhzhih
    if not enemies or not pairs:
        return None

    # Find fruit closest to any enemy
    best_fruit = None
    best_dist = float('inf')
    best_partner_center = None

    for d, i, j, ci, cj, val in pairs:
        for fi, fc, partner_c in [(i, ci, cj), (j, cj, ci)]:
            for e in enemies:
                ec = sc(game, e)
                ed = dist2d(fc, ec)
                if ed < best_dist:
                    best_dist = ed
                    best_fruit = fruits[fi]
                    best_partner_center = partner_c

    if best_fruit and best_partner_center:
        fc = sc(game, best_fruit)
        click = find_safe_pull_point(game, best_fruit,
                                      best_partner_center[0], best_partner_center[1])
        if click:
            return click
        return click_toward(fc[0], fc[1], best_partner_center[0], best_partner_center[1])

    return None


# ─── Target movement ────────────────────────────────────
def move_to_target(game, sprite, targets):
    if not targets:
        return None
    cx, cy = sc(game, sprite)
    t = min(targets, key=lambda t: (cx - t.x - t.width//2)**2 + (cy - t.y - t.height//2)**2)
    tx, ty = t.x + t.width//2, t.y + t.height//2

    # Try direct click first
    click = click_toward(cx, cy, tx, ty)
    if click and is_safe_click(game, click[0], click[1]):
        return click

    # Try safe alternative
    safe = find_safe_pull_point(game, sprite, tx, ty)
    if safe:
        return safe

    # Fallback: use direct click even if unsafe
    # Penalty is 2 steps, which is less than wasting many clicks on avoidance
    return click

def move_highest_to_target(game, targets):
    fruits = game.lkujttxgs
    if not fruits or not targets:
        return None
    best = max(fruits, key=lambda s: sv(game, s))
    return move_to_target(game, best, targets)

def move_needed_to_target(game, fruit_needs, targets):
    """Move needed fruits to targets, closest first to avoid cross-path issues."""
    fruits = game.lkujttxgs
    if not fruits or not targets:
        return None

    # Find which fruits need to be placed
    unplaced = []
    placed_targets = set()
    for s in fruits:
        v = sv(game, s)
        if v not in fruit_needs or fruit_needs[v] <= 0:
            continue
        cx, cy = sc(game, s)
        for ti, t in enumerate(targets):
            if t.x <= cx < t.x + t.width and t.y <= cy < t.y + t.height:
                placed_targets.add(ti)
                break
        else:
            unplaced.append((s, v))

    if not unplaced:
        return move_highest_to_target(game, targets)

    # Assign fruits to targets (greedy closest match)
    free_targets = [t for ti, t in enumerate(targets) if ti not in placed_targets]
    if not free_targets:
        free_targets = list(targets)

    # Find best assignment considering both distance and enemy safety
    enemies = game.fezhhzhih
    best = None
    best_score = float('inf')

    for s, v in unplaced:
        cx, cy = sc(game, s)
        for t in free_targets:
            tx, ty = t.x + t.width//2, t.y + t.height//2
            d = dist2d((cx, cy), (tx, ty))

            # If enemies present, penalize targets close to enemies
            if enemies:
                min_enemy_d = min(dist2d((tx, ty), sc(game, e)) for e in enemies)
                # Score: distance to target (want low) - enemy safety (want high)
                score = d - min_enemy_d * 0.3  # Prefer targets far from enemies
            else:
                score = d

            if score < best_score:
                best_score = score
                best = (s, t)

    if best:
        s, t = best
        return move_to_target(game, s, [t])
    return None


def move_needed_to_target_unsafe(game, fruit_needs, targets):
    """Move needed fruits to targets WITHOUT collision safety check.
    Used as fallback when safe moves are impossible."""
    fruits = game.lkujttxgs
    if not fruits or not targets:
        return None

    unplaced = []
    for s in fruits:
        v = sv(game, s)
        if v not in fruit_needs or fruit_needs[v] <= 0:
            continue
        cx, cy = sc(game, s)
        in_tgt = any(t.x <= cx < t.x + t.width and t.y <= cy < t.y + t.height for t in targets)
        if not in_tgt:
            unplaced.append((s, v))

    if not unplaced:
        return None

    # Move the one farthest from target
    best_s, best_d = None, -1
    for s, v in unplaced:
        cx, cy = sc(game, s)
        d = min(dist2d((cx, cy), (t.x + t.width//2, t.y + t.height//2)) for t in targets)
        if d > best_d:
            best_d = d
            best_s = s

    if best_s:
        cx, cy = sc(game, best_s)
        t = min(targets, key=lambda t: dist2d((cx, cy), (t.x + t.width//2, t.y + t.height//2)))
        return click_toward(cx, cy, t.x + t.width//2, t.y + t.height//2)
    return None


def handle_enemy_win_cond(game, fruit_needs, enemy_needs, targets):
    """Handle levels needing enemies in target zones."""
    fruits = game.lkujttxgs
    enemies = game.fezhhzhih

    # First ensure fruits are placed
    if fruit_needs:
        for val, count in fruit_needs.items():
            in_t = sum(1 for s in fruits
                       if sv(game, s) == val and
                       any(t.x <= sc(game,s)[0] < t.x+t.width and
                           t.y <= sc(game,s)[1] < t.y+t.height for t in targets))
            if in_t < count:
                # Protect fruits from enemy damage while moving
                if enemies:
                    threat = estimate_enemy_threat(game)
                    if threat < 8:
                        lure = compute_safe_lure(game)
                        if lure:
                            return lure
                return move_needed_to_target(game, fruit_needs, targets)

    if not targets:
        return None
    tc_list = [(t.x + t.width//2, t.y + t.height//2) for t in targets]

    for etype, count in enemy_needs.items():
        type_enemies = [e for e in enemies if enemy_type(game, e) == etype]

        # Check if we need to CREATE this enemy type by merging lower-type enemies
        if len(type_enemies) < count:
            # Need to merge enemies to create this type
            # Type hierarchy: type1 + type1 -> type2, type2 + type2 -> type3
            lower_type = None
            if etype == ENEMY_TYPE_2:
                lower_type = ENEMY_TYPE_1
            elif etype == ENEMY_TYPE_3:
                lower_type = ENEMY_TYPE_2

            if lower_type:
                lower_enemies = [e for e in enemies if enemy_type(game, e) == lower_type]
                if len(lower_enemies) >= 2:
                    # Attract 2 lower-type enemies together to merge them
                    e1, e2 = lower_enemies[0], lower_enemies[1]
                    ec1, ec2 = sc(game, e1), sc(game, e2)
                    mid_x = (ec1[0] + ec2[0]) // 2
                    mid_y = max(MIN_Y, min(MAX_Y-1, (ec1[1] + ec2[1]) // 2))
                    d = dist2d(ec1, ec2)

                    if d <= 16:
                        # Close enough, click midpoint to attract both
                        print(f"    Merging enemies at ({mid_x},{mid_y}) d={d:.0f}")
                        return (mid_x, mid_y)
                    else:
                        # Pull one toward the other
                        click = click_toward(ec1[0], ec1[1], ec2[0], ec2[1])
                        if click:
                            print(f"    Pulling enemies together, d={d:.0f}")
                            return click
            continue

        # We have enough enemies of this type, move them to targets
        not_in = []
        in_t = 0
        for e in type_enemies:
            ec = sc(game, e)
            if any(t.x <= ec[0] < t.x+t.width and t.y <= ec[1] < t.y+t.height for t in targets):
                in_t += 1
            else:
                not_in.append(e)
        if in_t >= count:
            continue
        if not_in:
            e = not_in[0]
            ec = sc(game, e)
            best_tc = min(tc_list, key=lambda tc: dist2d(ec, tc))
            # Enemies chase nearest fruit - they can't be directly controlled
            # Try clicking near enemy to attract type-1 toward target
            et = enemy_type(game, e)
            if game.dfqhmningy(et) == 1:
                return click_toward(ec[0], ec[1], best_tc[0], best_tc[1])
            else:
                # Non-type-1 enemies can't be attracted, need fruit bait
                # Move a fruit near the target so enemy chases it there
                if fruits:
                    nearest_f = min(fruits, key=lambda f: dist2d(sc(game,f), best_tc))
                    return move_to_target(game, nearest_f, targets)

    return move_highest_to_target(game, targets)


if __name__ == "__main__":
    solve()
