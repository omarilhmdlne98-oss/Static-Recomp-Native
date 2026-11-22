#include "NativeRuntime.h"
#include "RecompStubs.h"

#include <array>
#include <cstdlib>
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    static_recomp::RuntimeConfig config;
    uint64_t maxFrames = 0; // 0 = run until window closed

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--headless") {
            config.headless = true;
        } else if (arg == "--frames" && i + 1 < argc) {
            maxFrames = static_cast<uint64_t>(std::strtoull(argv[++i], nullptr, 10));
        } else if (arg == "--vram-mb" && i + 1 < argc) {
            config.vramBudgetMB = static_cast<uint32_t>(std::strtoul(argv[++i], nullptr, 10));
        } else if (arg == "--fps" && i + 1 < argc) {
            config.targetFps = static_cast<uint32_t>(std::strtoul(argv[++i], nullptr, 10));
        }
    }

    static_recomp::NativeRuntime runtime;
    if (!runtime.Initialize(config)) {
        std::cerr << "[Main] Runtime initialization failed.\n";
        return 1;
    }

    // Bind memory-mapped guest execution context and verify big-endian read/write
    auto& mem = runtime.GetMemoryContext();
    mem.WriteBE32(0x80000100ULL, 0xCAFEBABEu);
    const uint32_t readBack = mem.ReadBE32(0x80000100ULL);
    if (readBack != 0xCAFEBABEu) {
        std::cerr << "[Main] MemoryMappedContext endianness self-check failed.\n";
        return 1;
    }

    auto dispatch = static_recomp::BuildDispatchTable();
    static_recomp::RecompContext ctx{};
    ctx.rdram = mem.GuestToHost(0x80000000ULL);
    if (auto it = dispatch.find(static_recomp::kEntryPoint); it != dispatch.end() && it->second) {
        it->second(ctx);
        std::cout << "[Recomp] Executed entry stub @ 0x" << std::hex << ctx.pc << std::dec
                  << " (dispatch table entries: " << dispatch.size() << ")\n";
    }

    std::array<int16_t, 64> silencePcm{};
    while (runtime.PumpEvents()) {
        runtime.PollInput();
        const auto pad = runtime.TranslateToVirtualPad();
        (void)pad;
        runtime.BeginFrame();
        runtime.GetAudioBridge().SubmitPcmFrame(silencePcm.data(), 32);
        runtime.EndFrame();

        if (maxFrames > 0 && runtime.GetFrameIndex() >= maxFrames) {
            break;
        }
    }

    std::cout << "[Main] Clean shutdown after " << runtime.GetFrameIndex()
              << " frames (audio mixed frames: " << runtime.GetAudioBridge().mixedFrames << ").\n";
    runtime.Shutdown();
    return 0;
}
