import platform
import sys
from time import perf_counter

import pytest

from B.optimizer import optimize
from B.tests.support import (
    assert_feasible,
    make_warehouses,
    objective,
    output_lines,
    problem_text,
    run_cli,
)


def scale_cases():
    ids = [f"W{i:02d}" for i in range(30)]
    return [
        (
            "zero-full",
            [(name, 2000, 0, 0) for name in reversed(ids)],
            (1, 0, [("W00", 2000)]),
        ),
        (
            "zero-tight-multiple",
            [(name, 100, 0, 0) for name in reversed(ids)],
            (20, 0, [(name, 100) for name in ids[:20]]),
        ),
        (
            "zero-slack-many-ties",
            [(name, 137, 0, 0) for name in reversed(ids)],
            (15, 0, [("W00", 82), *[(name, 137) for name in ids[1:15]]]),
        ),
        (
            "max-fees-full",
            [(name, 2000, 10**6, 10**6) for name in reversed(ids)],
            (1, 2001000000, [("W00", 2000)]),
        ),
        (
            "all-30-required",
            [(name, 86 if i == 29 else 66, 10**6, 10**6) for i, name in enumerate(ids)],
            (30, 2030000000, [(name, 86 if i == 29 else 66) for i, name in enumerate(ids)]),
        ),
        (
            "priced-multiple",
            [(name, 100, 3 * (30 - i), 30 - i) for i, name in enumerate(ids)],
            (20, 21630, [(name, 100) for name in ids[10:]]),
        ),
    ]


@pytest.mark.parametrize(("name", "records", "expected"), scale_cases())
def test_b09_b10_maximum_scale_complete_solution_and_real_cli(name, records, expected) -> None:
    started = perf_counter()
    solution = optimize(make_warehouses(records), 2000)
    solver_elapsed = perf_counter() - started
    assert solution is not None
    assert objective(solution) == expected
    assert_feasible(solution, records, 2000)

    text = problem_text(records, 2000)
    started = perf_counter()
    process = run_cli(text)
    cli_elapsed = perf_counter() - started
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == [f"{expected[0]} {expected[1]}"] + [
        f"{warehouse_id} {allocated}" for warehouse_id, allocated in expected[2]
    ]
    print(
        f"\nB scale {name}: W=30 Q=2000 K={expected[0]} cost={expected[1]}, "
        f"solver={solver_elapsed:.6f}s, CLI={cli_elapsed:.6f}s, "
        f"Python={sys.version.split()[0]}, OS={platform.platform()}, CPU={platform.processor()}"
    )
