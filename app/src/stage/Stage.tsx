import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import type { Heading, Project, Role, Sample } from '../model';

export interface StageState { poses: Record<Role, Sample>; heading: Heading; camera: Project['camera']; overview: boolean; time: number }
export function Stage({ state, captureRef }: { state: StageState; captureRef: React.RefObject<(() => string) | null> }) {
  const host = useRef<HTMLDivElement>(null), latest = useRef(state);
  latest.current = state;
  const [error, setError] = useState('');
  useEffect(() => {
    const element = host.current!;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true }); }
    catch { setError('WebGL is unavailable. Enable hardware acceleration and reopen the browser. Your takes are still safe.'); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.3;
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#111b22');
    scene.fog = new THREE.Fog('#111b22', 16, 45);
    const camera = new THREE.PerspectiveCamera(48, 1, .1, 100);
    const material = (color: string, metalness = .1, roughness = .7) => new THREE.MeshStandardMaterial({ color, metalness, roughness });
    const floorMat = material('#343d44', .3, .65), dark = material('#182731'), trim = material('#79858a', .65, .3);
    const addBox = (size: number[], at: number[], mat: THREE.Material, parent: THREE.Object3D = scene) => {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(...size as [number, number, number]), mat);
      mesh.position.set(...at as [number, number, number]); mesh.castShadow = true; mesh.receiveShadow = true; parent.add(mesh); return mesh;
    };
    addBox([60, .2, 60], [0, -.12, 0], floorMat);
    const grid = new THREE.GridHelper(40, 40, '#586167', '#424a50'); grid.position.y = -.008; scene.add(grid);
    const warmEmissive = new THREE.MeshStandardMaterial({ color: '#ffc892', emissive: '#ffb36f', emissiveIntensity: 3 });
    const coolEmissive = new THREE.MeshStandardMaterial({ color: '#b4f2ee', emissive: '#67ccdf', emissiveIntensity: 2 });
    // Built-in, asset-free film set: repeating architectural portals and practical lights.
    for (let i = 0; i < 5; i++) {
      const z = -4.5 - i * 3;
      for (const x of [-6.2, 6.2]) {
        addBox([.5, 6.5, .5], [x, 3.2, z], dark);
        addBox([.08, 4.4, .08], [x + (x < 0 ? .27 : -.27), 3, z + .27], i % 2 ? coolEmissive : warmEmissive);
      }
      addBox([12.9, .4, .5], [0, 6.3, z], dark);
      addBox([5, .035, .15], [0, 6.05, z], warmEmissive);
    }
    addBox([14, 7, .4], [0, 3.4, -18], dark);
    addBox([3.6, 4.6, .2], [0, 2.3, -17.7], trim);
    addBox([.08, 4.4, .3], [0, 2.3, -17.5], coolEmissive);
    for (const [x, z, h] of [[-5, -5, 1.4], [4.7, -7, 1.9], [-4.7, -10, .9]]) {
      addBox([1.5, h, 1.5], [x, h / 2, z], material('#45555d'));
      addBox([1.55, .07, 1.55], [x, h, z], trim);
    }
    // Ground markings reinforce virtual scale without claiming a surveyed reconstruction.
    const stripe = material('#be8b52');
    for (const x of [-5.5, 5.5]) for (let i = 0; i < 15; i++) addBox([.1, .007, .65], [x, .002, 5 - i * 1.4], stripe);
    scene.add(new THREE.HemisphereLight('#d4e9ff', '#454b4e', 2.1));
    const key = new THREE.DirectionalLight('#ffdfb9', 3.4); key.position.set(-4, 9, 5); key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048); key.shadow.camera.left = -12; key.shadow.camera.right = 12; key.shadow.camera.top = 12; key.shadow.camera.bottom = -12; key.shadow.normalBias = .04; scene.add(key);
    const rim = new THREE.PointLight('#57bcdc', 65, 25, 2); rim.position.set(3, 5, -6); scene.add(rim);
    const practical = new THREE.PointLight('#ffa258', 45, 20, 2); practical.position.set(-5, 4, -3); scene.add(practical);

    function actor(color: string) {
      const group = new THREE.Group(), body = material(color, .32, .42), joint = material('#273238', .4);
      for (const x of [-.18, .18]) {
        addBox([.23, .65, .25], [x, .42, 0], joint, group);
        addBox([.28, .12, .44], [x, .08, .08], joint, group);
      }
      addBox([.7, .68, .37], [0, 1.05, 0], body, group);
      addBox([.62, .13, .4], [0, .73, 0], joint, group);
      for (const x of [-.47, .47]) {
        const arm = addBox([.22, .64, .25], [x, 1.06, .02], body, group); arm.rotation.z = x < 0 ? -.09 : .09;
        addBox([.19, .2, .2], [x, .66, .02], joint, group);
      }
      const head = new THREE.Mesh(new THREE.SphereGeometry(.255, 24, 16), body); head.position.y = 1.64; head.scale.set(1, 1.12, .92); head.castShadow = true; group.add(head);
      addBox([.37, .14, .08], [0, 1.67, .21], material('#10242d', .85, .17), group);
      addBox([.22, .04, .012], [0, 1.15, .192], coolEmissive, group);
      const ring = new THREE.Mesh(new THREE.RingGeometry(.53, .56, 48), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide, transparent: true, opacity: .65 })); ring.rotation.x = -Math.PI / 2; ring.position.y = .01; group.add(ring);
      scene.add(group); return group;
    }
    const actors = { 'actor-a': actor('#eaa75f'), 'actor-b': actor('#6ebdb5') };
    const cameraMarker = new THREE.Group(); addBox([.4, .25, .55], [0, 0, 0], material('#b09cf5'), cameraMarker); scene.add(cameraMarker);
    const target = new THREE.Vector3();
    const draw = () => {
      const s = latest.current;
      for (const role of ['actor-a', 'actor-b'] as const) {
        const pose = s.poses[role], mesh = actors[role]; mesh.visible = !!pose.position;
        if (pose.position) mesh.position.set(pose.position[0], 0, pose.position[1]);
        const other = s.poses[role === 'actor-a' ? 'actor-b' : 'actor-a'];
        if (s.heading === 'look-at' && other.position && pose.position) mesh.rotation.y = Math.atan2(other.position[0] - pose.position[0], other.position[1] - pose.position[1]);
        else mesh.rotation.y = role === 'actor-a' ? Math.PI / 2 : -Math.PI / 2;
      }
      const a = s.poses['actor-a'].position, b = s.poses['actor-b'].position;
      const chosen = s.camera.target === 'actor-a' ? a : s.camera.target === 'actor-b' ? b : a && b ? [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] : a ?? b;
      target.set(chosen?.[0] ?? 0, 1.05, chosen?.[1] ?? 0);
      const cp = s.poses.camera.position;
      cameraMarker.visible = s.overview && !!cp;
      if (cp) { cameraMarker.position.set(cp[0], s.camera.height, cp[1]); cameraMarker.lookAt(target); }
      if (s.overview) { camera.position.set(10, 10, 13); camera.lookAt(0, 0, -1); camera.fov = 44; }
      else { camera.position.set(cp?.[0] ?? 0, s.camera.height, cp?.[1] ?? 5.2); camera.lookAt(target); camera.fov = s.camera.fov; }
      camera.updateProjectionMatrix(); renderer.render(scene, camera);
    };
    const resize = new ResizeObserver(() => { const { width, height } = element.getBoundingClientRect(); if (width && height) { renderer.setSize(width, height); camera.aspect = width / height; draw(); } }); resize.observe(element);
    renderer.setAnimationLoop(draw);
    captureRef.current = () => { draw(); return renderer.domElement.toDataURL('image/png'); };
    const contextLost = (event: Event) => { event.preventDefault(); setError('Graphics context lost. Save your project, then reload the page.'); };
    renderer.domElement.addEventListener('webglcontextlost', contextLost);
    return () => {
      captureRef.current = null; resize.disconnect(); renderer.setAnimationLoop(null);
      scene.traverse(o => { if (o instanceof THREE.Mesh || o instanceof THREE.LineSegments) { o.geometry.dispose(); const mats = Array.isArray(o.material) ? o.material : [o.material]; mats.forEach(m => m.dispose()); } });
      renderer.dispose(); renderer.domElement.removeEventListener('webglcontextlost', contextLost); renderer.domElement.remove();
    };
  }, [captureRef]);
  return <div className="stage-canvas" ref={host}>{error && <div className="graphics-error" role="alert">{error}</div>}</div>;
}
