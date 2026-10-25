import pytest

from A.formatting import format_open, format_result
from A.ledger import Ledger
from A.tests.reference import ReferenceLedger, random_commands
from A.tests.support import apply_line, assert_invariants, output_lines, run_cli


@pytest.mark.parametrize("seed", range(20261022, 20261062))
def test_a14_seeded_sequences_match_independent_reference(seed: int) -> None:
    initial = seed % 31
    ledger, reference = Ledger(initial), ReferenceLedger(initial)
    statuses = set()
    for step, line in enumerate(random_commands(seed, 500)):
        expected = reference.step(line)
        result = apply_line(ledger, line)
        assert format_result(result) == expected, (seed, step, line)
        assert ledger.on_hand == reference.on_hand
        assert ledger.reservations == reference.orders
        assert ledger.processed_event_ids == reference.seen
        assert_invariants(ledger)
        statuses.add(result.status)
    assert list(format_open(ledger.reservations)) == reference.open_lines()
    assert statuses == {"OK", "REJECTED", "DUPLICATE"}


@pytest.mark.parametrize("seed", [20261022, 20261023, 20261024])
def test_a14_randomized_real_cli_matches_reference(seed: int) -> None:
    initial = seed % 31
    commands = random_commands(seed, 500)
    reference = ReferenceLedger(initial)
    expected = [reference.step(line) for line in commands]
    expected.extend(reference.open_lines())
    process = run_cli(f"{initial} {len(commands)}\n" + "\n".join(commands) + "\n")
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == expected
