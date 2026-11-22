#!/usr/bin/env python3
"""
XenonRecomp / Leonida-inspired Shader Microcode & PBR Asset Translator.

Translates console ALU/TEX shader IR definitions into:
1. Vulkan GLSL 450 / SPIR-V ready shader metadata
2. Three.js WebGL2 PBR battlefield shader presets
3. Unreal Engine 5.4 C++ battlefield PBR & tactical structure specs
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List


@dataclass
class PBRMaterialPreset:
    id: str
    name: str
    base_color_hex: str
    roughness: float
    metallic: float
    rim_strength: float
    ao_strength: float
    emissive_hex: str = "#000000"


@dataclass
class TacticalStructureSpec:
    id: str
    name: str
    category: str
    width_m: float
    height_m: float
    depth_m: float
    material_preset: str
    destructible: bool = False


def get_battlefield_presets() -> List[PBRMaterialPreset]:
    return [
        PBRMaterialPreset("weathered_concrete", "Weathered Tactical Concrete", "#6e7782", 0.86, 0.06, 0.14, 0.92),
        PBRMaterialPreset("brushed_steel", "Brushed Ballistic Steel", "#4c5868", 0.34, 0.84, 0.32, 0.85),
        PBRMaterialPreset("overwatch_alloy", "Overwatch Tower Alloy", "#364150", 0.38, 0.78, 0.38, 0.88, "#38bdf8"),
        PBRMaterialPreset("ballistic_bunker", "Reinforced Ballistic Bunker", "#586068", 0.76, 0.24, 0.18, 0.90),
        PBRMaterialPreset("vault_core", "Armored Vault Core", "#2b3544", 0.28, 0.88, 0.45, 0.82, "#2dd4bf"),
    ]


def get_tactical_structures() -> List[TacticalStructureSpec]:
    return [
        TacticalStructureSpec("overwatch_tower", "Armored Overwatch Guard Tower", "VerticalSightline", 3.6, 5.8, 3.6, "overwatch_alloy"),
        TacticalStructureSpec("ballistic_bunker", "Reinforced Ballistic Shield Bunker", "MidLaneCover", 4.6, 1.85, 2.2, "ballistic_bunker"),
        TacticalStructureSpec("steel_gantry", "Overhead Industrial Steel Gantry", "SkyBridge", 22.0, 0.45, 3.0, "brushed_steel"),
        TacticalStructureSpec("sniper_catwalk", "Elevated Sniper Perch Deck", "HighGround", 18.0, 3.1, 4.2, "brushed_steel"),
    ]


def translate_xenos_microcode_ir(ir_ops: List[str]) -> Dict[str, object]:
    """Translate simplified Xenon/RAGE shader IR opcodes into SPIR-V stage capabilities."""
    alu_count = sum(1 for op in ir_ops if op.startswith(("MUL", "ADD", "MAD", "DP3", "RSQ")))
    tex_count = sum(1 for op in ir_ops if op.startswith(("TFETCH", "SAMPLE")))
    return {
        "source_profile": "Xenos/RAGE_SM30_IR",
        "target_profile": "Vulkan_GLSL_450_SPIRV",
        "alu_instructions": alu_count,
        "tex_fetches": tex_count,
        "vram_2gb_safe": tex_count <= 8,
    }


def export_bundle(out_json: Path) -> Dict[str, object]:
    sample_ir = ["TFETCH2D r0, t0, s0", "DP3 r1.x, v1, c0", "MAD r2, r0, r1.x, c1", "MUL r3, r2, c2"]
    bundle = {
        "pipeline": "Static-Recomp-Native (Leonida + XenonRecomp Shader Bridge)",
        "translation_metrics": translate_xenos_microcode_ir(sample_ir),
        "pbr_presets": [asdict(p) for p in get_battlefield_presets()],
        "tactical_structures": [asdict(s) for s in get_tactical_structures()],
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Xenos/Leonida Shader Microcode & PBR Asset Translator")
    parser.add_argument("--export-json", type=Path, default=Path(__file__).resolve().parent / "pbr_export.json")
    args = parser.parse_args()
    bundle = export_bundle(args.export_json)
    print(
        f"[XenosTranslator] Exported {len(bundle['pbr_presets'])} PBR presets & "
        f"{len(bundle['tactical_structures'])} tactical structures -> {args.export_json}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
