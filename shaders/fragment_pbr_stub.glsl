#version 450
// Vulkan SPIR-V fragment shader stub with lightweight PBR lighting for 2GB VRAM GPUs

layout(location = 0) in vec3 fragNormal;
layout(location = 1) in vec2 fragUV;
layout(location = 2) in vec3 fragWorldPos;

layout(set = 0, binding = 1) uniform sampler2D albedoSampler;

layout(push_constant) uniform MaterialPush {
    vec4 sunDirIntensity;
    float roughness;
    float metallic;
} matPush;

layout(location = 0) out vec4 outColor;

void main() {
    vec3 N = normalize(fragNormal);
    vec3 L = normalize(matPush.sunDirIntensity.xyz);
    float ndotl = max(dot(N, L), 0.0);
    vec3 albedo = texture(albedoSampler, fragUV).rgb;
    vec3 ambient = albedo * 0.22;
    vec3 diffuse = albedo * ndotl * matPush.sunDirIntensity.w * (1.0 - matPush.metallic * 0.5);
    outColor = vec4(ambient + diffuse, 1.0);
}
