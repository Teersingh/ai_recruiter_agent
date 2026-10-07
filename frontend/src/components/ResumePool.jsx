
import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const OK = /\.(pdf|docx|txt)$/i;
const CHUNK = 20; // files per request, so 100+ resumes never hit a request-size/timeout limit

// Upload many resumes (or a whole folder) and watch the background parser work through them.
export default function ResumePool() {
  const [data, setData] = useState({ candidates: [], counts: {} });
  const [msg, setMsg] = useState("");
  const files = useRef();
  const folder = useRef();

  const load = () => api.candidates().then(setData).catch((e) => setMsg(e.message));
  const pending = data.counts.pending || 0;

  useEffect(() => { load(); }, []);
  useEffect(() => { // poll only while something is being parsed
    if (!pending) return;
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [pending]);

  async function onPick(e) {
    const all = [...e.target.files];
    const picked = all.filter((f) => OK.test(f.name));
    e.target.value = "";
    if (!picked.length) return setMsg("No PDF, DOCX or TXT files found.");
    let queued = 0, skipped = [];
    try {
      for (let i = 0; i < picked.length; i += CHUNK) {
        setMsg(`Uploading ${Math.min(i + CHUNK, picked.length)} / ${picked.length}…`);
        const r = await api.upload(picked.slice(i, i + CHUNK));
        queued += r.queued; skipped.push(...r.errors);
      }
      const dup = skipped.filter((s) => s.error.startsWith("Duplicate")).length;
      setMsg(`${queued} queued` + (dup ? `, ${dup} duplicates skipped` : "") +
        (skipped.length - dup ? `, ${skipped.length - dup} unreadable` : "") +
        (all.length - picked.length ? `, ${all.length - picked.length} non-resume files ignored` : ""));
    } catch (err) { setMsg(err.message); }
    load();
  }

  const { parsed = 0, failed = 0 } = data.counts;
  return (
    <section>
      <h2>Resume pool</h2>
      <p className="big">{data.candidates.length} <span>resumes</span></p>
      <p className="muted">{parsed} ready{pending ? ` · ${pending} parsing…` : ""}{failed ? ` · ${failed} text-only` : ""}</p>
      <input ref={files} type="file" multiple accept=".pdf,.docx,.txt" hidden onChange={onPick} />
      <input ref={folder} type="file" webkitdirectory="" directory="" multiple hidden onChange={onPick} />
      <div className="row">
        <button className="btn" onClick={() => files.current.click()}>Upload files</button>
        <button className="btn" onClick={() => folder.current.click()}>Upload folder</button>
      </div>
      {failed > 0 && (
        <button className="btn" style={{ marginTop: 8 }}
          onClick={() => api.reparseFailed().then(() => { setMsg("Retrying failed resumes…"); load(); })}>
          Retry {failed} failed
        </button>
      )}
      {msg && <p className="muted">{msg}</p>}
    </section>
  );
}

// import { useEffect, useRef, useState } from "react";
// import { api } from "../api";

// // Upload many resumes at once and watch the background parser work through them.
// export default function ResumePool() {
//   const [data, setData] = useState({ candidates: [], counts: {} });
//   const [msg, setMsg] = useState("");
//   const input = useRef();

//   const load = () => api.candidates().then(setData).catch((e) => setMsg(e.message));
//   useEffect(() => {
//     load();
//     const t = setInterval(load, 4000); // keeps "parsing…" counts live
//     return () => clearInterval(t);
//   }, []);

//   async function onFiles(e) {
//     const files = e.target.files;
//     if (!files.length) return;
//     setMsg("Uploading…");
//     try {
//       const r = await api.upload(files);
//       setMsg(`${r.queued} queued` + (r.errors.length ? `, ${r.errors.length} skipped: ${r.errors[0].error}` : ""));
//       load();
//     } catch (err) { setMsg(err.message); }
//     input.current.value = "";
//   }

//   const { pending = 0, parsed = 0, failed = 0 } = data.counts;
//   return (
//     <section>
//       <h2>Resume pool</h2>
//       <p className="big">{data.candidates.length} <span>resumes</span></p>
//       <p className="muted">{parsed} ready{pending ? ` · ${pending} parsing…` : ""}{failed ? ` · ${failed} text-only` : ""}</p>
//       <input ref={input} type="file" multiple accept=".pdf,.docx,.txt" hidden onChange={onFiles} />
//       <button className="btn" onClick={() => input.current.click()}>Upload resumes</button>
//       {msg && <p className="muted">{msg}</p>}
//     </section>
//   );
// }
