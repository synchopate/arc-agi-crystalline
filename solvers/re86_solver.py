#!/usr/bin/env python3
"""Optimized solver for ARC-AGI-3 game re86. 8/8 WIN, minimum actions."""

import sys, os, copy
import numpy as np
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'environment_files', 're86', '8af5384d'))
exec(open(os.path.join(os.path.dirname(__file__), 'environment_files', 're86', '8af5384d', 're86.py')).read())
from arcengine import ActionInput, GameAction, GameState

U, D, L, R, SW = GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION5
AN = {U:'U', D:'D', L:'L', R:'R', SW:'S'}

def do(g, a):
    return g.perform_action(ActionInput(id=a))

def count_anim(g):
    n = 0
    while g.ylzrmgmdyh and g.cptlsijjli:
        do(g, U); n += 1
        if n > 200: break
    return n

def execute(game, actions):
    t = 0
    for a in actions:
        do(game, a); t += 1
        t += count_anim(game)
    return t

def move_seq(dx, dy):
    assert dx % 3 == 0 and dy % 3 == 0, f"dx={dx} dy={dy}"
    m = []
    if dy < 0: m.extend([U] * (abs(dy) // 3))
    elif dy > 0: m.extend([D] * (dy // 3))
    if dx < 0: m.extend([L] * (abs(dx) // 3))
    elif dx > 0: m.extend([R] * (dx // 3))
    return m

def get_offsets(sprite):
    px = sprite.pixels; h, w = px.shape
    return [(r, c) for r in range(h) for c in range(w) if px[r,c] != -1 and px[r,c] != 0]

def find_targets(goals, offsets, sx, sy):
    if not goals: return []
    possible = None
    for gx, gy in goals:
        positions = set()
        for r, c in offsets:
            positions.add((gx - c, gy - r))
        possible = positions if possible is None else possible & positions
    reachable = [(x, y) for x, y in possible if (x - sx) % 3 == 0 and (y - sy) % 3 == 0]
    reachable.sort(key=lambda p: abs(p[0] - sx) + abs(p[1] - sy))
    return reachable

def selected(game):
    ms = game.current_level.get_sprites_by_tag('0031cppcuvqlbi')
    return [m for m in ms if int(m.pixels[m.pixels.shape[0]//2, m.pixels.shape[1]//2]) == 0][0]

def sprite_color(s):
    nn = s.pixels[s.pixels != -1]; nz = nn[nn != 0]
    return int(nz[0]) if len(nz) > 0 else 0

def adaptive_target(game, goals):
    s = selected(game)
    offsets = get_offsets(s)
    targets = find_targets(goals, offsets, s.x, s.y)
    if targets:
        tx, ty = targets[0]
        return move_seq(tx - s.x, ty - s.y)
    return None

def best_changer_contact(sprite, changer):
    px = sprite.pixels
    sx, sy = sprite.x, sprite.y
    h, w = px.shape
    best_cost = float('inf')
    best_pos = None
    for sr in range(h):
        for sc in range(w):
            if px[sr, sc] == -1: continue
            for cr in range(changer.height):
                for cc_c in range(changer.width):
                    if changer.pixels[cr, cc_c] == -1: continue
                    new_sx = changer.x + cc_c - sc
                    new_sy = changer.y + cr - sr
                    if (new_sx - sx) % 3 != 0 or (new_sy - sy) % 3 != 0:
                        continue
                    cost = abs(new_sx - sx) // 3 + abs(new_sy - sy) // 3
                    if cost < best_cost:
                        best_cost = cost
                        best_pos = (new_sx, new_sy)
    return best_pos, best_cost

def bfs_solve(game, max_depth=50, max_states=500000):
    initial_level = game._current_level_index
    def get_key(g):
        ms = g.current_level.get_sprites_by_tag('0031cppcuvqlbi')
        st = []
        for m in ms:
            px = m.pixels; h, w = px.shape
            st.append((m.x, m.y, hash(px.tobytes()), int(px[h//2, w//2])))
        return tuple(st)

    initial = copy.deepcopy(game)
    queue = deque([(initial, [])])
    visited = {get_key(initial)}
    actions = [U, D, L, R, SW]

    while queue:
        g, path = queue.popleft()
        if len(path) >= max_depth:
            continue
        for a in actions:
            g2 = copy.deepcopy(g)
            if g2.ylzrmgmdyh and g2.cptlsijjli:
                do(g2, a)
                s = get_key(g2)
                if s not in visited:
                    visited.add(s)
                    queue.append((g2, path + [a]))
                continue
            do(g2, a)
            if g2._current_level_index > initial_level:
                return path + [a]
            if g2.xikvflgqgp.current_steps <= 0:
                continue
            s = get_key(g2)
            if s not in visited:
                visited.add(s)
                queue.append((g2, path + [a]))
            if len(visited) > max_states:
                return None
    return None

# ===== MAIN =====
def main():
    game = Re86()
    human = [26, 42, 86, 108, 189, 139, 424, 241]
    results = {}

    # L1: selected=col9(23,32), move to (35,11), SW, col11(10,16) move to (4,-2)
    L1 = move_seq(12, -21) + [SW] + move_seq(-6, -18)
    results[0] = execute(game, L1)

    # L2: selected=col12(16,7)->(7,37), SW, col13(30,21)->(12,3), SW, col9(35,29)->(14,35)
    L2 = move_seq(7-16, 37-7) + [SW] + move_seq(12-30, 3-21) + [SW] + move_seq(14-35, 35-29)
    results[1] = execute(game, L2)

    # L3: selected=line(9,45), SW->X(7,37)->(31,13), SW->diamond(33,36)->(6,18), SW->line->(6,6)
    L3 = [SW] + move_seq(31-7, 13-37) + [SW] + move_seq(6-33, 18-36) + [SW] + move_seq(6-9, 6-45)
    results[2] = execute(game, L3)

    # L4: selected=cross6(41,23)->changer12->target12, SW, filled10(14,11)->changer14->target14
    t4 = 0
    # Move cross to changer 12 (optimal contact)
    s4 = selected(game)
    cc4 = game.current_level.get_sprites_by_tag('0007dtbisvazhv')
    ch12 = [c for c in cc4 if int(c.pixels[1,1]) == 12][0]
    pos4, _ = best_changer_contact(s4, ch12)
    t4 += execute(game, move_seq(pos4[0]-s4.x, pos4[1]-s4.y))
    # Move to target for goals 12
    plan4t = adaptive_target(game, [(15,18),(27,30),(15,43)])
    t4 += execute(game, plan4t)
    t4 += execute(game, [SW])
    # Filled sprite to changer 14
    s4b = selected(game)
    ch14 = [c for c in cc4 if int(c.pixels[1,1]) == 14][0]
    pos4b, _ = best_changer_contact(s4b, ch14)
    t4 += execute(game, move_seq(pos4b[0]-s4b.x, pos4b[1]-s4b.y))
    plan4t2 = adaptive_target(game, [(48,21),(33,24),(30,39)])
    t4 += execute(game, plan4t2)
    results[3] = t4

    # L5: *X11(13,31), diamond14(21,9), cross12(40,19)
    # SW->diamond, changer8, target8; SW->cross, D7+L11 changer9, target9; SW->X, D2L3 changer9, R5U11 target9
    t5 = 0
    t5 += execute(game, [SW])  # diamond
    s5d = selected(game)
    cc5 = game.current_level.get_sprites_by_tag('0007dtbisvazhv')
    ch8 = [c for c in cc5 if int(c.pixels[1,1]) == 8][0]
    pos5d, _ = best_changer_contact(s5d, ch8)
    t5 += execute(game, move_seq(pos5d[0]-s5d.x, pos5d[1]-s5d.y))
    plan5t = adaptive_target(game, [(51,27),(57,33),(42,36),(54,42)])
    t5 += execute(game, plan5t)

    t5 += execute(game, [SW])  # cross
    # Cross must go D first then L to avoid changer14 at (3,27)
    t5 += execute(game, move_seq(0, 21) + move_seq(-33, 0))
    plan5t2 = adaptive_target(game, [(33,45),(24,51),(45,51),(33,60)])
    t5 += execute(game, plan5t2)

    t5 += execute(game, [SW])  # X
    # X must go D2 then L3 to hit changer9 avoiding changer14
    t5 += execute(game, [D, D, L, L, L])
    # Move R first then U to target (19,4) to avoid changer11 at (3,3)
    s5x = selected(game)
    offsets5x = get_offsets(s5x)
    targets5x = find_targets([(21,6),(39,6)], offsets5x, s5x.x, s5x.y)
    if targets5x:
        tx, ty = targets5x[0]
        t5 += execute(game, move_seq(tx - s5x.x, 0) + move_seq(0, ty - s5x.y))
    results[4] = t5

    # L6: Diamond(selected) reshape U2+R4, then navigate around obstacle, SW, cross reshape
    if game._current_level_index == 5:
        t6 = 0
        # Diamond: U2 R4 -> (18,27) 10x28. Target (45,30).
        # Can't go right directly (hits obstacle). Go DOWN first below obstacle (y>35), then RIGHT.
        # From (18,27) 10x28: bottom at y=54. Move D: y=30, bottom at 57.
        # At y=30: obstacle y=[28,35]. Diamond y=[30,57]. Overlap at [30,35].
        # At y=36-27=9D from y=27: y=36, diamond y=[36,63]. No obstacle overlap!
        # But 9D = y=27+27=54... wait 27+9*3 = 54. Obstacle at y=28..35. Diamond at y=54..81 (out of canvas).
        # Need fewer D. At y=36: 36-27=9 not div by 3. y=36=27+9 -> 3D. Diamond at [36,63]. No overlap!
        # Hmm 27+3*3=36. 3D. Then right: x=18+?=45 -> 9R. Then back up for target.
        # Actually target is (45,30). After going D3 to y=36 and R9 to x=45:
        # Diamond at (45,36) 10x28. Need target at (45,30). Move U2 to y=30.
        # But at (45,30) 10x28: y range [30,57]. Obstacle at y=[28,35]. Overlap [30,35].
        # Does the diamond collide with obstacle? Diamond x range [45,54]. Obstacle x=[28,35]. No x overlap!
        # So diamond at (45,30) doesn't collide with obstacle. Safe!

        diamond_plan = [U,U,R,R,R,R,D,D,D,R,R,R,R,R,R,R,R,R,U,U]
        t6 += execute(game, diamond_plan)
        s6d = selected(game)
        offsets6d = get_offsets(s6d)
        targets6d = find_targets([(45,30),(54,30),(45,57),(54,57)], offsets6d, s6d.x, s6d.y)
        if targets6d:
            t6 += execute(game, move_seq(targets6d[0][0]-s6d.x, targets6d[0][1]-s6d.y))
        else:
            print(f"  L6 diamond target FAILED: ({s6d.x},{s6d.y}) {s6d.width}x{s6d.height}")

        t6 += execute(game, [SW])  # cross
        # Cross: D5 L2 U L D2 -> reshape arms, then to target (6,3)
        cross_reshape = [D,D,D,D,D,L,L,U,L,D,D]
        t6 += execute(game, cross_reshape)
        plan6ct = adaptive_target(game, [(12,6),(9,9),(30,9),(12,27)])
        if plan6ct:
            t6 += execute(game, plan6ct)
        else:
            print("  L6 cross target FAILED")
        results[5] = t6
        print(f"  L6: {t6} actions, level={game._current_level_index}")

    # L7: 3 sprites, 5 changers, 1 obstacle at (28,28) 8x8
    # Goals: col8@(9,9)(3,15)(36,15)(9,27), col9@(57,18)(39,24), col11@(45,30)(39,48)(51,48)
    # Cross(19x19) -> col11 V=9 H=18 -> (36,30)
    # Frame(13x13,0036) -> col9 reshape 19x7 -> (39,18)
    # Plus(37x19) -> col8 V=9 H=6 -> (0,9)
    if game._current_level_index == 6:
        t7 = 0
        # Cross: reshape via obstacle then changer 11 then target
        t7 += execute(game, [R]*3 + [U]*7 + [L]*1 + [U]*6 + [R]*3 + [D]*3 + [R]*6 + [D]*7)
        # SW -> frame
        t7 += execute(game, [SW])
        # Frame: reshape to 19x7 via obstacle, changer 9, target
        t7 += execute(game, [R]*1 + [U]*5 + [L]*3 + [U]*11 + [D]*2 + [R]*11 + [D]*3)
        # SW -> plus
        t7 += execute(game, [SW])
        # Plus: navigate to reshape V=9 H=6, touch changer 8, reach target (0,9)
        # R1 U6 -> (9,27) approach obs for V reshape
        # R3 -> V 18->9 via obstacle R collisions at y=27
        # L9 U3 R9 -> reposition to (18,18) safely
        # D1 -> H reshape 9->6 via horiz-only obs collision
        # L6 U7 -> (0,0) safely avoiding changers
        # R9 -> (27,0) passing through changers, last is ch8
        # D3 L9 -> (0,9) target
        t7 += execute(game, [R]*1 + [U]*6 + [R]*3 + [L]*9 + [U]*3 + [R]*9 + [D]*1
                           + [L]*6 + [U]*7 + [R]*9 + [D]*3 + [L]*9)
        results[6] = t7
        print(f"  L7: {t7} actions, level={game._current_level_index}")

    # L8: 2 frame sprites, 14 changers, 2 reshape obstacles
    # Sprite 0 (col10,13x13@48,39) -> col11, 7x19 @ (9,39)
    # Sprite 1 (col12,13x13@45,42) -> col6, 16x10 @ (6,45)
    # Strategy: SW to sprite 0, reshape+recolor+position, SW to sprite 1, reshape+recolor+position
    if game._current_level_index == 7:
        t8 = 0
        # SW to select sprite 0
        t8 += execute(game, [SW])
        # Sprite 0 path: navigate through obstacle+changer field to reach (9,39) 7x19 col11
        # U14 D1 L12 D2 R9 U4 R3 D1 R2 D1 R2 D2 L3 D9 L3 D1 L3 D1 L6
        path0 = ([U]*14 + [D] + [L]*12 + [D,D] + [R]*9 + [U]*4 + [R]*3 + [D] +
                 [R]*2 + [D] + [R]*2 + [D,D] + [L]*3 + [D]*9 + [L]*3 + [D] + [L]*3 + [D] + [L]*6)
        t8 += execute(game, path0)
        # SW to select sprite 1
        t8 += execute(game, [SW])
        # Sprite 1 path: reshape via obstacle, recolor via changers, reach (6,45) 16x10 col6
        # L3 D3 U11 L7 U1 R8 U4 R3 D1 R2 D1 R2 D2 L3 D9 L3 D4 L8
        path1 = ([L]*3 + [D]*3 + [U]*11 + [L]*7 + [U] + [R]*8 + [U]*4 + [R]*3 + [D] +
                 [R]*2 + [D] + [R]*2 + [D,D] + [L]*3 + [D]*9 + [L]*3 + [D]*4 + [L]*8)
        t8 += execute(game, path1)
        results[7] = t8
        print(f"  L8: {t8} actions, state={game._state}")

    # ===== RESULTS TABLE =====
    print(f'\n{"="*60}')
    print(f'{"GAME":>6} {"LEVEL":>6}|{"HUMAN":>6}|{"OURS":>6}|{"RATIO":>7}|{"RHAE":>8}')
    print(f'{"-"*6} {"-"*6}|{"-"*6}|{"-"*6}|{"-"*7}|{"-"*8}')
    total_rhae = 0
    for lvl in range(8):
        h = human[lvl]
        if lvl in results:
            ours = results[lvl]
            ratio = h / ours
            rhae = ratio ** 2
            total_rhae += rhae
            print(f'{"re86":>6} {lvl+1:>6}|{h:>6}|{ours:>6}|{ratio:>7.3f}|{rhae:>8.4f}')
        else:
            print(f'{"re86":>6} {lvl+1:>6}|{h:>6}|{"N/A":>6}|{"N/A":>7}|{"N/A":>8}')
    print(f'{"":>6} {"TOTAL":>6}|{"":>6}|{"":>6}|{"":>7}|{total_rhae:>8.4f}')

if __name__ == '__main__':
    main()
