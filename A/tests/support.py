import subprocess
import sys
from pathlib import Path

from A.ledger import Ledger, Result
from A.parsing import parse_command

ROOT = Path(__file__).resolve().parents[2]

MALFORMED = [
    "",
    " \t ",
    "UNKNOWN e o 1",
    "reserve e o 1",
    "RESERVE e o",
    "RESERVE e o 1 extra",
    "RESTOCK e",
    "RESTOCK e 1 extra",
    "RESERVE e o 0",
    "RESERVE e o -1",
    "RESERVE e o +1",
    "RESERVE e o 1.0",
    "RESERVE e o 1e2",
    "RESERVE e o 1_000",
    "RESERVE e o true",
    "RESERVE e o 1000000000001",
    "RESERVE e o １２",
    "RESERVE é o 1",
    "RESERVE e 订单 1",
    "RESERVE e\x00 o 1",
    "RESERVE e o\x7f 1",
    "RESERVE\u00a0e o 1",
    "RESERVE\ve o 1",
    "RESERVE e o\r 1",
    "RESTOCK e " + "9" * 5000,
]


def run_cli(text: str | bytes) -> subprocess.CompletedProcess[bytes]:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return subprocess.run(
        [sys.executable, "-m", "A.main"],
        input=data,
        capture_output=True,
        cwd=ROOT,
        timeout=120,  # Hang protection, not an assessment performance requirement.
        check=False,
    )


def output_lines(process: subprocess.CompletedProcess[bytes]) -> list[str]:
    return process.stdout.decode("ascii").splitlines()


def apply_line(ledger: Ledger, line: str) -> Result:
    return ledger.apply(parse_command(line))


def snapshot(ledger: Ledger) -> tuple[int, int, dict[str, int], set[str]]:
    return (
        ledger.on_hand,
        ledger.reserved_total,
        ledger.reservations.copy(),
        ledger.processed_event_ids.copy(),
    )


def assert_invariants(ledger: Ledger) -> None:
    assert 0 <= ledger.reserved_total <= ledger.on_hand
    assert ledger.reserved_total == sum(ledger.reservations.values())
    assert all(quantity > 0 for quantity in ledger.reservations.values())
    assert ledger.available == ledger.on_hand - ledger.reserved_total
