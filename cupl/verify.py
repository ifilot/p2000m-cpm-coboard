#!/usr/bin/env python3
"""Check the actual ATF1502AS CUPL equations against the mapper specification."""

from __future__ import annotations

import argparse
import ast
from itertools import product
import re
from pathlib import Path


PLD_PATH = Path(__file__).with_name("p2000m-cpm-coboard.pld")

EXPECTED_PINS = {
    1: "RES_N",
    2: "A5",
    4: "M1_N",
    5: "WR_N",
    6: "IORQ_N",
    8: "A15",
    9: "MRQ_N",
    11: "A6",
    12: "A14",
    14: "A4",
    16: "RA12",
    17: "RA14",
    18: "RA15",
    19: "D7",
    20: "RA13",
    21: "A11",
    27: "P6_CARS2_N",
    28: "P7_RAMS2",
    29: "RAMS3_N",
    31: "P5_CARS1_N",
    33: "P4_ROMS2_N",
    34: "A13",
    36: "P3_ROMS1_N",
    37: "P2_VIDS_N",
    39: "P1_RAMS1",
    40: "P0_MBEN_N",
    41: "A12",
    43: "A7",
    44: "T_MODEL",
}

NORMAL_P_TABLE = bytes.fromhex(
    """
    74 74 5C 5C  5C 5C 3C 3C
    3C 3C 79 7D  7E 7E 7E 7E
    7E 7E 7E 7E  FD FD FD FD
    FD FD FD FD  FD FD FD FD
    """
)

# P7..P0 only. RAMS3_N is a separate CPLD output, so local RAM has the
# all-inactive P-byte 0x7D rather than the old combined EEPROM byte 0x79.
CPM_M_P_TABLE = bytes.fromhex(
    """
    7E 7E 7E 7E  7E 7E 7E 7E
    FD FD FD FD  FD FD FD FD
    FD FD FD FD  7D 7D 7D 7D
    7D 7D 7D 7D  5C 5C FD FD
    """
)

CPM_T_P_TABLE = CPM_M_P_TABLE[:30] + bytes([0xF9, 0xFD])
ALL_P_SELECTS_INACTIVE = 0x7D


P_OUTPUTS = (
    "P0_MBEN_N", "P1_RAMS1", "P2_VIDS_N", "P3_ROMS1_N",
    "P4_ROMS2_N", "P5_CARS1_N", "P6_CARS2_N", "P7_RAMS2",
)
OUTPUTS = P_OUTPUTS + ("RAMS3_N", "RA12", "RA13", "RA14", "RA15")
INPUTS = set(EXPECTED_PINS.values()) - set(OUTPUTS)
CONTROLS = ("CPM_MODE.d", "CPM_MODE.ck", "CPM_MODE.ar")


def require(condition: bool, message: str) -> None:
    # Keep verification active even when Python is invoked with -O.
    if not condition:
        raise ValueError(message)


class Source:
    """Evaluate this project's scalar CUPL subset, rejecting unsupported syntax.

    Supports !, &, #, parentheses and binary constants. This is a functional
    source checker, not a CUPL compiler or a propagation-delay simulator.
    """

    def __init__(self, source: str, *, stock: bool = False):
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
        self.equations = {}
        pins = {}
        headers = {}
        properties = {}
        nodes = []
        for statement in source.split(";"):
            statement = " ".join(statement.split())
            if not statement:
                continue
            pin = re.fullmatch(r"PIN (\d+) = ([A-Z][A-Z0-9_]*)", statement)
            header = re.fullmatch(
                r"(Name|PartNo|Date|Revision|Designer|Company|Assembly|Location|Device) (.+)",
                statement,
            )
            prop = re.fullmatch(r"PROPERTY ATMEL \{(\w+) = (\w+)\}", statement)
            if pin:
                number, name = int(pin[1]), pin[2]
                require(number not in pins, f"Duplicate pin {number}")
                pins[number] = name
            elif header:
                require(header[1] not in headers, f"Duplicate header {header[1]}")
                headers[header[1]] = header[2]
            elif prop:
                require(prop[1] not in properties, f"Duplicate property {prop[1]}")
                properties[prop[1]] = prop[2]
            elif statement == "Pinnode = CPM_MODE":
                nodes.append("CPM_MODE")
            else:
                equation = re.fullmatch(r"([A-Z][A-Z0-9_]*(?:\.[a-z]+)?) = (.+)", statement)
                require(equation is not None, f"Unsupported CUPL statement: {statement}")
                name, expression = equation[1], equation[2]
                require(name not in self.equations, f"Duplicate equation {name}")
                require(name not in INPUTS | {"CPM_MODE"}, f"Cannot drive input/state {name}")
                require("." not in name or (not stock and name in CONTROLS),
                        f"Unsupported control {name}")
                expression = re.sub(r"'b'([01])", r"\1", expression)
                require(re.fullmatch(r"[A-Z0-9_!&#()\s]+", expression) is not None,
                        f"Unsupported expression for {name}: {expression}")
                tree = ast.parse(expression.replace("!", "~").replace("#", "|"), mode="eval")
                allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name,
                           ast.Load, ast.Constant, ast.BitAnd, ast.BitOr, ast.Invert)
                for node in ast.walk(tree):
                    require(isinstance(node, allowed), f"Unsupported operator in {name}")
                    if isinstance(node, ast.Constant):
                        require(type(node.value) is int and node.value in (0, 1),
                                f"Non-binary constant in {name}")
                dependencies = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
                self.equations[name] = (compile(tree, f"<CUPL {name}>", "eval"), dependencies)

        require(headers.get("Device") == "f1502ispplcc44", "Expected ATF1502AS PLCC-44 device")
        require(pins == EXPECTED_PINS, "Source pin assignments differ from board pinout")
        require(nodes == ([] if stock else ["CPM_MODE"]),
                "Expected no registers" if stock else "Expected exactly one CPM_MODE register")
        require(properties == {"POWER_RESET": "OFF", "PIN_KEEP": "ON", "PREASSIGN": "KEEP"},
                "Unsupported fitter properties; review verification assumptions")
        require(set(OUTPUTS + (() if stock else CONTROLS)) <= self.equations.keys(),
                "Missing output/register equation")
        # Resolve a dependency order once; detect undefined signals and feedback loops.
        self.order = []
        visiting = set()
        done = INPUTS | (set() if stock else {"CPM_MODE"})

        def visit(name):
            if name in done:
                return
            require(name in self.equations, f"Undefined signal {name}")
            require(name not in visiting, f"Combinational feedback at {name}")
            visiting.add(name)
            for dependency in self.equations[name][1]:
                visit(dependency)
            visiting.remove(name)
            done.add(name)
            self.order.append(name)

        for name in self.equations:
            visit(name)

        # The truth-table sweeps vary only the relevant inputs. Reject new
        # dependencies outside those sweeps rather than silently testing them
        # at a single default value (for example, a decode depending on D7).
        leaves = {name: {name} for name in INPUTS | {"CPM_MODE"}}
        for name in self.order:
            leaves[name] = set().union(*(leaves[dep] for dep in self.equations[name][1]))
        memory_inputs = {"CPM_MODE", "T_MODEL", "MRQ_N"} | {
            f"A{bit}" for bit in range(11, 16)
        }
        covered_inputs = {name: memory_inputs for name in OUTPUTS}
        covered_inputs.update({
            "CPM_MODE.ck": {"A4", "A5", "A6", "A7", "IORQ_N", "WR_N", "M1_N",
                            "D7", "RES_N", "CPM_MODE"},
            "CPM_MODE.d": {"D7"},
            "CPM_MODE.ar": {"RES_N"},
        })
        if stock:
            covered_inputs = {name: {f"A{bit}" for bit in range(11, 16)} for name in OUTPUTS}
        for name, covered in covered_inputs.items():
            uncovered = leaves[name] - covered
            require(not uncovered, f"Untested input dependencies for {name}: {sorted(uncovered)}")

    def evaluate(self, inputs: dict[str, int], mode: int) -> dict[str, int]:
        require(inputs.keys() == INPUTS, "Missing or unexpected input signals")
        values = dict(inputs, CPM_MODE=mode)
        for name in self.order:
            # Whitelisted AST only; bit zero implements scalar CUPL complement.
            values[name] = eval(self.equations[name][0], {"__builtins__": {}}, values) & 1
        return values

    def step(self, inputs: dict[str, int], mode: int, previous_clock: int) -> tuple[int, int]:
        values = self.evaluate(inputs, mode)
        clock = values["CPM_MODE.ck"]
        if values["CPM_MODE.ar"]:
            mode = 0
        elif clock and not previous_clock:
            mode = values["CPM_MODE.d"]
        return mode, clock


def inputs_for(address: int = 0, **overrides: int) -> dict[str, int]:
    inputs = {name: 0 for name in INPUTS}
    inputs.update(RES_N=1, M1_N=1, WR_N=1, IORQ_N=1, MRQ_N=1)
    for bit in (4, 5, 6, 7, 11, 12, 13, 14, 15):
        inputs[f"A{bit}"] = (address >> bit) & 1
    inputs.update(overrides)
    return inputs


def output_byte(values: dict[str, int]) -> int:
    return sum(values[name] << bit for bit, name in enumerate(P_OUTPUTS))


def verify(model: Source) -> None:
    for block, mode, t_model, mrq in product(range(32), range(2), range(2), range(2)):
        values = model.evaluate(inputs_for(block << 11, T_MODEL=t_model, MRQ_N=mrq), mode)
        table = (CPM_T_P_TABLE if t_model else CPM_M_P_TABLE) if mode else NORMAL_P_TABLE
        expected = ALL_P_SELECTS_INACTIVE if mode and mrq else table[block]
        context = f"block={block:02X}, CPM={mode}, T={t_model}, /MRQ={mrq}"
        require(output_byte(values) == expected, f"P7..P0 mismatch: {context}")
        require(values["RAMS3_N"] == int(not (mode and not mrq and 20 <= block <= 27)),
                f"/RAMS3 mismatch: {context}")
        translated = sum(values[f"RA{bit}"] << (bit - 12) for bit in range(12, 16))
        require(translated == ((block // 2 + 6 * mode) & 15), f"Translation mismatch: {context}")

    # Exhaust all control levels, both data values and both prior register states.
    for port, iorq, wr, m1, data, reset, mode in product(range(256), *([range(2)] * 6)):
        inputs = inputs_for(port, IORQ_N=iorq, WR_N=wr, M1_N=m1, D7=data, RES_N=reset)
        values = model.evaluate(inputs, mode)
        strobe = int(not iorq and not wr and m1 and 0x20 <= port <= 0x2F)
        context = f"port={port:02X}, /IORQ={iorq}, /WR={wr}, /M1={m1}, D7={data}, /RES={reset}, CPM={mode}"
        require(values["CPM_MODE.ck"] == strobe, f"Clock mismatch: {context}")
        require(values["CPM_MODE.d"] == data, f"Register data mismatch: {context}")
        require(values["CPM_MODE.ar"] == 1 - reset, f"Reset mismatch: {context}")
        for previous_clock in (0, 1):
            expected = 0 if not reset else data if strobe and not previous_clock else mode
            actual, clock = model.step(inputs, mode, previous_clock)
            require((actual, clock) == (expected, strobe), f"Register transition mismatch: {context}")

    # A complete write pulse: capture at assertion, hold through data changes
    # and deassertion, reset asynchronously, and write again after reset.
    mode, clock = 0, 0
    sequence = [
        ({}, 0),
        ({"IORQ_N": 0, "WR_N": 0, "D7": 1}, 1),
        ({"IORQ_N": 0, "WR_N": 0, "D7": 0}, 1),
        ({}, 1),
        ({"RES_N": 0}, 0),
        ({}, 0),
        ({"IORQ_N": 0, "WR_N": 0, "D7": 1}, 1),
        ({}, 1),
        ({"IORQ_N": 0, "WR_N": 0, "D7": 0}, 0),
    ]
    for overrides, expected in sequence:
        mode, clock = model.step(inputs_for(0x20, **overrides), mode, clock)
        require(mode == expected, "Write/reset sequence mismatch")


def verify_stock(model: Source) -> None:
    """Compare the stock-only logic to the physical PROM dump, with no state."""
    dump = (PLD_PATH.parent.parent / "literature/82s123_dump_mobo.bin").read_bytes()
    require(len(dump) == 32, "Expected a 32-byte original PROM dump")
    # Source(stock=True) excludes any dependence on non-address inputs.
    for block in range(32):
        values = model.evaluate(inputs_for(block << 11), 0)
        require(output_byte(values) == dump[block], f"Stock PROM mismatch at block {block:02X}")
        require(values["RAMS3_N"] == 1, "Stock SRAM must always be disabled")
        for bit in range(12, 16):
            require(values[f"RA{bit}"] == ((block << 11) >> bit) & 1,
                    f"Stock address pass-through mismatch: RA{bit}, block {block:02X}")


def dump_tables(model: Source) -> None:
    for title, mode, t_model in (("Normal", 0, 0), ("CP/M P2000M", 1, 0), ("CP/M P2000T", 1, 1)):
        print(f"{title} P7..P0:")
        data = [output_byte(model.evaluate(inputs_for(block << 11, T_MODEL=t_model, MRQ_N=0), mode))
                for block in range(32)]
        for offset in range(0, 32, 8):
            print(" ".join(f"{value:02X}" for value in data[offset:offset + 8]))
    print("CP/M upper-nibble translation:")
    translations = []
    for page in range(16):
        values = model.evaluate(inputs_for(page << 12), 1)
        translated = sum(values[f"RA{bit}"] << (bit - 12) for bit in range(12, 16))
        translations.append(f"{page:X}->{translated:X}")
    print(" ".join(translations))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", action="store_true", help="print the verified source tables")
    parser.add_argument("--source", type=Path, help="CUPL source to verify")
    parser.add_argument("--stock", action="store_true", help="verify the separate stock-only PROM image")
    args = parser.parse_args()
    try:
        path = args.source or (PLD_PATH.with_name("p2000m-stock-prom.pld") if args.stock else PLD_PATH)
        model = Source(path.read_text(encoding="ascii"), stock=args.stock)
        (verify_stock if args.stock else verify)(model)
    except (ValueError, SyntaxError, OSError) as error:
        parser.exit(1, f"Verification failed: {error}\n")
    if args.stock:
        print("Stock CUPL verified: original PROM dump, SRAM disabled, address pass-through, no registers.")
    else:
        print("CUPL source verified: pinout, 256 map cases, 16384 control cases and register transitions.")
    if args.dump:
        if args.stock:
            print(" ".join(f"{output_byte(model.evaluate(inputs_for(block << 11), 0)):02X}"
                           for block in range(32)))
        else:
            dump_tables(model)


if __name__ == "__main__":
    main()
