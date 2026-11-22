#!/usr/bin/env python3
"""
Step 1 Upper Combat Network Exporter (Static-Recomp-Native -> Zero-Zone-Web & Zero-Zone-UE5).

Adapts open-source 3D FPS verticality & physics patterns:
- dimforge/rapier.js: Rotated fixed cuboid colliders for smooth ~21-deg inclined ramps
- realskyrin/fps3ademo-saltline & Footprintarts/ThreeJS_FPS_2.0: Modular procedural steel catwalk/bridge deck layout
- mrdoob/three.js: InstancedMesh guardrail stanchion batching (2GB VRAM & minimal draw-call budget)
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List

UPPER_DECK_Y = 4.2
TOWER_COORD = 19.5
RAMP_HORIZ_LEN = 10.6
RAMP_SLOPE_LEN = math.hypot(RAMP_HORIZ_LEN, UPPER_DECK_Y)
RAMP_PITCH_RAD = math.atan2(UPPER_DECK_Y, RAMP_HORIZ_LEN)  # ~0.377 rad (~21.6 deg)


@dataclass
class NetworkSegment:
    id: str
    kind: str  # tower | catwalk | cross_bridge | vault_overpass | ramp
    x: float
    y: float
    z: float
    width: float
    height: float
    depth: float
    rx: float = 0.0
    rz: float = 0.0
    guardrail_sides: str = ""  # comma-separated: n,s,e,w


def build_upper_combat_network() -> dict:
    segments: List[NetworkSegment] = []

    # 1. Four Corner Overwatch Guard Towers aligned to UPPER_DECK_Y (4.2m)
    for tx, tz, tag in [
        (-TOWER_COORD, -TOWER_COORD, "nw"),
        (TOWER_COORD, -TOWER_COORD, "ne"),
        (-TOWER_COORD, TOWER_COORD, "sw"),
        (TOWER_COORD, TOWER_COORD, "se"),
    ]:
        segments.append(
            NetworkSegment(
                id=f"overwatch_tower_{tag}",
                kind="tower",
                x=tx,
                y=UPPER_DECK_Y,
                z=tz,
                width=4.0,
                height=0.32,
                depth=4.0,
                guardrail_sides="outer",
            )
        )

    # 2. Four Perimeter Steel Catwalks linking all 4 Overwatch Guard Towers (360-deg loop)
    span = (TOWER_COORD - 2.0) * 2.0  # 35.0m clear span between corner tower decks
    segments.extend(
        [
            NetworkSegment("catwalk_north", "catwalk", 0.0, UPPER_DECK_Y, -TOWER_COORD, span, 0.28, 3.2, guardrail_sides="s"),
            NetworkSegment("catwalk_south", "catwalk", 0.0, UPPER_DECK_Y, TOWER_COORD, span, 0.28, 3.2, guardrail_sides="n"),
            NetworkSegment("catwalk_west", "catwalk", -TOWER_COORD, UPPER_DECK_Y, 0.0, 3.2, 0.28, span, guardrail_sides="e"),
            NetworkSegment("catwalk_east", "catwalk", TOWER_COORD, UPPER_DECK_Y, 0.0, 3.2, 0.28, span, guardrail_sides="w"),
        ]
    )

    # 3. Vault Overpass Ring surrounding the central armored Vault (y = 4.2m)
    # Vault core is 4.2x4.2m centered at (0,0); overpass ring spans +/-4.6m around it
    segments.extend(
        [
            NetworkSegment("vault_overpass_n", "vault_overpass", 0.0, UPPER_DECK_Y, -3.5, 9.2, 0.28, 2.6, guardrail_sides=""),
            NetworkSegment("vault_overpass_s", "vault_overpass", 0.0, UPPER_DECK_Y, 3.5, 9.2, 0.28, 2.6, guardrail_sides=""),
            NetworkSegment("vault_overpass_w", "vault_overpass", -3.5, UPPER_DECK_Y, 0.0, 2.6, 0.28, 4.4, guardrail_sides=""),
            NetworkSegment("vault_overpass_e", "vault_overpass", 3.5, UPPER_DECK_Y, 0.0, 2.6, 0.28, 4.4, guardrail_sides=""),
        ]
    )

    # 4. Two Central Cross-Bridges (North-South & East-West) linking Perimeter Catwalks -> Vault Overpass
    # Clear span from 4.8 (vault overpass edge) to 17.9 (catwalk inner edge) = 13.1m, mid = 11.35m
    segments.extend(
        [
            NetworkSegment("cross_bridge_n", "cross_bridge", 0.0, UPPER_DECK_Y, -11.35, 3.0, 0.26, 13.1, guardrail_sides="e,w"),
            NetworkSegment("cross_bridge_s", "cross_bridge", 0.0, UPPER_DECK_Y, 11.35, 3.0, 0.26, 13.1, guardrail_sides="e,w"),
            NetworkSegment("cross_bridge_w", "cross_bridge", -11.35, UPPER_DECK_Y, 0.0, 13.1, 0.26, 3.0, guardrail_sides="n,s"),
            NetworkSegment("cross_bridge_e", "cross_bridge", 11.35, UPPER_DECK_Y, 0.0, 13.1, 0.26, 3.0, guardrail_sides="n,s"),
        ]
    )

    # 5. Four Smooth Inclined Access Ramps (NW, NE, SW, SE) running from ground (y=0) up to North/South catwalks (y=4.2)
    # Placed at x = +/-11.8, sloping along Z from z = +/-7.3 (ground) to z = +/-17.9 (catwalk inner edge)
    ramps = [
        ("access_ramp_nw", -11.8, -12.6, +RAMP_PITCH_RAD, -7.3, -17.9),
        ("access_ramp_ne", 11.8, -12.6, +RAMP_PITCH_RAD, -7.3, -17.9),
        ("access_ramp_sw", -11.8, 12.6, -RAMP_PITCH_RAD, 7.3, 17.9),
        ("access_ramp_se", 11.8, 12.6, -RAMP_PITCH_RAD, 7.3, 17.9),
    ]
    ramp_navs = []
    for rid, rx_pos, rz_mid, pitch_x, z_bot, z_top in ramps:
        segments.append(
            NetworkSegment(
                id=rid,
                kind="ramp",
                x=rx_pos,
                y=UPPER_DECK_Y * 0.5,
                z=rz_mid,
                width=2.8,
                height=0.24,
                depth=RAMP_SLOPE_LEN,
                rx=pitch_x,
                rz=0.0,
                guardrail_sides="e,w",
            )
        )
        ramp_navs.append(
            {
                "id": rid,
                "x": rx_pos,
                "halfWidth": 1.45,
                "zBottom": z_bot,
                "zTop": z_top,
                "topY": UPPER_DECK_Y,
            }
        )

    upper_waypoints = [
        {"x": -19.5, "y": UPPER_DECK_Y, "z": -19.5},
        {"x": 0.0, "y": UPPER_DECK_Y, "z": -19.5},
        {"x": 19.5, "y": UPPER_DECK_Y, "z": -19.5},
        {"x": 19.5, "y": UPPER_DECK_Y, "z": 0.0},
        {"x": 19.5, "y": UPPER_DECK_Y, "z": 19.5},
        {"x": 0.0, "y": UPPER_DECK_Y, "z": 19.5},
        {"x": -19.5, "y": UPPER_DECK_Y, "z": 19.5},
        {"x": -19.5, "y": UPPER_DECK_Y, "z": 0.0},
        {"x": 0.0, "y": UPPER_DECK_Y, "z": -11.35},
        {"x": 0.0, "y": UPPER_DECK_Y, "z": 11.35},
        {"x": -11.35, "y": UPPER_DECK_Y, "z": 0.0},
        {"x": 11.35, "y": UPPER_DECK_Y, "z": 0.0},
        {"x": 0.0, "y": UPPER_DECK_Y, "z": -3.5},
        {"x": 0.0, "y": UPPER_DECK_Y, "z": 3.5},
    ]

    return {
        "sources": [
            "dimforge/rapier.js (rotated cuboid sloped ramp physics)",
            "realskyrin/fps3ademo-saltline (modular procedural FPS industrial catwalk architecture)",
            "Footprintarts/ThreeJS_FPS_2.0 (vertical arena sightlines & traversal)",
            "mrdoob/three.js (InstancedMesh low-VRAM guardrail & truss batching)",
        ],
        "upper_deck_y": UPPER_DECK_Y,
        "ramp_pitch_rad": round(RAMP_PITCH_RAD, 5),
        "ramp_pitch_deg": round(math.degrees(RAMP_PITCH_RAD), 2),
        "segments": [asdict(s) for s in segments],
        "ramp_navs": ramp_navs,
        "upper_waypoints": upper_waypoints,
    }


def export_web_bridge_module(web_src: Path, data: dict) -> Path:
    out_path = web_src / "bridge_network.js"
    code = f"""// Auto-exported from Static-Recomp-Native/tools/bridge_network_exporter.py
// Open-source patterns: dimforge/rapier.js sloped ramps, fps3ademo-saltline & ThreeJS_FPS_2.0 vertical catwalks, Three.js InstancedMesh batching

export const UPPER_COMBAT_NETWORK = {json.dumps(data, indent=2)};

/**
 * Computes exact walkable floor height at (x, z) for AI navigation across ground, ramps, catwalks, and cross-bridges.
 */
export function sampleCombatSurfaceY(x, z, currentY = 0) {{
  const topY = UPPER_COMBAT_NETWORK.upper_deck_y;

  // Check 4 inclined access ramps first
  for (const r of UPPER_COMBAT_NETWORK.ramp_navs) {{
    if (Math.abs(x - r.x) <= r.halfWidth) {{
      const minZ = Math.min(r.zBottom, r.zTop);
      const maxZ = Math.max(r.zBottom, r.zTop);
      if (z >= minZ && z <= maxZ) {{
        const t = (z - r.zBottom) / (r.zTop - r.zBottom);
        return Math.max(0, Math.min(r.topY, t * r.topY));
      }}
    }}
  }}

  // If already elevated (above 1.8m), snap to upper deck when on catwalks/towers/cross-bridges/vault overpass
  if (currentY >= 1.8) {{
    const onPerim = Math.abs(x) >= 17.4 || Math.abs(z) >= 17.4;
    const onCrossNS = Math.abs(x) <= 1.75 && Math.abs(z) <= 21.0;
    const onCrossEW = Math.abs(z) <= 1.75 && Math.abs(x) <= 21.0;
    const onVaultRing = Math.abs(x) <= 4.7 && Math.abs(z) <= 4.7 && (Math.abs(x) >= 2.0 || Math.abs(z) >= 2.0);
    if (onPerim || onCrossNS || onCrossEW || onVaultRing) {{
      return topY;
    }}
  }}

  return 0;
}}
"""
    out_path.write_text(code, encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Step 1 Upper Combat Network (Catwalks, Cross-Bridges, Ramps)")
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--json-out", type=Path, default=repo_root / "assets" / "upper_combat_network.json")
    parser.add_argument("--web-src", type=Path, default=repo_root.parent / "Zero-Zone-Web" / "client" / "src")
    args = parser.parse_args()

    data = build_upper_combat_network()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    js_path = export_web_bridge_module(args.web_src, data)
    print(
        f"[BridgeExporter] Exported {len(data['segments'])} upper combat segments "
        f"(4 towers, 4 perimeter catwalks, 2 cross-bridges, Vault overpass, 4 smooth {data['ramp_pitch_deg']}° ramps)"
    )
    print(f"[BridgeExporter] JSON -> {args.json_out}")
    print(f"[BridgeExporter] Web  -> {js_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
