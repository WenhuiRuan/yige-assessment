"""Judge-facing output formatting; no parsing or state transitions."""

from collections.abc import Iterator, Mapping

from A.ledger import Result


def format_result(result: Result) -> str:
    return f"{result.status} {result.on_hand} {result.reserved_total}"


def format_open(reservations: Mapping[str, int]) -> Iterator[str]:
    orders = sorted(
        (order_id, quantity) for order_id, quantity in reservations.items() if quantity > 0
    )
    yield f"OPEN {len(orders)}"
    for order_id, quantity in orders:
        yield f"{order_id} {quantity}"
