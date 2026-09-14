import { useEffect, useRef, useState } from 'react';

const API = 'http://127.0.0.1:8765';
type Rect = [number, number, number, number];
type Status = { status: string; generation_id?: string; video_url?: string; error?: string };

export function KlingGenerationPanel({ jobId }: { jobId: string }) {
  const storageKey = `pocketstage-kling:${jobId}`;
  const [ids, setIds] = useState<string[]>([]), [selected, setSelected] = useState('');
  const [image, setImage] = useState(''), [regions, setRegions] = useState<Record<string, Rect>>({});
  const [prompt, setPrompt] = useState('A realistic cinematic scene. Animate each selected subject along its supplied motion path. Fixed camera, preserve identities and setting, no cuts.');
  const [start, setStart] = useState(0), [scale, setScale] = useState(1), [consent, setConsent] = useState(false);
  const [generationId, setGenerationId] = useState<string | null>(() => localStorage.getItem(storageKey));
  const [status, setStatus] = useState<Status | null>(null), [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const drag = useRef<[number, number] | null>(null);
  const request = useRef<string | null>(generationId);
  useEffect(() => {
    let active = true;
    void fetch(`${API}/api/jobs/${jobId}/tracks`).then(async response => {
      if (!response.ok) throw new Error('Could not load extracted coordinates.');
      const tracks = await response.json();
      const available = Object.keys(tracks.tracks_absolute || {});
      if (active) { setIds(available); setSelected(available[0] || ''); }
    }).catch(e => { if (active) setError(String(e.message)); });
    return () => { active = false; };
  }, [jobId]);
  useEffect(() => {
    if (!generationId) return;
    let active = true, timer = 0;
    const poll = async () => {
      try {
        const response = await fetch(`${API}/api/jobs/${jobId}/generations/${generationId}`, { cache: 'no-store' });
        const next: Status = await response.json();
        if (!response.ok) throw new Error(next.error || 'Reconnecting to generation.');
        if (!active) return;
        setStatus(next); setError('');
        if (['REVIEW_READY', 'NEEDS_RECONCILIATION'].includes(next.status)) return;
      } catch (e) { if (active) setError((e as Error).message); }
      if (active) timer = window.setTimeout(poll, 5000);
    };
    void poll();
    return () => { active = false; window.clearTimeout(timer); };
  }, [jobId, generationId]);
  function loadImage(file?: File) {
    if (!file) return;
    if (!['image/png','image/jpeg'].includes(file.type) || file.size > 10 * 1024 * 1024) { setError('Use a PNG/JPEG under 10 MB.'); return; }
    const reader = new FileReader();
    reader.onload = () => { setImage(String(reader.result)); setRegions({}); setError(''); };
    reader.readAsDataURL(file);
  }
  function point(event: React.PointerEvent<HTMLDivElement>): [number, number] {
    const bounds = event.currentTarget.getBoundingClientRect();
    return [Math.max(0, Math.min(1, (event.clientX-bounds.left)/bounds.width)), Math.max(0, Math.min(1, (event.clientY-bounds.top)/bounds.height))];
  }
  async function generate() {
    if (sending || !image || !consent || !Object.keys(regions).length) return;
    setSending(true); setError('');
    request.current ||= crypto.randomUUID().replaceAll('-', '');
    localStorage.setItem(storageKey, request.current);
    try {
      const response = await fetch(`${API}/api/jobs/${jobId}/generations`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ generation_id: request.current, consent, prompt, start_s: start, motion_scale: scale,
          image_base64: image.split(',')[1], bindings: Object.entries(regions).map(([object_id, rect]) => ({ object_id, rect })) }),
      });
      const next: Status = await response.json();
      if (!response.ok) {
        if (response.status === 400) { localStorage.removeItem(storageKey); request.current = null; }
        throw new Error(next.error || 'Generation could not start.');
      }
      setStatus(next); setGenerationId(request.current);
    } catch (e) {
      setError((e as Error).message);
      // A lost response may hide a paid submission: resume its ID, never create a replacement.
      if (request.current) setGenerationId(request.current);
    }
    finally { setSending(false); }
  }
  const locked = sending || !!generationId;
  return <section style={{ marginTop: 24, padding: 20, border: '1px solid #555', borderRadius: 12 }}>
    <h2>Generate with Kling Motion Brush</h2>
    <p>Use a clean starting image. Draw a box around each character and bind it to an extracted object. Five seconds of absolute screen-space motion are sent to Kling—not the source video or depth.</p>
    <fieldset disabled={locked} style={{ border: 0, padding: 0, display: 'grid', gap: 12 }}>
      <label>Starting image <input type="file" accept="image/png,image/jpeg" onChange={e => loadImage(e.target.files?.[0])}/></label>
      <label>Object to bind <select value={selected} onChange={e => setSelected(e.target.value)}>{ids.map(id => <option key={id}>{id}</option>)}</select></label>
      {image && <div style={{ position: 'relative', width: '100%', maxWidth: 440, touchAction: 'none', cursor: 'crosshair' }}
        onPointerDown={e => { if (locked || !selected) return; drag.current = point(e); e.currentTarget.setPointerCapture(e.pointerId); }}
        onPointerUp={e => { if (locked || !drag.current) return; const [x,y] = drag.current, [a,b] = point(e); drag.current = null;
          if (Math.abs(a-x) < .01 || Math.abs(b-y) < .01) return;
          setRegions(current => ({ ...current, [selected]: [Math.min(x,a),Math.min(y,b),Math.abs(a-x),Math.abs(b-y)] })); }}>
        <img src={image} alt="Draw character regions on the starting image" draggable={false} style={{ width: '100%', display: 'block', pointerEvents: 'none' }}/>
        {Object.entries(regions).map(([id,[x,y,w,h]]) => <div key={id} style={{ pointerEvents: 'none', position: 'absolute', left: `${x*100}%`, top: `${y*100}%`, width: `${w*100}%`, height: `${h*100}%`, border: '2px solid #ffcb75', color: '#fff', background: '#ffcb7520', fontSize: 12 }}>{id}</div>)}
      </div>}
      <div>{Object.keys(regions).map(id => <button key={id} type="button" onClick={() => setRegions(current => { const next = { ...current }; delete next[id]; return next; })}>{id} ×</button>)}</div>
      <label>Source start (seconds) <input type="number" min={0} max={600} step={.1} value={start} onChange={e => setStart(Number(e.target.value))}/></label>
      <label>Motion scale <input type="number" min={.05} max={3} step={.05} value={scale} onChange={e => setScale(Number(e.target.value))}/></label>
      <label>Scene prompt <textarea maxLength={2000} rows={4} value={prompt} onChange={e => setPrompt(e.target.value)} style={{ width: '100%' }}/></label>
      <label><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)}/> I reviewed the tracking and regions, and approve uploading this image/masks and one paid or sponsored Kling generation.</label>
    </fieldset>
    <p>Timing and exact path adherence are approximate. Regions are manual rectangles, not precise character segmentation. No 3D or depth control is claimed.</p>
    <button className="pipeline-primary" disabled={locked || !consent || !image || !Object.keys(regions).length || Object.keys(regions).length > 6} onClick={() => void generate()}>{sending ? 'Submitting…' : 'Generate 5-second Kling video'}</button>
    {status && <p role="status">Kling: {status.status}{status.status === 'NEEDS_RECONCILIATION' ? ' — submission uncertain; do not start a replacement.' : ''}</p>}
    {error && <p role="alert">{error}</p>}
    {status?.video_url && <><video src={`${API}${status.video_url}`} controls playsInline style={{ width: '100%', maxHeight: 600 }}/><a href={`${API}${status.video_url}`} target="_blank" rel="noreferrer">Open generated video</a><p>Generated result ready for review—not automatically accepted as accurate motion.</p></>}
    {(status?.status === 'REVIEW_READY' || (!generationId && !sending && error)) && <button onClick={() => { request.current = null; localStorage.removeItem(storageKey); setGenerationId(null); setStatus(null); setError(''); }}>Prepare a new generation</button>}
  </section>;
}
