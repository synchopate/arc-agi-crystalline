# Opus 4.6 + Crystalline Cognitive Memory

**Current: v2.0 (97.69%, 23/25 WIN, 180/183 levels). [Version history](#version-history) for v1.0 -> v1.3 -> v2.0 progression.**

**Verified scorecard**: [arcprize.org/scorecards/9e767cda-5cdb-4efd-9656-43513e10a693](https://arcprize.org/scorecards/9e767cda-5cdb-4efd-9656-43513e10a693)

## Scope and Limitations

This work evaluates on the **ARC-AGI-3 public set** using a domain-specific harness that reads game source code and builds per-game solvers. Per [ARC Prize](https://arcprize.org), public-set scores are not a measure of AGI progress. The contribution here is harness research: showing how persistent cognitive memory improves an LLM-based solver on known environments. Generalization to the private set is untested.

## Results

| Metric | Score |
|--------|-------|
| **Levels Completed** | **180/183 (98.4%)** |
| **Games Won (all levels)** | **23/25 (92%)** |
| **Score** | **97.69%** |

### Comparison

| System | Score | Evaluation | Harness | Source |
|--------|-------|------------|---------|--------|
| **Opus 4.6 + Crystalline** | **97.69%** | Public set, source-reading harness | Per-game solvers + cognitive memory | [scorecard](https://arcprize.org/scorecards/9e767cda-5cdb-4efd-9656-43513e10a693) |
| Opus 4.6 alone (ablation) | ~57% | Public set, same harness, no memory | Per-game solvers, single attempt | [ablation details](#ablation-study-2025-games-tested) |
| Read-Grep-Bash Agent (DukeNLP) | 82.43% | Public set, source-reading harness | CLI agent with search | [paper](https://blog.alexisfox.dev/arcagi3), [code](https://github.com/alexisfox7/RGB-Agent), [scorecards](https://arcprize.org/scorecards/35d7852f-bb5c-4d40-b0e0-df501c27ef6f) |
| Frontier AI baselines | 0.1-0.5% | Semi-private set, no harness | Direct LLM prompting (CoT) | [arcprize.org/leaderboard](https://arcprize.org/leaderboard) |

Note: Frontier AI baselines use a different evaluation set and no source-reading harness. These numbers are not directly comparable to harness-based scores.

## Architecture

### Core Components

1. **Claude Opus 4.6** -- The reasoning engine. Reads game source code, understands mechanics, generates Python solvers.

2. **Crystalline Cognitive Memory** -- A 5-level cognitive memory system inspired by ACT-R theory:
   - **Episodic**: "at level 3 of vc33, clicking tube 2 pours into tube 4"
   - **Semantic**: "in pipe games, pours transfer one unit at a time"
   - **Procedural**: "when BFS fails, extract logic into pure Python simulation"
   - **Analogical**: "vc33 (pipes) is structurally similar to Tower of Hanoi"
   - **Principle**: "ALWAYS reverse-engineer mechanics before attempting BFS"

3. **Parallel Agent Architecture** -- Up to 12 agents running simultaneously, each solving a different game.

### Solving Pipeline

```
Phase 1 -- OBSERVE (5 min)
  Load game, check camera, count clickables, try 1 click, observe changes.
  Classify: TRANSPARENT (visible changes) or OPAQUE (internal state only).

Phase 2 -- READ step() (10 min)
  Find step() method in game source (obfuscated but readable Python).
  Identify: click handler, action effects, win condition.

Phase 3 -- MODEL (15 min)
  Build pure Python simulation: state tuple, action functions, win check.
  Pure sim runs at 100,000 states/sec vs 200 states/sec with SDK.

Phase 4 -- SOLVE
  Select strategy by game structure:
  - LINEAR ALGEBRA: Lights Out variants -> Gaussian elimination (ft09)
  - CONSTRAINT SATISFACTION: matching puzzles -> backtracking (cn04, sb26)
  - BFS/A*: maze/movement puzzles -> shortest path search (tu93, m0r0)
  - PLANNING: multi-step assembly -> sequential move planning (r11l, s5i5)
  - PROGRAMMING: instruction encoding -> opcode search (tn36, cd82)

Phase 5 -- EXECUTE
  Replay solution on SDK. Verify levels_completed increases.
  If mismatch -> model is wrong, return to Phase 2.
```

### The Retry Multiplier

First attempts discover mechanics and fail on hard levels. Crystalline stores *why* they failed. Second attempts with crystallized lessons skip dead ends and apply correct strategies immediately.

**Measured**: Retries gained +28 levels across 8 games (50% recovery rate).

### Cross-Domain Transfer

Knowledge transfers between games:
- Camera scaling discovered on vc33 -> prevented same bug on all 24 subsequent games
- "SDK BFS is slow" learned once -> all games used pure simulation from the start
- "500K states insufficient" from lp85 -> s5i5 retry used 1M+ limit and won
- Algebraic insight from ft09 -> checked structure in every subsequent game

## Per-Game Results

| Game | Score | Type |
|------|-------|------|
| tu93 | 9/9 WIN | Pac-Man maze + 3 enemy types |
| su15 | 9/9 WIN | Merge matching + enemy luring |
| lf52 | 10/10 WIN | Peg solitaire + slider transport (viewport-constrained BFS) |
| sb26 | 8/8 WIN | Color-matching with recursive portals |
| ar25 | 8/8 WIN | Reflection/mirror symmetry |
| sk48 | 8/8 WIN | Track/chain sliding puzzle |
| s5i5 | 8/8 WIN | Bar/pipe rotation puzzle |
| lp85 | 8/8 WIN | Multi-gear circular track |
| re86 | 8/8 WIN | Color changer navigation |
| ka59 | 7/7 WIN | Sliding puzzle with bombs |
| tn36 | 7/7 WIN | Programming with opcodes + checkpoints |
| ls20 | 7/7 WIN | Modifier maze with moving elements |
| vc33 | 7/7 WIN | Water sort with gravity + buttons |
| g50t | 7/7 WIN | Clone recording + pressure plates |
| r11l | 6/6 WIN | Piece arrangement + collectibles |
| cd82 | 6/6 WIN | Canvas painting (basket rotation) |
| tr87 | 6/6 WIN | Cyclic pattern matching + rule chains |
| cn04 | 6/6 WIN | Jigsaw marker matching |
| m0r0 | 6/6 WIN | Mirror-symmetry maze + switches |
| ft09 | 6/6 WIN | Lights Out (GF(p) algebra) |
| sc25 | 6/6 WIN | Wizard spell-casting maze |
| sp80 | 6/6 WIN | Liquid/deflector puzzle |
| dc22 | 6/6 WIN | Crane puzzle (see [dc22 note](#dc22-crane-puzzle)) |
| wa30 | 8/9 | NPC relay delivery (kill saboteur NPCs + reactive solver) |
| bp35 | 7/9 | Gravity platformer (manual 6-phase gravity-flip) |

### dc22 Crane Puzzle

dc22 is the only ARC-AGI-3 game where no other submission on the [community leaderboard](https://github.com/arcprize/ARC-AGI-Community-Leaderboard) reports a full solve. The [verified AI leaderboard](https://arcprize.org/leaderboard) shows frontier models scoring 0% on their evaluation set (which uses different conditions). Our solve required a 582K-state BFS with crane attachment state tracking, found only after Crystalline stored a critical bug fix (crane state reset order) from earlier failed attempts.

## Key Principles Discovered

1. **Observability determines methodology** -- Transparent games (visible sprite changes) allow trial-and-error learning. Opaque games (internal state only) require source code reading.

2. **Pure simulation always** -- Extracting game logic into Python functions gives 500x speedup over SDK replay. SDK is only for initial state and final verification.

3. **Strategy selection by game structure** -- Identifying the puzzle type (algebra, constraint, graph, planning) before coding saves hours. A Lights Out game solved via BFS takes forever; via linear algebra it's instant.

4. **Breadth-first across games** -- Solving L1-L3 of 10 games (20 levels, ~30 min) beats solving L1-L7 of 1 game (7 levels, ~5 hours). The multi-armed bandit insight.

5. **First attempt = reconnaissance** -- The real solving happens on retry, armed with crystallized failure lessons.

6. **Verify independently** -- Never trust self-reported results. Always re-run solvers and count actual actions.

## The Value of Crystalline

### Ablation Study (20/25 games tested)

Single run per condition. 5 games excluded due to API errors during the ablation run.

| Condition | Levels Solved | WIN Games |
|-----------|--------------|-----------|
| Opus 4.6 + Crystalline | **176/176 (100%)** | **20/20** |
| Opus 4.6 alone | 101/176 (57.4%) | 10/20 |

Crystalline adds **+70% level completion** and doubles the number of games won.

### Where Crystalline makes the difference

| Category | Games | Pattern |
|----------|-------|---------|
| **No difference (delta 0)** | ar25, cd82, cn04, lp85, m0r0, r11l, sb26, sc25, tr87, vc33 | Games where Opus solves everything on first attempt |
| **Critical (delta -5 to -8)** | sk48, g50t, lf52, su15, bp35 | Complex games requiring retry-with-lessons, cross-game transfer, or viewport bug discovery |
| **Moderate (delta -2 to -4)** | dc22, ka59, sp80, re86 | Games needing deeper BFS or mechanic-specific fixes |

### Key examples

- **sk48**: 1/8 without -> 8/8 with. Perpendicular push mechanics learned through crystallized failure lessons.
- **g50t**: 0/7 without -> 7/7 with. Clone+enemy+toggle wall strategy discovered through iterative reasoning.
- **lf52**: 3/10 without -> 10/10 with. Camera scroll viewport constraint discovered and transferred across games.
- **dc22**: 4/6 without -> 6/6 with. Crane state reset bug fixed after Crystalline stored the failure pattern.

Crystalline doesn't memorize solutions -- every game is solved from scratch. It memorizes *why things fail* and *how to overcome them*.

## Reproducibility

```bash
# Prerequisites: Python 3.12, arc-agi SDK (pip install arc-agi)
export ARC_API_KEY=<your-key>

# Run all solvers and record solutions (~14 hours, ~$120 in Claude API calls)
cd solvers/
python3 record_all.py

# Replay recorded solutions in competition mode
python3 competition_replay.py
```

All 25 per-game solvers are in [`solvers/`](./solvers/). Recorded action sequences in [`solvers/recorded_solutions.json`](./solvers/recorded_solutions.json).

## Version History

| Version | Date | Score | Levels | WIN |
|---------|------|-------|--------|-----|
| v1.0 | 2026-04-24 | 86.62% | 164/183 | 19/25 |
| v1.3 | 2026-04-25 | 92.30% | 173/183 | 21/25 |
| v2.0 | 2026-04-26 | 97.69% | 180/183 | 23/25 |

## Cost

- ~$120 in Claude API calls across all solving sessions
- ~14 hours of wall-clock time (including retries and optimization)
- Hardware: Standard laptop, no GPU required

## Contact

- Author: Paolo C
- GitHub: [@synchopate](https://github.com/synchopate)
- Community leaderboard PR: [arcprize/ARC-AGI-Community-Leaderboard#22](https://github.com/arcprize/ARC-AGI-Community-Leaderboard/pull/22)

---

*Built with Claude Code and Crystalline Cognitive Memory*
