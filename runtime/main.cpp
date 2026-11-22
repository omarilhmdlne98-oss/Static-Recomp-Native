#include "NativeRuntime.h"
#include "RecompStubs.h"

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

    auto dispatch = static_recomp::BuildDispatchTable();
    static_recomp::RecompContext ctx{};
    if (auto it = dispatch.find(static_recomp::kEntryPoint); it != dispatch.end() && it->second) {
        it->second(ctx);
        std::cout << "[Recomp] Executed entry stub @ 0x" << std::hex << ctx.pc << std::dec
                  << " (dispatch table entries: " << dispatch.size() << ")\n";
    }

    while (runtime.PumpEvents()) {
        runtime.PollInput();
        runtime.BeginFrame();
        runtime.EndFrame();

        if (maxFrames > 0 && runtime.GetFrameIndex() >= maxFrames) {
            break;
        }
    }

    std::cout << "[Main] Clean shutdown after " << runtime.GetFrameIndex() << " frames.\n";
    runtime.Shutdown();
    return 0;
}
