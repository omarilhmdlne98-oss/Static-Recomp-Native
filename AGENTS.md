# AGENTS.md — Static-Recomp-Native Agent Architecture

This document defines the engineering architecture, invariants, and workflow rules for AI coding agents operating in `omarilhmdlne98-oss/Static-Recomp-Native`.

## Pipeline Architecture

`Static-Recomp-Native` is a modular static recompilation framework inspired by **Leonida**, **XenonRecomp**, and **N64Recomp**:

```
[Legally Owned Console Binary (.xex / .z64 / .elf)]
        │
        ▼
1. Binary Disassembly & Header Analysis (`tools/recomp_pipeline.py`, `tools/symbol_mapper.py`)
   - Parses executable headers, endianness, entry points, and section tables
   - Maps symbols & jump tables to deterministic C++ identifiers
        │
        ▼
2. Static C++20 Code Generation (`generated_code/`)
   - Emits typed C++20 function stubs & register context structs (`RecompContext`)
   - Eliminates runtime JIT overhead via Ahead-Of-Time (AOT) compilation
        │
        ▼
3. SPIR-V Shader Translation (`shaders/spirv_translator.py`, `shaders/*.glsl`)
   - Translates console microcode / fixed-function state into GLSL 450 -> SPIR-V
   - Validates descriptor sets, push constants, and uniform alignment
        │
        ▼
4. Native Vulkan / D3D12 Runtime Bridge (`runtime/NativeRuntime.h`, `runtime/NativeRuntime.cpp`)
   - Win32 high-FPS windowing & frame pacing (`QueryPerformanceCounter`)
   - Dynamic XInput + Keyboard/Mouse input abstraction
   - Audio mixer bridge & Vulkan RHI with strict 2GB VRAM budget enforcement
        │
        ▼
5. Native Win64 x86-64 Executable (`StaticRecompNative.exe`)
   - Built automatically in GitHub Actions (`windows-latest` + CMake + MSVC)
```

## Repository Layout

| Directory | Responsibility |
| :--- | :--- |
| `tools/` | Binary header analyzers (`.xex`, `.z64`, `.elf`), section extractors, symbol mappers, and C++ stub generators |
| `shaders/` | SPIR-V shader translation stubs, GLSL 450 shaders, and validation scripts |
| `runtime/` | C++20 native runtime bridge (Win32 windowing, XInput/KBM, audio stub, Vulkan RHI + 2GB VRAM manager) |
| `generated_code/` | Auto-generated C++20 recompiled function stubs and dispatch tables |
| `assets/` | Extracted texture/model inspector and VRAM budget estimator |
| `viewer/` | Lightweight browser-based WebGL/Three.js asset & shader previewer |
| `.github/workflows/` | Automated `windows-latest` CMake + MSVC CI/CD pipeline producing `StaticRecompNative.exe` |

## Agent Rules & Invariants

1. **Clean-Room & Legal Compliance**: Never commit proprietary game binaries (`.xex`, `.z64`, `.elf`, `.iso`) or copyrighted assets. All tools operate on user-supplied, legally owned dumps at runtime.
2. **Low-VRAM First (2GB VRAM Target)**: Any Vulkan RHI or asset streaming change must respect the `2048 MB` VRAM budget (`VramBudgetManager` in `runtime/NativeRuntime.h`), capping staging buffers and clamping high-res mip levels when over budget.
3. **Zero-Friction CI Builds**: Runtime code must dynamically load optional platform DLLs (`vulkan-1.dll`, `xinput1_4.dll`) so `windows-latest` CI builds and headless smoke tests pass without external SDK installers.
4. **C++20 Portability**: Keep `runtime/` warning-clean under MSVC (`/W4`) and GCC/Clang (`-Wall -Wextra`) with `#ifdef _WIN32` guards around Win32 APIs.
5. **Validation Before Push**:
   - Run `python3 tools/recomp_pipeline.py --self-test`
   - Run `python3 shaders/spirv_translator.py --validate`
   - Run `python3 assets/asset_inspector.py --manifest assets/manifest.example.json`
   - Build & run CMake target locally (`--headless --frames 5`) before pushing.
