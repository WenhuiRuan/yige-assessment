from itertools import permutations

import pytest

from B.optimizer import Warehouse, optimize
from B.tests.support import ROOT, assert_feasible, make_warehouses, objective


def test_b01_original_sample() -> None:
    records = [("AU", 5, 8, 2), ("CN", 7, 20, 1), ("US", 4, 3, 4)]
    solution = optimize(make_warehouses(records), 7)
    assert objective(solution) == (1, 27, [("CN", 7)])
    assert solution is not None
    assert_feasible(solution, records, 7)
    assert (ROOT / "B/examples/sample.out").read_text().splitlines() == ["1 27", "CN 7"]


@pytest.mark.parametrize(
    "records", [[("A", 0, 0, 0)], [("A", 1, 0, 0), ("B", 1, 0, 0)]]
)
def test_b02_insufficient_or_zero_stock(records: list[tuple[str, int, int, int]]) -> None:
    assert optimize(make_warehouses(records), 3) is None


def test_b03_warehouse_count_precedes_cheaper_cost() -> None:
    records = [("A", 3, 1000, 100), ("B", 2, 0, 0), ("C", 1, 0, 0)]
    assert objective(optimize(make_warehouses(records), 3)) == (1, 1300, [("A", 3)])


@pytest.mark.parametrize(
    ("records", "quantity", "expected"),
    [
        ([("A", 3, 9, 1), ("B", 3, 0, 5)], 3, (1, 12, [("A", 3)])),
        ([("A", 3, 10, 1), ("B", 3, 0, 3)], 3, (1, 9, [("B", 3)])),
        (
            [("A", 4, 5, 4), ("B", 4, 8, 1), ("C", 4, 0, 3)],
            6,
            (2, 18, [("B", 4), ("C", 2)]),
        ),
    ],
)
def test_b04_fixed_and_unit_costs_both_matter(records, quantity, expected) -> None:
    solution = optimize(make_warehouses(records), quantity)
    assert objective(solution) == expected
    assert solution is not None
    assert_feasible(solution, records, quantity)


def test_b05_regression_compare_nonzero_list_not_zero_vector() -> None:
    records = [("A", 1, 0, 0), ("B", 1, 0, 0)]
    assert objective(optimize(make_warehouses(records), 1)) == (1, 0, [("A", 1)])


def test_b05_different_sets_compare_first_differing_id() -> None:
    records = [("C", 2, 0, 0), ("B", 2, 0, 0), ("A", 1, 0, 0)]
    assert objective(optimize(make_warehouses(records), 3)) == (2, 0, [("A", 1), ("B", 2)])


def test_b06_regression_quantity_is_integer_not_text() -> None:
    records = [("A", 10, 0, 0), ("B", 10, 0, 0)]
    assert objective(optimize(make_warehouses(records), 12)) == (2, 0, [("A", 2), ("B", 10)])


def test_b07_zero_fees_do_not_use_zero_stock_or_zero_allocations() -> None:
    records = [("0", 0, 0, 0), ("A", 2, 0, 0), ("B", 2, 0, 0)]
    assert objective(optimize(make_warehouses(records), 3)) == (2, 0, [("A", 1), ("B", 2)])


def test_b08_all_input_permutations_produce_same_complete_solution() -> None:
    records = [("A", 2, 0, 0), ("B", 3, 0, 0), ("C", 2, 0, 0), ("D", 0, 0, 0)]
    for permutation in permutations(records):
        assert objective(optimize(make_warehouses(permutation), 4)) == (
            2, 0, [("A", 1), ("B", 3)],
        )


@pytest.mark.parametrize(
    ("records", "quantity", "expected"),
    [
        ([("A", 1, 0, 0)], 1, (1, 0, [("A", 1)])),
        ([("A", 2000, 10**6, 10**6)], 2000, (1, 2001000000, [("A", 2000)])),
        ([(f"W{i:02d}", 1, 0, 0) for i in range(30)], 1, (1, 0, [("W00", 1)])),
    ],
)
def test_b09_dimension_and_fee_boundaries(records, quantity, expected) -> None:
    solution = optimize(make_warehouses(records), quantity)
    assert objective(solution) == expected
    assert solution is not None
    assert_feasible(solution, records, quantity)


@pytest.mark.parametrize(
    ("records", "quantity", "expected"),
    [
        ([("A", 1, 0, 0), ("B", 1, 10, 0)], 2, (2, 10, [("A", 1), ("B", 1)])),
        ([("A", 0, 0, 0), ("B", 1, 4, 3)], 1, (1, 7, [("B", 1)])),
        ([("A", 2, 5, 1), ("B", 1, 4, 2)], 3, (2, 13, [("A", 2), ("B", 1)])),
        ([("A", 3, 0, 0), ("B", 3, 0, 0)], 4, (2, 0, [("A", 1), ("B", 3)])),
        (
            [("A", 1, 0, 0), ("B", 3, 100, 0), ("C", 1, 0, 0), ("D", 1, 0, 0)],
            3,
            (1, 100, [("B", 3)]),
        ),
    ],
)
def test_b10_window_excludes_zero_and_over_capacity_and_reads_only_suffix(
    records, quantity, expected
) -> None:
    solution = optimize(make_warehouses(records), quantity)
    assert objective(solution) == expected
    assert solution is not None
    assert_feasible(solution, records, quantity)


def test_b11_unicode_ids_are_case_sensitive_and_not_normalized() -> None:
    records = [("仓库", 1, 0, 0), ("é", 1, 0, 0), ("e\u0301", 1, 0, 0)]
    assert objective(optimize(make_warehouses(records), 1)) == (1, 0, [("e\u0301", 1)])
    assert objective(optimize([Warehouse("a", 1, 0, 0), Warehouse("A", 1, 0, 0)], 1)) == (
        1, 0, [("A", 1)],
    )


@pytest.mark.parametrize("quantity", [0, 2001, True, 1.0])
def test_b11_invalid_programmatic_quantity(quantity: int) -> None:
    with pytest.raises(ValueError):
        optimize([Warehouse("A", 1, 0, 0)], quantity)


def test_b11_invalid_programmatic_count_and_duplicate() -> None:
    for warehouses in ([], [Warehouse(str(i), 1, 0, 0) for i in range(31)],
                       [Warehouse("A", 1, 0, 0), Warehouse("A", 2, 0, 0)]):
        with pytest.raises(ValueError):
            optimize(warehouses, 1)


@pytest.mark.parametrize(
    "record",
    [
        ("", 1, 0, 0), ("A B", 1, 0, 0), ("A\u00a0B", 1, 0, 0),
        ("A\x00", 1, 0, 0), ("A\u200b", 1, 0, 0), ("A", -1, 0, 0),
        ("A", 2001, 0, 0), ("A", 1, -1, 0), ("A", 1, 0, 1000001),
        ("A", True, 0, 0), ("A", 1, 1.0, 0),
    ],
)
def test_b11_invalid_programmatic_warehouse(record) -> None:
    with pytest.raises(ValueError):
        Warehouse(*record)
