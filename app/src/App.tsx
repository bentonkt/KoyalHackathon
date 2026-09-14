import { useEffect, useRef, useState } from 'react';
import { Aperture, ArrowDownToLine, ArrowUpFromLine, Box, Camera, Check, ChevronRight, Circle, Clapperboard, Focus, Layers3, Maximize, Pause, Play, RotateCcw, Save, Scan, SkipBack, Square, X } from 'lucide-react';
import { commitTake, durationOf, parseProject, ROLES, sampleAt, selectedTake, uid, type Project, type Role, type Sample, type Take, type Track, type Vec2 } from './model';
import { DEMO_DURATION, demoProject, mockSample } from './tracking/mock';
import { importCandidate, importRelativeMotion, relativeObjectIds } from './tracking/adapter';
import { Stage } from './stage/Stage';
import { MotionRecorder, type MotionFrame } from './recording/recorder';
import { SourcePreview } from './tracking/SourcePreview';

const LABEL: Record<Role, string> = { 'actor-a': 'Actor A', 'actor-b': 'Actor B', camera: 'Camera' };
const CACHE = 'pocketstage-director-v1';
type Mode = 'idle' | 'play' | 'actors' | 'camera';
function download(url: string, name: string) { const a = document.createElement('a'); a.href = url; a.download = name; a.click(); }
function initialProject() {
  try { const s = localStorage.getItem(CACHE); if (s) return { project: parseProject(JSON.parse(s)), recovery: false }; }
  catch { return { project: demoProject(), recovery: true }; }
  return { project: demoProject(), recovery: false };
}
const seconds = (t: number) => `${Math.floor(t).toString().padStart(2, '0')}:${Math.floor((t % 1) * 30).toString().padStart(2, '0')}`;

export default function App() {
  const [boot] = useState(initialProject);
  const [project, setProject] = useState<Project>(boot.project);
  const [mode, setMode] = useState<Mode>('idle'), [time, setTime] = useState(0), [overview, setOverview] = useState(false);
  const [notice, setNotice] = useState(boot.recovery ? 'Could not read the browser save. It has NOT been overwritten; autosave is disabled for this session. Export JSON to save your work.' : 'Ready to rehearse. This opening scene uses simulated tracking, not a webcam.');
  const [sourceMode, setSourceMode] = useState<'script' | 'manual'>('script');
  const [alternate, setAlternate] = useState(false), [loseObject, setLoseObject] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null), [importOpen, setImportOpen] = useState(false);
  const [saved, setSaved] = useState(true);
  const [manual, setManual] = useState<Record<Role, Vec2>>({ 'actor-a': [-3.5, 0], 'actor-b': [3.3, 0], camera: [0, 3.5] });
  const latest = useRef({ project, manual, sourceMode, alternate, loseObject }); latest.current = { project, manual, sourceMode, alternate, loseObject };
  const capture = useRef<(() => string) | null>(null), openFile = useRef<HTMLInputElement>(null);
  const running = useRef<{ mode: Mode; wall: number; origin: number; duration: number; next: number; tracks: Track[]; recorder?: MotionRecorder; countdownEnd?: number } | null>(null);
  const actors = selectedTake(project, 'actors'), cameraTake = selectedTake(project, 'camera');
  const duration = actors?.duration || DEMO_DURATION;
  const busy = mode !== 'idle';

  useEffect(() => { if (boot.recovery) { setSaved(false); return; } try { localStorage.setItem(CACHE, JSON.stringify(project)); setSaved(true); } catch { setSaved(false); } }, [project, boot.recovery]);
  useEffect(() => {
    let raf: number;
    function tick(now: number) {
      const r = running.current;
      if (r) {
        if (r.countdownEnd && now < r.countdownEnd) { setCountdown(Math.ceil((r.countdownEnd - now) / 1000)); }
        else {
          setCountdown(null);
          const t = Math.min(r.duration, r.origin + (now - r.wall) / 1000);
          setTime(Math.max(0, t));
          if (r.mode === 'actors' || r.mode === 'camera') {
            // Mock producer has an explicit 15 Hz source clock, independent of renderer FPS.
            while (r.next / 15 <= t + 1e-6) {
              const ts = r.next / 15;
              const objects: MotionFrame['objects'] = {};
              for (const track of r.tracks) {
                const v = latest.current;
                objects[track.role] = v.loseObject ? { position: null, status: 'LOST', yaw: null } : mockSample(track.role, ts, v.alternate, v.sourceMode === 'manual' ? v.manual[track.role] : undefined);
              }
              r.recorder!.push({ schema: 'pocketstage-motion/1', stageId: r.tracks[0].stageId, clockId: r.tracks[0].clockId, timeS: ts, objects });
              r.next++;
            }
            if (latest.current.loseObject) {
              running.current = null; setMode('idle'); setNotice('Tracking-loss rehearsal: recording rejected. The last accepted actors and camera are unchanged. Loss was not filled with invented motion.');
            } else if (t >= r.duration) {
              try {
                const take = r.recorder!.finish(`${r.mode === 'actors' ? 'Blocking' : 'Camera'} · ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} (mock)`, r.duration);
                setProject(p => commitTake(p, take));
                setNotice(r.mode === 'actors' ? 'Actor take recorded. Now perform a camera pass; the actors will replay on their original clock.' : 'Camera pass recorded. Play the final shot. Your actor take is unchanged, and the previous camera version is retained.');
              } catch (e) { setNotice((e as Error).message); }
              running.current = null; setMode('idle'); setTime(0);
            }
          } else if (t >= r.duration) { running.current = null; setMode('idle'); }
        }
      }
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf);
  }, []);

  function stop() {
    const recording = mode === 'actors' || mode === 'camera';
    running.current = null; setMode('idle'); setCountdown(null);
    if (recording) setNotice('Canceled incomplete rehearsal. No accepted take was replaced.');
  }
  function play() {
    if (busy) { stop(); return; }
    const start = time >= duration ? 0 : time;
    running.current = { mode: 'play', wall: performance.now(), origin: start, duration, next: 0, tracks: [] }; setMode('play');
  }
  function record(kind: 'actors' | 'camera') {
    if (busy || (kind === 'camera' && !actors)) return;
    if (kind === 'camera' && duration > 10.05) { setNotice('Rehearsal capture is bounded to 10 seconds. Import a camera candidate for longer source footage.'); return; }
    const roles: Role[] = kind === 'actors' ? ['actor-a', 'actor-b'] : ['camera'];
    const clock = uid(), start = performance.now() + 3000;
    const recorder = new MotionRecorder({ kind, roles, stageId: project.stage.id, clockId: clock, source: 'mock', sourceStart: 0 });
    running.current = { mode: kind, wall: start, origin: 0, duration: kind === 'actors' ? DEMO_DURATION : duration, next: 0, tracks: recorder.tracks, recorder, countdownEnd: start };
    setLoseObject(false); setTime(0); setMode(kind); setCountdown(3); setOverview(false);
    setNotice(kind === 'actors' ? 'Recording simulated object motion after the countdown. Drag controls in manual mode.' : 'Actors replay from scene time zero. Only the camera trajectory is being recorded.');
  }
  const poses = Object.fromEntries(ROLES.map(role => {
    const recording = (mode === 'actors' && role !== 'camera') || (mode === 'camera' && role === 'camera');
    let s: Sample;
    if (recording) s = loseObject ? { t: time, position: null, status: 'LOST', yaw: null } : mockSample(role, time, alternate, sourceMode === 'manual' ? manual[role] : undefined);
    else {
      const take = role === 'camera' ? cameraTake : actors;
      s = sampleAt(take?.tracks.find(t => t.role === role), time - (take?.offset ?? 0));
      // A missing camera take uses an explicitly labeled fixed preview, not recorded coverage.
      if (role === 'camera' && !take) s = { t: time, position: [0, 5.2], status: 'UNAVAILABLE', yaw: null };
    }
    return [role, s];
  })) as Record<Role, Sample>;
  const cameraMissing = !cameraTake || !poses.camera.position;
  const missingActors = ['actor-a', 'actor-b'].filter(r => !poses[r as Role].position);
  const sources = [...new Set([...(actors?.tracks ?? []), ...(cameraTake?.tracks ?? [])].map(t => t.source))];
  const sourceLabel = sources.includes('cv') ? sources.includes('mock') ? 'CV + MOCK COMPOSITION' : 'IMPORTED CV TRAJECTORIES' : 'MOCK TRACKING';
  function save() { const url = URL.createObjectURL(new Blob([JSON.stringify(project, null, 2)], { type: 'application/json' })); download(url, 'pocketstage-scene.json'); setTimeout(() => URL.revokeObjectURL(url), 1000); setNotice('Project JSON exported with all take versions, source timestamps, gaps, and imported candidate provenance. Original video remains in the Python project.'); }
  async function load(file: File | undefined) {
    if (!file) return;
    try { if (file.size > 20_000_000) throw new Error('Project exceeds the 20 MB import limit.'); const next = parseProject(JSON.parse(await file.text())); stop(); setProject(next); setTime(0); setNotice('Project reopened. Timing, take versions, and selected composition restored.'); }
    catch (e) { setNotice(`Could not open: ${(e as Error).message} Current project preserved.`); }
  }

  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="#"><span className="brand-mark"><Aperture size={23}/></span>PocketStage<span className="beta">DIRECTOR'S DESK</span></a><div className="project-title"><span className="small-dot"/> The encounter <span className="slash">/</span> Scene 01</div><div className="header-actions"><span className={`save-status ${!saved ? 'warning' : ''}`}>{saved ? 'Saved in this browser' : 'Local storage full · export JSON'}</span><button disabled={busy} onClick={() => openFile.current?.click()}><ArrowUpFromLine size={15}/> Open</button><button onClick={save}><Save size={15}/> Save project</button></div></header>
    <input ref={openFile} hidden type="file" accept=".json,application/json" onChange={e => { void load(e.target.files?.[0]); e.target.value = ''; }}/>
    <nav className="workflow" aria-label="Directing workflow"><div className="workflow-title"><Clapperboard size={18}/> A scene, in your hands.</div><button disabled={busy} onClick={() => record('actors')} className={mode === 'actors' ? 'active' : ''}><span className="step-number">01</span> Block the actors {actors && <Check size={13}/>}</button><ChevronRight size={14}/><button disabled={busy || !actors} onClick={() => record('camera')} className={mode === 'camera' ? 'active' : ''}><span className="step-number">02</span> Perform the camera {cameraTake && <Check size={13}/>}</button><ChevronRight size={14}/><button disabled={mode === 'actors' || mode === 'camera' || !actors} onClick={play}><span className="step-number">03</span> Watch your shot</button></nav>
    <main className="desk">
      <aside className="left-panel panel"><div className="panel-heading"><span><Scan size={16}/> Motion source</span><span className="tag">SANDBOX</span></div>
        <div className="source-intro"><h2>Small objects.<br/><span>Big direction.</span></h2><p>Rehearse with virtual stand-ins.<br/>Replace them with Benton's CV tracks.</p></div>
        <div className="tabletop-label"><span className="status-dot"/> SIMULATED TABLETOP <span>TOP VIEW</span></div>
        <Tabletop poses={poses} manual={manual} editable={sourceMode === 'manual'} activeMode={mode} setManual={setManual} stage={project.stage}/>
        <div className="source-toggle"><button disabled={busy} className={sourceMode === 'script' ? 'selected' : ''} onClick={() => setSourceMode('script')}>Scripted motion</button><button disabled={busy} className={sourceMode === 'manual' ? 'selected' : ''} onClick={() => setSourceMode('manual')}>Drag to rehearse</button></div>
        <p className="hint">{sourceMode === 'manual' ? 'Drag A + B while recording actors. Then drag C during the separate camera pass.' : 'Two actors approach, pause, then retreat. A camera object arcs around their performance.'}</p>
        <div className="divider"/><div className="section-label">OBJECT → VIRTUAL ROLE</div>
        {ROLES.map((role, i) => <div className="binding" key={role}><span className={`object-token ${role}`}>{i === 2 ? <Camera size={17}/> : <Box size={17}/>}</span><div><strong>{['Pencil case', 'Small box', 'Stapler'][i]}</strong><small>{LABEL[role]} <span>· simulated binding</span></small></div><span className={`binding-letter ${role}`}>{['A', 'B', 'C'][i]}</span></div>)}
        <button className="full-width import-button" disabled={busy} onClick={() => setImportOpen(true)}><ArrowUpFromLine size={15}/> Import real CV trajectory</button>
        <SourcePreview tracks={actors?.tracks ?? []} time={time} playing={(mode === 'play' || mode === 'camera') && countdown === null}/>
        <div className="integration-note"><span className="small-dot"/> No webcam opened here. Selection, tracking, and calibration stay in Benton's pipeline.</div>
      </aside>
      <section className="center-panel"><div className="monitor-header"><div><span className="section-label">DIRECTOR MONITOR</span><h1>The encounter <span>01 / INT. HANGAR</span></h1></div><div className="view-toggle"><button className={!overview ? 'selected' : ''} onClick={() => setOverview(false)}><Camera size={14}/> Shot</button><button className={overview ? 'selected' : ''} onClick={() => setOverview(true)}><Layers3 size={14}/> Stage</button></div></div>
        <div className="monitor"><Stage state={{ poses, heading: project.heading, camera: project.camera, overview, time }} captureRef={capture}/><div className="monitor-shade"/><div className="monitor-top"><span className={`monitor-badge ${mode === 'actors' || mode === 'camera' ? 'recording' : ''}`}><span className="small-dot"/>{mode === 'actors' || mode === 'camera' ? `REC · ${mode.toUpperCase()} · MOCK` : sourceLabel}</span><span className="monitor-badge">{overview ? 'STAGE OVERVIEW' : `${project.camera.fov}° FOV · ${project.camera.height.toFixed(1)}u HEIGHT`}</span></div>
          <div className="frame-corner tl"/><div className="frame-corner tr"/><div className="frame-corner bl"/><div className="frame-corner br"/>
          {countdown !== null && <div className="countdown"><span>{countdown}</span><small>{mode === 'actors' ? 'ACTOR PERFORMANCE' : 'CAMERA PASS'} STARTS AT 00:00</small></div>}
          <div className="monitor-bottom"><span>{cameraMissing && mode !== 'camera' ? 'FIXED PREVIEW · NO CAMERA COVERAGE' : overview ? 'BUILT-IN SET · Y-UP' : 'CAMERA 01 · LOOK-AT LOCK'}{missingActors.length > 0 && ` · ${missingActors.length} ACTOR TRACK MISSING`}</span><span className="timecode">00:00:{seconds(time)}</span></div>
        </div>
        <div className="monitor-caption"><span><Focus size={14}/> {mode === 'camera' ? 'Actors replay. Your hand directs the camera.' : 'Same performance. A different point of view.'}</span><button onClick={() => { const data = capture.current?.(); if (data) { download(data, `pocketstage-${seconds(time).replace(':', '-')}.png`); setNotice('Current virtual frame exported as PNG.'); } }}><ArrowDownToLine size={13}/> Frame</button><button title="Toggle stage view" aria-label="Toggle stage view" onClick={() => setOverview(!overview)}><Maximize size={14}/></button></div>
        <section className="timeline panel"><div className="transport"><div className="transport-buttons"><button aria-label="Return to start" disabled={busy} onClick={() => setTime(0)}><SkipBack size={16}/></button><button className="play-button" aria-label={busy ? 'Pause or cancel' : 'Play final shot'} onClick={play}>{busy ? <Pause size={17}/> : <Play size={17} fill="currentColor"/>}</button><span className="transport-time">{seconds(time)} <span>/ {seconds(duration)}</span></span></div><span className="timeline-title">COMPOSITION <span>· SOURCE-TIMED</span></span><button disabled={busy || !actors} onClick={() => { setTime(0); setNotice('Actor timing is locked. Re-record the camera to try a new angle.'); }}><RotateCcw size={13}/> Rewind</button></div>
          <div className="timeline-ruler"><span>TRACK</span><div>{Array.from({ length: 5 }, (_, i) => <span key={i}>{(duration * i / 4).toFixed(1)}s</span>)}</div></div>
          {ROLES.map(role => { const take = role === 'camera' ? cameraTake : actors; const track = take?.tracks.find(t => t.role === role); return <div className="track-row" key={role}><span><i className={`track-dot ${role}`}/>{LABEL[role]}</span><div className={`track-lane ${role}`}><div className="lane-grid"/>{track && track.samples.slice(0, -1).map((s, i) => { const end = Math.min(track.samples[i + 1].t, s.t + .25), left = (s.t + (take?.offset ?? 0)) / duration * 100; return s.position && s.status !== 'LOST' && s.status !== 'UNAVAILABLE' ? <i key={i} style={{ left: `${left}%`, width: `${(end - s.t) / duration * 100}%` }} className={s.status === 'DEGRADED' ? 'degraded' : ''}/> : null; })}<span className="track-name">{track ? `${track.source === 'mock' ? 'MOCK' : 'CV'} · ${track.samples.length} observations` : 'No recorded trajectory'}</span><span className="playhead" style={{ left: `${time / duration * 100}%` }}/></div></div>; })}
          <div className="scrub-row"><span>SCRUB</span><input aria-label="Scene time" type="range" min="0" max={duration} step="0.01" value={time} disabled={busy} onChange={e => setTime(+e.target.value)}/></div>
        </section>
        <div className="notice" role="status"><span className="small-dot"/>{notice}</div>
      </section>
      <aside className="right-panel panel"><div className="panel-heading"><span><Camera size={16}/> Shot controls</span><span className="tag">01</span></div><div className="right-content"><div className="section-label">THE VIRTUAL CAMERA</div><h2>Find your angle.</h2><p className="hint">Record blocking once. Perform a new camera move without touching the actors.</p>
          <label className="field-label">Look-at target<select disabled={busy} value={project.camera.target} onChange={e => setProject(p => ({ ...p, camera: { ...p.camera, target: e.target.value as Project['camera']['target'] } }))}><option value="midpoint">Between both actors</option><option value="actor-a">Actor A</option><option value="actor-b">Actor B</option></select></label>
          <label className="field-label">Field of view <strong>{project.camera.fov}°</strong><input disabled={busy} type="range" min="25" max="80" value={project.camera.fov} onChange={e => setProject(p => ({ ...p, camera: { ...p.camera, fov: +e.target.value } }))}/></label>
          <label className="field-label">Camera height <strong>{project.camera.height.toFixed(1)}u</strong><input disabled={busy} type="range" min="0.5" max="6" step=".1" value={project.camera.height} onChange={e => setProject(p => ({ ...p, camera: { ...p.camera, height: +e.target.value } }))}/></label>
          <label className="field-label">Actor facing<select disabled={busy} value={project.heading} onChange={e => setProject(p => ({ ...p, heading: e.target.value as Project['heading'] }))}><option value="look-at">Face each other</option><option value="fixed">Fixed opposing directions</option></select></label><p className="microcopy">Facing is independent of travel. A retreat never becomes an accidental turn.</p>
          <div className="divider"/><div className="section-label">REHEARSAL CAPTURE <span className="tag">MOCK</span></div>
          <label className="checkbox"><input disabled={busy} type="checkbox" checked={alternate} onChange={e => setAlternate(e.target.checked)}/> Reverse the scripted camera arc</label>
          <button className="record-secondary full-width" disabled={busy} onClick={() => record('actors')}><Circle size={13}/> Record actors <span>8s</span></button>
          <button className="primary full-width" disabled={busy || !actors} onClick={() => record('camera')}><Camera size={16}/> {cameraTake ? 'Retake camera' : 'Record camera'}<ChevronRight size={16}/></button>
          {(mode === 'actors' || mode === 'camera') && <><button className="full-width danger" onClick={stop}><Square size={13}/> Cancel take · preserve previous</button><button className="text-button" onClick={() => setLoseObject(true)}>Simulate tracking loss</button></>}
          <div className="divider"/><div className="section-label">TAKE LIBRARY <span>{project.takes.length} VERSIONS</span></div>
          <label className="field-label">Actor performance<select disabled={busy} value={project.selectedActors ?? ''} onChange={e => { setProject(p => ({ ...p, selectedActors: e.target.value || null, selectedCamera: null })); setTime(0); setNotice('Actor take selected. Select a compatible camera pass or record a new one.'); }}><option value="">None</option>{project.takes.filter(t => t.kind === 'actors').map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
          <label className="field-label">Camera pass<select disabled={busy || !actors} value={project.selectedCamera ?? ''} onChange={e => { setProject(p => ({ ...p, selectedCamera: e.target.value || null })); setTime(0); }}><option value="">Fixed preview only</option>{project.takes.filter(t => t.kind === 'camera' && t.actorTakeId === project.selectedActors).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
          {cameraTake && <label className="field-label">Camera start offset (seconds)<input key={cameraTake.id} disabled={busy} type="number" min="-10" max="10" step="0.1" defaultValue={cameraTake.offset} onBlur={e => { const value = +e.target.value; if (Number.isFinite(value) && Math.abs(value) <= 10 && value !== cameraTake.offset) setProject(p => commitTake(p, { ...cameraTake, id: uid(), name: `${cameraTake.name} · aligned`, offset: value })); else e.target.value = String(cameraTake.offset); }}/></label>}
          <p className="microcopy">Gaps and short camera coverage stay visible. No time stretching or inferred depth.</p>
        </div></aside>
    </main><footer><span><Aperture size={13}/> POCKETSTAGE <span className="slash">/</span> TANGIBLE CINEMATOGRAPHY</span><span>Built-in set · Local playback · No cloud required</span><span>HACKATHON BUILD <span className="status-dot"/></span></footer>
    {importOpen && <ImportDialog project={project} onClose={() => setImportOpen(false)} onAccept={p => { setProject(p); setTime(0); setImportOpen(false); setNotice('Reviewed CV candidate accepted as a new take version. Original candidate remains unchanged; no gap was filled.'); }}/>}
  </div>;
}

function Tabletop({ poses, manual, editable, activeMode, setManual, stage }: { poses: Record<Role, Sample>; manual: Record<Role, Vec2>; editable: boolean; activeMode: Mode; setManual: React.Dispatch<React.SetStateAction<Record<Role, Vec2>>>; stage: Project['stage'] }) {
  const drag = useRef<Role | null>(null);
  const move = (e: React.PointerEvent<SVGSVGElement>) => { if (!drag.current) return; const r = e.currentTarget.getBoundingClientRect(); const x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)), z = Math.max(0, Math.min(1, (e.clientY - r.top) / r.height)); const role = drag.current; setManual(p => ({ ...p, [role]: [(x - .5) * stage.width, (z - .5) * stage.depth] })); };
  return <svg className={`tabletop ${editable ? 'editable' : ''}`} viewBox="0 0 240 160" role="img" aria-label="Simulated object control pad. Drag A, B, or C in manual rehearsal mode." onPointerMove={move} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
    <defs><pattern id="dots" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="8" cy="8" r=".7" fill="#475351"/></pattern></defs><rect width="240" height="160" fill="url(#dots)"/><rect x="10" y="10" width="220" height="140" rx="3" fill="none" stroke="#495452" strokeDasharray="3 4"/><text x="17" y="24" className="table-label">STAGE PLANE</text>
    <path d="M 35 80 Q 120 37 205 80" fill="none" stroke="#859a91" strokeWidth=".7" strokeDasharray="3 4"/>
    {ROLES.map((role, i) => { const useManual = editable && (activeMode === 'idle' || activeMode === 'actors' && role !== 'camera' || activeMode === 'camera' && role === 'camera'); const pos = useManual ? manual[role] : poses[role].position; if (!pos) return null; const x = (pos[0] / stage.width + .5) * 240, y = (pos[1] / stage.depth + .5) * 160; return <g key={role} className={`pad-object ${role}`} transform={`translate(${x},${y})`} onPointerDown={e => { if (!useManual) return; e.currentTarget.ownerSVGElement!.setPointerCapture(e.pointerId); drag.current = role; }}><circle r="19" fill="currentColor" opacity=".08"/><rect x="-12" y="-10" width="24" height="20" rx={i === 0 ? 7 : 3} fill="currentColor" opacity=".9"/><text textAnchor="middle" y="4" fill="#15201e" fontWeight="700" fontSize="10">{['A', 'B', 'C'][i]}</text></g>; })}
  </svg>;
}

function ImportDialog({ project, onClose, onAccept }: { project: Project; onClose: () => void; onAccept: (p: Project) => void }) {
  const [role, setRole] = useState<Role>('actor-a'), [candidate, setCandidate] = useState<unknown>(null), [filename, setFilename] = useState('');
  const [width, setWidth] = useState(1), [depth, setDepth] = useState(1), [reviewed, setReviewed] = useState(false), [error, setError] = useState('');
  const [startNew, setStartNew] = useState(false), [relativeObject, setRelativeObject] = useState(''), [motionScale, setMotionScale] = useState(8), [originX, setOriginX] = useState(0), [originZ, setOriginZ] = useState(0);
  const relativeIds = relativeObjectIds(candidate), isRelative = relativeIds.length > 0;
  function accept() { try {
    if (!reviewed) throw new Error('Confirm the physical stage and coordinate extents first.');
    const track = isRelative
      ? importRelativeMotion(candidate, { role, objectId: relativeObject || relativeIds[0], stageId: project.stage.id, scale: motionScale, origin: [originX, originZ] })
      : importCandidate(candidate, { role, stageId: project.stage.id, sourceWidth: width, sourceDepth: depth, stageWidth: project.stage.width, stageDepth: project.stage.depth });
    const kind = role === 'camera' ? 'camera' : 'actors', old = selectedTake(project, 'actors');
    if (kind === 'camera' && !old) throw new Error('Import an actor performance before a camera pass.');
    const others = kind === 'actors' && !startNew ? (old?.tracks ?? []).filter(t => t.role !== role && t.source === 'cv') : [];
    const tracks = [...others, track];
    const next = commitTake(project, { id: uid(), name: `${kind === 'actors' ? 'CV actors' : 'CV camera'} · ${filename}`, kind, tracks, duration: durationOf(tracks), offset: 0 });
    onAccept(parseProject(next));
  } catch (e) { setError((e as Error).message); } }
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="import-title"><button className="modal-close" aria-label="Close import" onClick={onClose}><X size={18}/></button><span className="section-label">CV → DIRECTOR'S DESK</span><h2 id="import-title">Bring physical motion on stage.</h2><p>Import a calibrated <code>candidates/*.json</code> file or Benton's approximate multi-object <code>motion-tracks.json</code>. This is a reviewed mapping, not tracking or calibration.</p>
    <label className="file-picker"><ArrowUpFromLine size={22}/><strong>{filename || 'Choose a trajectory candidate'}</strong><span>Stage candidate or multi-object motion-tracks.json · local only</span><input type="file" accept=".json,application/json" onChange={async e => { const f = e.target.files?.[0]; if (!f) return; setCandidate(null); setReviewed(false); setError(''); try { if (f.size > 10_000_000) throw new Error('Candidate exceeds 10 MB.'); const parsed = JSON.parse(await f.text()); const ids = relativeObjectIds(parsed); setCandidate(parsed); setRelativeObject(ids[0] ?? ''); setFilename(f.name); } catch (err) { setError((err as Error).message); } }}/></label>
    {isRelative && <><p className="format-badge">APPROXIMATE MASK-CENTROID MOTION · REVIEW REQUIRED</p><label className="field-label">Source object<select value={relativeObject || relativeIds[0]} onChange={e => setRelativeObject(e.target.value)}>{relativeIds.map(id => <option key={id} value={id}>{id}</option>)}</select></label></>}
    <label className="field-label">Assign to<select value={role} onChange={e => setRole(e.target.value as Role)}>{ROLES.map(r => <option key={r} value={r}>{LABEL[r]}</option>)}</select></label>
    {isRelative ? <><div className="two-fields"><label className="field-label">Motion scale<input type="number" min=".01" max="100" step=".1" value={motionScale} onChange={e => setMotionScale(+e.target.value)}/></label><label className="field-label">Stage origin X / Z<span className="inline-inputs"><input type="number" step=".1" value={originX} onChange={e => setOriginX(+e.target.value)}/><input type="number" step=".1" value={originZ} onChange={e => setOriginZ(+e.target.value)}/></span></label></div><p className="microcopy">Normalized image offsets from the measured reference become X/Z control motion. Image Y maps to stage Z. Every usable sample stays <code>DEGRADED</code>. Raw depth differences remain evidence only and do not change height.</p></> : <><div className="two-fields"><label className="field-label">CV stage width<input type="number" min=".01" step=".1" value={width} onChange={e => setWidth(+e.target.value)}/></label><label className="field-label">CV stage depth<input type="number" min=".01" step=".1" value={depth} onChange={e => setDepth(+e.target.value)}/></label></div><p className="microcopy">The current Python CLI exports 1 × 1. Change these only if Benton changes the geometry function's stage dimensions. Mapped to the {project.stage.width} × {project.stage.depth} virtual stage; this is reviewed artistic scale, not meters. Heading is fixed/look-at.</p></>}
    <label className="checkbox"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)}/> {isRelative ? `I reviewed this approximate artistic mapping and confirm the fixed physical setup belongs to ${project.stage.id}.` : `I reviewed these extents and confirm this candidate belongs to this project's unchanged physical stage (${project.stage.id}).`}</label>
    {role !== 'camera' && <label className="checkbox"><input type="checkbox" checked={startNew} onChange={e => setStartNew(e.target.checked)}/> Start a new actor performance, instead of pairing with the existing CV actor. Previous take versions are preserved.</label>}
    <p className="microcopy">Pair Actor A and B from the same Python take ID or motion export. Camera may use a separate take; align its start with the offset control after import. Source evidence remains in the Python project.</p>
    {error && <p className="error" role="alert">{error}</p>}<button className="primary full-width" disabled={!candidate || !reviewed} onClick={accept}><Check size={16}/> Accept as a new take version</button>
  </section></div>;
}
