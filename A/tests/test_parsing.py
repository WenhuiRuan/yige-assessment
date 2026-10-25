from io import StringIO

import pytest

from A.ledger import Operation
from A.main import run
from A.parsing import InputFrameError, parse_command, parse_input


def test_input_frame_preserves_blank_commands_and_ignores_only_tail_blanks() -> None:
    frame = parse_input("0 3\r\n\r\nRESTOCK e 1\r\n \t\r\n\r\n")
    assert frame.initial_stock == 0
    assert frame.commands == ("", "RESTOCK e 1", " \t")


def test_long_leading_zero_tokens_do_not_hit_python_int_digit_limit() -> None:
    zeros = "0" * 5000
    frame = parse_input(f"{zeros}1 {zeros}1\nRESTOCK e {zeros}1\n")
    assert frame.initial_stock == 1
    command = parse_command(frame.commands[0])
    assert command is not None
    assert (command.operation, command.event_id, command.quantity, command.order_id) == (
        Operation.RESTOCK, "e", 1, None,
    )


@pytest.mark.parametrize("trailer", ["EXTRA", "\v", "\u00a0", "\r"])
def test_a13_nonblank_or_unsupported_tail_characters_fail_frame(trailer: str) -> None:
    with pytest.raises(InputFrameError):
        parse_input(f"1 1\nRESTOCK e 1\n{trailer}")


def test_run_does_not_write_a_valid_prefix_before_frame_validation() -> None:
    stdout, stderr = StringIO(), StringIO()
    code = run("1 1\nRESTOCK valid 1\nEXTRA\n", stdout, stderr)
    assert code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue().startswith("Input error: ")
