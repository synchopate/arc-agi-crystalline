#!/usr/bin/env python3
"""Solver for ARC-AGI-3 game m0r0 — mirror-movement puzzle with barriers and switches."""

import arc_agi
from universal_harness import grid_to_display, replay_solution


def solve():
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make("m0r0")
    obs = env.reset()
    obs = env.step(5)  # initial action
    game = env._game

    print(f"m0r0: {obs.win_levels} levels")

    level_solutions = {}

    # =========================================================================
    # Level 1: wahtyt-Level6 rotated 180, grid 11x11
    # Pieces: leklkn(3,9), rivmdg(7,9) — pure directional, no obstacles
    # Mirror movement: leklkn=(dx,dy), rivmdg=(-dx,dy)
    # Navigate around hourglass-shaped wall to merge at top
    # =========================================================================
    sol1 = [1, 1, 3, 1, 3, 1, 1, 1, 1, 1, 4, 1, 4, 4, 4]  # UULULUUUUURURRR
    for a in sol1:
        obs = env.step(a)
    print(f"L1: {obs.levels_completed} ({'OK' if obs.levels_completed >= 1 else 'FAIL'})")
    game = env._game

    # =========================================================================
    # Level 2: wahtyt-Level11 at (2,0), grid 13x13
    # Pieces: leklkn(4,1), rivmdg(8,1) — spswjz hazards at rows 8,12
    # Strategy: go around the wall via the outer columns, avoid hazard rows
    # =========================================================================
    sol2 = [2, 3, 3, 3, 2, 2, 2, 4, 4, 1, 4, 4, 2, 2, 2, 2, 2, 2, 4, 4, 4, 1, 3]
    for a in sol2:
        obs = env.step(a)
    print(f"L2: {obs.levels_completed} ({'OK' if obs.levels_completed >= 2 else 'FAIL'})")
    game = env._game

    # =========================================================================
    # Level 3: wahtyt-Level1, grid 13x13
    # Pieces: leklkn(4,10), rivmdg(8,10)
    # mosdlc obstacles at (1,3), (6,2), (8,6) block piece movement
    # Strategy: click each mosdlc and move it to safe cells, then navigate
    # Key: mosdlc(6,2) blocks the ONLY crossing between left/right halves
    # =========================================================================
    cam = game.camera
    s3, x3, y3 = cam._calculate_scale_and_offset()

    def click3(gx, gy):
        return env.step(6, data={"x": int(gx * s3 + x3), "y": int(gy * s3 + y3)})

    # Move mosdlc (1,3) -> (2,11): click, 15 moves, deselect
    click3(1, 3)
    for a in [2, 2, 2, 2, 4, 4, 4, 4, 2, 2, 2, 2, 3, 3, 3]:
        obs = env.step(a)
    click3(2, 9)

    # Move mosdlc (6,2) -> (3,11): click, 26 moves, deselect
    click3(6, 2)
    for a in [3, 2, 2, 2, 3, 3, 1, 1, 1, 3, 3, 2, 2, 2, 2, 2, 4, 4, 4, 4, 2, 2, 2, 2, 3, 3]:
        obs = env.step(a)
    click3(2, 9)

    # Move mosdlc (8,6) -> (11,11): click, 8 moves, deselect
    click3(8, 6)
    for a in [4, 4, 2, 2, 2, 2, 2, 4]:
        obs = env.step(a)
    click3(2, 9)

    # Navigate pieces: 31 directional moves
    sol3_pieces = [1, 3, 3, 1, 1, 1, 4, 4, 4, 1, 1, 3, 3, 3, 3, 1, 1, 1, 1, 1, 4, 4, 4, 4, 2, 4, 4, 2, 2, 2, 4]
    for a in sol3_pieces:
        obs = env.step(a)
    print(f"L3: {obs.levels_completed} ({'OK' if obs.levels_completed >= 3 else 'FAIL'})")
    game = env._game

    # =========================================================================
    # Level 4: wahtyt-Level9, grid 11x11
    # Pieces: leklkn(2,6), rivmdg(8,4) — asymmetric start
    # mosdlc at (5,5) blocks center crossing
    # spswjz hazards ring the edges and center corridors
    # Strategy: click mosdlc, move LEFT x4 to (1,5), then navigate pieces
    # =========================================================================
    cam = game.camera
    s4, x4, y4 = cam._calculate_scale_and_offset()

    def click4(gx, gy):
        return env.step(6, data={"x": int(gx * s4 + x4), "y": int(gy * s4 + y4)})

    # Move mosdlc (5,5) -> (1,5): click, 4 moves, deselect
    click4(5, 5)
    for a in [3, 3, 3, 3]:
        obs = env.step(a)
    click4(2, 8)

    # Navigate pieces: 10 directional moves
    sol4_pieces = [1, 1, 3, 2, 2, 4, 2, 4, 4, 4]  # UULDDRDRRR
    for a in sol4_pieces:
        obs = env.step(a)
    print(f"L4: {obs.levels_completed} ({'OK' if obs.levels_completed >= 4 else 'FAIL'})")
    game = env._game

    # =========================================================================
    # Level 5: wahtyt-Level2, grid 15x15
    # Pieces: leklkn(13,12), rivmdg(1,12) — opposite sides
    # gayktr barriers (colored walls) toggled by standing on unobxw switches
    # No mosdlc or spswjz — pure barrier puzzle
    # Strategy: navigate through barriers by stepping on switches to open paths
    # =========================================================================
    sol5 = [3, 3, 1, 1, 1, 1, 3, 1, 4, 4, 1, 4, 4, 1, 3, 3, 3, 3, 1, 1, 1, 3, 3, 1, 1, 1, 1, 1, 4, 4, 1, 1, 1, 1, 1, 3, 3, 3, 3]
    for a in sol5:
        obs = env.step(a)
    print(f"L5: {obs.levels_completed} ({'OK' if obs.levels_completed >= 5 else 'FAIL'})")
    game = env._game

    # =========================================================================
    # Level 6: no wahtyt walls, grid 13x13
    # Pieces: leklkn(3,4), rivmdg(9,4) — separated by spswjz walls at col 6
    # gayktr barriers block row 6 crossing entirely
    # mosdlc at (6,9) — must be repositioned as blocking tool
    # Strategy (3-phase mosdlc blocking):
    #   Phase 1: UP x2 to activate both switches (3,2)/(9,2) -> barriers OFF
    #   Phase 2: Move mosdlc to (3,3) blocking leklkn DOWN; send rivmdg
    #            through orfrpe gap to bottom right via DOWN x7
    #   Phase 3: Move mosdlc to (4,2) blocking leklkn RIGHT; send rivmdg
    #            LEFT x6 to grwjuk switch at (3,9)
    #   Phase 4: Move mosdlc to (3,10) blocking rivmdg DOWN; send leklkn
    #            DOWN x7 through grwjuk gap to merge at (3,9)
    # =========================================================================
    cam = game.camera
    s6, x6, y6 = cam._calculate_scale_and_offset()

    def click6(gx, gy):
        return env.step(6, data={"x": int(gx * s6 + x6), "y": int(gy * s6 + y6)})

    # Phase 1: UP UP -> pieces at switches, both barriers OFF
    obs = env.step(1)
    obs = env.step(1)

    # Phase 2: Move mosdlc (6,9) -> (3,3) to block leklkn
    click6(6, 9)
    for a in [3, 1, 3, 1, 1, 1, 1, 1, 3]:  # L U L UUUUU L -> (5,9)(5,8)(4,8)(4,3)(3,3)
        obs = env.step(a)
    click6(2, 4)  # deselect

    # DOWN x7: rivmdg descends to (9,9), leklkn held at (3,2) by mosdlc
    for _ in range(7):
        obs = env.step(2)

    # Phase 3: Move mosdlc (3,3) -> (4,2) to block leklkn RIGHT
    click6(3, 3)
    obs = env.step(4)  # RIGHT to (4,3)
    obs = env.step(1)  # UP to (4,2)
    click6(2, 4)  # deselect

    # RIGHT x6: rivmdg goes LEFT from (9,9) to (3,9), leklkn held at (3,2)
    for _ in range(6):
        obs = env.step(4)

    # Phase 4: Move mosdlc (4,2) -> (3,10) to block rivmdg on switch
    click6(4, 2)
    for _ in range(8):  # DOWN x8: (4,2) -> (4,10)
        obs = env.step(2)
    obs = env.step(3)  # LEFT to (3,10)
    click6(2, 4)  # deselect

    # DOWN x7: leklkn descends from (3,2) through grwjuk gap to merge at (3,9)
    for _ in range(7):
        obs = env.step(2)

    print(f"L6: {obs.levels_completed} ({'OK' if obs.levels_completed >= 6 else 'FAIL'})")

    # Final result
    print(f"\n{'=' * 40}")
    print(f"m0r0 RESULT: {obs.levels_completed}/{obs.win_levels} — {obs.state.name}")
    print(f"{'=' * 40}")
    return obs.levels_completed, obs.win_levels


if __name__ == "__main__":
    solve()
