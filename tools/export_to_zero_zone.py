#!/usr/bin/env python3
"""
Cross-Repository Exporter: Static-Recomp-Native -> Zero-Zone-Web & Zero-Zone-UE5.
Exports validated PBR battlefield shaders, tactical structures, and weapon inspection specs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from shaders.spirv_translator import validate_shader_directory  # noqa: E402
from shaders.xenos_microcode_translator import get_battlefield_presets, get_tactical_structures  # noqa: E402


def export_web_pbr_module(web_client_src: Path) -> Path:
    presets = {p.id: p.__dict__ for p in get_battlefield_presets()}
    structures = [s.__dict__ for s in get_tactical_structures()]
    js_path = web_client_src / "pbr_shaders.js"
    code = f"""// Auto-exported from Static-Recomp-Native (Leonida / XenonRecomp PBR Shader Bridge)
import * as THREE from 'three';

export const BATTLEFIELD_PBR_PRESETS = {json.dumps(presets, indent=2)};

export const TACTICAL_STRUCTURE_SPECS = {json.dumps(structures, indent=2)};

/**
 * Enhances a Three.js MeshStandardMaterial with Fresnel tactical rim lighting
 * and micro-contrast tuned for 2GB VRAM GPUs (mirrors battlefield_pbr_frag.glsl).
 */
export function applyBattlefieldPBRShader(material, presetId = 'brushed_steel') {{
  const preset = BATTLEFIELD_PBR_PRESETS[presetId] || BATTLEFIELD_PBR_PRESETS.brushed_steel;
  material.roughness = preset.roughness;
  material.metalness = preset.metallic;
  material.userData.pbrPreset = preset.id;

  const rimColor = new THREE.Color(preset.emissive_hex !== '#000000' ? preset.emissive_hex : '#38bdf8');
  const rimStrength = preset.rim_strength;

  material.onBeforeCompile = (shader) => {{
    shader.uniforms.uRimColor = {{ value: rimColor }};
    shader.uniforms.uRimStrength = {{ value: rimStrength }};
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
         uniform vec3 uRimColor;
         uniform float uRimStrength;`
      )
      .replace(
        '#include <dithering_fragment>',
        `float zzFresnel = pow(1.0 - clamp(dot(normalize(vNormal), normalize(vViewPosition)), 0.0, 1.0), 3.2);
         gl_FragColor.rgb += uRimColor * zzFresnel * uRimStrength * 0.42;
         #include <dithering_fragment>`
      );
  }};
  material.needsUpdate = true;
  return material;
}}
"""
    js_path.write_text(code, encoding="utf-8")
    return js_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export PBR shaders & tactical structures to Zero-Zone-Web")
    parser.add_argument(
        "--web-src",
        type=Path,
        default=REPO_ROOT.parent / "Zero-Zone-Web" / "client" / "src",
        help="Target Zero-Zone-Web/client/src directory",
    )
    args = parser.parse_args()

    report = validate_shader_directory(REPO_ROOT / "shaders")
    if not report["ready"]:
        print(f"[Exporter] Shader validation failed: {report['errors']}")
        return 1

    out_js = export_web_pbr_module(args.web_src)
    print(f"[Exporter] Exported PBR Battlefield Shader Module -> {out_js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
