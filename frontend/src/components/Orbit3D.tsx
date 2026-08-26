import { useEffect, useMemo, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { Line, OrbitControls, Stars } from '@react-three/drei';
import type { Event, Trajectory } from '../lib/api';

type Vec3 = [number, number, number];
 const EARTH_RADIUS_KM = 6378.137;
 const SCALE = 1 / EARTH_RADIUS_KM;

type MultiPayload = { frame:string; frame_note?:string; duration_minutes:number; step_seconds:number; trajectories:Array<{catalog_number:number;name:string;points:Array<Trajectory['points'][number] & {ecef_km?: {x:number;y:number;z:number}}>}> };

type VizPayload = {
  event: Event;
  frame: string;
  source_frame?: string;
  frame_note?: string;
  window_start: string;
  window_duration_minutes: number;
  step_seconds: number;
  closest_approach_positions_km: { a: {x:number;y:number;z:number}; b:{x:number;y:number;z:number} };
  trajectories: {
    a: { name: string; catalog_number: number; points: Array<Trajectory['points'][number] & {ecef_km?: {x:number;y:number;z:number}}> };
    b: { name: string; catalog_number: number; points: Array<Trajectory['points'][number] & {ecef_km?: {x:number;y:number;z:number}}> };
  };
};

function Earth(){
  return <group>
    <mesh>
      <sphereGeometry args={[1,64,64]}/>
      <meshStandardMaterial color="#0b5f96" roughness={0.82} metalness={0.08}/>
    </mesh>
    <mesh scale={[1.018,1.018,1.018]}>
      <sphereGeometry args={[1,40,40]}/>
      <meshBasicMaterial color="#41b8ff" transparent opacity={0.08} wireframe/>
    </mesh>
  </group>;
}

function Orbit({points,color}:{points:Vec3[];color:string}){
  if(points.length<2) return null;
  return <Line points={points} color={color} lineWidth={1.5} transparent opacity={0.78}/>;
}

function Marker({position,color="2fcbff",size=0.018}:{position:Vec3;color?:string;size?:number}){
  return <mesh position={position}>
    <sphereGeometry args={[size,14,14]}/>
    <meshBasicMaterial color={`#${color}`}/>
  </mesh>;
}

function TcaMarker({position}:{position:Vec3}){
  return <group position={position}>
    <mesh><sphereGeometry args={[0.035,18,18]}/><meshBasicMaterial color="#ff665e"/></mesh>
    <mesh scale={[2.2,2.2,2.2]}><sphereGeometry args={[0.035,18,18]}/><meshBasicMaterial color="#ff665e" transparent opacity={0.14} wireframe/></mesh>
  </group>;
}

export default function Orbit3D({catalogNumber=25544,event=null,objectCatalogs=[]}:{catalogNumber?:number;event?:Event|null;objectCatalogs?:number[]}){
  const [trajectory,setTrajectory]=useState<Trajectory|null>(null);
  const [viz,setViz]=useState<VizPayload|null>(null);
  const [multi,setMulti]=useState<MultiPayload|null>(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  const [cursor,setCursor]=useState(0);
  const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

  useEffect(()=>{
    let cancelled=false;
    setLoading(true); setError(''); setCursor(0); setViz(null); setTrajectory(null); setMulti(null);
    const pairReady = Boolean(event && event.catalog_a && event.catalog_b);
    const selectedEvent = pairReady ? event! : null;
    const url = selectedEvent
      ? `${API}/conjunctions/visualization?catalog_a=${selectedEvent.catalog_a}&catalog_b=${selectedEvent.catalog_b}&duration_minutes=20&step_seconds=30`
      : objectCatalogs.length > 1
        ? `${API}/visualization/multi?catalog_numbers=${objectCatalogs.join(',')}&duration_minutes=90&step_seconds=180`
        : `${API}/satellites/${catalogNumber}/earth-fixed-trajectory?duration_minutes=180&step_seconds=120`;
    fetch(url)
      .then(r=>{if(!r.ok) throw new Error(`Backend returned ${r.status}`); return r.json()})
      .then(data=>{if(cancelled)return; if(selectedEvent) setViz(data as VizPayload); else if(objectCatalogs.length > 1) setMulti(data as MultiPayload); else setTrajectory(data as Trajectory);})
      .catch(err=>{if(!cancelled)setError(err instanceof Error?err.message:'Visualization unavailable')})
      .finally(()=>{if(!cancelled)setLoading(false)});
    return ()=>{cancelled=true};
  },[API,catalogNumber,event?.catalog_a,event?.catalog_b,objectCatalogs.join(',')]);

  const multiLines=useMemo(()=>multi?.trajectories.map((traj,idx)=>({name:traj.name,catalog_number:traj.catalog_number,color:['#4fc8ff','#ff8d7f','#9fe37d','#c0a7ff','#f0d36a','#7ee7df','#ffb16b','#c9d1e7'][idx%8],points:traj.points.map(p=>{const q=p.ecef_km ?? p.position_km!; return [q.x*SCALE,q.y*SCALE,q.z*SCALE] as Vec3})})),[multi]);
  const pointsA=useMemo<Vec3[]>(()=>viz?.trajectories.a.points.map(p=>{const q=p.ecef_km ?? p.position_km!; return [q.x*SCALE,q.y*SCALE,q.z*SCALE] as Vec3})??[],[viz]);
  const pointsB=useMemo<Vec3[]>(()=>viz?.trajectories.b.points.map(p=>{const q=p.ecef_km ?? p.position_km!; return [q.x*SCALE,q.y*SCALE,q.z*SCALE] as Vec3})??[],[viz]);
  const fallbackPoints=useMemo<Vec3[]>(()=>trajectory?.points.map((p: any)=>{const q=p.ecef_km ?? p.position_km!; return [q.x*SCALE,q.y*SCALE,q.z*SCALE] as Vec3})??[],[trajectory]);

  useEffect(()=>{
    const count = viz ? Math.max(pointsA.length,pointsB.length) : multi ? Math.max(0,...multi.trajectories.map(t=>t.points.length)) : fallbackPoints.length;
    if(!count) return;
    const timer=window.setInterval(()=>setCursor(i=>(i+1)%count),80);
    return ()=>window.clearInterval(timer);
  },[viz,multi,pointsA.length,pointsB.length,fallbackPoints.length]);

  const currentA=pointsA[Math.min(cursor,Math.max(0,pointsA.length-1))] ?? [0,0,0];
  const currentB=pointsB[Math.min(cursor,Math.max(0,pointsB.length-1))] ?? [0,0,0];
  const currentFallback=fallbackPoints[Math.min(cursor,Math.max(0,fallbackPoints.length-1))] ?? [0,0,0];
  const tcaA = viz ? ([
    viz.closest_approach_positions_km.a.x*SCALE,
    viz.closest_approach_positions_km.a.y*SCALE,
    viz.closest_approach_positions_km.a.z*SCALE,
  ] as Vec3) : null;
  const tcaB = viz ? ([
    viz.closest_approach_positions_km.b.x*SCALE,
    viz.closest_approach_positions_km.b.y*SCALE,
    viz.closest_approach_positions_km.b.z*SCALE,
  ] as Vec3) : null;

  const subject = event && viz ? `${viz.trajectories.a.name} × ${viz.trajectories.b.name}` : multi ? `${multi.trajectories.length} tracked objects` : (trajectory?.name ?? `CAT ${catalogNumber}`);
  const timeLabel = viz ? `TCA · ${new Date(viz.event.tca).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})} UTC` : multi ? `+${Math.round((cursor*(multi.step_seconds||180))/60)} min` : trajectory ? `+${Math.round((cursor*(trajectory.step_seconds||120))/60)} min` : loading ? 'Loading…' : 'Unavailable';

  return <div className="orbit3d-shell">
    <div className="orbit3d-stage">
      <Canvas camera={{position:[2.7,2.1,2.7],fov:45}} dpr={[1,2]}>
        <color attach="background" args={['#06101b']}/>
        <ambientLight intensity={0.8}/><directionalLight position={[3,4,2]} intensity={2.2}/>
        <Stars radius={8} depth={20} count={1600} factor={1.8} saturation={0} fade speed={0.2}/>
        <Earth/>
        {viz ? <>
          <Orbit points={pointsA} color="#4fc8ff"/>
          <Orbit points={pointsB} color="#ff8d7f"/>
          <Marker position={currentA} color="4fc8ff" size={0.020}/>
          <Marker position={currentB} color="ff8d7f" size={0.020}/>
          {tcaA && tcaB && <>
            <TcaMarker position={tcaA}/>
            <TcaMarker position={tcaB}/>
            <Line points={[tcaA,tcaB]} color="#ff665e" lineWidth={2.2}/>
          </>}
        </> : multi ? <>{multiLines?.map((line,i)=><span key={line.catalog_number}><Orbit points={line.points} color={line.color}/><Marker position={line.points[Math.min(cursor,line.points.length-1)] ?? [0,0,0]} color={line.color.slice(1)} size={0.015}/></span>)}</> : <>
          <Orbit points={fallbackPoints} color="#56c8ff"/>
          <Marker position={currentFallback} color="ff6c62"/>
        </>}
        <OrbitControls enablePan={false} minDistance={1.35} maxDistance={5.5}/>
      </Canvas>
      <div className="orbit3d-badge"><span className="live-dot"/> {viz ? 'CONJUNCTION FOCUS' : multi ? 'MULTI-OBJECT SSA VIEW' : 'LIVE 3D ORBITAL VIEW'} · SGP4 · ECEF</div>
      <div className="orbit3d-readout">
        <span>{subject}</span>
        <b>{timeLabel}</b>
        {viz && <small>{viz.event.miss_distance_km.toFixed(2)} km miss distance</small>}
      </div>
      {viz && <div className="orbit3d-encounter"><span><i className="blue-dot"/> Object A</span><span><i className="red-dot"/> Object B</span><span><i className="tca-dot"/> Closest approach</span></div>}
      {multi && <div className="orbit3d-encounter multi-legend">{multiLines?.slice(0,6).map(line=><span key={line.catalog_number}><i style={{background:line.color}}/>{line.name}</span>)}</div>}
      {error && <div className="orbit3d-error">{error}. Start the FastAPI backend to enable live conjunction visualization.</div>}
    </div>
    <div className="orbit3d-foot"><span>{viz ? `Encounter window: ${viz.window_duration_minutes} min` : multi ? `Multi-object forecast: ${multi.duration_minutes} min` : 'Orbit trail: 3 h forecast'}</span><span>{loading?'Fetching SGP4 states…':viz?`${viz.trajectories.a.points.length} × 2 propagated states`:multi?`${multi.trajectories.length} objects · ${multi.trajectories[0]?.points.length||0} states each`:trajectory?`${trajectory.points.length} propagated states`:error?'Backend offline':'—'}</span></div>
  </div>;
}
