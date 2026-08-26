import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Line, OrbitControls, Stars } from '@react-three/drei';
import * as THREE from 'three';

import type { ConjunctionEvent, FullOrbitResponse, ObjectCatalogEntry } from '../../types/orbitguard';

// Scene scale: 1 scene unit ≈ 1600 km  →  ISS at ~6791 km ≈ 4.24 scene units
const KM_TO_SCENE = 1 / 1600;

type ScenePoint = { x_km: number; y_km: number; z_km: number; timestamp?: string };

type OrbitSceneProps = {
  selectedEvent?: ConjunctionEvent | null;
  selectedObject?: ObjectCatalogEntry | null;
  objects?: ObjectCatalogEntry[];
  trajectories?: Record<string, ScenePoint[]>;
  selectedOrbit?: FullOrbitResponse | null;
  conjunctionData?: any | null;
  mode?: 'LIVE' | 'CACHED' | 'OFFLINE';
};

// ---------------------------------------------------------------------------
// Earth
// ---------------------------------------------------------------------------
function Earth() {
  return (
    <group>
      <mesh>
        <sphereGeometry args={[1.8, 48, 48]} />
        <meshStandardMaterial color="#0d2b45" roughness={0.85} metalness={0.1} />
      </mesh>
      <mesh scale={1.055}>
        <sphereGeometry args={[1.8, 32, 32]} />
        <meshStandardMaterial color="#3ab5e6" transparent opacity={0.08} depthWrite={false} />
      </mesh>
      <mesh scale={1.12}>
        <sphereGeometry args={[1.8, 24, 24]} />
        <meshStandardMaterial color="#1a6ca8" transparent opacity={0.03} depthWrite={false} />
      </mesh>
    </group>
  );
}

// ---------------------------------------------------------------------------
// Satellite marker (optionally pulsing)
// ---------------------------------------------------------------------------
function Marker({
  position,
  color,
  size = 0.075,
  pulse = false,
}: {
  position: [number, number, number];
  color: string;
  size?: number;
  pulse?: boolean;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  useFrame(({ clock }) => {
    if (pulse && meshRef.current) {
      const s = 1 + 0.28 * Math.sin(clock.getElapsedTime() * 4.5);
      meshRef.current.scale.setScalar(s);
    }
  });
  return (
    <mesh ref={meshRef} position={position}>
      <sphereGeometry args={[size, 16, 16]} />
      <meshStandardMaterial
        color={color}
        emissive={new THREE.Color(color)}
        emissiveIntensity={1.3}
      />
    </mesh>
  );
}

// ---------------------------------------------------------------------------
// Full orbit shell — renders a complete closed SGP4 orbit from backend data
// ---------------------------------------------------------------------------
function FullOrbitShell({ orbit }: { orbit: FullOrbitResponse }) {
  if (!orbit.points || orbit.points.length < 2) return null;

  const orbitPath = orbit.points.map(
    (pt) => [pt.x_km * KM_TO_SCENE, pt.y_km * KM_TO_SCENE, pt.z_km * KM_TO_SCENE] as [number, number, number]
  );
  // Close the loop
  if (orbitPath.length > 2) orbitPath.push(orbitPath[0]);

  // Direction arrow at midpoint (velocity-aligned)
  let arrowDir: [number, number, number] | null = null;
  let arrowOrigin: [number, number, number] | null = null;
  const midIdx = Math.floor(orbit.points.length / 2);
  const midPt = orbit.points[midIdx];
  if (midPt) {
    const speed = Math.sqrt(midPt.vx_km_s ** 2 + midPt.vy_km_s ** 2 + midPt.vz_km_s ** 2);
    if (speed > 0) {
      arrowDir = [midPt.vx_km_s / speed, midPt.vy_km_s / speed, midPt.vz_km_s / speed];
      arrowOrigin = [midPt.x_km * KM_TO_SCENE, midPt.y_km * KM_TO_SCENE, midPt.z_km * KM_TO_SCENE];
    }
  }

  const currentPos = orbit.current_position;
  const markerPos: [number, number, number] | null = currentPos
    ? [currentPos.x_km * KM_TO_SCENE, currentPos.y_km * KM_TO_SCENE, currentPos.z_km * KM_TO_SCENE]
    : null;

  return (
    <>
      <Line points={orbitPath} color="#2dd4f0" transparent opacity={0.78} lineWidth={1.7} />
      {arrowDir && arrowOrigin && (
        <Line
          points={[
            arrowOrigin,
            [
              arrowOrigin[0] + arrowDir[0] * 0.24,
              arrowOrigin[1] + arrowDir[1] * 0.24,
              arrowOrigin[2] + arrowDir[2] * 0.24,
            ] as [number, number, number],
          ]}
          color="#fde047"
          transparent
          opacity={0.92}
          lineWidth={2.4}
        />
      )}
      {markerPos && <Marker position={markerPos} color="#2dd4f0" size={0.115} pulse />}
    </>
  );
}

// ---------------------------------------------------------------------------
// Multi-object live trajectory shell
// ---------------------------------------------------------------------------
function LiveTrajectoryShell({ trajectories }: { trajectories: Record<string, ScenePoint[]> }) {
  const entries = Object.entries(trajectories).slice(0, 8);
  const palette = ['#76d5ff', '#6ee7a4', '#ffc266', '#e879f9', '#fb923c', '#a78bfa', '#f87171', '#34d399'];
  return (
    <>
      {entries.map(([catalogNumber, points], index) => {
        const color = palette[index % palette.length];
        const mapped = points.map((p) => [p.x_km, p.y_km, p.z_km] as [number, number, number]);
        if (mapped.length < 2) return null;
        return <Line key={catalogNumber} points={mapped} color={color} transparent opacity={0.72} lineWidth={1.3} />;
      })}
    </>
  );
}

// ---------------------------------------------------------------------------
// Decorative fleet shell (offline/no data fallback)
// ---------------------------------------------------------------------------
function orbitPoints(radius: number, phase: number, tilt: number, height: number): [number, number, number][] {
  return Array.from({ length: 121 }, (_, index) => {
    const angle = (index / 120) * Math.PI * 2 + phase;
    return [
      Math.cos(angle) * radius,
      Math.sin(angle * 1.3 + tilt) * height,
      Math.sin(angle) * radius * 0.88,
    ] as [number, number, number];
  });
}

function FleetShell({ objects }: { objects: ObjectCatalogEntry[] }) {
  const palette = ['#76d5ff', '#6ee7a4', '#ffc266', '#e879f9', '#fb923c', '#a78bfa'];
  return (
    <>
      {objects.slice(0, 6).map((object, index) => {
        const points = orbitPoints(2.15 + (index % 3) * 0.42, index * 0.7 + 0.5, 0.55 + index * 0.22, 0.75 + (index % 2) * 0.28);
        return <Line key={object.catalog_number} points={points} color={palette[index % palette.length]} transparent opacity={0.55} lineWidth={1} />;
      })}
    </>
  );
}

// ---------------------------------------------------------------------------
// Conjunction focal view
// ---------------------------------------------------------------------------
function EncounterFocal({
  selectedEvent,
  conjunctionData,
}: {
  selectedEvent: ConjunctionEvent;
  conjunctionData: any | null;
}) {
  if (!conjunctionData || !conjunctionData.trajectory_a || !conjunctionData.trajectory_b) {
    const fallbackPosA: [number, number, number] = [1.9, 0.5, 0.7];
    const fallbackPosB: [number, number, number] = [1.4, -0.55, -1.3];
    const fallbackTca: [number, number, number] = [
      (fallbackPosA[0] + fallbackPosB[0]) / 2,
      (fallbackPosA[1] + fallbackPosB[1]) / 2,
      (fallbackPosA[2] + fallbackPosB[2]) / 2,
    ];
    return (
      <>
        <Line points={orbitPoints(2.25, 0.4, 0.85, 0.9)} color="#2dd4f0" transparent opacity={0.85} lineWidth={1.3} />
        <Line points={orbitPoints(2.65, 2.6, 1.2, 1.1)} color="#fb923c" transparent opacity={0.85} lineWidth={1.3} />
        <Line points={[fallbackPosA, fallbackPosB]} color="#fbbf24" transparent opacity={0.9} lineWidth={1.8} />
        <Marker position={fallbackPosA} color="#2dd4f0" size={0.12} />
        <Marker position={fallbackPosB} color="#fb923c" size={0.11} />
        <Marker position={fallbackTca} color="#ef4444" size={0.15} pulse />
      </>
    );
  }

  // Real SGP4 coordinates mapped to scene units
  const pointsA = conjunctionData.trajectory_a.map((p: any) => [
    (p.x_km ?? 0) * KM_TO_SCENE,
    (p.y_km ?? 0) * KM_TO_SCENE,
    (p.z_km ?? 0) * KM_TO_SCENE
  ] as [number, number, number]);

  const pointsB = conjunctionData.trajectory_b.map((p: any) => [
    (p.x_km ?? 0) * KM_TO_SCENE,
    (p.y_km ?? 0) * KM_TO_SCENE,
    (p.z_km ?? 0) * KM_TO_SCENE
  ] as [number, number, number]);

  const tcaA: [number, number, number] = [
    (conjunctionData.tca_position_a?.x_km ?? 0) * KM_TO_SCENE,
    (conjunctionData.tca_position_a?.y_km ?? 0) * KM_TO_SCENE,
    (conjunctionData.tca_position_a?.z_km ?? 0) * KM_TO_SCENE
  ];

  const tcaB: [number, number, number] = [
    (conjunctionData.tca_position_b?.x_km ?? 0) * KM_TO_SCENE,
    (conjunctionData.tca_position_b?.y_km ?? 0) * KM_TO_SCENE,
    (conjunctionData.tca_position_b?.z_km ?? 0) * KM_TO_SCENE
  ];

  const tcaMid: [number, number, number] = [
    (tcaA[0] + tcaB[0]) / 2,
    (tcaA[1] + tcaB[1]) / 2,
    (tcaA[2] + tcaB[2]) / 2
  ];

  return (
    <>
      <Line points={pointsA} color="#2dd4f0" transparent opacity={0.85} lineWidth={1.5} />
      <Line points={pointsB} color="#fb923c" transparent opacity={0.85} lineWidth={1.5} />
      <Line points={[tcaA, tcaB]} color="#ef4444" transparent opacity={0.95} lineWidth={2.0} />
      <Marker position={tcaA} color="#2dd4f0" size={0.10} />
      <Marker position={tcaB} color="#fb923c" size={0.09} />
      <Marker position={tcaMid} color="#ef4444" size={0.13} pulse />
    </>
  );
}

// ---------------------------------------------------------------------------
// Scene content
// ---------------------------------------------------------------------------
function SceneContent({ selectedEvent, selectedObject, objects, trajectories, selectedOrbit, conjunctionData }: OrbitSceneProps) {
  const hasSelectedOrbit = selectedOrbit && selectedOrbit.points && selectedOrbit.points.length > 1;
  const selectedTraj =
    selectedObject?.catalog_number && trajectories?.[selectedObject.catalog_number]
      ? { [selectedObject.catalog_number]: trajectories[selectedObject.catalog_number] }
      : undefined;

  return (
    <>
      <color attach="background" args={['#030c17']} />
      <fog attach="fog" args={['#030c17', 9, 18]} />
      <ambientLight intensity={0.65} />
      <directionalLight position={[5, 8, 5]} intensity={1.4} color="#d8eeff" />
      <pointLight position={[-6, -4, -6]} intensity={0.3} color="#1a4a8a" />
      <Stars radius={40} depth={16} count={4800} factor={4} saturation={0} fade speed={0.6} />
      <Earth />
      {selectedEvent ? (
        <EncounterFocal selectedEvent={selectedEvent} conjunctionData={conjunctionData} />
      ) : selectedObject ? (
        hasSelectedOrbit ? (
          <FullOrbitShell orbit={selectedOrbit!} />
        ) : null
      ) : trajectories && Object.keys(trajectories).length > 0 ? (
        <LiveTrajectoryShell trajectories={trajectories} />
      ) : (
        <FleetShell objects={objects ?? []} />
      )}
      <OrbitControls
        enablePan={false}
        minDistance={3.5}
        maxDistance={14}
        autoRotate={!hasSelectedOrbit && !selectedEvent}
        autoRotateSpeed={0.4}
      />
    </>
  );
}

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------
export function OrbitScene({
  selectedEvent,
  selectedObject,
  objects = [],
  trajectories = {},
  selectedOrbit,
  conjunctionData,
  mode = 'OFFLINE',
}: OrbitSceneProps) {
  const hasFullOrbit = selectedOrbit && selectedOrbit.points && selectedOrbit.points.length > 1;
  const period = selectedOrbit?.orbital_period_minutes ?? 90;
  const camDist = period > 600 ? 11 : period > 200 ? 8.5 : 7;
  const cameraPos: [number, number, number] = [0, camDist * 0.55, camDist];

  const legendItems = selectedEvent
    ? [
        { color: '#2dd4f0', label: 'Object A' },
        { color: '#fb923c', label: 'Object B' },
        { color: '#ef4444', label: 'TCA marker' },
        { color: '#fbbf24', label: 'Miss vector' },
      ]
    : hasFullOrbit
    ? [
        { color: '#2dd4f0', label: 'Orbital path (1 period)' },
        { color: '#fde047', label: 'Direction of motion' },
        { color: '#2dd4f0', label: 'Current position ●' },
      ]
    : [
        { color: '#76d5ff', label: 'Object A' },
        { color: '#6ee7a4', label: 'Object B' },
        { color: '#ffc266', label: 'Tracked' },
      ];

  return (
    <div className="orbit-scene">
      <div className="mini-banner">
        {selectedEvent ? 'CONJUNCTION FOCUS' : hasFullOrbit ? `FULL ORBIT — ${selectedOrbit!.name}` : 'MULTI-OBJECT VIEW'}
      </div>
      <div className="mini-readout">
        <span>MODE</span>
        <strong>{mode}</strong>
        {hasFullOrbit && (
          <>
            <span style={{ marginLeft: '1rem' }}>PERIOD</span>
            <strong>{selectedOrbit!.orbital_period_minutes.toFixed(1)} min</strong>
          </>
        )}
      </div>
      <Canvas
        camera={{ position: cameraPos, fov: 38 }}
        key={`${selectedOrbit?.catalog_number ?? 'none'}-${selectedEvent?.id ?? 'no-event'}`}
      >
        <SceneContent
          selectedEvent={selectedEvent}
          selectedObject={selectedObject}
          objects={objects}
          trajectories={trajectories}
          selectedOrbit={selectedOrbit}
          conjunctionData={conjunctionData}
          mode={mode}
        />
      </Canvas>
      <div className="scene-legend">
        {legendItems.map((item) => (
          <span key={item.label}>
            <i style={{ background: item.color }} />
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
