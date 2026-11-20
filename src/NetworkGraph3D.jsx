import React, { useRef, useMemo, useState } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, shaderMaterial } from '@react-three/drei';
import { extend } from '@react-three/fiber';
import * as THREE from 'three';
import { EffectComposer, Bloom } from '@react-three/postprocessing';

const WireframeSphereMaterial = shaderMaterial(
  {
    uTime: 0,
    uColor: new THREE.Color('#00D2FF'),
    uDistortion: 0.5,
    uHover: 0,
  },
  `
  uniform float uTime;
  uniform float uDistortion;
  uniform float uHover;
  varying vec3 vPosition;
  varying vec3 vNormal;

  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x*34.0)+1.0)*x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
  float snoise(vec3 v) {
    const vec2 C = vec2(1.0/6.0, 1.0/3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i  = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(
               i.z + vec4(0.0, i1.z, i2.z, 1.0))
             + i.y + vec4(0.0, i1.y, i2.y, 1.0))
             + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3  ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ *ns.x + ns.yyyy;
    vec4 y = y_ *ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4( x.xy, y.xy );
    vec4 b1 = vec4( x.zw, y.zw );
    vec4 s0 = floor(b0)*2.0 + 1.0;
    vec4 s1 = floor(b1)*2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
    vec3 p0 = vec3(a0.xy,h.x);
    vec3 p1 = vec3(a0.zw,h.y);
    vec3 p2 = vec3(a1.xy,h.z);
    vec3 p3 = vec3(a1.zw,h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2, p2), dot(p3,p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
    m = m * m;
    return 42.0 * dot( m*m, vec4( dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3) ) );
  }

  void main() {
    vNormal = normal;
    float currentDistortion = uDistortion + (uHover * 0.6);
    float noise = snoise(vec3(position * 2.0 + uTime * 0.2)) * currentDistortion;
    vec3 newPosition = position + normal * noise;
    vPosition = newPosition;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(newPosition, 1.0);
  }
  `,
  `
  uniform vec3 uColor;
  uniform float uHover;
  varying vec3 vPosition;
  varying vec3 vNormal;

  void main() {
    float linePattern = sin(vPosition.x * 20.0) * sin(vPosition.y * 20.0) * sin(vPosition.z * 20.0);
    linePattern = smoothstep(0.85, 1.0, abs(linePattern));
    
    vec3 viewDir = normalize(vPosition);
    float fresnel = pow(1.0 - abs(dot(vNormal, viewDir)), 3.0);

    float alpha = (linePattern * (0.8 + uHover * 0.2)) + (fresnel * 0.5);
    vec3 finalColor = mix(uColor, vec3(1.0), uHover * 0.5);
    
    gl_FragColor = vec4(finalColor, alpha);
  }
  `
);

extend({ WireframeSphereMaterial });

function Sphere({ statusColor, onClick }) {
  const materialRef = useRef();
  const meshRef = useRef();
  const [hovered, setHovered] = useState(false);
  const targetColor = useMemo(() => new THREE.Color(statusColor), [statusColor]);

  React.useEffect(() => {
    document.body.style.cursor = hovered ? 'pointer' : 'auto';
    return () => { document.body.style.cursor = 'auto'; };
  }, [hovered]);

  useFrame((state, delta) => {
    if (materialRef.current) {
      materialRef.current.uTime = state.clock.getElapsedTime();
      materialRef.current.uColor.lerp(targetColor, 0.05);
      const targetHover = hovered ? 1.0 : 0.0;
      materialRef.current.uHover += (targetHover - materialRef.current.uHover) * 0.1;
    }
    
    if (meshRef.current) {
      const targetScale = hovered ? 1.05 : 1.0;
      meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
      meshRef.current.rotation.y += delta * (hovered ? 0.5 : 0.2);
    }
  });

  return (
    <mesh 
      ref={meshRef}
      onClick={(e) => { e.stopPropagation(); if(onClick) onClick(); }}
      onPointerOver={(e) => { e.stopPropagation(); setHovered(true); }}
      onPointerOut={(e) => { e.stopPropagation(); setHovered(false); }}
      position={[0.8, 0, 0]} // Чуть смещен вправо от центра
    >
      <sphereGeometry args={[2.2, 128, 128]} /> {/* Вернули нормальный размер */}
      <wireframeSphereMaterial 
        ref={materialRef} 
        transparent={true} 
        depthWrite={false} 
        blending={THREE.AdditiveBlending} 
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

export default function NetworkGraph3D({ status = 'normal', onClick }) {
  const color = status === 'critical' ? '#FF0032' : '#00D2FF';

  return (
    <div className="w-full h-full absolute inset-0 bg-[#05080F]">
      <Canvas camera={{ position: [0, 0, 7], fov: 45 }}>
        <Sphere statusColor={color} onClick={onClick} />
        <OrbitControls enableZoom={false} enablePan={false} autoRotate={false} />
        <EffectComposer>
          <Bloom luminanceThreshold={0.1} mipmapBlur intensity={1.5} radius={0.8} />
        </EffectComposer>
      </Canvas>
    </div>
  );
}