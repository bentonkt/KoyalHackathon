import { useEffect, useRef, useState } from 'react';
import { Aperture, ArrowRight, Check, ChevronRight, Clapperboard, Download, Film, LoaderCircle, MousePointer2, Plus, ScanLine, Trash2, Upload, Video } from 'lucide-react';
import './pipeline.css';
import { KlingGenerationPanel } from './KlingGenerationPanel';

type Phase = 'import' | 'select' | 'analyze' | 'result';
type ObjectRole = 'actor-a' | 'actor-b' | 'camera' | 'reference';
type VideoAsset = { file: File; url: string; duration: number; width: number; height: number };
type TrackedObject = { id: string; label: string; role: ObjectRole; x: number; y: number; time: number; color: string };
type AnalysisStatus = { job_id?: string; status: string; stage: string; progress: number; message: string; error?: string; preview_url?: string; tracks_url?: string };

const COLORS = ['#efb37d', '#73cdb5', '#a99dea', '#e77977', '#85b8eb', '#d3cf78'];
const API_BASE = 'http://127.0.0.1:8765';
const ROLE_LABELS: Record<ObjectRole, string> = { 'actor-a': 'Actor A', 'actor-b': 'Actor B', camera: 'Virtual camera', reference: 'Reference prop' };
const PHASES: Array<{ id: Phase; number: string; label: string }> = [
  { id: 'import', number: '01', label: 'Import video' }, { id: 'select', number: '02', label: 'Select & label' },
  { id: 'analyze', number: '03', label: 'Analyze' }, { id: 'result', number: '04', label: 'Generate & review' },
];
const phaseIndex = (phase: Phase) => PHASES.findIndex(step => step.id === phase);
const formatTime = (seconds: number) => `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
const encodeMetadata = (value: unknown) => {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  let binary = '';
  bytes.forEach(byte => { binary += String.fromCharCode(byte); });
  return window.btoa(binary);
};

export function PipelineWorkspace({ onOpenDirector }: { onOpenDirector: () => void }) {
  const fileInput = useRef<HTMLInputElement>(null), sourceVideo = useRef<HTMLVideoElement>(null), sourceCanvas = useRef<HTMLDivElement>(null), resultCanvas = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<Phase>('import'), [video, setVideo] = useState<VideoAsset | null>(null);
  const [objects, setObjects] = useState<TrackedObject[]>([]), [selectedId, setSelectedId] = useState<string | null>(null);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState<{ url: string; name: string } | null>(null);
  const [videoFrame, setVideoFrame] = useState({ width: 0, height: 0 });
  const [resultVideoSize, setResultVideoSize] = useState({ width: 0, height: 0 });
  const [resultFrame, setResultFrame] = useState({ width: 0, height: 0 });
  const [selectionConfirmed, setSelectionConfirmed] = useState(false);
  const [uploadConsent, setUploadConsent] = useState(false);
  const [analysisJobId, setAnalysisJobId] = useState<string | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<AnalysisStatus | null>(null);
  const [tracksUrl, setTracksUrl] = useState<string | null>(null);
  const analysisRequestId = useRef<string | null>(null);
  const assets = useRef<{ video: VideoAsset | null; result: { url: string; name: string } | null }>({ video: null, result: null });
  assets.current = { video, result };

  useEffect(() => () => { if (assets.current.video) URL.revokeObjectURL(assets.current.video.url); if (assets.current.result?.url.startsWith('blob:')) URL.revokeObjectURL(assets.current.result.url); }, []);
  useEffect(() => {
    if (!analysisJobId) return;
    let cancelled = false, timer = 0;
    const poll = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/jobs/${analysisJobId}`, { cache: 'no-store' });
        const status = await response.json() as AnalysisStatus;
        if (!response.ok) throw new Error(status.error || 'Could not read processing status.');
        if (cancelled) return;
        setAnalysisStatus(status);
        if (status.status === 'READY' && status.preview_url && status.tracks_url) {
          setResultVideoSize({ width: 0, height: 0 });
          setResult({ url: `${API_BASE}${status.preview_url}`, name: 'motion-preview.mp4' });
          setTracksUrl(`${API_BASE}${status.tracks_url}`);
          setAnalysisJobId(null);
          setPhase('result');
          return;
        }
        if (status.status === 'FAILED') { setAnalysisJobId(null); return; }
      } catch (error) {
        if (!cancelled) setAnalysisStatus(current => ({ status: 'RUNNING', stage: current?.stage || 'CONNECTING', progress: current?.progress || 0, message: 'Reconnecting to the local processing service…', error: (error as Error).message }));
      }
      if (!cancelled) timer = window.setTimeout(poll, 1500);
    };
    void poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [analysisJobId]);
  useEffect(() => {
    const canvas = sourceCanvas.current;
    if (!canvas || !video || phase !== 'select') return;
    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      const scale = Math.min(bounds.width / video.width, bounds.height / video.height);
      setVideoFrame({ width: Math.floor(video.width * scale), height: Math.floor(video.height * scale) });
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas); resize();
    return () => observer.disconnect();
  }, [phase, video]);
  useEffect(() => {
    const canvas = resultCanvas.current;
    if (!canvas || !video || phase !== 'result') return;
    const mediaWidth = result && resultVideoSize.width ? resultVideoSize.width : video.width;
    const mediaHeight = result && resultVideoSize.height ? resultVideoSize.height : video.height;
    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      const scale = Math.min(bounds.width / mediaWidth, bounds.height / mediaHeight);
      setResultFrame({ width: Math.floor(mediaWidth * scale), height: Math.floor(mediaHeight * scale) });
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas); resize();
    return () => observer.disconnect();
  }, [phase, result, resultVideoSize, video]);

  function chooseVideo(file?: File) {
    if (!file) return;
    if (!file.type.startsWith('video/')) return setMessage('Choose a video file.');
    if (file.size > 500_000_000) return setMessage('Video must be under 500 MB.');
    const url = URL.createObjectURL(file), probe = document.createElement('video');
    probe.preload = 'metadata'; probe.src = url;
    probe.onloadedmetadata = () => { if (video) URL.revokeObjectURL(video.url); analysisRequestId.current = null; setVideo({ file, url, duration: probe.duration, width: probe.videoWidth, height: probe.videoHeight }); setObjects([]); setSelectedId(null); setSelectionConfirmed(false); setUploadConsent(false); setAnalysisStatus(null); setAnalysisJobId(null); setTracksUrl(null); setResult(null); setMessage(''); setPhase('select'); };
    probe.onerror = () => { URL.revokeObjectURL(url); setMessage('This browser could not read that video.'); };
  }
  function selectAt(event: React.MouseEvent<HTMLDivElement>) {
    if (!video || selectionConfirmed) return;
    const rect = event.currentTarget.getBoundingClientRect(), index = objects.length;
    const next: TrackedObject = { id: crypto.randomUUID(), label: `Object ${index + 1}`, role: index === 0 ? 'actor-a' : index === 1 ? 'actor-b' : index === 2 ? 'camera' : 'reference', x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)), time: 0, color: COLORS[index % COLORS.length] };
    setObjects(current => [...current, next]); setSelectedId(next.id); setMessage('');
  }
  function updateObject(id: string, patch: Partial<TrackedObject>) { setObjects(current => current.map(object => object.id === id ? { ...object, ...patch } : object)); }
  function holdFirstFrame() {
    const player = sourceVideo.current;
    if (!player) return;
    player.pause();
    if (player.currentTime !== 0) player.currentTime = 0;
  }
  function editFirstFrameSelections(messageText = 'Click the object in the first frame to add it.') {
    analysisRequestId.current = null;
    setSelectionConfirmed(false);
    setMessage(messageText);
    window.requestAnimationFrame(holdFirstFrame);
  }
  function confirmFirstFrameSelections() {
    if (!objects.length || objects.some(object => !object.label.trim())) return;
    holdFirstFrame();
    setSelectionConfirmed(true);
    setMessage('Selections confirmed. Playback is now available.');
  }
  function removeObject(id: string) { setObjects(current => current.filter(object => object.id !== id)); if (selectedId === id) setSelectedId(null); editFirstFrameSelections('Selection reopened at the first frame.'); }
  function reset() { if (video) URL.revokeObjectURL(video.url); if (result?.url.startsWith('blob:')) URL.revokeObjectURL(result.url); analysisRequestId.current = null; setVideo(null); setResult(null); setResultVideoSize({ width: 0, height: 0 }); setResultFrame({ width: 0, height: 0 }); setObjects([]); setSelectedId(null); setSelectionConfirmed(false); setUploadConsent(false); setAnalysisJobId(null); setAnalysisStatus(null); setTracksUrl(null); setMessage(''); setPhase('import'); }
  async function beginAnalysis() {
    if (!video || !selectionConfirmed || !objects.length) return;
    if (!uploadConsent) {
      setMessage('Check “Allow fal.ai processing” before starting SAM + depth.');
      return;
    }
    setResult(null);
    setTracksUrl(null);
    setAnalysisJobId(null);
    setAnalysisStatus({ status: 'CONNECTING', stage: 'CONNECTING', progress: 0, message: 'Sending the video to the local processing service…' });
    setPhase('analyze');
    try {
      analysisRequestId.current ||= crypto.randomUUID().replaceAll('-', '');
      const metadata = encodeMetadata({
        upload_consent: true,
        sponsor_coverage: true,
        objects: objects.map(({ label, role, x, y }) => ({ label: label.trim(), role, x, y })),
      });
      const response = await fetch(`${API_BASE}/api/jobs`, {
        method: 'POST',
        headers: {
          'Content-Type': video.file.type || 'application/octet-stream',
          'X-PocketStage-Metadata': metadata,
          'X-PocketStage-Filename': encodeURIComponent(video.file.name),
          'X-PocketStage-Job': analysisRequestId.current,
        },
        body: video.file,
      });
      const status = await response.json() as AnalysisStatus;
      if (!response.ok || !status.job_id) throw new Error(status.error || 'The local processing service did not accept the job.');
      setAnalysisStatus(status);
      setAnalysisJobId(status.job_id);
    } catch (error) {
      setAnalysisStatus({ status: 'FAILED', stage: 'FAILED', progress: 0, message: 'Processing could not start.', error: (error as Error).message });
    }
  }
  function downloadManifest() {
    if (!video) return;
    const data = { schema: 'pocketstage-analysis-selection/1', source: { name: video.file.name, width: video.width, height: video.height, duration_s: video.duration }, objects: objects.map(({ color: _color, ...object }) => ({ ...object, frame_hint_15fps: Math.round(object.time * 15) })), pipeline: ['fal-ai/sam2/video', 'fal-ai/depth-anything-video'] };
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })), anchor = document.createElement('a'); anchor.href = url; anchor.download = 'pocketstage-analysis-selection.json'; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function downloadTracks() {
    if (!tracksUrl) return;
    const anchor = document.createElement('a');
    anchor.href = tracksUrl;
    anchor.download = 'motion-tracks.json';
    anchor.click();
  }
  const selected = objects.find(object => object.id === selectedId);
  const analysisProgress = Math.max(0, Math.min(100, analysisStatus?.progress ?? 0));
  const analysisStep = analysisProgress >= 88 ? 3 : analysisProgress >= 55 ? 2 : analysisProgress >= 12 ? 1 : 0;

  return <div className="pipeline-shell">
    <header className="pipeline-topbar"><a className="pipeline-brand" href="#"><span><Aperture size={22}/></span>PocketStage <small>CAPTURE STUDIO</small></a><div className="pipeline-project"><i/> Untitled scene <span>/</span> Local workspace</div><button className="quiet-button" onClick={onOpenDirector}><Clapperboard size={15}/> Director's Desk <ArrowRight size={14}/></button></header>
    <nav className="pipeline-steps" aria-label="Video tracking workflow">{PHASES.map((step, index) => { const current = step.id === phase, complete = index < phaseIndex(phase); return <div className={`pipeline-step ${current ? 'current' : ''} ${complete ? 'complete' : ''}`} key={step.id}><span>{complete ? <Check size={13}/> : step.number}</span><strong>{step.label}</strong>{index < PHASES.length - 1 && <ChevronRight className="step-arrow" size={15}/>}</div>; })}</nav>

    {phase === 'import' && <main className="pipeline-page import-page"><section className="pipeline-hero"><div className="eyebrow"><ScanLine size={14}/> MARKERLESS PERFORMANCE CAPTURE</div><h1>Turn a tabletop video<br/>into a directed scene.</h1><p>Bring in one short take. Point to the objects that matter, tell us what each one controls, and PocketStage turns their motion into a reviewable shot.</p><div className="promise-row"><span><strong>01</strong> Choose a take</span><span><strong>02</strong> Point and label</span><span><strong>03</strong> Generate motion</span></div></section><section className="upload-card"><div className="upload-icon"><Upload size={26}/></div><span className="card-kicker">START WITH A VIDEO</span><h2>Drop in your performance.</h2><p>Use a fixed camera and keep each object visible when possible. Five to ten seconds works best.</p><button className="pipeline-primary" onClick={() => fileInput.current?.click()}><Film size={17}/> Choose video</button><div className="upload-meta"><span>MOV, MP4</span><span>UP TO 500 MB</span><span>LOCAL UNTIL ANALYSIS</span></div><input ref={fileInput} hidden type="file" accept="video/*" onChange={event => { chooseVideo(event.target.files?.[0]); event.target.value = ''; }}/>{message && <p className="pipeline-error" role="alert">{message}</p>}</section></main>}

    {phase === 'select' && video && <main className="pipeline-page selection-page">
      <section className="selection-main">
        <div className="workspace-heading"><div><span className="card-kicker">SELECT OBJECTS</span><h1>What should we track?</h1><p>Select every object on the first frame. Playback unlocks after confirmation.</p></div><button className="quiet-button" onClick={reset}>Replace video</button></div>
        <div ref={sourceCanvas} className={`source-canvas ${selectionConfirmed ? 'reviewing' : ''}`}>
          <div className="video-frame" style={{ width: videoFrame.width || undefined, height: videoFrame.height || undefined }} onClick={selectAt}>
            <video
              ref={sourceVideo}
              src={video.url}
              controls={selectionConfirmed}
              playsInline
              onLoadedMetadata={event => { if (!selectionConfirmed) { event.currentTarget.pause(); event.currentTarget.currentTime = 0; } }}
              onPlay={event => { if (!selectionConfirmed) { event.currentTarget.pause(); event.currentTarget.currentTime = 0; } }}
              onSeeking={event => { if (!selectionConfirmed && event.currentTarget.currentTime !== 0) event.currentTarget.currentTime = 0; }}
            />
            {objects.map((object, index) => <button key={object.id} className={`object-marker ${selectedId === object.id ? 'selected' : ''}`} style={{ left: `${object.x * 100}%`, top: `${object.y * 100}%`, '--marker': object.color } as React.CSSProperties} onClick={event => { event.stopPropagation(); setSelectedId(object.id); }} aria-label={`Edit ${object.label}`}><span>{index + 1}</span><small>{object.label}</small></button>)}
          </div>
          <div className="canvas-instruction"><MousePointer2 size={13}/> {selectionConfirmed ? 'PLAYBACK UNLOCKED · REVIEW THE VIDEO' : 'FRAME 1 LOCKED · SELECT EVERY OBJECT'}</div>
        </div>
        <div className="video-facts"><span><Video size={14}/>{video.file.name}</span><span>{video.width} × {video.height}</span><span>{formatTime(video.duration)}</span></div>
      </section>
      <aside className="object-panel">
        <div className="object-panel-heading"><div><span className="card-kicker">TRACKING SET</span><h2>{objects.length} {objects.length === 1 ? 'object' : 'objects'}</h2></div><button aria-label="Add another object" onClick={() => editFirstFrameSelections()}><Plus size={15}/></button></div>
        {objects.length === 0 ? <div className="empty-objects"><MousePointer2 size={25}/><strong>No objects selected</strong><p>Click the center of the first object on frame 1.</p></div> : <div className="object-list">{objects.map((object, index) => <button key={object.id} className={selectedId === object.id ? 'selected' : ''} onClick={() => setSelectedId(object.id)}><i style={{ background: object.color }}>{index + 1}</i><span><strong>{object.label}</strong><small>{ROLE_LABELS[object.role]} · {formatTime(object.time)}</small></span><ChevronRight size={14}/></button>)}</div>}
        {selected && <div className="object-editor"><div className="editor-title"><span>OBJECT DETAILS</span><button aria-label={`Remove ${selected.label}`} onClick={() => removeObject(selected.id)}><Trash2 size={14}/></button></div><label>Name<input maxLength={24} value={selected.label} onChange={event => updateObject(selected.id, { label: event.target.value })}/></label><label>Controls<select value={selected.role} onChange={event => updateObject(selected.id, { role: event.target.value as ObjectRole })}>{Object.entries(ROLE_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><p>Prompt at {formatTime(selected.time)} · {Math.round(selected.x * video.width)}, {Math.round(selected.y * video.height)} px</p></div>}
        <div className="object-panel-footer">
          <p>{message || (selectionConfirmed ? 'Playback is unlocked. Review the take, then start analysis.' : objects.length ? 'Label every object, then confirm this first-frame tracking set.' : 'Add at least one object to continue.')}</p>
          {selectionConfirmed && <label className="upload-consent"><input type="checkbox" checked={uploadConsent} onChange={event => { setUploadConsent(event.target.checked); if (event.target.checked) setMessage('Ready to run SAM 2 + Depth Anything.'); }}/><span><strong>Allow fal.ai processing</strong><small>I consent to upload this clip and confirm sponsored SAM 2 + Depth Anything processing.</small></span></label>}
          {selectionConfirmed && <button className="quiet-button edit-selection-button" onClick={() => editFirstFrameSelections('Selection reopened at the first frame.')}><MousePointer2 size={15}/> Edit first-frame selections</button>}
          <button className="pipeline-primary" disabled={!objects.length || objects.some(object => !object.label.trim())} onClick={selectionConfirmed ? () => void beginAnalysis() : confirmFirstFrameSelections}>
            {selectionConfirmed ? <><ScanLine size={16}/> Run SAM + depth <ArrowRight size={15}/></> : <><Check size={16}/> Confirm selections & enable playback</>}
          </button>
        </div>
      </aside>
    </main>}

    {phase === 'analyze' && video && <main className="pipeline-page analysis-page">
      <section className="analysis-copy"><span className="card-kicker">ANALYZING TAKE</span><h1>Finding motion<br/>across every frame.</h1><p>The local service is running the established fal.ai pipeline: one canonical video upload, an independent SAM 2 pass for every selected object, and one shared Depth Anything pass.</p><div className="analysis-file"><Film size={18}/><span><strong>{video.file.name}</strong><small>{objects.length} labeled objects · {formatTime(video.duration)}</small></span></div></section>
      <section className={`analysis-card ${analysisStatus?.status === 'FAILED' ? 'failed' : ''}`}>
        <div className="analysis-orbit">{analysisStatus?.status === 'FAILED' ? <ScanLine size={38}/> : <><LoaderCircle className="spinner" size={54}/><ScanLine size={23}/></>}</div>
        <h2>{analysisStatus?.status === 'FAILED' ? 'Processing stopped' : analysisStatus?.message || 'Connecting to the local service…'}</h2>
        <div className="analysis-progress" aria-label={`Analysis ${analysisProgress}% complete`}><i style={{ width: `${analysisProgress}%` }}/></div>
        <div className="analysis-jobs"><Job label="Canonical video and timing validated" done={analysisStep >= 1}/><Job label="Shared Depth Anything result validated" done={analysisStep >= 2}/><Job label={`SAM 2 masks validated · ${objects.length} objects`} done={analysisStep >= 3}/></div>
        {analysisStatus?.error && <p className="analysis-error" role="alert">{analysisStatus.error}</p>}
        {analysisStatus?.status === 'FAILED' && <div className="analysis-recovery"><button className="quiet-button" onClick={() => setPhase('select')}>Back to selections</button><button className="pipeline-primary" onClick={() => void beginAnalysis()}>Check or retry safely</button></div>}
        <span className="demo-badge">LIVE PIPELINE · SAM 2 VIDEO + VIDEO DEPTH ANYTHING</span>
      </section>
    </main>}

    {phase === 'result' && video && result && <main className="pipeline-page result-page"><section className="result-main"><div className="workspace-heading"><div><span className="card-kicker">GENERATE & REVIEW</span><h1>Your tracked take is ready.</h1><p>Review the SAM 2 motion and shared Depth Anything output before directing the scene.</p></div><span className="result-status ready"><i/>PIPELINE COMPLETE</span></div><div ref={resultCanvas} className="result-player"><div className="result-video-frame" style={{ width: resultFrame.width || undefined, height: resultFrame.height || undefined }}><video src={result.url} controls autoPlay muted playsInline onLoadedMetadata={event => setResultVideoSize({ width: event.currentTarget.videoWidth, height: event.currentTarget.videoHeight })}/></div></div><div className="result-actions"><button className="quiet-button" onClick={() => { analysisRequestId.current = null; setSelectionConfirmed(false); setUploadConsent(false); setMessage('Selection reopened at the first frame.'); setPhase('select'); }}><MousePointer2 size={15}/> Edit selections</button><button className="quiet-button" onClick={downloadManifest}><Download size={15}/> Export selection</button><button className="pipeline-primary" disabled={!tracksUrl} onClick={downloadTracks}><Download size={15}/> Download motion tracks</button></div></section><aside className="result-summary"><span className="card-kicker">TRACK SUMMARY</span><h2>{objects.length} labeled objects</h2><div className="summary-list">{objects.map((object, index) => <div key={object.id}><i style={{ background: object.color }}>{index + 1}</i><span><strong>{object.label}</strong><small>{ROLE_LABELS[object.role]}</small></span><Check size={15}/></div>)}</div><div className="pipeline-stack"><span>ANALYSIS STACK</span><strong>SAM 2 Video</strong><small>Independent object masks</small><strong>Video Depth Anything</strong><small>One shared relative-depth pass</small></div><button className="pipeline-primary" onClick={onOpenDirector}><Clapperboard size={16}/> Continue to Director's Desk <ArrowRight size={15}/></button><p className="result-note">The Director’s Desk stays downstream: it turns reviewed trajectories into actors, cameras, and a virtual shot.</p></aside></main>}
    {phase === 'result' && analysisStatus?.job_id && <KlingGenerationPanel key={analysisStatus.job_id} jobId={analysisStatus.job_id}/>}
  </div>;
}

function Job({ label, done }: { label: string; done: boolean }) { return <div className={done ? 'done' : ''}><span>{done ? <Check size={13}/> : <LoaderCircle className="spinner" size={13}/>}</span>{label}</div>; }
