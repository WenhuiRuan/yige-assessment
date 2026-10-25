"""Format a completed solution; never compare these strings to break ties."""

from B.optimizer import Solution


def format_solution(solution: Solution | None) -> str:
    if solution is None:
        return "-1\n"
    lines = [f"{solution.warehouse_count} {solution.total_cost}"]
    lines.extend(f"{warehouse_id} {quantity}" for warehouse_id, quantity in solution.allocations)
    return "\n".join(lines) + "\n"
