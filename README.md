# Static-Recomp-Native

A modular **C++20 / Python** Static Recompilation pipeline inspired by **Leonida**, **XenonRecomp**, and **N64Recomp**, designed to analyze console executables (`.xex`, `.z64`, `.elf`) and compile them into native **Windows x86-64 (`.exe`)** binaries powered by **Vulkan / SPIR-V** and tuned for **2GB VRAM** GPUs.

## End-to-End Pipeline

```
Console Binary / Archive (.rpf / .xex / .z64 / .elf)
  ├──► tools/recomp_pipeline.py     (Header & Section Parser → generated_code/ C++20 Stubs)
  ├──► tools/archive_unpacker.py    (RPF7/8, XEX2, Z64 Unpacker → meshes/textures/ui/audio)
  ├──► shaders/spirv_translator.py  (DXBC/DXIL/RDNA2/GLSL 450 → Vulkan SPIR-V 1.3 .spv)
  ├──► assets/asset_inspector.py    (Texture/Mesh Inspection & 2GB VRAM Budget Audit)
  └──► runtime/NativeRuntime.*      (Memory-Mapped Context, Win32, XInput/KBM, PCM Audio, Vulkan RHI)
             │
             ▼
    CMake + MSVC (GitHub Actions: windows-latest)
             │
             ▼
    StaticRecompNative.exe (Native Win64 x86-64)
```

## Quick Start

### 1. Analyze a Legally Owned Binary & Generate C++ Stubs
```bash
python3 tools/recomp_pipeline.py --input path/to/your_game.xex --out generated_code --validate-shaders
```
Supported formats:
- **Xbox 360 (`.xex`)** — `XEX2` header parser & PowerPC section table extractor
- **Nintendo 64 (`.z64` / `.v64` / `.n64`)** — ROM header, CRC, entry point, and MIPS segment extractor
- **ELF32 / ELF64 (`.elf`)** — Architecture, endianness, entry point, and section header table extractor

To run the built-in synthetic self-test (no game binary needed):
```bash
python3 tools/recomp_pipeline.py --self-test
```

### 2. Inspect Extracted Assets Against the 2GB VRAM Budget
```bash
python3 assets/asset_inspector.py --manifest assets/manifest.example.json --vram-mb 2048
```

### 3. Preview Assets & Shaders in Browser
Open `viewer/index.html` (or serve `viewer/` locally) to inspect PBR shaders, wireframe topology, and lighting presets in Three.js.

### 4. Cloud Build (Zero Local Heavy Compilation)
Every push to `main` triggers `.github/workflows/native-win64-build.yml` on `windows-latest`, which:
1. Validates all Python recompilation & shader tools.
2. Compiles `StaticRecompNative.exe` using **CMake + MSVC (x64 Release)**.
3. Runs a headless smoke test (`StaticRecompNative.exe --headless --frames 10`).
4. Uploads the native Windows `.exe` as a downloadable GitHub Actions artifact.

## Legal Notice
This repository contains **no copyrighted game binaries, ROMs, keys, or proprietary assets**. You must supply your own legally obtained game dumps to use with the recompilation pipeline.
