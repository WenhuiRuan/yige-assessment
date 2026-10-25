import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from B.optimizer import Solution, Warehouse

ROOT = Path(__file__).resolve().parents[2]
RawWarehouse = tuple[str, int, int, int]
Objective = tuple[int, int, list[tuple[str, int]]]


def make_warehouses(records: Sequence[RawWarehouse]) -> list[Warehouse]:
    return [Warehouse(*record) for record in records]


def objective(solution: Solution | None) -> Objective | None:
    if solution is None:
        return None
    return solution.warehouse_count, solution.total_cost, list(solution.allocations)


def problem_text(records: Sequence[RawWarehouse], quantity: int) -> str:
    return f"{len(records)} {quantity}\n" + "".join(
        f"{warehouse_id} {stock} {fixed} {unit}\n"
        for warehouse_id, stock, fixed, unit in records
    )


def run_cli(text: str | bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "B.main"],
        input=text.encode("utf-8") if isinstance(text, str) else text,
        capture_output=True,
        cwd=ROOT,
        timeout=120,  # Hang protection, not a scoring or performance threshold.
        check=False,
    )


def output_lines(process: subprocess.CompletedProcess[bytes]) -> list[str]:
    return process.stdout.decode("utf-8").splitlines()


def assert_feasible(solution: Solution, records: Sequence[RawWarehouse], quantity: int) -> None:
    by_id = {warehouse_id: (stock, fixed, unit) for warehouse_id, stock, fixed, unit in records}
    allocations = solution.allocations
    assert len(allocations) == solution.warehouse_count
    assert len({warehouse_id for warehouse_id, _ in allocations}) == len(allocations)
    assert allocations == tuple(sorted(allocations))
    assert sum(allocated for _, allocated in allocations) == quantity
    for warehouse_id, allocated in allocations:
        assert 1 <= allocated <= by_id[warehouse_id][0]
    assert solution.total_cost == sum(
        by_id[warehouse_id][1] + allocated * by_id[warehouse_id][2]
        for warehouse_id, allocated in allocations
    )
    capacity = 0
    for count, stock in enumerate(sorted((row[1] for row in records), reverse=True), start=1):
        capacity += stock
        if capacity >= quantity:
            assert solution.warehouse_count == count
            break
