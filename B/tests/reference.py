"""Small exhaustive oracle. No production modules, DP, or reconstruction are imported."""

import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from itertools import product

RawWarehouse = tuple[str, int, int, int]
Objective = tuple[int, int, list[tuple[str, int]]]


@dataclass(frozen=True, slots=True)
class OracleResult:
    objective: Objective | None
    optimal_pair_allocations: tuple[tuple[tuple[str, int], ...], ...]


def exhaustive_reference(records: Sequence[RawWarehouse], quantity: int) -> OracleResult:
    ordered = sorted(records, key=lambda row: row[0])
    best: Objective | None = None
    ties: list[tuple[tuple[str, int], ...]] = []
    for amounts in product(*(range(min(row[1], quantity) + 1) for row in ordered)):
        if sum(amounts) != quantity:
            continue
        allocation = [
            (row[0], amount) for row, amount in zip(ordered, amounts, strict=True) if amount > 0
        ]
        cost = sum(
            row[2] + amount * row[3]
            for row, amount in zip(ordered, amounts, strict=True)
            if amount > 0
        )
        candidate = (len(allocation), cost, allocation)
        if best is None or candidate[:2] < best[:2]:
            ties = [tuple(allocation)]
        elif candidate[:2] == best[:2]:
            ties.append(tuple(allocation))
        if best is None or candidate < best:
            best = candidate
    return OracleResult(best, tuple(ties))


def random_problems(seed: int, count: int) -> Iterator[tuple[list[RawWarehouse], int]]:
    rng = random.Random(seed)
    ids = ["A", "a", "Z", "B", "仓库", "é", "e\u0301", "猫"]
    for index in range(count):
        mode = index % 5
        chosen_ids = rng.sample(ids, rng.randint(1, 6))
        records = []
        for row_index, warehouse_id in enumerate(chosen_ids):
            stock = 0 if mode == 4 and row_index % 2 == 0 else rng.randint(0, 3)
            fixed = 0 if mode in (0, 1) else rng.randint(0, 5)
            unit = 0 if mode == 0 else rng.randint(0, 1 if mode == 1 else 5)
            records.append((warehouse_id, stock, fixed, unit))
        total = sum(row[1] for row in records)
        quantity = total + 1 if mode == 3 else rng.randint(1, max(1, min(10, total + 2)))
        rng.shuffle(records)
        yield records, quantity
