from io import StringIO

import pytest

from B.main import run
from B.parsing import parse_input
from B.tests.reference import exhaustive_reference, random_problems
from B.tests.support import ROOT, output_lines, problem_text, run_cli


@pytest.mark.parametrize("example", ["sample", "tie-id", "tie-quantity"])
def test_b01_b05_b06_real_cli_examples(example: str) -> None:
    process = run_cli((ROOT / f"B/examples/{example}.in").read_bytes())
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == (ROOT / f"B/examples/{example}.out").read_text().splitlines()


@pytest.mark.parametrize("text", ["1 1\nA 0 0 0\n", "2 3\nA 1 0 0\nB 1 0 0\n"])
def test_b02_infeasible_is_only_minus_one(text: str) -> None:
    process = run_cli(text)
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == ["-1"]


@pytest.mark.parametrize(
    "text",
    [
        "", "\n", "1\n", "1 1 extra\nA 1 0 0\n", "0 1\n", "31 1\n",
        "1 0\nA 1 0 0\n", "1 2001\nA 2000 0 0\n", "-1 1\n", "+1 1\n",
        "1.0 1\nA 1 0 0\n", "１ 1\nA 1 0 0\n", "1 1\n", "2 1\nA 1 0 0\n",
        "1 1\n\n", "1 1\nA 1 0\n", "1 1\nA 1 0 0 extra\n",
        "1 1\nA -1 0 0\n", "1 1\nA 2001 0 0\n", "1 1\nA 1 -1 0\n",
        "1 1\nA 1 1000001 0\n", "1 1\nA 1 0 -1\n", "1 1\nA 1 0 1000001\n",
        "1 1\nA 1.0 0 0\n", "1 1\nA +1 0 0\n", "1 1\nA 1_000 0 0\n",
        "1 1\nA 1 true 0\n", "1 1\nA 1 0 ０\n", "1 1\nA\x00 1 0 0\n",
        "1 1\nA\x7f 1 0 0\n", "1 1\nA\u200b 1 0 0\n",
        "1 1\nA\u00a0B 1 0 0\n", "1 1\nA B 1 0 0\n",
        "2 1\nA 1 0 0\nA 2 0 0\n", "2 1\n仓库 0 0 0\n仓库 0 0 0\n",
        "1 1\nA 0 0 0\nEXTRA\n",  # Even an infeasible prefix must not bypass validation.
        "1 1\nA 1 0 0\n\nEXTRA\n", "\ufeff1 1\nA 1 0 0\n",
        "1 1\nA 1 0 0\n\u00a0\n", "1 1\nA\r 1 0 0\n",
        "9" * 5000 + " 1\nA 1 0 0\n", "1 1\nA " + "9" * 5000 + " 0 0\n",
    ],
)
def test_b11_bad_input_is_error_not_business_infeasibility(text: str) -> None:
    process = run_cli(text)
    assert process.returncode == 2
    assert process.stdout == b""
    assert process.stderr.startswith(b"Input error: ")
    assert b"Traceback" not in process.stderr


@pytest.mark.parametrize(
    "text",
    ["1 1\n仓库 1 0 0", "1 1\r\n仓库 1 0 0\r\n \t\r\n\r\n",
     "0001\t0001\n  仓库\t0001  0000\t0000  \n"],
)
def test_b11_unicode_ids_and_valid_transport(text: str) -> None:
    process = run_cli(text)
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == ["1 0", "仓库 1"]


def test_b11_unicode_codepoint_order_without_casefold_or_normalization() -> None:
    process = run_cli("3 1\né 1 0 0\n仓库 1 0 0\ne\u0301 1 0 0\n")
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == ["1 0", "e\u0301 1"]


def test_b11_invalid_utf8_has_no_partial_output() -> None:
    process = run_cli(b"1 1\nA\xff 1 0 0\n")
    assert process.returncode == 2
    assert process.stdout == b""
    assert process.stderr.startswith(b"Input error: ")
    assert b"Traceback" not in process.stderr


def test_b11_long_leading_zeros_are_accepted_without_int_digit_limit_failure() -> None:
    zeros = "0" * 5000
    text = f"{zeros}1 {zeros}1\nA {zeros}1 {zeros}0 {zeros}0\n"
    assert parse_input(text).quantity == 1
    process = run_cli(text)
    assert process.returncode == 0
    assert process.stderr == b""
    assert output_lines(process) == ["1 0", "A 1"]


def test_b11_run_validates_every_row_before_any_output() -> None:
    stdout, stderr = StringIO(), StringIO()
    code = run("2 1\nA 1 0 0\nA 1 0 0\n", stdout, stderr)
    assert code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue().startswith("Input error: ")


@pytest.mark.parametrize(("records", "quantity"), list(random_problems(20261027, 25)))
def test_b12_real_cli_differential(records, quantity) -> None:
    expected = exhaustive_reference(records, quantity).objective
    process = run_cli(problem_text(records, quantity))
    assert process.returncode == 0
    assert process.stderr == b""
    lines = ["-1"] if expected is None else [f"{expected[0]} {expected[1]}"] + [
        f"{warehouse_id} {allocated}" for warehouse_id, allocated in expected[2]
    ]
    assert output_lines(process) == lines, problem_text(records, quantity)
