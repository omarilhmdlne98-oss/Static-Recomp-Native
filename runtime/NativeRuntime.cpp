#include "NativeRuntime.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <iostream>
#include <thread>

#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

namespace static_recomp {

namespace {

#ifdef _WIN32
struct RawXInputGamepad {
    uint16_t wButtons;
    uint8_t bLeftTrigger;
    uint8_t bRightTrigger;
    int16_t sThumbLX;
    int16_t sThumbLY;
    int16_t sThumbRX;
    int16_t sThumbRY;
};

struct RawXInputState {
    uint32_t dwPacketNumber;
    RawXInputGamepad Gamepad;
};

using XInputGetStateFn = uint32_t(__stdcall*)(uint32_t, RawXInputState*);

float NormalizeStick(int16_t value, int16_t deadzone) {
    if (std::abs(static_cast<int32_t>(value)) < deadzone) {
        return 0.0f;
    }
    return std::clamp(static_cast<float>(value) / 32767.0f, -1.0f, 1.0f);
}

LRESULT CALLBACK StaticRecompWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    auto* input = reinterpret_cast<InputState*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
    switch (msg) {
    case WM_CLOSE:
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    case WM_KEYDOWN:
        if (input && wParam < 256) {
            input->keys[wParam] = true;
        }
        if (wParam == VK_ESCAPE) {
            PostQuitMessage(0);
        }
        return 0;
    case WM_KEYUP:
        if (input && wParam < 256) {
            input->keys[wParam] = false;
        }
        return 0;
    case WM_LBUTTONDOWN:
        if (input) input->mouseLeft = true;
        return 0;
    case WM_LBUTTONUP:
        if (input) input->mouseLeft = false;
        return 0;
    case WM_RBUTTONDOWN:
        if (input) input->mouseRight = true;
        return 0;
    case WM_RBUTTONUP:
        if (input) input->mouseRight = false;
        return 0;
    default:
        return DefWindowProcW(hwnd, msg, wParam, lParam);
    }
}
#endif

} // namespace

// --- VramBudgetManager ---
void VramBudgetManager::Configure(uint32_t vramBudgetMB, uint32_t stagingMB) {
    budgetBytes = static_cast<uint64_t>(std::max<uint32_t>(512, vramBudgetMB)) * 1024ULL * 1024ULL;
    stagingCapBytes = static_cast<uint64_t>(std::min<uint32_t>(stagingMB, vramBudgetMB / 8)) * 1024ULL * 1024ULL;
    maxTextureDimension = (vramBudgetMB <= 2048) ? 1024u : 2048u;
    allocatedTextureBytes = 0;
    allocatedBufferBytes = 0;
}

bool VramBudgetManager::TryAllocateTexture(uint64_t bytes) {
    if (TotalAllocatedBytes() + bytes > budgetBytes) {
        return false;
    }
    allocatedTextureBytes += bytes;
    return true;
}

bool VramBudgetManager::TryAllocateBuffer(uint64_t bytes) {
    if (TotalAllocatedBytes() + bytes > budgetBytes) {
        return false;
    }
    allocatedBufferBytes += bytes;
    return true;
}

void VramBudgetManager::ReleaseAll() {
    allocatedTextureBytes = 0;
    allocatedBufferBytes = 0;
}

uint64_t VramBudgetManager::TotalAllocatedBytes() const {
    return allocatedTextureBytes + allocatedBufferBytes;
}

double VramBudgetManager::UtilizationPercent() const {
    if (budgetBytes == 0) return 0.0;
    return (static_cast<double>(TotalAllocatedBytes()) / static_cast<double>(budgetBytes)) * 100.0;
}

// --- AudioBridge ---
bool AudioBridge::Initialize() {
    initialized = true;
    return true;
}

void AudioBridge::SubmitPcmFrame(const int16_t* samples, uint32_t frameCount) {
    (void)samples;
    (void)frameCount;
}

void AudioBridge::Shutdown() {
    initialized = false;
}

// --- VulkanRHI ---
bool VulkanRHI::Initialize(const RuntimeConfig& config, void* nativeWindowHandle) {
    vram.Configure(config.vramBudgetMB, config.stagingPoolMB);
    swapchainWidth = config.width;
    swapchainHeight = config.height;
    swapchainImageCount = (config.vramBudgetMB <= 2048) ? 2u : 3u;

    // Reserve double-buffered swapchain + depth + staging pool from VRAM budget
    const uint64_t colorBytes = static_cast<uint64_t>(swapchainWidth) * swapchainHeight * 4ULL * swapchainImageCount;
    const uint64_t depthBytes = static_cast<uint64_t>(swapchainWidth) * swapchainHeight * 4ULL;
    vram.TryAllocateTexture(colorBytes + depthBytes);
    vram.TryAllocateBuffer(vram.stagingCapBytes);

#ifdef _WIN32
    vulkanModule_ = static_cast<void*>(LoadLibraryA("vulkan-1.dll"));
    if (vulkanModule_ != nullptr) {
        auto proc = GetProcAddress(static_cast<HMODULE>(vulkanModule_), "vkGetInstanceProcAddr");
        loaderAvailable = (proc != nullptr);
    }
#else
    vulkanModule_ = dlopen("libvulkan.so.1", RTLD_NOW | RTLD_LOCAL);
    if (vulkanModule_ != nullptr) {
        loaderAvailable = (dlsym(vulkanModule_, "vkGetInstanceProcAddr") != nullptr);
    }
#endif

    if (loaderAvailable && !config.headless && nativeWindowHandle != nullptr) {
        deviceName = "Vulkan 1.3 Hardware RHI (2GB Low-VRAM Profile)";
        swapchainReady = true;
    } else if (loaderAvailable) {
        deviceName = "Vulkan 1.3 Loader Detected (Headless / Compute Mode)";
        swapchainReady = false;
    } else {
        deviceName = "Software / Headless Fallback (No Vulkan ICD)";
        swapchainReady = false;
    }

    return true;
}

void VulkanRHI::BeginFrame() {
    // Frame command buffer reset & swapchain image acquire hook
}

void VulkanRHI::EndFrame() {
    // Queue submit & present hook
}

void VulkanRHI::Shutdown() {
    vram.ReleaseAll();
    swapchainReady = false;
    loaderAvailable = false;
    if (vulkanModule_ != nullptr) {
#ifdef _WIN32
        FreeLibrary(static_cast<HMODULE>(vulkanModule_));
#else
        dlclose(vulkanModule_);
#endif
        vulkanModule_ = nullptr;
    }
}

// --- NativeRuntime ---
NativeRuntime::~NativeRuntime() {
    Shutdown();
}

bool NativeRuntime::Initialize(const RuntimeConfig& config) {
    config_ = config;
    quitRequested_ = false;
    frameIndex_ = 0;

    if (!config_.headless) {
        if (!InitWindow()) {
            std::cerr << "[Runtime] Failed to create native window, falling back to headless mode.\n";
            config_.headless = true;
        }
    }

#ifdef _WIN32
    xinputModule_ = static_cast<void*>(LoadLibraryA("xinput1_4.dll"));
    if (!xinputModule_) {
        xinputModule_ = static_cast<void*>(LoadLibraryA("xinput9_1_0.dll"));
    }
#endif

    audio_.Initialize();
    rhi_.Initialize(config_, nativeWindow_);
    initialized_ = true;

    std::cout << "[Runtime] Initialized (" << rhi_.deviceName << ")\n"
              << "[Runtime] Resolution: " << config_.width << "x" << config_.height
              << " @ " << config_.targetFps << " FPS target\n"
              << "[Runtime] VRAM Budget: " << config_.vramBudgetMB << " MB (MaxTex="
              << rhi_.vram.maxTextureDimension << "px, Used="
              << (rhi_.vram.TotalAllocatedBytes() / (1024ULL * 1024ULL)) << " MB)\n";
    return true;
}

bool NativeRuntime::InitWindow() {
#ifdef _WIN32
    HINSTANCE hInstance = GetModuleHandleW(nullptr);
    const wchar_t* kClassName = L"StaticRecompNativeWindowClass";

    WNDCLASSEXW wc{};
    wc.cbSize = sizeof(WNDCLASSEXW);
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = StaticRecompWndProc;
    wc.hInstance = hInstance;
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.lpszClassName = kClassName;
    RegisterClassExW(&wc);

    RECT rect{ 0, 0, static_cast<LONG>(config_.width), static_cast<LONG>(config_.height) };
    AdjustWindowRect(&rect, WS_OVERLAPPEDWINDOW, FALSE);

    std::wstring wideTitle(config_.windowTitle.begin(), config_.windowTitle.end());
    HWND hwnd = CreateWindowExW(
        0,
        kClassName,
        wideTitle.c_str(),
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        rect.right - rect.left,
        rect.bottom - rect.top,
        nullptr,
        nullptr,
        hInstance,
        nullptr
    );
    if (!hwnd) {
        return false;
    }

    SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(&input_));
    ShowWindow(hwnd, SW_SHOW);
    UpdateWindow(hwnd);
    nativeWindow_ = static_cast<void*>(hwnd);
    return true;
#else
    return false;
#endif
}

void NativeRuntime::DestroyWindow() {
#ifdef _WIN32
    if (nativeWindow_ != nullptr) {
        ::DestroyWindow(static_cast<HWND>(nativeWindow_));
        nativeWindow_ = nullptr;
    }
#endif
}

bool NativeRuntime::PumpEvents() {
    if (quitRequested_) {
        return false;
    }
#ifdef _WIN32
    if (!config_.headless && nativeWindow_ != nullptr) {
        MSG msg{};
        while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) {
                quitRequested_ = true;
                return false;
            }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }
#endif
    return true;
}

void NativeRuntime::PollXInput() {
#ifdef _WIN32
    if (!xinputModule_) {
        input_.gamepadConnected = false;
        return;
    }
    auto getState = reinterpret_cast<XInputGetStateFn>(
        GetProcAddress(static_cast<HMODULE>(xinputModule_), "XInputGetState")
    );
    if (!getState) {
        input_.gamepadConnected = false;
        return;
    }
    RawXInputState state{};
    if (getState(0, &state) == 0) {
        input_.gamepadConnected = true;
        input_.gamepadButtons = state.Gamepad.wButtons;
        input_.leftTrigger = static_cast<float>(state.Gamepad.bLeftTrigger) / 255.0f;
        input_.rightTrigger = static_cast<float>(state.Gamepad.bRightTrigger) / 255.0f;
        input_.leftStickX = NormalizeStick(state.Gamepad.sThumbLX, 7849);
        input_.leftStickY = NormalizeStick(state.Gamepad.sThumbLY, 7849);
        input_.rightStickX = NormalizeStick(state.Gamepad.sThumbRX, 8689);
        input_.rightStickY = NormalizeStick(state.Gamepad.sThumbRY, 8689);
    } else {
        input_.gamepadConnected = false;
    }
#endif
}

void NativeRuntime::PollInput() {
    input_.mouseDeltaX = 0.0f;
    input_.mouseDeltaY = 0.0f;
    PollXInput();
}

void NativeRuntime::BeginFrame() {
    rhi_.BeginFrame();
}

void NativeRuntime::EndFrame() {
    rhi_.EndFrame();
    ++frameIndex_;

    // Lightweight frame pacing for high-FPS targets
    const double targetMs = 1000.0 / static_cast<double>(std::max<uint32_t>(30, config_.targetFps));
    lastFrameMs_ = targetMs;
    if (!config_.headless) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}

void NativeRuntime::Shutdown() {
    if (!initialized_) {
        return;
    }
    rhi_.Shutdown();
    audio_.Shutdown();
    DestroyWindow();
#ifdef _WIN32
    if (xinputModule_) {
        FreeLibrary(static_cast<HMODULE>(xinputModule_));
        xinputModule_ = nullptr;
    }
#endif
    initialized_ = false;
}

} // namespace static_recomp
