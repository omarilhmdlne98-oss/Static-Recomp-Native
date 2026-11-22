#pragma once
// Default baseline stub — overwritten when running tools/recomp_pipeline.py on a target binary.

#include <cstdint>
#include <unordered_map>

namespace static_recomp {

struct RecompContext {
    uint64_t gpr[32]{};
    double fpr[32]{};
    uint64_t pc = 0;
    uint64_t lr = 0;
    uint8_t* rdram = nullptr;
};

using RecompFunc = void (*)(RecompContext&);

inline constexpr uint64_t kEntryPoint = 0x0000000082000000ULL;

inline void recomp_entry_stub_82000000(RecompContext& ctx) {
    ctx.pc = kEntryPoint;
}

inline std::unordered_map<uint64_t, RecompFunc> BuildDispatchTable() {
    return {
        { kEntryPoint, &recomp_entry_stub_82000000 },
    };
}

} // namespace static_recomp
