#!/usr/bin/env python3
"""Extracted texture & mesh asset inspector with 2GB VRAM budget auditing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

FORMAT_BPP: Dict[str, float] = {
    "BC1": 0.5,
    "BC3": 1.0,
    "BC5": 1.0,
    "BC7": 1.0,
    "RGBA8": 4.0,
    "RGBA16F": 8.0,
}


def estimate_texture_bytes(width: int, height: int, fmt: str, mipmapped: bool = True) -> int:
    bpp = FORMAT_BPP.get(fmt.upper(), 4.0)
    base = width * height * bpp
    return int(base * (1.3333 if mipmapped else 1.0))


def inspect_manifest(manifest_path: Path, vram_budget_mb: int) -> int:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    textures = data.get("textures", [])
    meshes = data.get("meshes", [])

    tex_bytes = 0
    oversized = []
    for t in textures:
        w, h = int(t["width"]), int(t["height"])
        fmt = str(t.get("format", "BC7"))
        sz = estimate_texture_bytes(w, h, fmt, bool(t.get("mipmapped", True)))
        tex_bytes += sz
        if vram_budget_mb <= 2048 and max(w, h) > 1024:
            oversized.append(f"{t['name']} ({w}x{h} {fmt})")

    mesh_bytes = 0
    for m in meshes:
        verts = int(m.get("vertices", 0))
        tris = int(m.get("triangles", 0))
        mesh_bytes += verts * 32 + tris * 6

    total_mb = (tex_bytes + mesh_bytes) / (1024 * 1024)
    print(f"[Assets] Manifest: {manifest_path.name}")
    print(f"[Assets] Textures: {len(textures)} ({tex_bytes / (1024 * 1024):.2f} MB) | Meshes: {len(meshes)} ({mesh_bytes / (1024 * 1024):.2f} MB)")
    print(f"[Assets] Total Estimated VRAM: {total_mb:.2f} MB / {vram_budget_mb} MB budget")

    if oversized:
        print(f"[Assets] 2GB VRAM Hint: Clamp mip level 0 on {len(oversized)} texture(s): {', '.join(oversized)}")

    if total_mb > vram_budget_mb * 0.85:
        print("[Assets] WARNING: Asset set exceeds 85% of VRAM budget — enable mip streaming.")
        return 1

    print("[Assets] VRAM budget check PASSED.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect extracted console textures/meshes against VRAM budget")
    parser.add_argument("--manifest", type=Path, required=True, help="Path to extracted asset manifest JSON")
    parser.add_argument("--vram-mb", type=int, default=2048, help="Target GPU VRAM budget in MB (default: 2048)")
    args = parser.parse_args()
    return inspect_manifest(args.manifest, args.vram_mb)


if __name__ == "__main__":
    raise SystemExit(main())
