"""Bounded suffix DP with a monotone queue and independent lexicographic reconstruction."""

import unicodedata
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

MAX_WAREHOUSES = 30
MAX_QUANTITY = 2000
MAX_COST = 10**6
Score = tuple[int, int]


def valid_warehouse_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not any(
            char.isspace() or unicodedata.category(char) in {"Cc", "Cf", "Cs"}
            for char in value
        )
    )


@dataclass(frozen=True, slots=True)
class Warehouse:
    warehouse_id: str
    stock: int
    fixed_cost: int
    unit_cost: int

    def __post_init__(self) -> None:
        if not valid_warehouse_id(self.warehouse_id):
            raise ValueError("Warehouse ID must be a nonempty token without whitespace or controls")
        for name, value, maximum in (
            ("stock", self.stock, MAX_QUANTITY),
            ("fixed_cost", self.fixed_cost, MAX_COST),
            ("unit_cost", self.unit_cost, MAX_COST),
        ):
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError(f"{name} must be an integer in [0, {maximum}]")


@dataclass(frozen=True, slots=True)
class Solution:
    warehouse_count: int
    total_cost: int
    allocations: tuple[tuple[str, int], ...]


def _suffix_states(warehouses: list[Warehouse], quantity: int) -> list[list[Score | None]]:
    layers: list[list[Score | None]] = [
        [None] * (quantity + 1) for _ in range(len(warehouses) + 1)
    ]
    layers[-1][0] = (0, 0)

    for index in range(len(warehouses) - 1, -1, -1):
        warehouse = warehouses[index]
        capacity = min(warehouse.stock, quantity)
        suffix = layers[index + 1]
        current = suffix.copy()  # Not using this warehouse, including q=0.
        window: deque[tuple[int, Score]] = deque()

        for requested in range(1, quantity + 1):
            remainder = requested - 1  # x >= 1, so the right edge excludes t=q.
            state = suffix[remainder]
            if state is not None:
                key = (state[0], state[1] - remainder * warehouse.unit_cost)
                # A newer equal/better key expires later and dominates the older candidate.
                # This queue chooses only (count, cost); allocation ties are rebuilt below.
                while window and window[-1][1] >= key:
                    window.pop()
                window.append((remainder, key))
            while window and window[0][0] < requested - capacity:
                window.popleft()

            if window:
                _, best_key = window[0]
                candidate = (
                    best_key[0] + 1,
                    best_key[1] + warehouse.fixed_cost + requested * warehouse.unit_cost,
                )
                if current[requested] is None or candidate < current[requested]:
                    current[requested] = candidate
        layers[index] = current

    return layers


def _reconstruct(
    warehouses: list[Warehouse], layers: list[list[Score | None]], quantity: int, target: Score
) -> tuple[tuple[str, int], ...]:
    answer: list[tuple[str, int]] = []
    start = 0
    remaining = quantity
    while remaining:
        for index in range(start, len(warehouses)):
            warehouse = warehouses[index]
            for allocated in range(1, min(warehouse.stock, remaining) + 1):
                suffix = layers[index + 1][remaining - allocated]
                if suffix is not None and (
                    suffix[0] + 1,
                    suffix[1] + warehouse.fixed_cost + allocated * warehouse.unit_cost,
                ) == target:
                    answer.append((warehouse.warehouse_id, allocated))
                    remaining -= allocated
                    target = suffix
                    start = index + 1
                    break
            else:
                continue
            break
        else:
            raise RuntimeError("No allocation completes the optimal suffix state")
    if target != (0, 0):
        raise RuntimeError("Reconstruction ended with an inconsistent optimal state")
    return tuple(answer)


def optimize(warehouses: Iterable[Warehouse], quantity: int) -> Solution | None:
    if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
        raise ValueError("Requested quantity must be an integer in [1, 2000]")
    ordered = sorted(warehouses, key=lambda warehouse: warehouse.warehouse_id)
    if not 1 <= len(ordered) <= MAX_WAREHOUSES:
        raise ValueError("Warehouse count must be in [1, 30]")
    if len({warehouse.warehouse_id for warehouse in ordered}) != len(ordered):
        raise ValueError("Duplicate warehouse ID")
    if sum(warehouse.stock for warehouse in ordered) < quantity:
        return None

    layers = _suffix_states(ordered, quantity)
    best = layers[0][quantity]
    if best is None:
        raise RuntimeError("Sufficient integer capacity produced an unreachable DP state")
    return Solution(best[0], best[1], _reconstruct(ordered, layers, quantity, best))
