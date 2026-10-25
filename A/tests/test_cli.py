import pytest

from A.tests.support import MALFORMED, ROOT, output_lines, run_cli


@pytest.mark.parametrize("example", ["sample", "open"])
def test_a01_a11_real_cli_examples(example: str) -> None:
    process = run_cli((ROOT / f"A/examples/{example}.in").read_bytes())
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == (ROOT / f"A/examples/{example}.out").read_text().splitlines()


def test_a02_to_a08_cli_state_changes_and_replays() -> None:
    process = run_cli(
        "0 13\n"
        "RESERVE rejected o 1\n"
        "RESTOCK r 6\n"
        "RESERVE rejected other 2\n"
        "RESERVE a o 6\n"
        "RESERVE over x 1\n"
        "RESERVE a other 1\n"
        "RELEASE release o 2\n"
        "SHIP ship o 1\n"
        "SHIP ship o 2\n"
        "SHIP too-many o 4\n"
        "RELEASE missing unknown 1\n"
        "SHIP finish o 3\n"
        "RESTOCK a 100\n"
    )
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == [
        "REJECTED 0 0", "OK 6 0", "DUPLICATE 6 0", "OK 6 6", "REJECTED 6 6",
        "DUPLICATE 6 6", "OK 6 4", "OK 5 3", "DUPLICATE 5 3", "REJECTED 5 3",
        "REJECTED 5 3", "OK 2 0", "DUPLICATE 2 0", "OPEN 0",
    ]


def test_a09_all_bad_commands_count_as_lines_and_processing_continues() -> None:
    commands = [*MALFORMED, "RESERVE final order 1"]
    text = f"3 {len(commands)}\n" + "\n".join(commands) + "\n"
    process = run_cli(text)
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == ["REJECTED 3 0"] * (len(commands) - 1) + [
        "OK 3 1", "OPEN 1", "order 1",
    ]


def test_a10_cli_validation_precedes_duplicate_lookup() -> None:
    process = run_cli(
        "5 5\nRESERVE e o 0\nRESERVE e o 2\nRESTOCK e 0\nRESTOCK e 1\nSHIP done o 2\n"
    )
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == [
        "REJECTED 5 0", "OK 5 2", "REJECTED 5 2", "DUPLICATE 5 2", "OK 3 0", "OPEN 0",
    ]


def test_a12_cli_accumulated_stock_exceeds_initial_limit() -> None:
    process = run_cli("1000000000000 2\nRESTOCK e1 1000000000000\nRESTOCK e2 1000000000000\n")
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == ["OK 2000000000000 0", "OK 3000000000000 0", "OPEN 0"]


@pytest.mark.parametrize(
    "text",
    [
        "", "\n", "1\n", "1 1 extra\nRESTOCK e 1\n",
        "-1 1\nRESTOCK e 1\n", "+1 1\nRESTOCK e 1\n",
        "1.0 1\nRESTOCK e 1\n", "１ 1\nRESTOCK e 1\n",
        "1 0\n", "1 200001\n", "1000000000001 1\nRESTOCK e 1\n",
        "1 1\n",  # A terminal newline does not manufacture the missing command.
        "1 2\nRESTOCK valid 1\n",  # No output for the valid prefix before a missing line.
        "1 1\nRESTOCK valid 1\nEXTRA\n",
        "1 1\nRESTOCK valid 1\n\nEXTRA\n",
        "\ufeff1 1\nRESTOCK e 1\n",
        "1\x001 1\nRESTOCK e 1\n",
        "9" * 5000 + " 1\nRESTOCK e 1\n",
    ],
)
def test_a13_invalid_frame_has_no_partial_stdout(text: str) -> None:
    process = run_cli(text)
    assert process.returncode == 2
    assert process.stdout == b""
    assert process.stderr.startswith(b"Input error: ")
    assert b"Traceback" not in process.stderr


@pytest.mark.parametrize(
    "text",
    [
        "1 1\nRESTOCK e 1",  # No final newline required.
        "1 1\nRESTOCK e 1\n\n \t\n",
        "1 1\r\nRESTOCK e 1\r\n\r\n \t\r\n",
        "0001\t0001\n  RESTOCK\te\t0001  \n",
    ],
)
def test_a13_valid_line_endings_whitespace_and_leading_zeros(text: str) -> None:
    process = run_cli(text)
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == ["OK 2 0", "OPEN 0"]


def test_a13_blank_command_is_not_globally_filtered() -> None:
    process = run_cli("1 3\n\nRESTOCK e 1\n\t\n\n")
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == ["REJECTED 1 0", "OK 2 0", "REJECTED 2 0", "OPEN 0"]


def test_invalid_utf8_is_a_malformed_command_without_consuming_id() -> None:
    process = run_cli(b"2 2\nRESERVE e o\xff 1\nRESERVE e o 1\n")
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == ["REJECTED 2 0", "OK 2 1", "OPEN 1", "o 1"]
