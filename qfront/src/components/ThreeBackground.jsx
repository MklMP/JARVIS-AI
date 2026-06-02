import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'

function ParticleField() {
  const count = 2000
  const meshRef = useRef()
  const mouseRef = useRef({ x: 0, y: 0 })

  const [positions, sizes] = useMemo(() => {
    const pos = new Float32Array(count * 3)
    const siz = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 50
      pos[i * 3 + 1] = (Math.random() - 0.5) * 50
      pos[i * 3 + 2] = (Math.random() - 0.5) * 30 - 10
      siz[i] = Math.random() * 2 + 0.5
    }
    return [pos, siz]
  }, [])

  useFrame(({ clock, pointer }) => {
    if (!meshRef.current) return
    const t = clock.getElapsedTime()
    meshRef.current.rotation.y = t * 0.02 + pointer.x * 0.1
    meshRef.current.rotation.x = Math.sin(t * 0.01) * 0.1 + pointer.y * 0.05
  })

  return (
    <points ref={meshRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-size" args={[sizes, 1]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.08}
        color="#00d4ff"
        transparent
        opacity={0.6}
        sizeAttenuation
        blending={2}
      />
    </points>
  )
}

export default function ThreeBackground() {
  return (
    <div className="fixed inset-0 z-0 opacity-40">
      <Canvas camera={{ position: [0, 0, 15], fov: 60 }}>
        <ParticleField />
      </Canvas>
    </div>
  )
}
