"""Physical-line framing and strict ASCII command parsing, without ledger mutation."""

from dataclasses import dataclass

from A.ledger import MAX_QUANTITY, Command, Operation

MAX_COMMANDS = 200_000


class InputFrameError(ValueError):
    """The header or physical command count is invalid."""


@dataclass(frozen=True, slots=True)
class InputFrame:
    initial_stock: int
    commands: tuple[str, ...]


def _fields(line: str) -> list[str] | None:
    # Only spaces/tabs delimit fields. Other control or Unicode characters are not separators.
    if any(char != "\t" and not " " <= char <= "~" for char in line):
        return None
    return line.split()


def _decimal(token: str, minimum: int, maximum: int) -> int | None:
    if not token.isascii() or not token.isdecimal():
        return None
    significant = token.lstrip("0") or "0"
    # Reject long magnitudes before int(), while permitting arbitrarily many leading zeros.
    if len(significant) > len(str(maximum)):
        return None
    value = int(significant)
    return value if minimum <= value <= maximum else None


def parse_input(text: str) -> InputFrame:
    """Preflight the entire frame before processing even the first command."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[-1] == "":
        # A terminating newline closes the previous line; it does not create another line.
        lines.pop()
    if not lines:
        raise InputFrameError("Expected initial stock S and command count N")

    header = _fields(lines[0])
    if header is None or len(header) != 2:
        raise InputFrameError("Header must contain exactly S and N")
    initial_stock = _decimal(header[0], 0, MAX_QUANTITY)
    count = _decimal(header[1], 1, MAX_COMMANDS)
    if initial_stock is None or count is None:
        raise InputFrameError("Header requires 0 <= S <= 10^12 and 1 <= N <= 200000")
    if len(lines) - 1 < count:
        raise InputFrameError(f"Expected {count} physical command lines; input is shorter")
    if any(line.strip(" \t") for line in lines[count + 1 :]):
        raise InputFrameError("Unexpected nonblank content after N command lines")

    return InputFrame(initial_stock, tuple(lines[1 : count + 1]))


def parse_command(line: str) -> Command | None:
    fields = _fields(line)
    if not fields:
        return None
    try:
        operation = Operation(fields[0])
    except ValueError:
        return None
    expected_count = 3 if operation == Operation.RESTOCK else 4
    if len(fields) != expected_count:
        return None
    quantity = _decimal(fields[-1], 1, MAX_QUANTITY)
    if quantity is None:
        return None
    try:
        return Command(
            operation=operation,
            event_id=fields[1],
            quantity=quantity,
            order_id=None if operation == Operation.RESTOCK else fields[2],
        )
    except ValueError:
        return None
