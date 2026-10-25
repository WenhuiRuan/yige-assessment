# Task B - Fulfilment Split Optimiser

[中文版](README.md)

Run from the repository root:

```powershell
Get-Content B/examples/sample.in | .venv/Scripts/python.exe -m B.main
.venv/Scripts/python.exe -m pytest B/tests -q
```

## State representation

First sort warehouses by ID. `D[i][q]` is the best `(warehouse count, total cost)` for shipping exactly q units using only warehouse i and the warehouses after it. Unreachable states use None. Initially, `D[W][0]=(0,0)`; all other quantities are unreachable.

Let the current warehouse have stock s, fixed fee f, and unit cost u. Compare these transitions:

- Skip the current warehouse: use `D[i+1][q]`.
- Allocate x units: add 1 to the next layer's warehouse count and `f+x*u` to its cost, where `1 ≤ x ≤ min(s,q)`.

To avoid enumerating every x, set `t=q-x` and use a monotonic deque to maintain the minimum `(count, cost-t*u)` over the window `max(0,q-s)..q-1`, then add 1 and `f+q*u` respectively. Each layer reads only the next layer, so a warehouse is never reused. The implementation uses only the Python standard library.

## Tie-breaking

Compare warehouse count first, then total cost. If both are equal, compare the list of nonzero `(warehouse_id, quantity)` pairs sorted by ID.

The DP stores the optimum for the first two objectives. During reconstruction, try IDs in ascending order and quantities from smallest to largest. Accept only candidates satisfying “current warehouse contribution + optimal suffix value = current target.” Select the first such candidate, then reconstruct the remaining suffix. Each step chooses the smallest item that can still achieve the optimal target, producing the lexicographically smallest list.

For example, warehouses A and B each hold 10 units with zero costs, and demand is 12. All feasible two-warehouse allocations have the same cost; the result should be `[(A,2),(B,10)]`. Quantities are compared as integers, and unused warehouses are omitted from the list.

## Time and space complexity

Sorting takes O(W log W). Each state enters and leaves the monotonic deque at most once, so the DP takes O(WQ). Reconstruction moves only forward through the warehouses and tries at most Q quantities per warehouse, also taking O(WQ).

Total time is **O(WQ+W log W)**. Storing the full suffix table takes **O(WQ)** space. Input buffering adds O(L), where L is the input length; ID comparisons assume fixed-length IDs.

## Tests and input conventions

[test_optimizer.py](tests/test_optimizer.py) covers insufficient stock, zero stock, warehouse-count priority, costs, and ties. [test_scale.py](tests/test_scale.py) covers W=30 and Q=2000. Another 5,000 differential cases compare all three objectives against an independent exhaustive search.

Warehouse IDs are sorted by case-sensitive Unicode code point order; duplicate IDs are rejected. Input errors are reported to stderr with exit code 2. Valid but infeasible inputs output -1. Feasible results output the warehouse count, cost, and sorted allocation in the required format.
