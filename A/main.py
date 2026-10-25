"""Run with python -m A.main; stdin/stdout implement the assessment protocol."""

import sys
from typing import TextIO

from A.formatting import format_open, format_result
from A.ledger import Ledger
from A.parsing import InputFrameError, parse_command, parse_input


def run(text: str, stdout: TextIO, stderr: TextIO) -> int:
    try:
        frame = parse_input(text)
    except InputFrameError as error:
        stderr.write(f"Input error: {error}\n")
        return 2

    ledger = Ledger(frame.initial_stock)
    for line in frame.commands:
        result = ledger.apply(parse_command(line))
        stdout.write(format_result(result) + "\n")
    for line in format_open(ledger.reservations):
        stdout.write(line + "\n")
    return 0


def main() -> int:
    # Non-UTF-8 bytes survive as invalid characters, so a malformed command is rejected
    # locally instead of crashing decoding or changing the physical command count.
    text = sys.stdin.buffer.read().decode("utf-8", errors="surrogateescape")
    return run(text, sys.stdout, sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
