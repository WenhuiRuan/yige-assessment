# Task A - Inventory Reservation Ledger

[中文版](README.md)

## Run

Run from the repository root. See the root [README](../README.en.md) for dependency installation:

```powershell
Get-Content A/examples/sample.in | .venv/Scripts/python.exe -m A.main
.venv/Scripts/python.exe -m pytest A/tests -q
```

The program reads commands from stdin and writes results to stdout. A dictionary stores each order's reservation, a set tracks processed events, and the total reserved quantity is maintained incrementally.

## Edge-case tests

The following cases are implemented in [test_ledger.py](tests/test_ledger.py). [test_cli.py](tests/test_cli.py) separately checks input line counts and command-line output.

| Case | Expected result |
| --- | --- |
| Stock is 0; reserve 1 unit | REJECTED; stock and reservations remain unchanged |
| Stock is 4; separately attempt to reserve 4 and 5 units | The first succeeds and leaves zero available stock; the second is rejected |
| An order reserves 2 units but attempts to release or ship 3, or the order does not exist | Rejected; another order's reservation cannot be used |
| Partial/full release and partial/full shipment | Release reduces only the reservation; shipping reduces both on-hand and reserved quantities; orders with zero reservation are omitted from the final list |
| Quantity is zero, negative, fractional, or a field is missing | Rejected; stock, orders, and the event set remain unchanged |
| One quantity reaches 10^12; repeated additions exceed 10^12 in total | The per-command limit is enforced; cumulative stock and reservations are still calculated correctly |

Tests also check that open orders are sorted by ID and that an invalid first line or line count does not produce partial output.

## Replay tests

[test_ledger.py](tests/test_ledger.py) also checks the following:

- Replaying a successful event for any of the four commands returns DUPLICATE and leaves the full state unchanged.
- A reservation is rejected when stock is 0. After restocking 5 units, replaying that event still returns DUPLICATE and does not reserve stock.
- A release or shipment rejected because the order's reservation is insufficient is still treated as processed when retried with the original ID.
- Reusing a processed ID with a different valid order, quantity, or command still returns DUPLICATE.
- An initially malformed command does not register its ID and can execute after correction. I validate the format before checking duplicates, so a processed ID with an invalid quantity still returns REJECTED.

Randomized tests compare each step with an independent reference model. Scale tests cover 200,000 commands.

## Complexity and output conventions

Processing N commands takes amortized O(N); sorting R open orders at the end takes O(R log R), for total time O(N+R log R). Ledger space is O(E+R), where E is the number of registered events. Input buffering adds O(L), where L is the input length. Hash operations assume fixed-size IDs and integers; character-processing costs for long IDs are additional.

Final output starts with `OPEN K`, followed by one `order_id quantity` pair per line. An invalid first line or line count is reported to stderr with exit code 2. An individual invalid command returns REJECTED, and processing continues. IDs use non-empty printable ASCII.
