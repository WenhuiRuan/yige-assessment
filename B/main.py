"""Run python -m B.main from the repository root."""

import sys
from typing import TextIO

from B.formatting import format_solution
from B.optimizer import optimize
from B.parsing import InputError, parse_input


def run(text: str, stdout: TextIO, stderr: TextIO) -> int:
    try:
        problem = parse_input(text)
    except InputError as error:
        stderr.write(f"Input error: {error}\n")
        return 2
    solution = optimize(problem.warehouses, problem.quantity)
    # Complete validation, optimization and reconstruction before producing any output.
    stdout.write(format_solution(solution))
    return 0


def main() -> int:
    try:
        text = sys.stdin.buffer.read().decode("utf-8")
    except UnicodeDecodeError:
        sys.stderr.write("Input error: Input must be UTF-8\n")
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    return run(text, sys.stdout, sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
