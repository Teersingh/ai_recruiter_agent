import { useState } from "react";
import { api } from "../api";

// The HR "prompt box": instruction + JD (pasted or uploaded).
export default function ScreenForm({ onStarted }) {
  const [hrRequest, setHr] = useState("Analyze these resumes for the Python Backend Developer position. Shortlist candidates with FastAPI, Python, PostgreSQL and 2+ years experience.");
  const [jdText, setJd] = useState("");
  const [jdFile, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function submit() {
    setBusy(true); setErr("");
    try {
      const { screening_id } = await api.startScreening({ hrRequest, jdText, jdFile });
      onStarted(screening_id);
    } catch (e) { setErr(e.message); setBusy(false); }
  }

  return (
    <div className="panel">
      <h2>What should I look for?</h2>
      <label>Your request</label>
      <textarea rows={3} value={hrRequest} onChange={(e) => setHr(e.target.value)} />
      <label>Job description <small>(optional if your request already lists the criteria)</small></label>
      <textarea rows={8} placeholder="Paste the JD here…" value={jdText} onChange={(e) => setJd(e.target.value)} />
      <div className="row">
        <label className="file">
          {jdFile ? jdFile.name : "…or attach a JD file (PDF, DOCX, TXT)"}
          <input type="file" hidden accept=".pdf,.docx,.txt" onChange={(e) => setFile(e.target.files[0])} />
        </label>
        <button className="btn primary" disabled={busy || !hrRequest.trim()} onClick={submit}>
          {busy ? "Starting…" : "Analyze all resumes"}
        </button>
      </div>
      {err && <p className="error">{err}</p>}
    </div>
  );
}
