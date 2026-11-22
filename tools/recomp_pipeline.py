#!/usr/bin/env python3
"""
Static-Recomp-Native Pipeline CLI
Inspired by Leonida, XenonRecomp, and N64Recomp.

Inspects target console executable headers (.xex / .z64 / .elf),
extracts section tables, generates C++20 function stub mappings in
generated_code/, and validates SPIR-V shader translation readiness.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.symbol_mapper import SymbolMapper  # noqa: E402
from shaders.spirv_translator import validate_shader_directory  # noqa: E402


@dataclass
class SectionInfo:
    name: str
    virtual_address: int
    file_offset: int
    size: int
    executable: bool


@dataclass
class BinaryMetadata:
    source_file: str
    format_name: str
    architecture: str
    endianness: str
    entry_point: int
    title: str
    file_size: int
    sections: List[SectionInfo]


def parse_xex(data: bytes, source_name: str) -> BinaryMetadata:
    """Parse Xbox 360 XEX2 executable header (big-endian PowerPC64 / Xenon)."""
    if len(data) < 24 or data[:4] != b"XEX2":
        raise ValueError("Not a valid XEX2 binary (missing 'XEX2' magic).")

    module_flags, pe_data_offset, _reserved, sec_info_offset, opt_header_count = struct.unpack(">IIIII", data[4:24])
    entry_point = 0x82000000
    base_address = 0x82000000

    cursor = 24
    for _ in range(min(opt_header_count, 64)):
        if cursor + 8 > len(data):
            break
        key, value = struct.unpack(">II", data[cursor : cursor + 8])
        cursor += 8
        if key == 0x00010100:  # XEX_HEADER_ENTRY_POINT
            entry_point = value
        elif key == 0x00010201:  # XEX_HEADER_IMAGE_BASE_ADDRESS
            base_address = value

    code_size = max(0, len(data) - pe_data_offset)
    sections = [
        SectionInfo(
            name=".text",
            virtual_address=base_address,
            file_offset=pe_data_offset,
            size=code_size,
            executable=True,
        ),
        SectionInfo(
            name=".xex_secinfo",
            virtual_address=base_address + code_size,
            file_offset=min(sec_info_offset, len(data)),
            size=max(0, min(0x1000, len(data) - min(sec_info_offset, len(data)))),
            executable=False,
        ),
    ]
    return BinaryMetadata(
        source_file=source_name,
        format_name=f"XEX2 (flags=0x{module_flags:08X})",
        architecture="PowerPC64 (Xbox 360 Xenon)",
        endianness="big",
        entry_point=entry_point,
        title=Path(source_name).stem,
        file_size=len(data),
        sections=sections,
    )


def parse_z64(data: bytes, source_name: str) -> BinaryMetadata:
    """Parse Nintendo 64 ROM header (.z64 big-endian, .v64 byte-swapped, .n64 little-endian)."""
    if len(data) < 0x40:
        raise ValueError("N64 ROM is smaller than 64-byte header.")

    magic = data[:4]
    endian = "big"
    rom = data
    if magic == b"\x80\x37\x12\x40":
        fmt = "N64 (.z64 big-endian)"
    elif magic == b"\x37\x80\x40\x12":
        fmt = "N64 (.v64 byte-swapped)"
        endian = "byte-swapped"
        swapped = bytearray(data[:0x40])
        for i in range(0, 0x40, 2):
            swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
        rom = bytes(swapped)
    elif magic == b"\x40\x12\x37\x80":
        fmt = "N64 (.n64 little-endian)"
        endian = "little"
        swapped = bytearray(data[:0x40])
        for i in range(0, 0x40, 4):
            swapped[i : i + 4] = swapped[i : i + 4][::-1]
        rom = bytes(swapped)
    else:
        raise ValueError(f"Unrecognized N64 ROM magic: {magic.hex()}")

    entry_point = struct.unpack(">I", rom[0x08:0x0C])[0]
    crc1, crc2 = struct.unpack(">II", rom[0x10:0x18])
    raw_title = rom[0x20:0x34].decode("ascii", errors="replace").strip("\x00 ").strip()
    title = raw_title or Path(source_name).stem

    boot_size = min(0x1000, max(0, len(data) - 0x40))
    code_offset = min(0x1000, len(data))
    code_size = max(0, len(data) - code_offset)

    sections = [
        SectionInfo(name=".ipl3_boot", virtual_address=0xA4000040, file_offset=0x40, size=boot_size, executable=True),
        SectionInfo(name=".text", virtual_address=entry_point, file_offset=code_offset, size=code_size, executable=True),
    ]
    return BinaryMetadata(
        source_file=source_name,
        format_name=f"{fmt} CRC={crc1:08X}:{crc2:08X}",
        architecture="MIPS R4300i (N64)",
        endianness=endian,
        entry_point=entry_point,
        title=title,
        file_size=len(data),
        sections=sections,
    )


def parse_elf(data: bytes, source_name: str) -> BinaryMetadata:
    """Parse ELF32 / ELF64 console executable header and section table."""
    if len(data) < 52 or data[:4] != b"\x7fELF":
        raise ValueError("Not a valid ELF binary (missing 0x7F 'ELF' magic).")

    ei_class = data[4]  # 1 = 32-bit, 2 = 64-bit
    ei_data = data[5]   # 1 = little-endian, 2 = big-endian
    is_64 = ei_class == 2
    endian_prefix = "<" if ei_data == 1 else ">"
    endian_name = "little" if ei_data == 1 else "big"

    machine_map = {
        0x08: "MIPS",
        0x14: "PowerPC32",
        0x15: "PowerPC64",
        0x28: "ARM32",
        0x3E: "x86-64",
        0xB7: "AArch64",
    }

    if is_64:
        if len(data) < 64:
            raise ValueError("Truncated ELF64 header.")
        _e_type, e_machine, _e_ver, e_entry, _e_phoff, e_shoff, _e_flags, _e_ehsize, _e_phent, _e_phnum, e_shentsize, e_shnum, e_shstrndx = struct.unpack(
            f"{endian_prefix}HHIQQQIHHHHHH", data[16:64]
        )
    else:
        _e_type, e_machine, _e_ver, e_entry, _e_phoff, e_shoff, _e_flags, _e_ehsize, _e_phent, _e_phnum, e_shentsize, e_shnum, e_shstrndx = struct.unpack(
            f"{endian_prefix}HHIIIIIHHHHHH", data[16:52]
        )

    arch = machine_map.get(e_machine, f"ELF_Machine_0x{e_machine:02X}")
    sections: List[SectionInfo] = []

    strtab_data = b""
    if e_shoff and e_shnum > 0 and e_shstrndx < e_shnum:
        shstr_off = e_shoff + e_shstrndx * e_shentsize
        if is_64 and shstr_off + 64 <= len(data):
            _, _, _, _, s_off, s_size = struct.unpack(f"{endian_prefix}IIQQQQ", data[shstr_off : shstr_off + 40])
            strtab_data = data[s_off : s_off + s_size]
        elif not is_64 and shstr_off + 40 <= len(data):
            _, _, _, _, s_off, s_size = struct.unpack(f"{endian_prefix}IIIIII", data[shstr_off : shstr_off + 24])
            strtab_data = data[s_off : s_off + s_size]

    def read_str(idx: int) -> str:
        if not strtab_data or idx >= len(strtab_data):
            return f"sec_{idx}"
        end = strtab_data.find(b"\x00", idx)
        if end == -1:
            end = len(strtab_data)
        return strtab_data[idx:end].decode("ascii", errors="replace") or f"sec_{idx}"

    for i in range(min(e_shnum, 128)):
        off = e_shoff + i * e_shentsize
        if is_64 and off + 64 <= len(data):
            sh_name, _sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack(
                f"{endian_prefix}IIQQQQ", data[off : off + 40]
            )
        elif not is_64 and off + 40 <= len(data):
            sh_name, _sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack(
                f"{endian_prefix}IIIIII", data[off : off + 24]
            )
        else:
            break
        if sh_size > 0:
            sections.append(
                SectionInfo(
                    name=read_str(sh_name),
                    virtual_address=sh_addr,
                    file_offset=sh_offset,
                    size=sh_size,
                    executable=bool(sh_flags & 0x4),  # SHF_EXECINSTR
                )
            )

    if not sections:
        sections.append(SectionInfo(name=".text", virtual_address=e_entry, file_offset=0, size=len(data), executable=True))

    return BinaryMetadata(
        source_file=source_name,
        format_name="ELF64" if is_64 else "ELF32",
        architecture=arch,
        endianness=endian_name,
        entry_point=e_entry,
        title=Path(source_name).stem,
        file_size=len(data),
        sections=sections,
    )


def inspect_binary(path: Path) -> BinaryMetadata:
    data = path.read_bytes()
    suffix = path.suffix.lower()
    if data[:4] == b"XEX2" or suffix == ".xex":
        return parse_xex(data, path.name)
    if data[:4] == b"\x7fELF" or suffix == ".elf":
        return parse_elf(data, path.name)
    if suffix in {".z64", ".v64", ".n64"} or data[:4] in {b"\x80\x37\x12\x40", b"\x37\x80\x40\x12", b"\x40\x12\x37\x80"}:
        return parse_z64(data, path.name)
    raise ValueError(f"Unsupported binary format for '{path.name}'. Expected .xex, .z64/.v64/.n64, or .elf.")


def generate_cpp_stubs(meta: BinaryMetadata, mapper: SymbolMapper, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    mapper.register("entry_main", meta.entry_point, 0x100, ".text", meta.architecture)
    for idx, sec in enumerate(meta.sections):
        if sec.executable:
            mapper.register(f"sec_{idx}_{sec.name.strip('.') or 'exec'}", sec.virtual_address, sec.size, sec.name, meta.architecture)

    mapper.export_json(out_dir / "symbols.json")

    header_path = out_dir / "RecompStubs.h"
    lines = [
        "#pragma once",
        "// Auto-generated by tools/recomp_pipeline.py — DO NOT EDIT MANUALLY",
        f"// Source: {meta.source_file} | Format: {meta.format_name} | Arch: {meta.architecture}",
        "",
        "#include <cstdint>",
        "#include <unordered_map>",
        "",
        "namespace static_recomp {",
        "",
        "struct RecompContext {",
        "    uint64_t gpr[32]{};",
        "    double fpr[32]{};",
        "    uint64_t pc = 0;",
        "    uint64_t lr = 0;",
        "    uint8_t* rdram = nullptr;",
        "};",
        "",
        "using RecompFunc = void (*)(RecompContext&);",
        "",
        f"inline constexpr uint64_t kEntryPoint = 0x{meta.entry_point:016X}ULL;",
        "",
    ]

    for sym in mapper.sorted_symbols():
        lines.append(f"inline void {sym.cpp_identifier}(RecompContext& ctx) {{")
        lines.append(f"    // Stub for {sym.name} @ 0x{sym.address:08X} ({sym.section}, {sym.size} bytes)")
        lines.append(f"    ctx.pc = 0x{sym.address:016X}ULL;")
        lines.append("}")
        lines.append("")

    lines.append("inline std::unordered_map<uint64_t, RecompFunc> BuildDispatchTable() {")
    lines.append("    return {")
    for sym in mapper.sorted_symbols():
        lines.append(f"        {{ 0x{sym.address:016X}ULL, &{sym.cpp_identifier} }},")
    lines.append("    };")
    lines.append("}")
    lines.append("")
    lines.append("} // namespace static_recomp")
    lines.append("")

    header_path.write_text("\n".join(lines), encoding="utf-8")
    return header_path


def run_self_test() -> int:
    """Validate XEX2, Z64, and ELF64 parsers + C++ stub codegen + shader validation using synthetic headers."""
    print("[Self-Test] Running Static-Recomp-Native pipeline diagnostics...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # 1. Synthetic XEX2 header
        xex_bytes = b"XEX2" + struct.pack(">IIIII", 0x00000001, 0x100, 0, 0x80, 2)
        xex_bytes += struct.pack(">II", 0x00010201, 0x82000000)
        xex_bytes += struct.pack(">II", 0x00010100, 0x82001000)
        xex_bytes += b"\x00" * 0x200
        xex_file = tmp_dir / "sample_xbox360.xex"
        xex_file.write_bytes(xex_bytes)
        xex_meta = inspect_binary(xex_file)
        assert xex_meta.entry_point == 0x82001000
        print(f"  [OK] XEX2 parsed: arch={xex_meta.architecture}, entry=0x{xex_meta.entry_point:08X}")

        # 2. Synthetic N64 .z64 header
        z64_bytes = bytearray(0x2000)
        z64_bytes[0:4] = b"\x80\x37\x12\x40"
        struct.pack_into(">I", z64_bytes, 0x08, 0x80000400)
        struct.pack_into(">II", z64_bytes, 0x10, 0xCAFEBABE, 0x12345678)
        z64_bytes[0x20:0x34] = b"SYNTHETIC N64 DEMO  "
        z64_file = tmp_dir / "sample_n64.z64"
        z64_file.write_bytes(bytes(z64_bytes))
        z64_meta = inspect_binary(z64_file)
        assert z64_meta.entry_point == 0x80000400
        assert z64_meta.title == "SYNTHETIC N64 DEMO"
        print(f"  [OK] Z64  parsed: title='{z64_meta.title}', entry=0x{z64_meta.entry_point:08X}")

        # 3. Synthetic ELF64 header
        elf_bytes = bytearray(0x100)
        elf_bytes[0:4] = b"\x7fELF"
        elf_bytes[4] = 2  # ELF64
        elf_bytes[5] = 1  # little-endian
        struct.pack_into("<HHIQQQIHHHHHH", elf_bytes, 16, 2, 0x3E, 1, 0x00401000, 0, 0, 0, 64, 0, 0, 64, 0, 0)
        elf_file = tmp_dir / "sample_console.elf"
        elf_file.write_bytes(bytes(elf_bytes))
        elf_meta = inspect_binary(elf_file)
        assert elf_meta.entry_point == 0x00401000
        print(f"  [OK] ELF  parsed: arch={elf_meta.architecture}, entry=0x{elf_meta.entry_point:08X}")

        # 4. Generate C++ stubs into temp dir
        mapper = SymbolMapper()
        stub_hdr = generate_cpp_stubs(xex_meta, mapper, tmp_dir / "generated_code")
        assert stub_hdr.is_file()
        assert "BuildDispatchTable" in stub_hdr.read_text(encoding="utf-8")
        print(f"  [OK] C++20 stubs generated: {stub_hdr.name} ({len(mapper.symbols)} symbols)")

    # 5. Validate SPIR-V shader translation readiness
    shader_report = validate_shader_directory(REPO_ROOT / "shaders")
    if not shader_report["ready"]:
        print(f"  [FAIL] Shader validation errors: {shader_report['errors']}")
        return 1
    print(f"  [OK] Shaders validated: {shader_report['shader_count']} GLSL 450 files ready for SPIR-V")
    print("[Self-Test] All Static-Recomp-Native checks PASSED.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Static-Recomp-Native Binary Analysis & C++20 Stub Generator")
    parser.add_argument("--input", type=Path, help="Path to legally owned console binary (.xex, .z64, .elf)")
    parser.add_argument("--symbols", type=Path, help="Optional JSON symbol map to import")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "generated_code", help="Output directory for C++20 stubs")
    parser.add_argument("--validate-shaders", action="store_true", help="Validate shaders/ for SPIR-V translation readiness")
    parser.add_argument("--self-test", action="store_true", help="Run built-in synthetic header & pipeline self-test")
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not args.input:
        parser.print_help()
        return 1

    meta = inspect_binary(args.input)
    mapper = SymbolMapper()
    if args.symbols and args.symbols.is_file():
        mapper.load_map_json(args.symbols)

    stub_path = generate_cpp_stubs(meta, mapper, args.out)
    report_path = args.out / "binary_report.json"
    report_path.write_text(
        json.dumps(
            {
                **asdict(meta),
                "entry_point_hex": f"0x{meta.entry_point:08X}",
                "sections": [
                    {**asdict(s), "virtual_address_hex": f"0x{s.virtual_address:08X}"} for s in meta.sections
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[Recomp] Analyzed {meta.source_file} ({meta.format_name} | {meta.architecture})")
    print(f"[Recomp] Entry Point: 0x{meta.entry_point:08X} | Sections: {len(meta.sections)}")
    print(f"[Recomp] Generated C++20 stubs: {stub_path}")
    print(f"[Recomp] Wrote binary report:   {report_path}")

    if args.validate_shaders:
        shader_report = validate_shader_directory(REPO_ROOT / "shaders")
        print(f"[Shaders] Ready={shader_report['ready']} | Files={shader_report['shader_count']}")
        if not shader_report["ready"]:
            for err in shader_report["errors"]:
                print(f"  ERROR: {err}")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
