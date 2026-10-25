import platform
import sys
from time import perf_counter

import pytest

from A.formatting import format_open
from A.ledger import Ledger
from A.tests.support import apply_line, assert_invariants, output_lines, run_cli

CYCLES = 40_000
COUNT = 5 * CYCLES
STOCK = 80_000


@pytest.fixture(scope="module")
def scale_commands() -> list[str]:
    commands = []
    for cycle in range(CYCLES):
        order = f"o{CYCLES - cycle:05d}"
        commands.extend(
            [
                f"RESERVE reserve-{cycle} {order} 3",
                f"RELEASE release-{cycle} {order} 1",
                f"SHIP ship-{cycle} {order} 1",
                f"RESTOCK restock-{cycle} 1",
                f"RESERVE reserve-{cycle} changed-order 1",
            ]
        )
    return commands


def test_a14_200000_commands_in_ledger(scale_commands: list[str]) -> None:
    ledger = Ledger(STOCK)
    started = perf_counter()
    statuses = {"OK": 0, "REJECTED": 0, "DUPLICATE": 0}
    for index, line in enumerate(scale_commands, start=1):
        statuses[apply_line(ledger, line).status] += 1
        if index % 10_000 == 0:
            assert_invariants(ledger)
    elapsed = perf_counter() - started
    assert statuses == {"OK": 160_000, "REJECTED": 0, "DUPLICATE": 40_000}
    assert ledger.on_hand == STOCK
    assert ledger.reserved_total == CYCLES
    assert len(ledger.processed_event_ids) == 160_000
    assert ledger.reservations == {f"o{index:05d}": 1 for index in range(1, CYCLES + 1)}
    assert_invariants(ledger)
    assert list(format_open(ledger.reservations)) == [f"OPEN {CYCLES}"] + [
        f"o{index:05d} 1" for index in range(1, CYCLES + 1)
    ]
    print(
        f"\nA14 ledger: N={COUNT}, E=160000, R={CYCLES}, "
        f"parse+apply+periodic invariant checks={elapsed:.6f}s; "
        f"Python={sys.version.split()[0]}, OS={platform.platform()}, CPU={platform.processor()}"
    )


def test_a14_200000_commands_through_real_cli(scale_commands: list[str]) -> None:
    text = f"{STOCK} {COUNT}\n" + "\n".join(scale_commands) + "\n"
    started = perf_counter()
    process = run_cli(text)
    elapsed = perf_counter() - started
    assert process.returncode == 0
    assert process.stderr == b""
    lines = output_lines(process)
    assert len(lines) == COUNT + CYCLES + 1
    for cycle in range(CYCLES):
        assert lines[cycle * 5 : cycle * 5 + 5] == [
            f"OK {STOCK} {cycle + 3}",
            f"OK {STOCK} {cycle + 2}",
            f"OK {STOCK - 1} {cycle + 1}",
            f"OK {STOCK} {cycle + 1}",
            f"DUPLICATE {STOCK} {cycle + 1}",
        ]
    assert lines[COUNT:] == [f"OPEN {CYCLES}"] + [
        f"o{index:05d} 1" for index in range(1, CYCLES + 1)
    ]
    print(
        f"\nA14 CLI: N={COUNT}, R={CYCLES}, input={len(text.encode('ascii'))} bytes, "
        f"stdout={len(process.stdout)} bytes, end-to-end={elapsed:.6f}s "
        "(includes Python startup, framing, parsing, state, sorting, and captured I/O)"
    )
