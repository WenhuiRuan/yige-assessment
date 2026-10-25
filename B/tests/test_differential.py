from collections import Counter

import pytest

from B.optimizer import optimize
from B.tests.reference import exhaustive_reference, random_problems
from B.tests.support import assert_feasible, make_warehouses, objective, problem_text


@pytest.mark.parametrize("seed", range(20261022, 20261027))
def test_b12_1000_cases_per_seed_match_full_exhaustive_objective(seed: int) -> None:
    counts: Counter[str] = Counter()
    for index, (records, quantity) in enumerate(random_problems(seed, 1000)):
        context = f"seed={seed}, case={index}\n{problem_text(records, quantity)}"
        try:
            oracle = exhaustive_reference(records, quantity)
            solution = optimize(make_warehouses(records), quantity)
            assert objective(solution) == oracle.objective
            if solution is not None:
                assert_feasible(solution, records, quantity)
        except Exception as error:
            # Preserve the original cause and always attach a directly replayable input.
            raise AssertionError(context) from error
        counts["cases"] += 1
        if solution is None:
            counts["impossible"] += 1
        else:
            sets = {tuple(warehouse_id for warehouse_id, _ in a)
                    for a in oracle.optimal_pair_allocations}
            if len(sets) > 1:
                counts["equal_cost_sets"] += 1
            if len(oracle.optimal_pair_allocations) > len(sets):
                counts["equal_cost_quantities"] += 1
    assert counts["cases"] == 1000
    assert counts["impossible"] > 0
    assert counts["equal_cost_sets"] > 0
    assert counts["equal_cost_quantities"] > 0
    print(f"\nB12 seed={seed}: {dict(counts)}")
