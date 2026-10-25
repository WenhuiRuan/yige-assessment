"""Validated commands and the single-SKU inventory state machine."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

MAX_QUANTITY = 10**12


class Operation(StrEnum):
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    SHIP = "SHIP"
    RESTOCK = "RESTOCK"


def is_ascii_token(value: object) -> bool:
    return isinstance(value, str) and bool(value) and all("!" <= char <= "~" for char in value)


@dataclass(frozen=True, slots=True)
class Command:
    operation: Operation
    event_id: str
    quantity: int
    order_id: str | None = None

    def __post_init__(self) -> None:
        # Construction is the validation boundary, including for programmatic callers.
        if not isinstance(self.operation, Operation):
            raise ValueError("Unknown operation")
        if not is_ascii_token(self.event_id):
            raise ValueError("Invalid event ID")
        if type(self.quantity) is not int or not 1 <= self.quantity <= MAX_QUANTITY:
            raise ValueError("Quantity is out of range")
        if self.operation == Operation.RESTOCK:
            if self.order_id is not None:
                raise ValueError("RESTOCK has no order ID")
        elif not is_ascii_token(self.order_id):
            raise ValueError("Invalid order ID")


@dataclass(frozen=True, slots=True)
class Result:
    status: Literal["OK", "REJECTED", "DUPLICATE"]
    on_hand: int
    reserved_total: int


@dataclass(slots=True)
class Ledger:
    on_hand: int
    reserved_total: int = field(init=False, default=0)
    reservations: dict[str, int] = field(init=False, default_factory=dict)
    processed_event_ids: set[str] = field(init=False, default_factory=set)

    def __post_init__(self) -> None:
        if type(self.on_hand) is not int or not 0 <= self.on_hand <= MAX_QUANTITY:
            raise ValueError("Initial stock is out of range")

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved_total

    def apply(self, command: Command | None) -> Result:
        """None denotes malformed input; validated business failures consume their ID."""
        if command is None:
            return Result("REJECTED", self.on_hand, self.reserved_total)
        if command.event_id in self.processed_event_ids:
            return Result("DUPLICATE", self.on_hand, self.reserved_total)

        self.processed_event_ids.add(command.event_id)
        quantity = command.quantity
        status: Literal["OK", "REJECTED", "DUPLICATE"] = "OK"

        if command.operation == Operation.RESTOCK:
            self.on_hand += quantity
        elif command.operation == Operation.RESERVE:
            if self.available < quantity:
                status = "REJECTED"
            else:
                # Command validation guarantees an order ID for non-RESTOCK operations.
                assert command.order_id is not None
                self.reservations[command.order_id] = (
                    self.reservations.get(command.order_id, 0) + quantity
                )
                self.reserved_total += quantity
        else:
            assert command.order_id is not None
            held = self.reservations.get(command.order_id, 0)
            if held < quantity:
                status = "REJECTED"
            else:
                remaining = held - quantity
                if remaining:
                    self.reservations[command.order_id] = remaining
                else:
                    del self.reservations[command.order_id]
                self.reserved_total -= quantity
                if command.operation == Operation.SHIP:
                    self.on_hand -= quantity

        return Result(status, self.on_hand, self.reserved_total)
