"""Intentionally simple test oracle; it never calls the production parser or ledger."""

import random
import re
from dataclasses import dataclass, field


@dataclass
class ReferenceLedger:
    on_hand: int
    orders: dict[str, int] = field(default_factory=dict)
    seen: set[str] = field(default_factory=set)

    def step(self, line: str) -> str:
        fields = line.split()
        valid = all(char == "\t" or 32 <= ord(char) <= 126 for char in line)
        valid = valid and bool(fields) and fields[0] in ("RESERVE", "RELEASE", "SHIP", "RESTOCK")
        if valid:
            valid = len(fields) == (3 if fields[0] == "RESTOCK" else 4)
        quantity = 0
        if valid:
            numeric = fields[-1].lstrip("0") or "0"
            valid = re.fullmatch(r"[0-9]+", fields[-1]) is not None and len(numeric) <= 13
            if valid:
                quantity = int(numeric)
                valid = 1 <= quantity <= 10**12

        status = "REJECTED"
        if valid:
            operation, event = fields[:2]
            if event in self.seen:
                status = "DUPLICATE"
            else:
                self.seen.add(event)
                if operation == "RESTOCK":
                    self.on_hand += quantity
                    status = "OK"
                elif operation == "RESERVE":
                    if self.on_hand - sum(self.orders.values()) >= quantity:
                        order = fields[2]
                        self.orders[order] = self.orders.get(order, 0) + quantity
                        status = "OK"
                else:
                    order = fields[2]
                    if self.orders.get(order, 0) >= quantity:
                        self.orders[order] -= quantity
                        if not self.orders[order]:
                            self.orders.pop(order)
                        if operation == "SHIP":
                            self.on_hand -= quantity
                        status = "OK"

        return f"{status} {self.on_hand} {sum(self.orders.values())}"

    def open_lines(self) -> list[str]:
        return [f"OPEN {len(self.orders)}"] + [
            f"{order} {self.orders[order]}" for order in sorted(self.orders)
        ]


def random_commands(seed: int, count: int) -> list[str]:
    rng = random.Random(seed)
    commands = []
    issued = []
    for index in range(count):
        event = rng.choice(issued) if issued and rng.random() < 0.35 else f"e{index}"
        issued.append(event)
        operation = rng.choice(["RESERVE", "RELEASE", "SHIP", "RESTOCK"])
        order = rng.choice(["A", "a", "z", *[f"o{number}" for number in range(16)]])
        quantity = str(rng.choice([1, 2, 3, 5, 10, 20, 40, 10**12]))
        if rng.random() < 0.20:
            quantity = rng.choice(["0", "-1", "+1", "1.0", "１２", "1000000000001"])
        fields = [operation, event]
        if operation != "RESTOCK":
            fields.append(order)
        fields.append(quantity)
        line = rng.choice([" ", "\t", "  "]).join(fields)
        damage = rng.randrange(20)
        if damage == 0:
            line = ""
        elif damage == 1:
            line += " extra"
        elif damage == 2:
            line = line.replace(event, event + "é", 1)
        elif damage == 3:
            line = "UNKNOWN " + event + " " + quantity
        commands.append(line)
    return commands
