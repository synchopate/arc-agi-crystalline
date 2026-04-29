#!/usr/bin/env python3
"""
Solver for ARC-AGI-3 game "tr87".

This is a pattern-matching puzzle with cyclic symbol rules:
- Top row = "question" (fixed sequence of pattern sprites)
- Bottom row = "answer" (must be manipulated to satisfy rules)
- Rules map left-side patterns to right-side patterns
- Sprites cycle through 7 variants (suffix 1-7)

Actions: 1=cycle_backward, 2=cycle_forward, 3=cursor_left, 4=cursor_right

Level types:
- Basic (L1-3): modify answer sprites to match rule application on question
- double_translation (L4): chain two rules (A->B->C)
- alter_rules (L5): modify rules themselves (not answers) so they transform Q->A
- tree_translation + alter_rules (L6): tree-structured rule chaining with modifiable rules
"""
import arc_agi
import logging
logging.disable(logging.WARNING)

from itertools import permutations

NUM_VARIANTS = 7


def cyc(v, d):
    """Cycle variant v by delta d, wrapping 1-7."""
    return (v + d - 1) % NUM_VARIANTS + 1


def optimal_actions_for_delta(delta):
    """Return minimal action list to cycle by delta (0 = no change)."""
    delta = delta % NUM_VARIANTS
    if delta == 0:
        return []
    bwd = NUM_VARIANTS - delta
    if delta <= bwd:
        return [2] * delta   # forward
    else:
        return [1] * bwd     # backward


def generate_cursor_actions(current_variants, target_variants):
    """Generate optimal action sequence to cycle answer slots from current to target."""
    actions = []
    cursor = 0
    for i in range(len(current_variants)):
        delta = (target_variants[i] - current_variants[i]) % NUM_VARIANTS
        if delta == 0:
            continue
        while cursor < i:
            actions.append(4); cursor += 1
        while cursor > i:
            actions.append(3); cursor -= 1
        actions.extend(optimal_actions_for_delta(delta))
    return actions


def generate_set_actions(deltas, num_sets):
    """Generate optimal action sequence for alter_rules: cycle each set by delta."""
    actions = []
    cursor = 0
    for si in range(num_sets):
        d = deltas[si] % NUM_VARIANTS
        if d == 0:
            continue
        while cursor < si:
            actions.append(4); cursor += 1
        while cursor > si:
            actions.append(3); cursor -= 1
        actions.extend(optimal_actions_for_delta(d))
    return actions


# --- BASIC LEVEL SOLVER (L1-L3) ---

def solve_basic(game):
    """Solve a basic level: apply rules to question, then adjust answer sprites."""
    rules = game.cifzvbcuwqe
    question = game.zvojhrjxxm
    answers = game.ztgmtnnufb

    # Apply rules to question to get target answer names
    targets = []
    qi = 0
    while qi < len(question):
        for left, right in rules:
            L = len(left)
            if qi + L <= len(question) and all(
                question[qi + j].name == left[j].name for j in range(L)
            ):
                targets.extend(r.name for r in right)
                qi += L
                break
        else:
            return None

    cur_v = [int(s.name[-1]) for s in answers]
    tgt_v = [int(n[-1]) for n in targets]
    return generate_cursor_actions(cur_v, tgt_v)


# --- DOUBLE TRANSLATION SOLVER (L4) ---

def solve_double(game):
    """Solve a double_translation level: chain two rules (Q -> mid -> answer)."""
    rules = game.cifzvbcuwqe
    question = game.zvojhrjxxm
    answers = game.ztgmtnnufb

    # No portals in L4, so lonhgifaes is a no-op.
    # Logic: match Q to rule1, then match rule1's right to rule2's left,
    # then rule2's right is the target.
    targets = []
    qi = 0
    while qi < len(question):
        matched = False
        for l1, r1 in rules:
            L1 = len(l1)
            if qi + L1 > len(question):
                continue
            if not all(question[qi + j].name == l1[j].name for j in range(L1)):
                continue
            # Chain: find rule2 where left matches r1
            r1_names = [s.name for s in r1]
            for l2, r2 in rules:
                if [s.name for s in l2] == r1_names:
                    targets.extend(s.name for s in r2)
                    qi += L1
                    matched = True
                    break
            if matched:
                break
        if not matched:
            return None

    cur_v = [int(s.name[-1]) for s in answers]
    tgt_v = [int(n[-1]) for n in targets]
    return generate_cursor_actions(cur_v, tgt_v)


# --- ALTER_RULES SOLVER (L5) ---

def solve_alter_rules(game):
    """
    Solve an alter_rules level (without tree/double translation).

    We modify the rules (not the answers). Each rule set cycles independently.
    The first rule whose left matches each question position is committed to,
    and its right must match the answer -- otherwise it fails immediately.
    """
    rules = game.cifzvbcuwqe
    question = game.zvojhrjxxm
    answers = game.ztgmtnnufb

    num_rules = len(rules)
    num_sets = num_rules * 2  # left + right for each rule

    # Extract structure
    q_digits = [int(s.name[-1]) for s in question]
    a_digits = [int(s.name[-1]) for s in answers]

    rules_info = []
    for left, right in rules:
        rules_info.append((
            len(left), len(right),
            [int(s.name[-1]) for s in left],
            [int(s.name[-1]) for s in right],
        ))

    def check_deltas(d):
        """Check if set deltas d produce a valid solution."""
        # Build modified rules
        mod_rules = []
        for ri, (ls, rs, ld, rd) in enumerate(rules_info):
            dl = d[ri * 2]
            dr = d[ri * 2 + 1]
            new_left = [cyc(ld[j], dl) for j in range(ls)]
            new_right = [cyc(rd[j], dr) for j in range(rs)]
            mod_rules.append((new_left, new_right))

        qi = 0
        ai = 0
        while qi < len(q_digits):
            matched = False
            for ri, (left, right) in enumerate(mod_rules):
                L = len(left)
                R = len(right)
                if qi + L > len(q_digits) or ai + R > len(a_digits):
                    continue
                if all(q_digits[qi + j] == left[j] for j in range(L)):
                    # First matching rule -- must have correct right side
                    if all(a_digits[ai + j] == right[j] for j in range(R)):
                        qi += L
                        ai += R
                        matched = True
                    else:
                        return False  # Committed to wrong answer
                    break
            if not matched:
                return False
        return qi == len(q_digits) and ai == len(a_digits)

    # Brute force search over all 7^num_sets combinations
    # For L5: num_sets=8, 7^8 = 5.7M -- feasible
    best_cost = float('inf')
    best_d = None

    def search(idx, d):
        nonlocal best_cost, best_d
        if idx == num_sets:
            if check_deltas(d):
                cost = sum(min(di % NUM_VARIANTS, NUM_VARIANTS - di % NUM_VARIANTS) for di in d)
                # Add cursor movement cost
                pos = 0
                for si in range(num_sets):
                    if d[si] % NUM_VARIANTS != 0:
                        cost += abs(si - pos)
                        pos = si
                if cost < best_cost:
                    best_cost = cost
                    best_d = list(d)
            return

        for v in range(NUM_VARIANTS):
            d[idx] = v
            search(idx + 1, d)

    # For efficiency, use itertools instead of recursion for small spaces
    import itertools
    for combo in itertools.product(range(NUM_VARIANTS), repeat=num_sets):
        d = list(combo)
        if check_deltas(d):
            cost = sum(min(di, NUM_VARIANTS - di) for di in d)
            pos = 0
            for si in range(num_sets):
                if d[si] != 0:
                    cost += abs(si - pos)
                    pos = si
            if cost < best_cost:
                best_cost = cost
                best_d = d

    if best_d:
        return generate_set_actions(best_d, num_sets)
    return None


# --- TREE TRANSLATION + ALTER_RULES SOLVER (L6) ---

def solve_tree_alter(game):
    """
    Solve a level with tree_translation + alter_rules.

    Tree translation: for each Q item matched by an "A" rule, the rule's right side
    (B sprites) each get matched by a "B" rule, and those rules' right sides (C sprites)
    form the final answer.

    With alter_rules: each rule set (left or right of each rule) cycles independently.
    """
    rules = game.cifzvbcuwqe
    question = game.zvojhrjxxm
    answers = game.ztgmtnnufb

    num_rules = len(rules)
    num_sets = num_rules * 2

    q_digits = [int(s.name[-1]) for s in question]
    a_digits = [int(s.name[-1]) for s in answers]

    # Classify rules as "A" rules (left matches Q base) and "B" rules (left matches B base)
    # by checking the letter group
    q_base = question[0].name[:-1]  # e.g., "nxkictbbvztA"
    a_base = answers[0].name[:-1]   # e.g., "nxkictbbvztC"

    a_rules = []  # indices of rules whose left base matches Q base
    b_rules = []  # indices of rules whose left base matches intermediate base

    for ri, (left, right) in enumerate(rules):
        left_base = left[0].name[:-1]
        if left_base == q_base:
            a_rules.append(ri)
        else:
            b_rules.append(ri)

    # Extract rule info
    rules_info = []
    for left, right in rules:
        rules_info.append((
            len(left), len(right),
            [int(s.name[-1]) for s in left],
            [int(s.name[-1]) for s in right],
        ))

    def check_tree_deltas(d):
        """Check if deltas produce valid tree_translation solution."""
        # Build modified rules
        mod_rules = []
        for ri in range(num_rules):
            ls, rs, ld, rd = rules_info[ri]
            dl = d[ri * 2]
            dr = d[ri * 2 + 1]
            new_left = [cyc(ld[j], dl) for j in range(ls)]
            new_right = [cyc(rd[j], dr) for j in range(rs)]
            mod_rules.append((new_left, new_right))

        qi = 0
        ai = 0
        while qi < len(q_digits):
            matched = False
            for ri in range(num_rules):
                left, right = mod_rules[ri]
                L = len(left)
                if qi + L > len(q_digits):
                    continue
                if not all(q_digits[qi + j] == left[j] for j in range(L)):
                    continue

                # Tree translation: for each B value in right,
                # find a rule whose left[0] matches it
                c_values = []
                ok = True
                for rv in right:
                    b_matched = False
                    for bri in range(num_rules):
                        bl, br = mod_rules[bri]
                        if len(bl) == 1 and bl[0] == rv:
                            c_values.extend(br)
                            b_matched = True
                            break
                    if not b_matched:
                        ok = False
                        break

                if not ok:
                    continue  # This A rule can't be resolved

                # Check if c_values match answer
                if ai + len(c_values) > len(a_digits):
                    return False
                if all(a_digits[ai + j] == c_values[j] for j in range(len(c_values))):
                    qi += L
                    ai += len(c_values)
                    matched = True
                    break
                else:
                    return False  # First matching rule failed

            if not matched:
                return False
        return qi == len(q_digits) and ai == len(a_digits)

    # For L6: 6 rules -> 12 sets -> 7^12 = 13B too large for brute force.
    # Use structured search: enumerate A rule assignments to Q items,
    # then compute needed deltas.

    # Each Q item must be matched by one A rule.
    # Each A rule produces 2 B values (typically), each B value maps through a B rule to C values.

    a_rule_bases = [(ri, rules_info[ri][2][0]) for ri in a_rules]  # (rule_idx, left_base_digit)
    b_rule_bases = [(ri, rules_info[ri][2][0], rules_info[ri][3]) for ri in b_rules]

    best_cost = float('inf')
    best_deltas = None

    # Try all permutations of A rules to Q positions
    # (with repetition if len(Q) > len(a_rules), but typically len(Q) == len(a_rules))
    from itertools import product as iprod

    if len(q_digits) <= len(a_rules):
        # Try all assignments of a_rules to Q positions (permutations)
        for perm in permutations(range(len(a_rules)), len(q_digits)):
            # For each assignment, compute needed left deltas
            d_left = {}
            ok = True
            for qi in range(len(q_digits)):
                ari_idx = perm[qi]
                ri = a_rules[ari_idx]
                base_digit = rules_info[ri][2][0]
                needed_delta = (q_digits[qi] - base_digit) % NUM_VARIANTS
                if ari_idx in d_left and d_left[ari_idx] != needed_delta:
                    ok = False; break
                d_left[ari_idx] = needed_delta
            if not ok:
                continue

            # For each A rule's right side delta, try all 7 values
            # Typically each A rule produces 2 B values
            right_delta_ranges = [range(NUM_VARIANTS)] * len(a_rules)

            for right_deltas in iprod(*right_delta_ranges):
                # Compute B values produced
                b_targets = []  # list of (b_value, needed_c_value)
                for qi in range(len(q_digits)):
                    ari_idx = perm[qi]
                    ri = a_rules[ari_idx]
                    _, rs, _, rd = rules_info[ri]
                    dr = right_deltas[ari_idx]
                    b_vals = [cyc(rd[j], dr) for j in range(rs)]
                    # Each B val maps to C val(s) via answer
                    c_start = qi * 2  # Each Q item produces 2 C values (for this game)
                    for j, bv in enumerate(b_vals):
                        if c_start + j < len(a_digits):
                            b_targets.append((bv, a_digits[c_start + j]))

                # Now find B rule deltas that satisfy all b_targets
                # Each B rule has one left delta and one right delta.
                # Rules are tried in ORDER, so first-match matters.

                b_deltas = {}  # bri_idx -> (left_delta, right_delta)
                ok = True

                for bv, cv in b_targets:
                    resolved = False
                    for bri_idx, bri in enumerate(b_rules):
                        _, brs, bld, brd = rules_info[bri]
                        needed_ld = (bv - bld[0]) % NUM_VARIANTS

                        if bri_idx in b_deltas:
                            # Already assigned -- check consistency
                            if b_deltas[bri_idx][0] == needed_ld:
                                # Left matches, check right
                                needed_rd = (cv - brd[0]) % NUM_VARIANTS
                                if b_deltas[bri_idx][1] != needed_rd:
                                    ok = False; break
                                resolved = True
                                break
                            else:
                                # This B rule has different left delta, won't match
                                # But check if earlier assigned rules intercept
                                prev_ld = b_deltas[bri_idx][0]
                                if cyc(bld[0], prev_ld) == bv:
                                    # Earlier rule matches this bv first!
                                    prev_rd = b_deltas[bri_idx][1]
                                    if cyc(brd[0], prev_rd) != cv:
                                        ok = False; break
                                    resolved = True
                                    break
                                continue
                        else:
                            # Check if any already-assigned earlier B rule matches bv first
                            blocked = False
                            for prev_bri_idx in range(bri_idx):
                                if prev_bri_idx in b_deltas:
                                    prev_bld = rules_info[b_rules[prev_bri_idx]][2][0]
                                    prev_ld = b_deltas[prev_bri_idx][0]
                                    if cyc(prev_bld, prev_ld) == bv:
                                        # Earlier rule matches -- check its right
                                        prev_brd = rules_info[b_rules[prev_bri_idx]][3][0]
                                        prev_rd = b_deltas[prev_bri_idx][1]
                                        if cyc(prev_brd, prev_rd) != cv:
                                            ok = False
                                        resolved = True
                                        blocked = True
                                        break
                            if not ok or blocked:
                                break

                            # Assign this B rule
                            needed_rd = (cv - brd[0]) % NUM_VARIANTS
                            b_deltas[bri_idx] = (needed_ld, needed_rd)
                            resolved = True
                            break

                    if not ok:
                        break
                    if not resolved:
                        ok = False; break

                if not ok:
                    continue

                # Build full delta array
                deltas = [0] * num_sets
                for ari_idx in range(len(a_rules)):
                    ri = a_rules[ari_idx]
                    deltas[ri * 2] = d_left.get(ari_idx, 0)
                    deltas[ri * 2 + 1] = right_deltas[ari_idx]

                for bri_idx in range(len(b_rules)):
                    ri = b_rules[bri_idx]
                    if bri_idx in b_deltas:
                        deltas[ri * 2] = b_deltas[bri_idx][0]
                        deltas[ri * 2 + 1] = b_deltas[bri_idx][1]

                # Verify with full simulation
                if not check_tree_deltas(deltas):
                    continue

                # Compute cost
                cost = sum(min(d % NUM_VARIANTS, NUM_VARIANTS - d % NUM_VARIANTS) for d in deltas)
                pos = 0
                for si in range(num_sets):
                    if deltas[si] % NUM_VARIANTS != 0:
                        cost += abs(si - pos)
                        pos = si

                if cost < best_cost:
                    best_cost = cost
                    best_deltas = list(deltas)

    if best_deltas:
        return generate_set_actions(best_deltas, num_sets)
    return None


# --- MAIN SOLVER LOOP ---

def solve_all_levels():
    """Main solver: solve all 6 levels analytically."""
    arc_inst = arc_agi.Arcade()
    env = arc_inst.make('tr87')
    obs = env.reset()
    game = env._game

    print(f"tr87: {obs.win_levels} levels")

    level_actions = []

    for level_num in range(1, obs.win_levels + 1):
        if obs.state.name != 'NOT_FINISHED':
            break

        game = env._game
        alter = game.current_level.get_data('alter_rules')
        double = game.current_level.get_data('double_translation')
        tree = game.current_level.get_data('tree_translation')

        print(f"\nL{level_num}: alter={alter}, double={double}, tree={tree}, "
              f"budget={game.vfpimnmtnta}, rules={len(game.cifzvbcuwqe)}, "
              f"Q={len(game.zvojhrjxxm)}, A={len(game.ztgmtnnufb)}")

        if tree and alter:
            actions = solve_tree_alter(game)
        elif alter:
            actions = solve_alter_rules(game)
        elif double:
            actions = solve_double(game)
        else:
            actions = solve_basic(game)

        if actions is None:
            print(f"  FAILED to find solution!")
            break

        print(f"  Solution: {len(actions)} moves")

        # Execute: replay all previous levels then this one
        obs = env.reset()
        for prev in level_actions:
            for act in prev:
                obs = env.step(act)
        for act in actions:
            obs = env.step(act)
            if obs.levels_completed >= level_num:
                break
            if obs.state.name == 'GAME_OVER':
                break

        if obs.levels_completed >= level_num:
            print(f"  SOLVED!")
            level_actions.append(actions)
        else:
            print(f"  EXECUTION FAILED (state={obs.state.name}, completed={obs.levels_completed})")
            break

    total = obs.levels_completed
    if obs.state.name == 'WIN':
        total = obs.win_levels

    print(f"\n{'='*50}")
    print(f"tr87 RESULT: {total}/{obs.win_levels}")
    print(f"{'='*50}")
    return total


if __name__ == "__main__":
    solve_all_levels()
