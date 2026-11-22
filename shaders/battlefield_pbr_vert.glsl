#version 450
// Battlefield PBR Vertex Shader (Leonida / XenonRecomp SPIR-V Pipeline)

layout(location = 0) in vec3 inPosition;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in vec2 inUV;

layout(set = 0, binding = 0) uniform BattlefieldUBO {
    mat4 model;
    mat4 view;
    mat4 proj;
    vec4 cameraPos;
} ubo;

layout(location = 0) out vec3 outWorldPos;
layout(location = 1) out vec3 outNormal;
layout(location = 2) out vec2 outUV;
layout(location = 3) out vec3 outViewDir;

void main() {
    vec4 worldPos = ubo.model * vec4(inPosition, 1.0);
    outWorldPos = worldPos.xyz;
    outNormal = normalize(mat3(ubo.model) * inNormal);
    outUV = inUV;
    outViewDir = normalize(ubo.cameraPos.xyz - worldPos.xyz);
    gl_Position = ubo.proj * ubo.view * worldPos;
}
