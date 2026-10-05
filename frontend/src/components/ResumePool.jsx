import { useEffect, useRef, useState } from "react";
import { api } from "../api";

// Upload many resumes at once and watch the background parser work through them.
export default function ResumePool() {
  const [data, setData] = useState({ candidates: [], counts: {} });
  const [msg, setMsg] = useState("");
  const input = useRef();

  const load = () => api.candidates().then(setData).catch((e) => setMsg(e.message));
  useEffect(() => {
    load();
    const t = setInterval(load, 4000); // keeps "parsing…" counts live
    return () => clearInterval(t);
  }, []);

  async function onFiles(e) {
    const files = e.target.files;
    if (!files.length) return;
    setMsg("Uploading…");
    try {
      const r = await api.upload(files);
      setMsg(`${r.queued} queued` + (r.errors.length ? `, ${r.errors.length} skipped: ${r.errors[0].error}` : ""));
      load();
    } catch (err) { setMsg(err.message); }
    input.current.value = "";
  }

  const { pending = 0, parsed = 0, failed = 0 } = data.counts;
  return (
    <section>
      <h2>Resume pool</h2>
      <p className="big">{data.candidates.length} <span>resumes</span></p>
      <p className="muted">{parsed} ready{pending ? ` · ${pending} parsing…` : ""}{failed ? ` · ${failed} text-only` : ""}</p>
      <input ref={input} type="file" multiple accept=".pdf,.docx,.txt" hidden onChange={onFiles} />
      <button className="btn" onClick={() => input.current.click()}>Upload resumes</button>
      {msg && <p className="muted">{msg}</p>}
    </section>
  );
}
