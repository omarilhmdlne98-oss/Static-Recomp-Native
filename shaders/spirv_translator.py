#!/usr/bin/env python3
"""SPIR-V Shader Translation Readiness Validator & Stub Compiler."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List


def validate_shader_directory(shader_dir: Path) -> Dict[str, object]:
    glsl_files = sorted(shader_dir.glob("*.glsl"))
    errors: List[str] = []

    if not glsl_files:
        errors.append(f"No .glsl shader files found in {shader_dir}")

    for f in glsl_files:
        text = f.read_text(encoding="utf-8")
        if "#version 450" not in text:
            errors.append(f"{f.name}: missing '#version 450' directive required for Vulkan SPIR-V")
        if "void main()" not in text:
            errors.append(f"{f.name}: missing 'void main()' entry point")
        if text.count("{") != text.count("}"):
            errors.append(f"{f.name}: unbalanced curly braces")
        # Ensure explicit layout(location=...) or layout(set=..., binding=...)
        if not re.search(r"layout\s*\(", text):
            errors.append(f"{f.name}: missing explicit Vulkan layout(...) qualifiers")

    compiler = shutil.which("glslc") or shutil.which("glslangValidator")
    return {
        "ready": len(errors) == 0,
        "shader_count": len(glsl_files),
        "files": [f.name for f in glsl_files],
        "spirv_compiler": compiler or "stub-validator-only",
        "errors": errors,
    }


def compile_to_spirv(shader_dir: Path, out_dir: Path) -> int:
    report = validate_shader_directory(shader_dir)
    if not report["ready"]:
        for err in report["errors"]:
            print(f"[Shader Error] {err}")
        return 1

    compiler = shutil.which("glslc")
    out_dir.mkdir(parents=True, exist_ok=True)
    if not compiler:
        print("[SPIR-V] glslc not found on PATH — structural GLSL 450 validation passed.")
        return 0

    for glsl in sorted(shader_dir.glob("*.glsl")):
        stage = "vert" if "vertex" in glsl.stem else "frag"
        out_spv = out_dir / f"{glsl.stem}.spv"
        subprocess.run([compiler, f"-fshader-stage={stage}", str(glsl), "-o", str(out_spv)], check=True)
        print(f"[SPIR-V] Compiled {glsl.name} -> {out_spv.name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and compile GLSL 450 shaders to Vulkan SPIR-V")
    parser.add_argument("--dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "compiled")
    args = parser.parse_args()

    if args.validate:
        rep = validate_shader_directory(args.dir)
        print(f"[SPIR-V Validator] Ready={rep['ready']} | Shaders={rep['shader_count']} | Compiler={rep['spirv_compiler']}")
        if not rep["ready"]:
            for err in rep["errors"]:
                print(f"  ERROR: {err}")
            return 1
        return 0

    return compile_to_spirv(args.dir, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
