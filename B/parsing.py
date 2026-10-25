"""Validate the complete B input; identifiers deliberately allow Unicode."""

from dataclasses import dataclass

from B.optimizer import MAX_COST, MAX_QUANTITY, MAX_WAREHOUSES, Warehouse


class InputError(ValueError):
    """Input syntax, ranges, or warehouse identity is invalid."""


@dataclass(frozen=True, slots=True)
class Problem:
    warehouses: tuple[Warehouse, ...]
    quantity: int


def _fields(line: str) -> list[str]:
    # Do not reinterpret Unicode whitespace inside an ID as a field separator.
    return [field for field in line.replace("\t", " ").split(" ") if field]


def _decimal(token: str, minimum: int, maximum: int) -> int:
    if not token.isascii() or not token.isdecimal():
        raise InputError("Numeric fields must contain ASCII decimal digits")
    significant = token.lstrip("0") or "0"
    if len(significant) > len(str(maximum)):
        raise InputError(f"Numeric field must be in [{minimum}, {maximum}]")
    value = int(significant)
    if not minimum <= value <= maximum:
        raise InputError(f"Numeric field must be in [{minimum}, {maximum}]")
    return value


def parse_input(text: str) -> Problem:
    lines = text.replace("\r\n", "\n").split("\n")
    if lines[-1] == "":
        lines.pop()
    if not lines:
        raise InputError("Expected warehouse count W and requested quantity Q")
    header = _fields(lines[0])
    if len(header) != 2:
        raise InputError("Header must contain exactly W and Q")
    count = _decimal(header[0], 1, MAX_WAREHOUSES)
    quantity = _decimal(header[1], 1, MAX_QUANTITY)
    if len(lines) - 1 < count:
        raise InputError(f"Expected {count} physical warehouse lines; input is shorter")
    if any(line.strip(" \t") for line in lines[count + 1 :]):
        raise InputError("Unexpected nonblank content after W warehouse lines")

    warehouses: list[Warehouse] = []
    seen: set[str] = set()
    for number, line in enumerate(lines[1 : count + 1], start=1):
        fields = _fields(line)
        if len(fields) != 4:
            raise InputError(f"Warehouse line {number} must contain exactly four fields")
        warehouse_id = fields[0]
        if warehouse_id in seen:
            raise InputError(f"Duplicate warehouse ID on line {number}")
        try:
            warehouse = Warehouse(
                warehouse_id,
                _decimal(fields[1], 0, MAX_QUANTITY),
                _decimal(fields[2], 0, MAX_COST),
                _decimal(fields[3], 0, MAX_COST),
            )
        except ValueError as error:
            raise InputError(f"Invalid warehouse line {number}: {error}") from error
        warehouses.append(warehouse)
        seen.add(warehouse_id)
    return Problem(tuple(warehouses), quantity)
