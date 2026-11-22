#version 450
// Battlefield PBR Fragment Shader (GGX Microfacet + Fresnel Rim + Fog, 2GB VRAM optimized)

layout(location = 0) in vec3 inWorldPos;
layout(location = 1) in vec3 inNormal;
layout(location = 2) in vec2 inUV;
layout(location = 3) in vec3 inViewDir;

layout(set = 0, binding = 1) uniform sampler2D albedoMap;

layout(push_constant) uniform BattlefieldMaterialPush {
    vec4 sunDirIntensity;
    vec4 fogColorDensity;
    float roughness;
    float metallic;
    float rimStrength;
    float aoStrength;
} matPush;

layout(location = 0) out vec4 outColor;

void main() {
    vec3 N = normalize(inNormal);
    vec3 V = normalize(inViewDir);
    vec3 L = normalize(matPush.sunDirIntensity.xyz);
    vec3 H = normalize(V + L);

    float ndotl = max(dot(N, L), 0.0);
    float ndoth = max(dot(N, H), 0.0);
    float ndotv = max(dot(N, V), 0.001);

    float r = clamp(matPush.roughness, 0.08, 1.0);
    float a2 = r * r * r * r;
    float denom = (ndoth * ndoth * (a2 - 1.0) + 1.0);
    float ggxD = a2 / (3.14159265 * denom * denom + 0.0001);
    float fresnel = pow(1.0 - ndotv, 4.0);

    vec3 albedo = texture(albedoMap, inUV).rgb;
    vec3 ambient = albedo * (0.20 * matPush.aoStrength);
    vec3 diffuse = albedo * (1.0 - matPush.metallic * 0.65) * ndotl * matPush.sunDirIntensity.w;
    vec3 specColor = mix(vec3(0.04), albedo, matPush.metallic);
    vec3 spec = specColor * ggxD * ndotl * 0.35;
    vec3 rim = vec3(0.22, 0.74, 0.97) * fresnel * matPush.rimStrength;

    vec3 lit = ambient + diffuse + spec + rim;
    float dist = length(inWorldPos);
    float fogFactor = 1.0 - exp(-pow(dist * matPush.fogColorDensity.w, 2.0));
    vec3 finalCol = mix(lit, matPush.fogColorDensity.rgb, clamp(fogFactor, 0.0, 0.85));
    outColor = vec4(finalCol, 1.0);
}
