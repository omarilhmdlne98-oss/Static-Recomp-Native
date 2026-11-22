#!/usr/bin/env python3
"""Symbol table & address-to-C++ identifier mapper for Static-Recomp-Native."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List


@dataclass
class FunctionSymbol:
    name: str
    address: int
    size: int
    section: str
    arch: str

    @property
    def cpp_identifier(self) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", self.name)
        if not sanitized or sanitized[0].isdigit():
            sanitized = f"sub_{self.address:08X}"
        return f"recomp_{sanitized}_{self.address:08X}"


class SymbolMapper:
    """Maps disassembled addresses & console symbols to deterministic C++20 identifiers."""

    def __init__(self) -> None:
        self.symbols: Dict[int, FunctionSymbol] = {}

    def register(self, name: str, address: int, size: int, section: str, arch: str) -> FunctionSymbol:
        sym = FunctionSymbol(name=name, address=address, size=size, section=section, arch=arch)
        self.symbols[address] = sym
        return sym

    def load_map_json(self, path: Path) -> int:
        data = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        for entry in data.get("symbols", []):
            addr = int(entry["address"], 16) if isinstance(entry["address"], str) else int(entry["address"])
            self.register(
                name=entry.get("name", f"sub_{addr:08X}"),
                address=addr,
                size=int(entry.get("size", 0)),
                section=entry.get("section", ".text"),
                arch=entry.get("arch", "unknown"),
            )
            count += 1
        return count

    def export_json(self, path: Path) -> None:
        payload = {
            "count": len(self.symbols),
            "symbols": [
                {
                    **asdict(sym),
                    "address_hex": f"0x{sym.address:08X}",
                    "cpp_identifier": sym.cpp_identifier,
                }
                for sym in self.sorted_symbols()
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def sorted_symbols(self) -> List[FunctionSymbol]:
        return [self.symbols[k] for k in sorted(self.symbols.keys())]
