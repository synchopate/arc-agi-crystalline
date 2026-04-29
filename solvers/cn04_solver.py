#!/usr/bin/env python3
"""cn04 solver -- jigsaw puzzle: align sprite markers (8/13) by moving/rotating/cycling."""
import arc_agi
import numpy as np
import logging
logging.disable(logging.WARNING)
from universal_harness import grid_to_display, replay_solution


def get_markers_at_rot(game, s, rotation):
    """Get 8/13 marker offsets for a sprite at a given rotation."""
    orig = game.hlxyvcmpk[s.name]
    saved_px, saved_rot = s.pixels.copy(), s.rotation
    s.pixels = orig.copy()
    s.rotation = rotation
    rendered = s.render()
    w, h = rendered.shape[1], rendered.shape[0]
    s.pixels, s.rotation = saved_px, saved_rot
    eights = [(c, r) for r in range(h) for c in range(w) if rendered[r, c] == 8]
    thirteens = [(c, r) for r in range(h) for c in range(w) if rendered[r, c] == 13]
    return eights, thirteens, (w, h)


def find_click_coord(game, sprite):
    """Find a display coordinate that hits a non-transparent pixel of the sprite."""
    cam = game.camera
    rendered = sprite.render()
    for r in range(rendered.shape[0]):
        for c in range(rendered.shape[1]):
            if rendered[r, c] >= 0:
                gx, gy = sprite.x + c, sprite.y + r
                return grid_to_display(gx, gy, cam)
    return None


def gen_matchings(items):
    """Generate all perfect matchings of a list."""
    if len(items) == 0:
        yield []
        return
    first = items[0]
    rest = items[1:]
    for i, second in enumerate(rest):
        remaining = rest[:i] + rest[i + 1:]
        for m in gen_matchings(remaining):
            yield [(first, second)] + m


def find_solution_positions(game, level_idx, visible_sprites):
    """Find minimum-cost (x, y, rotation) for each sprite to solve the level."""
    from itertools import product
    n = len(visible_sprites)
    grid_w, grid_h = 20, 20
    best_cost = float('inf')
    best_sol = None

    for rot_combo in product([0, 90, 180, 270], repeat=n):
        m = []
        for i, s in enumerate(visible_sprites):
            e8, e13, (w, h) = get_markers_at_rot(game, s, rot_combo[i])
            m.append({'8': e8, '13': e13, 'w': w, 'h': h})

        flat_8 = [(i, ox, oy) for i in range(n) for ox, oy in m[i]['8']]
        flat_13 = [(i, ox, oy) for i in range(n) for ox, oy in m[i]['13']]

        if len(flat_8) % 2 != 0 or len(flat_13) % 2 != 0:
            continue
        if len(flat_8) == 0 and len(flat_13) == 0:
            continue

        for matching_8 in gen_matchings(list(range(len(flat_8)))):
            if not all(flat_8[a][0] != flat_8[b][0] for a, b in matching_8):
                continue
            rc = {}
            ok8 = True
            for a, b in matching_8:
                si, oxi, oyi = flat_8[a]
                sj, oxj, oyj = flat_8[b]
                if si > sj:
                    si, sj = sj, si
                    oxi, oyi, oxj, oyj = oxj, oyj, oxi, oyi
                dx, dy = oxi - oxj, oyi - oyj
                if (si, sj) in rc and rc[(si, sj)] != (dx, dy):
                    ok8 = False
                    break
                rc[(si, sj)] = (dx, dy)
            if not ok8:
                continue

            for matching_13 in gen_matchings(list(range(len(flat_13)))):
                if not all(flat_13[a][0] != flat_13[b][0] for a, b in matching_13):
                    continue
                rc2 = dict(rc)
                ok13 = True
                for a, b in matching_13:
                    si, oxi, oyi = flat_13[a]
                    sj, oxj, oyj = flat_13[b]
                    if si > sj:
                        si, sj = sj, si
                        oxi, oyi, oxj, oyj = oxj, oyj, oxi, oyi
                    dx, dy = oxi - oxj, oyi - oyj
                    if (si, sj) in rc2 and rc2[(si, sj)] != (dx, dy):
                        ok13 = False
                        break
                    rc2[(si, sj)] = (dx, dy)
                if not ok13:
                    continue

                for px0 in range(grid_w - m[0]['w'] + 1):
                    for py0 in range(grid_h - m[0]['h'] + 1):
                        pos = {0: (px0, py0)}
                        ok = True
                        for _ in range(n * 2):
                            for (si, sj), (dx, dy) in rc2.items():
                                if si in pos and sj not in pos:
                                    px, py = pos[si][0] + dx, pos[si][1] + dy
                                    if 0 <= px and px + m[sj]['w'] <= grid_w and 0 <= py and py + m[sj]['h'] <= grid_h:
                                        pos[sj] = (px, py)
                                    else:
                                        ok = False
                                        break
                                elif sj in pos and si not in pos:
                                    px, py = pos[sj][0] - dx, pos[sj][1] - dy
                                    if 0 <= px and px + m[si]['w'] <= grid_w and 0 <= py and py + m[si]['h'] <= grid_h:
                                        pos[si] = (px, py)
                                    else:
                                        ok = False
                                        break
                                elif si in pos and sj in pos:
                                    if pos[sj] != (pos[si][0] + dx, pos[si][1] + dy):
                                        ok = False
                                        break
                            if not ok:
                                break
                        if not ok or len(pos) < n:
                            continue

                        cost = sum(abs(pos[i][0] - visible_sprites[i].x) + abs(pos[i][1] - visible_sprites[i].y) for i in range(n))
                        rot_cost = sum(((rot_combo[i] - visible_sprites[i].rotation) % 360) // 90 for i in range(n))
                        total = cost + rot_cost
                        if total < best_cost:
                            best_cost = total
                            best_sol = {i: (pos[i][0], pos[i][1], rot_combo[i]) for i in range(n)}

    return best_sol, best_cost


def generate_move_sequence(env, game, sprite, target_x, target_y, target_rot):
    """Generate action sequence to move sprite from current to target position/rotation."""
    actions = []

    # Rotate first (for solo sprites only)
    groups = game.vausolnec
    is_grouped = len(groups[sprite]) > 1

    if not is_grouped:
        rot_diff = ((target_rot - sprite.rotation) % 360) // 90
        for _ in range(rot_diff):
            actions.append(5)

    # Move
    dx = target_x - sprite.x
    dy = target_y - sprite.y

    if is_grouped:
        # After cycling, sprite position may have changed
        # We need to compute moves after rotation is set
        # For grouped sprites, rotation doesn't change via ACTION5 (it cycles instead)
        pass

    # Generate directional moves
    if dx > 0:
        actions.extend([4] * dx)  # right
    elif dx < 0:
        actions.extend([3] * (-dx))  # left

    if dy > 0:
        actions.extend([2] * dy)  # down
    elif dy < 0:
        actions.extend([1] * (-dy))  # up

    return actions


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('cn04')
    obs = env.reset()
    game = env._game

    print(f"cn04: {obs.win_levels} levels")

    all_actions = []  # Complete action sequence

    # =============================================
    # LEVEL 1: 2 solo sprites
    # s0 stays at (3,3,r=90), s1 -> (2,8,r=90)
    # =============================================
    print("\n=== Level 1 ===")
    # s0 is auto-selected. We need to select s1 instead.
    s1 = game.current_level.get_sprites()[1]
    click = find_click_coord(game, s1)
    all_actions.append(click)
    obs = env.step(6, data={"x": click[0], "y": click[1]})
    print(f"  Selected: {game.xseexqzst.name}")

    # Rotate s1: 0 -> 90 (1 rotate)
    all_actions.append(5)
    obs = env.step(5)

    # Move s1: (12,9) -> need to reach position where level completes
    # After rotation, s1 is at (12,9) with rot=90, size=(7,4)
    # Target: (2,8) but may be clamped. Let's just move and check.
    # Move left: 12 -> 2 = 10 lefts, up: 9 -> 8 = 1 up
    for _ in range(10):
        all_actions.append(3)
        obs = env.step(3)
        if obs.levels_completed >= 1:
            break
    if obs.levels_completed < 1:
        all_actions.append(1)
        obs = env.step(1)

    print(f"  Level 1 complete: {obs.levels_completed >= 1}")
    assert obs.levels_completed >= 1, "Level 1 not solved!"

    # =============================================
    # LEVEL 2: 4 solo sprites
    # s0 (0002) -> (4,5,r=0): move up 6
    # s1 (0003) -> (8,6,r=0): move left 4, up +2... wait
    # s2 (0004) -> (3,3,r=0): stays
    # s3 (0005) -> (12,8,r=0): move left 4, up 8, unrotate
    # =============================================
    print("\n=== Level 2 ===")
    game = env._game
    sprites = game.current_level.get_sprites()
    # s0=0002 at (4,11), s1=0003 at (12,4), s2=0004 at (3,3), s3=0005 at (16,16)
    # Target: s0->(4,5), s1->(8,6), s2->(3,3), s3->(12,8)

    # Auto-selected sprite is the one closest to origin = s2 (0004) at (3,3)
    selected = game.xseexqzst
    print(f"  Auto-selected: {selected.name} at ({selected.x},{selected.y})")

    # s2 stays. Don't need to move it.
    # Select s3 (0005) - needs unrotate (90->0 = 3 rotates) and move
    s3 = [s for s in sprites if s.name == '0005xgnvywyzea'][0]
    click = find_click_coord(game, s3)
    all_actions.append(click)
    obs = env.step(6, data={"x": click[0], "y": click[1]})
    print(f"  Selected s3: {game.xseexqzst.name}")

    # Rotate 90->0: need 3 rotates (90->180->270->0)
    for _ in range(3):
        all_actions.append(5)
        obs = env.step(5)
    print(f"  s3 rot: {game.xseexqzst.rotation}, pos: ({game.xseexqzst.x},{game.xseexqzst.y})")

    # Move s3: current pos -> (12,8)
    dx = 12 - game.xseexqzst.x
    dy = 8 - game.xseexqzst.y
    for _ in range(abs(dx)):
        act = 4 if dx > 0 else 3
        all_actions.append(act)
        obs = env.step(act)
    for _ in range(abs(dy)):
        act = 2 if dy > 0 else 1
        all_actions.append(act)
        obs = env.step(act)
    print(f"  s3 at ({game.xseexqzst.x},{game.xseexqzst.y})")

    # Select s1 (0003) -> move to (8,6)
    s1 = [s for s in sprites if s.name == '0003phpzvjydcv'][0]
    click = find_click_coord(game, s1)
    all_actions.append(click)
    obs = env.step(6, data={"x": click[0], "y": click[1]})
    print(f"  Selected s1: {game.xseexqzst.name}")

    dx = 8 - game.xseexqzst.x
    dy = 6 - game.xseexqzst.y
    for _ in range(abs(dx)):
        act = 4 if dx > 0 else 3
        all_actions.append(act)
        obs = env.step(act)
    for _ in range(abs(dy)):
        act = 2 if dy > 0 else 1
        all_actions.append(act)
        obs = env.step(act)
    print(f"  s1 at ({game.xseexqzst.x},{game.xseexqzst.y})")

    # Select s0 (0002) -> move to (4,5)
    s0 = [s for s in sprites if s.name == '0002gbumdnqksn'][0]
    click = find_click_coord(game, s0)
    all_actions.append(click)
    obs = env.step(6, data={"x": click[0], "y": click[1]})
    print(f"  Selected s0: {game.xseexqzst.name}")

    dx = 4 - game.xseexqzst.x
    dy = 5 - game.xseexqzst.y
    for _ in range(abs(dx)):
        act = 4 if dx > 0 else 3
        all_actions.append(act)
        obs = env.step(act)
    for _ in range(abs(dy)):
        act = 2 if dy > 0 else 1
        all_actions.append(act)
        obs = env.step(act)

    print(f"  s0 at ({game.xseexqzst.x},{game.xseexqzst.y})")
    print(f"  Level 2 complete: {obs.levels_completed >= 2}")

    if obs.levels_completed < 2:
        print("  ERROR: Level 2 not solved!")
        # Debug
        for s in game.current_level.get_sprites():
            if s.is_visible:
                e8, e13, _ = get_markers_at_rot(game, s, s.rotation)
                g8 = [(s.x+x, s.y+y) for x, y in e8]
                g13 = [(s.x+x, s.y+y) for x, y in e13]
                print(f"    {s.name} at ({s.x},{s.y}) r={s.rotation}: 8={g8} 13={g13}")
        return

    # =============================================
    # LEVEL 3: 3 solo sprites
    # =============================================
    print("\n=== Level 3 ===")
    game = env._game
    sprites = game.current_level.get_sprites()
    selected = game.xseexqzst
    print(f"  Auto-selected: {selected.name} at ({selected.x},{selected.y}) r={selected.rotation}")

    # Targets: s0(0009) -> (9,9,r=90), s1(0010) -> (5,4,r=90), s2(0011) -> (9,3,r=90)
    targets = {
        '0009hlzrfewrmd': (9, 9, 90),
        '0010uuknhqagrb': (5, 4, 90),
        '0011vjpznxltqu': (9, 3, 90),
    }

    # Process sprites that need the most rotations first to minimize clicks
    sprite_work = []
    for s in sprites:
        if s.name in targets:
            tx, ty, tr = targets[s.name]
            rot_diff = ((tr - s.rotation) % 360) // 90
            move_dist = abs(tx - s.x) + abs(ty - s.y)
            sprite_work.append((s, tx, ty, tr, rot_diff, move_dist))

    # Sort by: sprites that don't need movement first (avoid unnecessary clicks)
    sprite_work.sort(key=lambda x: x[4] + x[5])

    for s, tx, ty, tr, rot_diff, move_dist in sprite_work:
        if rot_diff == 0 and move_dist == 0:
            continue  # Skip sprites that don't need changes

        # Select this sprite
        if game.xseexqzst is None or game.xseexqzst.name != s.name:
            click = find_click_coord(game, s)
            if click:
                all_actions.append(click)
                obs = env.step(6, data={"x": click[0], "y": click[1]})

        # Rotate
        for _ in range(rot_diff):
            all_actions.append(5)
            obs = env.step(5)

        # Move
        dx = tx - game.xseexqzst.x
        dy = ty - game.xseexqzst.y
        for _ in range(abs(dx)):
            act = 4 if dx > 0 else 3
            all_actions.append(act)
            obs = env.step(act)
            if obs.levels_completed >= 3:
                break
        if obs.levels_completed >= 3:
            break
        for _ in range(abs(dy)):
            act = 2 if dy > 0 else 1
            all_actions.append(act)
            obs = env.step(act)
            if obs.levels_completed >= 3:
                break
        if obs.levels_completed >= 3:
            break

    print(f"  Level 3 complete: {obs.levels_completed >= 3}")

    if obs.levels_completed < 3:
        print("  ERROR: Level 3 not solved!")
        for s in game.current_level.get_sprites():
            if s.is_visible:
                print(f"    {s.name} at ({s.x},{s.y}) r={s.rotation}")
        return

    # =============================================
    # LEVEL 4: 4 solo sprites
    # =============================================
    print("\n=== Level 4 ===")
    game = env._game
    sprites = game.current_level.get_sprites()
    selected = game.xseexqzst
    print(f"  Auto-selected: {selected.name}")

    targets = {
        '0012ubfwjimbbi': (5, 3, 90),
        '0013quifjzcfgq': (10, 8, 270),
        '0014njoasulfiw': (5, 10, 180),
        '0015wrcdrghheq': (5, 12, 90),
    }

    for s in sprites:
        if s.name not in targets:
            continue
        tx, ty, tr = targets[s.name]
        rot_diff = ((tr - s.rotation) % 360) // 90
        move_dist = abs(tx - s.x) + abs(ty - s.y)
        if rot_diff == 0 and move_dist == 0:
            continue

        if game.xseexqzst is None or game.xseexqzst.name != s.name:
            click = find_click_coord(game, s)
            if click:
                all_actions.append(click)
                obs = env.step(6, data={"x": click[0], "y": click[1]})

        for _ in range(rot_diff):
            all_actions.append(5)
            obs = env.step(5)

        dx = tx - game.xseexqzst.x
        dy = ty - game.xseexqzst.y
        for _ in range(abs(dx)):
            act = 4 if dx > 0 else 3
            all_actions.append(act)
            obs = env.step(act)
            if obs.levels_completed >= 4:
                break
        if obs.levels_completed >= 4:
            break
        for _ in range(abs(dy)):
            act = 2 if dy > 0 else 1
            all_actions.append(act)
            obs = env.step(act)
            if obs.levels_completed >= 4:
                break
        if obs.levels_completed >= 4:
            break

    print(f"  Level 4 complete: {obs.levels_completed >= 4}")

    if obs.levels_completed < 4:
        print("  ERROR: Level 4 not solved!")
        for s in game.current_level.get_sprites():
            if s.is_visible:
                print(f"    {s.name} at ({s.x},{s.y}) r={s.rotation}")
        return

    # =============================================
    # LEVEL 5: 1 group (5 variants) + 3 solo sprites
    # Need variant 0020sgbkbumnay (index 4 in group)
    # =============================================
    print("\n=== Level 5 ===")
    game = env._game
    sprites = game.current_level.get_sprites()
    selected = game.xseexqzst
    print(f"  Auto-selected: {selected.name}")

    # The group sprite (0016) is auto-selected (closest to origin)
    # Cycle 4 times to reach variant 0020
    for i in range(4):
        all_actions.append(5)
        obs = env.step(5)
    print(f"  After cycling: {game.xseexqzst.name}")

    # Now move the group sprite (0020) to target (7,4,r=0)
    # Current position: (7,4), rotation: already at 0 after cycling? Check.
    print(f"  Group sprite at ({game.xseexqzst.x},{game.xseexqzst.y}) r={game.xseexqzst.rotation}")

    # Target for 0020: (7,4,r=0) - stays at same position!
    # No rotation needed (grouped sprites don't rotate with ACTION5)

    # Now move to solo sprites
    targets = {
        '0021aifjorrdrv': (5, 5, 90),
        '0022anglfyizgt': (9, 4, 0),
        '0023ltzbbieezx': (11, 8, 0),
    }

    for s in sprites:
        if s.name not in targets:
            continue
        if not s.is_visible:
            continue
        tx, ty, tr = targets[s.name]
        rot_diff = ((tr - s.rotation) % 360) // 90
        move_dist = abs(tx - s.x) + abs(ty - s.y)
        if rot_diff == 0 and move_dist == 0:
            continue

        click = find_click_coord(game, s)
        if click:
            all_actions.append(click)
            obs = env.step(6, data={"x": click[0], "y": click[1]})
            print(f"  Selected: {game.xseexqzst.name}")

        for _ in range(rot_diff):
            all_actions.append(5)
            obs = env.step(5)

        dx = tx - game.xseexqzst.x
        dy = ty - game.xseexqzst.y
        for _ in range(abs(dx)):
            act = 4 if dx > 0 else 3
            all_actions.append(act)
            obs = env.step(act)
            if obs.levels_completed >= 5:
                break
        if obs.levels_completed >= 5:
            break
        for _ in range(abs(dy)):
            act = 2 if dy > 0 else 1
            all_actions.append(act)
            obs = env.step(act)
            if obs.levels_completed >= 5:
                break
        if obs.levels_completed >= 5:
            break

    print(f"  Level 5 complete: {obs.levels_completed >= 5}")

    if obs.levels_completed < 5:
        print("  ERROR: Level 5 not solved!")
        for s in game.current_level.get_sprites():
            if s.is_visible:
                e8, e13, _ = get_markers_at_rot(game, s, s.rotation)
                g8 = [(s.x+x, s.y+y) for x, y in e8]
                g13 = [(s.x+x, s.y+y) for x, y in e13]
                print(f"    {s.name} at ({s.x},{s.y}) r={s.rotation}: 8={g8} 13={g13}")
        return

    # =============================================
    # LEVEL 6: 2 groups + 3 solo sprites
    # Group1 (6 variants, 0029 visible): need 0024 (index 0) -- cycle 5 times
    # Group2 (4 variants, 0034 visible): need 0031 (index 0) -- cycle 3 times
    # =============================================
    print("\n=== Level 6 ===")
    game = env._game
    sprites = game.current_level.get_sprites()
    selected = game.xseexqzst
    print(f"  Auto-selected: {selected.name}")

    # Group 1 sprite should be auto-selected or we need to find it
    # Find group 1 sprite (0029 is initially visible)
    grp1_sprite = [s for s in sprites if s.name == '0029vpufvyeoxr'][0]
    grp2_sprite = [s for s in sprites if s.name == '0034tlmfuvkxfw'][0]

    # Select group 1 if not already selected
    if game.xseexqzst.name != grp1_sprite.name:
        click = find_click_coord(game, grp1_sprite)
        if click:
            all_actions.append(click)
            obs = env.step(6, data={"x": click[0], "y": click[1]})

    # Cycle group 1: from 0029 (index 5) to 0024 (index 0)
    # ztpxqonhr starts True, from index 5: 5->4(flip), 4->3, 3->2, 2->1, 1->0
    for i in range(5):
        all_actions.append(5)
        obs = env.step(5)
    print(f"  Group1 cycled to: {game.xseexqzst.name}")

    # Target for group1: (6,6,r=90) -- stays at same position
    print(f"  Group1 at ({game.xseexqzst.x},{game.xseexqzst.y}) r={game.xseexqzst.rotation}")

    # Now handle group 2
    click = find_click_coord(game, grp2_sprite)
    if click:
        all_actions.append(click)
        obs = env.step(6, data={"x": click[0], "y": click[1]})
    print(f"  Selected group2: {game.xseexqzst.name}")

    # Cycle group 2: from 0034 (index 3) to 0031 (index 0)
    # ztpxqonhr is False after group1 cycling: 3->2, 2->1, 1->0
    for i in range(3):
        all_actions.append(5)
        obs = env.step(5)
    print(f"  Group2 cycled to: {game.xseexqzst.name}")

    # Move group 2 to target (5,11,r=90)
    dx = 5 - game.xseexqzst.x
    dy = 11 - game.xseexqzst.y
    for _ in range(abs(dx)):
        act = 4 if dx > 0 else 3
        all_actions.append(act)
        obs = env.step(act)
    for _ in range(abs(dy)):
        act = 2 if dy > 0 else 1
        all_actions.append(act)
        obs = env.step(act)
    print(f"  Group2 at ({game.xseexqzst.x},{game.xseexqzst.y})")

    # Now handle solo sprites
    targets = {
        '0030bwvbcqnslb': (4, 4, 90),
        '0035cnwthztcfw': (11, 4, 90),
        '0036elhntsdonx': (4, 9, 90),
    }

    for s in sprites:
        if s.name not in targets:
            continue
        if not s.is_visible:
            continue
        tx, ty, tr = targets[s.name]
        rot_diff = ((tr - s.rotation) % 360) // 90
        move_dist = abs(tx - s.x) + abs(ty - s.y)
        if rot_diff == 0 and move_dist == 0:
            continue

        click = find_click_coord(game, s)
        if click:
            all_actions.append(click)
            obs = env.step(6, data={"x": click[0], "y": click[1]})
            print(f"  Selected: {game.xseexqzst.name}")

        for _ in range(rot_diff):
            all_actions.append(5)
            obs = env.step(5)

        dx = tx - game.xseexqzst.x
        dy = ty - game.xseexqzst.y
        for _ in range(abs(dx)):
            act = 4 if dx > 0 else 3
            all_actions.append(act)
            obs = env.step(act)
            if obs.levels_completed >= 6:
                break
        if obs.levels_completed >= 6:
            break
        for _ in range(abs(dy)):
            act = 2 if dy > 0 else 1
            all_actions.append(act)
            obs = env.step(act)
            if obs.levels_completed >= 6:
                break
        if obs.levels_completed >= 6:
            break

    print(f"  Level 6 complete: {obs.levels_completed >= 6}")

    # Final result
    print(f"\n{'='*40}")
    print(f"cn04 RESULT: {obs.levels_completed}/{obs.win_levels}")
    print(f"State: {obs.state}")
    print(f"Total actions: {len(all_actions)}")
    print(f"{'='*40}")

    return obs.levels_completed, obs.win_levels


if __name__ == "__main__":
    solve()
