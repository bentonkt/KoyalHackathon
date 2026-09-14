import { useEffect, useRef, useState } from 'react';
import type { Track } from '../model';
import { Film, X } from 'lucide-react';

/** Read-only evidence preview; never opens a webcam or computes tracking. */
export function SourcePreview({ tracks, time, playing }: { tracks: Track[]; time: number; playing: boolean }) {
  const video = useRef<HTMLVideoElement>(null), input = useRef<HTMLInputElement>(null);
  const [attached, setAttached] = useState<{ url: string; hash: string; name: string } | null>(null), [message, setMessage] = useState('');
  const expected = tracks.find(t => t.source === 'cv')?.provenance?.proxySha256;
  const visible = attached?.hash === expected ? attached : null;
  useEffect(() => () => { if (attached) URL.revokeObjectURL(attached.url); }, [attached]);
  useEffect(() => {
    const v = video.current;
    if (!v || !visible || v.readyState < 1) return;
    if (Math.abs(v.currentTime - time) > .12 || !playing) v.currentTime = Math.min(time, v.duration || time);
    if (playing) void v.play().catch(() => setMessage('Preview playback was blocked. The virtual scene still plays; click the preview to start video.'));
    else v.pause();
  }, [time, playing, visible]);
  if (!expected) return null;
  async function attach(file: File | undefined) {
    if (!file) return;
    try {
      if (file.size > 100_000_000) throw new Error('Proxy preview is limited to 100 MB.');
      setMessage('Verifying proxy checksum…');
      const bytes = await file.arrayBuffer();
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      const hash = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, '0')).join('');
      if (hash !== expected) throw new Error('This file does not match the candidate proxy_sha256. Select the original canonical proxy.mp4 from the Python take.');
      setAttached({ url: URL.createObjectURL(file), hash, name: file.name }); setMessage('Checksum verified · actor-source clock · session-only preview');
    } catch (e) { setMessage((e as Error).message); }
  }
  return <section className="source-evidence"><input ref={input} hidden type="file" accept="video/*" onChange={e => { void attach(e.target.files?.[0]); e.target.value = ''; }}/>
    {visible ? <><div className="section-label">VERIFIED SOURCE PROXY<button aria-label="Detach source preview" onClick={() => setAttached(null)}><X size={12}/></button></div><video ref={video} src={visible.url} muted playsInline onLoadedMetadata={() => { if (video.current) video.current.currentTime = time; }} onClick={() => { void video.current?.play(); }}/><p className="microcopy">{message}</p></> : <><button className="full-width" onClick={() => input.current?.click()}><Film size={14}/> Attach matching proxy video</button><p className="microcopy">{message || 'Optional: watch the recorded physical motion beside the shot. Files stay on this computer.'}</p></>}
  </section>;
}
