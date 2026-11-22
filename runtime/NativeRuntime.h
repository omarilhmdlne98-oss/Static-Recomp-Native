#pragma once

#include <array>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace static_recomp {

struct RuntimeConfig {
    std::string windowTitle = "Static-Recomp-Native (Win64 / Vulkan RHI)";
    uint32_t width = 1280;
    uint32_t height = 720;
    uint32_t targetFps = 120;
    uint32_t vramBudgetMB = 2048; // Low-VRAM 2GB GPU friendly default
    uint32_t stagingPoolMB = 64;  // Capped staging buffer for 2GB GPUs
    uint32_t guestRamMB = 64;     // Guest memory-mapped execution heap
    bool headless = false;
    bool enableValidation = false;
};

struct InputState {
    std::array<bool, 256> keys{};
    float mouseDeltaX = 0.0f;
    float mouseDeltaY = 0.0f;
    bool mouseLeft = false;
    bool mouseRight = false;

    // XInput Gamepad (Controller 0)
    bool gamepadConnected = false;
    float leftStickX = 0.0f;
    float leftStickY = 0.0f;
    float rightStickX = 0.0f;
    float rightStickY = 0.0f;
    float leftTrigger = 0.0f;
    float rightTrigger = 0.0f;
    uint16_t gamepadButtons = 0;
};

// Unified console controller abstraction combining XInput + Native KBM
struct VirtualPadState {
    float moveX = 0.0f;
    float moveY = 0.0f;
    float lookX = 0.0f;
    float lookY = 0.0f;
    float triggerL = 0.0f;
    float triggerR = 0.0f;
    uint32_t buttonsMask = 0; // bit0=A/Jump, bit1=B/Crouch, bit2=X/Reload, bit3=Y/Switch, bit4=L3/Sprint
};

// Leonida / XenonRecomp-inspired virtual memory page directory & guest RAM
struct MemoryMappedContext {
    uint64_t guestBaseAddress = 0x80000000ULL;
    uint32_t pageSize = 4096;
    std::vector<uint8_t> guestRam;
    std::unordered_map<uint64_t, uint64_t> pageDirectory; // guestPage -> hostOffset

    bool Initialize(uint64_t baseAddr, uint32_t sizeMB);
    uint8_t* GuestToHost(uint64_t guestAddr);
    const uint8_t* GuestToHost(uint64_t guestAddr) const;
    uint32_t ReadBE32(uint64_t guestAddr) const;
    void WriteBE32(uint64_t guestAddr, uint32_t value);
    uint32_t ReadLE32(uint64_t guestAddr) const;
    void WriteLE32(uint64_t guestAddr, uint32_t value);
    void Shutdown();
};

struct VramBudgetManager {
    uint64_t budgetBytes = 2048ULL * 1024ULL * 1024ULL;
    uint64_t stagingCapBytes = 64ULL * 1024ULL * 1024ULL;
    uint64_t allocatedTextureBytes = 0;
    uint64_t allocatedBufferBytes = 0;
    uint32_t maxTextureDimension = 1024; // Clamp 4K textures on 2GB GPUs

    void Configure(uint32_t vramBudgetMB, uint32_t stagingMB);
    bool TryAllocateTexture(uint64_t bytes);
    bool TryAllocateBuffer(uint64_t bytes);
    void ReleaseAll();
    uint64_t TotalAllocatedBytes() const;
    double UtilizationPercent() const;
};

struct SpirvModuleInfo {
    std::string name;
    uint32_t version = 0;
    uint32_t boundIds = 0;
    size_t byteSize = 0;
    bool valid = false;
};

struct VulkanPipelineState {
    std::string name;
    std::string vertexShader;
    std::string fragmentShader;
    uint32_t pushConstantBytes = 64;
    bool depthTestEnabled = true;
    bool alphaBlendEnabled = false;
    bool wireframe = false;
};

struct AudioBridge {
    uint32_t sampleRate = 48000;
    uint32_t channels = 2;
    float masterGain = 0.85f;
    bool initialized = false;
    uint64_t mixedFrames = 0;
    std::vector<int16_t> mixRingBuffer;

    bool Initialize(uint32_t ringFrames = 2048);
    void MixStereoVoice(const int16_t* samples, uint32_t frameCount, float gain = 1.0f);
    void SubmitPcmFrame(const int16_t* samples, uint32_t frameCount);
    void ClearMixBuffer();
    void Shutdown();
};

struct VulkanRHI {
    bool loaderAvailable = false;
    bool swapchainReady = false;
    std::string deviceName = "Software / Headless Fallback";
    uint32_t swapchainWidth = 0;
    uint32_t swapchainHeight = 0;
    uint32_t swapchainImageCount = 2; // Double-buffered to save VRAM
    VramBudgetManager vram;
    std::vector<SpirvModuleInfo> loadedShaders;
    std::vector<VulkanPipelineState> pipelineCache;

    bool Initialize(const RuntimeConfig& config, void* nativeWindowHandle);
    SpirvModuleInfo LoadSpirvModule(const std::string& name, const std::vector<uint8_t>& spirvBytes);
    bool RegisterPipelineState(const VulkanPipelineState& state);
    void BeginFrame();
    void EndFrame();
    void Shutdown();

private:
    void* vulkanModule_ = nullptr;
};

class NativeRuntime {
public:
    NativeRuntime() = default;
    ~NativeRuntime();

    NativeRuntime(const NativeRuntime&) = delete;
    NativeRuntime& operator=(const NativeRuntime&) = delete;

    bool Initialize(const RuntimeConfig& config);
    bool PumpEvents();
    void PollInput();
    VirtualPadState TranslateToVirtualPad() const;
    void BeginFrame();
    void EndFrame();
    void Shutdown();

    const InputState& GetInputState() const { return input_; }
    const VulkanRHI& GetVulkanRHI() const { return rhi_; }
    VulkanRHI& GetVulkanRHIMutable() { return rhi_; }
    MemoryMappedContext& GetMemoryContext() { return memory_; }
    AudioBridge& GetAudioBridge() { return audio_; }
    const RuntimeConfig& GetConfig() const { return config_; }
    uint64_t GetFrameIndex() const { return frameIndex_; }
    double GetLastFrameMs() const { return lastFrameMs_; }

private:
    bool InitWindow();
    void DestroyWindow();
    void PollXInput();

    RuntimeConfig config_{};
    InputState input_{};
    MemoryMappedContext memory_{};
    VulkanRHI rhi_{};
    AudioBridge audio_{};

    void* nativeWindow_ = nullptr;
    void* xinputModule_ = nullptr;
    bool initialized_ = false;
    bool quitRequested_ = false;
    uint64_t frameIndex_ = 0;
    double lastFrameMs_ = 0.0;
};

} // namespace static_recomp
