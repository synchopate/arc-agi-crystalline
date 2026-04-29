#!/usr/bin/env python3
"""sb26 solver — Color puzzle with frames, portals, and target matching.

Mechanics:
  - Arrange colored pieces from palette (bottom row) into frame slots
  - Portal pieces (vgszefyyyp) link to other frames by matching border color
  - ACTION5 submits: evaluates frames left-to-right, matching piece colors against
    target sequence shown in top row
  - Portals redirect evaluation into sub-frames recursively
  - Win when all targets are matched in order

Strategy:
  1. Extract level structure: targets, frames, slots, portals, palette
  2. Build evaluation order via brute-force permutation search
  3. Place pieces and submit
"""
import arc_agi
import numpy as np
import warnings
import logging
from itertools import permutations

warnings.filterwarnings('ignore')
logging.disable(logging.WARNING)

# Constants from game source
KOJDUUMCAP = 6    # slot spacing within frame
GMELNTISSB = 2    # offset from frame border to first slot
EVRMZYFOPO = 53   # y-coordinate of divider line


def simulate_eval(frame_contents, frame_borders, targets, max_iters=500):
    """Simulate the evaluation algorithm from dbfxrigdqx.

    Args:
        frame_contents: dict {frame_idx: [(type, color), ...]} where type is 'piece' or 'portal'
        frame_borders: dict {border_color: frame_idx}
        targets: list of target colors in order

    Returns:
        True if arrangement matches all targets.
    """
    stack = [(0, 0)]
    target_idx = 0
    ppsxsxiod = False
    iters = 0

    while stack and iters < max_iters:
        iters += 1
        fi, si = stack[-1]
        items = frame_contents[fi]
        num_slots = len(items)

        if si >= num_slots:
            if len(stack) > 1:
                stack.pop()
                ppsxsxiod = True
            else:
                break
            continue

        item_type, item_color = items[si]

        # Portal entry (not during ppsxsxiod return)
        if item_type == 'portal' and not ppsxsxiod:
            # Error check from game code line 976
            if si == 0:
                for prev_fi, prev_si in stack[:-1]:
                    if prev_fi == fi and prev_si == 0:
                        if len(stack) >= 2 and stack[-2][1] == 0:
                            return False
            target_fi = frame_borders.get(item_color)
            if target_fi is None:
                return False
            stack.append((target_fi, 0))
            continue

        # Win: last target matched
        if target_idx == len(targets) - 1:
            if item_type == 'piece' and not ppsxsxiod:
                return item_color == targets[target_idx]

        # Piece match
        if item_type == 'piece' and not ppsxsxiod:
            if target_idx >= len(targets):
                return False
            if item_color != targets[target_idx]:
                return False

        # Advance to next slot (handles both piece match and ppsxsxiod return)
        if ppsxsxiod:
            ppsxsxiod = False

        next_si = si + 1
        if next_si < num_slots:
            stack[-1] = (fi, next_si)
            target_idx += 1
        elif len(stack) > 1:
            stack.pop()
            ppsxsxiod = True
        else:
            break

    return False


def analyze_level(game):
    """Extract level structure from game state."""
    g = game

    # Target colors sorted by position (y, x)
    target_sprites = sorted(g.wcfyiodrx, key=lambda s: (s.y, s.x))
    target_colors = [int(s.pixels[0, 0]) for s in target_sprites]

    # Frames sorted by (y, x) - frame 0 is always the starting frame
    frames = sorted(g.qaagahahj, key=lambda f: (f.y, f.x))

    frame_info = []
    border_to_frame = {}  # border_color -> frame_index

    for idx, f in enumerate(frames):
        num_slots = int(f.name[-1])
        border_color = int(f.pixels[0, 0])
        if border_color not in border_to_frame:
            border_to_frame[border_color] = idx

        slots = []
        for i in range(num_slots):
            x, y = f.x + GMELNTISSB + i * KOJDUUMCAP, f.y + GMELNTISSB
            item_type = 'empty'
            item_color = None
            item_sprite = None
            movable = True

            for s in g.dkouqqads:
                if s.x == x and s.y == y:
                    if s.name == 'vgszefyyyp':
                        item_type = 'portal'
                    else:
                        item_type = 'piece'
                    item_color = int(s.pixels[1, 1])
                    item_sprite = s
                    movable = 'sys_click' in s.tags
                    break

            if item_type == 'empty':
                for s in g.dewwplfix:
                    if s.x == x and s.y == y:
                        break

            slots.append({
                'x': x, 'y': y,
                'type': item_type,
                'color': item_color,
                'movable': movable,
                'sprite': item_sprite,
            })

        frame_info.append({
            'frame': f,
            'border_color': border_color,
            'num_slots': num_slots,
            'slots': slots,
        })

    # Palette items (below divider line, have sys_click)
    palette = []
    for s in g.dkouqqads:
        if s.y > EVRMZYFOPO:
            ptype = 'portal' if s.name == 'vgszefyyyp' else 'piece'
            palette.append({
                'x': s.x, 'y': s.y,
                'type': ptype,
                'color': int(s.pixels[1, 1]),
                'sprite': s,
            })
    palette.sort(key=lambda p: p['x'])

    return {
        'targets': target_colors,
        'frames': frame_info,
        'palette': palette,
        'border_to_frame': border_to_frame,
    }


def find_placement(info):
    """Find optimal placement of palette items into frame slots via brute force.

    Returns list of (palette_idx, frame_idx, slot_idx) or None.
    """
    frames = info['frames']
    palette = info['palette']
    targets = info['targets']
    border_to_frame = info['border_to_frame']

    # Collect empty slots across all frames
    empty_slots = []
    pre_placed = {}  # (frame_idx, slot_idx) -> (type, color)

    for fi, frame in enumerate(frames):
        for si, slot in enumerate(frame['slots']):
            if slot['type'] == 'empty':
                empty_slots.append((fi, si))
            else:
                pre_placed[(fi, si)] = (slot['type'], slot['color'])

    n_empty = len(empty_slots)
    n_palette = len(palette)

    if n_palette != n_empty:
        print(f"  WARNING: palette({n_palette}) != empty({n_empty})")
        # Try anyway with min
        n_to_place = min(n_palette, n_empty)
    else:
        n_to_place = n_palette

    # Build palette items as (type, color) tuples
    palette_items = [(p['type'], p['color']) for p in palette]

    # Brute force: try all permutations of palette items into empty slots
    best = None
    seen = set()

    for perm in permutations(range(n_to_place)):
        # Build frame contents
        frame_contents = {}
        for fi, frame in enumerate(frames):
            contents = []
            for si in range(frame['num_slots']):
                if (fi, si) in pre_placed:
                    contents.append(pre_placed[(fi, si)])
                else:
                    # Find this slot in empty_slots
                    slot_idx_in_empty = None
                    for esi, (efi, esi2) in enumerate(empty_slots):
                        if efi == fi and esi2 == si:
                            slot_idx_in_empty = esi
                            break
                    if slot_idx_in_empty is not None and slot_idx_in_empty < n_to_place:
                        pi = perm[slot_idx_in_empty]
                        contents.append(palette_items[pi])
                    else:
                        contents.append(('empty', -1))
            frame_contents[fi] = contents

        # Deduplicate
        key = tuple(tuple(v) for v in frame_contents.values())
        if key in seen:
            continue
        seen.add(key)

        if simulate_eval(frame_contents, border_to_frame, targets):
            # Build placement mapping
            placement = []
            for esi, (efi, esi2) in enumerate(empty_slots):
                if esi < n_to_place:
                    pi = perm[esi]
                    placement.append((pi, efi, esi2))
            return placement

    return None


def solve_level(env, game, level_num):
    """Solve a single level."""
    info = analyze_level(game)

    print(f"  Targets ({len(info['targets'])}): {info['targets']}")
    print(f"  Frames: {len(info['frames'])}")
    for i, fi in enumerate(info['frames']):
        n_pre = sum(1 for s in fi['slots'] if s['type'] != 'empty')
        n_empty = sum(1 for s in fi['slots'] if s['type'] == 'empty')
        print(f"    F{i} border={fi['border_color']} slots={fi['num_slots']} (pre={n_pre} empty={n_empty})")
    print(f"  Palette ({len(info['palette'])}): {[(p['type'][0], p['color']) for p in info['palette']]}")

    placement = find_placement(info)

    if placement is None:
        print(f"  No valid placement found!")
        return None

    print(f"  Found placement with {len(placement)} moves")

    # Execute placement
    for pi, fi, si in placement:
        p = info['palette'][pi]
        slot = info['frames'][fi]['slots'][si]
        # Click center of palette piece
        px, py = p['x'] + 3, p['y'] + 3
        # Click center of target slot
        sx, sy = slot['x'] + 3, slot['y'] + 3
        env.step(6, data={'x': px, 'y': py})
        env.step(6, data={'x': sx, 'y': sy})

    # Submit with ACTION5
    obs = env.step(5)
    return obs


def main():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('sb26')
    obs = env.reset()
    obs = env.step(6)
    game = env._game

    print(f"sb26: {obs.win_levels} levels")

    for level in range(1, obs.win_levels + 1):
        if obs.state.name != 'NOT_FINISHED':
            break

        print(f"\n=== Level {level} ===")
        obs = solve_level(env, game, level)

        if obs is None:
            print(f"  FAILED")
            break

        print(f"  completed={obs.levels_completed} state={obs.state.name}")

        if obs.state.name == 'WIN':
            break

        game = env._game

    total = obs.levels_completed if obs.state.name != 'WIN' else obs.win_levels
    print(f"\n{'=' * 40}")
    print(f"sb26 RESULT: {total}/{obs.win_levels}")
    print(f"{'=' * 40}")
    return total, obs.win_levels


if __name__ == "__main__":
    main()
