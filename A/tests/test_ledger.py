import pytest

from A.formatting import format_open, format_result
from A.ledger import MAX_QUANTITY, Command, Ledger, Operation
from A.tests.support import MALFORMED, ROOT, apply_line, assert_invariants, snapshot


def test_a01_original_sample() -> None:
    lines = (ROOT / "A/examples/sample.in").read_text().splitlines()
    ledger = Ledger(10)
    actual = []
    for line in lines[1:]:
        actual.append(format_result(apply_line(ledger, line)))
        assert_invariants(ledger)
    actual.extend(format_open(ledger.reservations))
    assert actual == (ROOT / "A/examples/sample.out").read_text().splitlines()


@pytest.mark.parametrize(
    ("stock", "quantity", "status", "reserved"),
    [(0, 1, "REJECTED", 0), (4, 4, "OK", 4), (4, 5, "REJECTED", 0)],
)
def test_a02_reserve_boundaries(stock: int, quantity: int, status: str, reserved: int) -> None:
    ledger = Ledger(stock)
    result = apply_line(ledger, f"RESERVE e o {quantity}")
    assert (result.status, result.on_hand, result.reserved_total) == (status, stock, reserved)
    assert ledger.processed_event_ids == {"e"}
    assert_invariants(ledger)


def test_a03_accumulate_partial_and_full_release() -> None:
    ledger = Ledger(10)
    for line, reserved in [
        ("RESERVE e1 o 3", 3),
        ("RESERVE e2 o 4", 7),
        ("RELEASE e3 o 2", 5),
        ("RELEASE e4 o 5", 0),
    ]:
        assert apply_line(ledger, line).status == "OK"
        assert ledger.on_hand == 10
        assert ledger.reserved_total == reserved
        assert ledger.reservations == ({"o": reserved} if reserved else {})
        assert_invariants(ledger)


def test_a04_partial_and_full_ship_preserve_available_stock() -> None:
    ledger = Ledger(10)
    apply_line(ledger, "RESERVE e1 o 7")
    for line, stock, reserved in [("SHIP e2 o 2", 8, 5), ("SHIP e3 o 5", 3, 0)]:
        assert apply_line(ledger, line).status == "OK"
        assert (ledger.on_hand, ledger.reserved_total, ledger.available) == (stock, reserved, 3)
        assert_invariants(ledger)
    assert ledger.reservations == {}


@pytest.mark.parametrize("operation", ["RELEASE", "SHIP"])
@pytest.mark.parametrize("order", ["missing", "o"])
def test_a05_business_rejections_consume_events(operation: str, order: str) -> None:
    ledger = Ledger(10)
    apply_line(ledger, "RESERVE seed o 2")
    before = snapshot(ledger)
    assert apply_line(ledger, f"{operation} refused {order} 3").status == "REJECTED"
    assert snapshot(ledger)[:3] == before[:3]
    assert ledger.processed_event_ids == {"seed", "refused"}
    assert apply_line(ledger, f"{operation} refused {order} 1").status == "DUPLICATE"
    assert_invariants(ledger)


@pytest.mark.parametrize(
    "line",
    ["RESERVE event o 2", "RELEASE event o 1", "SHIP event o 1", "RESTOCK event 2"],
)
def test_a06_replay_each_successful_operation(line: str) -> None:
    ledger = Ledger(5)
    apply_line(ledger, "RESERVE seed o 2")
    assert apply_line(ledger, line).status == "OK"
    before = snapshot(ledger)
    assert apply_line(ledger, line).status == "DUPLICATE"
    assert snapshot(ledger) == before
    assert_invariants(ledger)


def test_a07_rejected_reserve_stays_processed_after_restock() -> None:
    ledger = Ledger(0)
    assert apply_line(ledger, "RESERVE failed o 1").status == "REJECTED"
    assert apply_line(ledger, "RESTOCK supply 5").status == "OK"
    before = snapshot(ledger)
    assert apply_line(ledger, "RESERVE failed o 1").status == "DUPLICATE"
    assert snapshot(ledger) == before


@pytest.mark.parametrize(
    "replacement",
    [
        "RESERVE event other 1",
        "RESERVE event o 5",
        "RELEASE event o 1",
        "SHIP event o 1",
        "RESTOCK event 10",
    ],
)
def test_a08_same_event_different_valid_payload(replacement: str) -> None:
    ledger = Ledger(10)
    apply_line(ledger, "RESERVE event o 2")
    before = snapshot(ledger)
    assert apply_line(ledger, replacement).status == "DUPLICATE"
    assert snapshot(ledger) == before


@pytest.mark.parametrize("line", MALFORMED)
def test_a09_malformed_command_changes_no_state(line: str) -> None:
    ledger = Ledger(10)
    apply_line(ledger, "RESERVE seed kept 2")
    before = snapshot(ledger)
    assert apply_line(ledger, line).status == "REJECTED"
    assert snapshot(ledger) == before
    assert_invariants(ledger)


def test_a10_format_error_then_corrected_event_and_invalid_replay() -> None:
    ledger = Ledger(5)
    assert apply_line(ledger, "RESERVE reused o 0").status == "REJECTED"
    assert "reused" not in ledger.processed_event_ids
    assert apply_line(ledger, "RESERVE reused o 2").status == "OK"
    before = snapshot(ledger)
    assert apply_line(ledger, "RESTOCK reused 0").status == "REJECTED"
    assert snapshot(ledger) == before
    assert apply_line(ledger, "RESTOCK reused 1").status == "DUPLICATE"
    assert snapshot(ledger) == before


def test_a11_open_reservations_sort_and_remove_zero_orders() -> None:
    ledger = Ledger(10)
    for line in (ROOT / "A/examples/open.in").read_text().splitlines()[1:]:
        apply_line(ledger, line)
        assert_invariants(ledger)
    assert "z" not in ledger.reservations
    assert list(format_open(ledger.reservations)) == ["OPEN 3", "A 2", "B 4", "a 1"]
    assert list(format_open({"z": 0, "a": 2})) == ["OPEN 1", "a 2"]


def test_a12_quantity_limit_does_not_cap_accumulated_stock_or_order() -> None:
    ledger = Ledger(MAX_QUANTITY)
    for line, expected in [
        (f"RESTOCK r1 {MAX_QUANTITY}", (2 * MAX_QUANTITY, 0)),
        (f"RESTOCK r2 {MAX_QUANTITY}", (3 * MAX_QUANTITY, 0)),
        (f"RESERVE e1 o {MAX_QUANTITY}", (3 * MAX_QUANTITY, MAX_QUANTITY)),
        (f"RESERVE e2 o {MAX_QUANTITY}", (3 * MAX_QUANTITY, 2 * MAX_QUANTITY)),
        (f"SHIP e3 o {MAX_QUANTITY}", (2 * MAX_QUANTITY, MAX_QUANTITY)),
        (f"RELEASE e4 o {MAX_QUANTITY}", (2 * MAX_QUANTITY, 0)),
    ]:
        assert apply_line(ledger, line).status == "OK"
        assert (ledger.on_hand, ledger.reserved_total) == expected
        assert_invariants(ledger)


@pytest.mark.parametrize("stock", [-1, MAX_QUANTITY + 1, True, 1.0])
def test_invalid_programmatic_initial_stock(stock: int) -> None:
    with pytest.raises(ValueError):
        Ledger(stock)


@pytest.mark.parametrize(
    ("operation", "event", "quantity", "order"),
    [
        (Operation.RESERVE, "e", 0, "o"),
        (Operation.RESERVE, "e", True, "o"),
        (Operation.RESERVE, "e", 1, None),
        (Operation.RESTOCK, "e", 1, "o"),
        (Operation.RESTOCK, "é", 1, None),
    ],
)
def test_programmatic_commands_are_validated(
    operation: Operation, event: str, quantity: int, order: str | None
) -> None:
    with pytest.raises(ValueError):
        Command(operation, event, quantity, order)
