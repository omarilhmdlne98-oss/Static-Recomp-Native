#pragma once

#include <array>
#include <cstdint>
#include <string>

namespace static_recomp {

struct RuntimeConfig {
    std::string windowTitle = "Static-Recomp-Native (Win64 / Vulkan RHI)";
    uint32_t width = 1280;
    uint32_t height = 720;
    uint32_t targetFps = 120;
    uint32_t vramBudgetMB = 2048; // Low-VRAM 2GB GPU friendly default
    uint32_t stagingPoolMB = 64;  // Capped staging buffer for 2GB GPUs
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

struct AudioBridge {
    uint32_t sampleRate = 48000;
    uint32_t channels = 2;
    bool initialized = false;

    bool Initialize();
    void SubmitPcmFrame(const int16_t* samples, uint32_t frameCount);
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

    bool Initialize(const RuntimeConfig& config, void* nativeWindowHandle);
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
    void BeginFrame();
    void EndFrame();
    void Shutdown();

    const InputState& GetInputState() const { return input_; }
    const VulkanRHI& GetVulkanRHI() const { return rhi_; }
    const RuntimeConfig& GetConfig() const { return config_; }
    uint64_t GetFrameIndex() const { return frameIndex_; }
    double GetLastFrameMs() const { return lastFrameMs_; }

private:
    bool InitWindow();
    void DestroyWindow();
    void PollXInput();

    RuntimeConfig config_{};
    InputState input_{};
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
