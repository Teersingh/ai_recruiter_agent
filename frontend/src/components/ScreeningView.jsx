import { Fragment, useEffect, useState } from "react";
import { api } from "../api";

const toolLabel = {
  parse_jd: "Read the job description", retrieve_candidates: "Loaded resumes from database",
  match_candidates: "Compared candidates with requirements", rank_shortlist: "Ranked and proposed a shortlist",
  save_results: "Saved scores and evidence", request_approval: "Asked for your approval",
};

// One screening: live agent steps -> reviewable evidence table -> approve -> Excel.
export default function ScreeningView({ id }) {
  const [s, setS] = useState(null);
  const [open, setOpen] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [answer, setAnswer] = useState("");

  const load = () => api.screening(id).then(setS).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, [id]);
  useEffect(() => { // poll while the agent is still working
    if (s?.status !== "running") return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [s?.status]);

  if (!s) return <p className="muted">{err || "Loading…"}</p>;
  const locked = s.status === "approved";
  const shortlisted = (s.results || []).filter((r) => r.shortlisted).length;

  async function toggle(r) {
    try { await api.override(s.id, r.id, !r.shortlisted); load(); } catch (e) { setErr(e.message); }
  }
  async function approve() {
    try { setS(await api.approve(s.id)); load(); } catch (e) { setErr(e.message); }
  }
  async function ask() {
    setAnswer("Thinking…");
    try { setAnswer((await api.ask(s.id, q)).answer); } catch (e) { setAnswer(e.message); }
  }

  return (
    <div>
      <div className="panel">
        <h2>{s.title || "Screening"} <small className={"tag " + s.status}>{s.status.replace("_", " ")}</small></h2>
        <p className="muted">{s.hr_request}</p>
        {s.requirements?.must_have_skills && (
          <p>
            {s.requirements.must_have_skills.map((k) => <span key={k} className="chip">{k}</span>)}
            {s.requirements.min_experience_years && <span className="chip">{s.requirements.min_experience_years}+ yrs</span>}
            {s.requirements.nice_to_have_skills.map((k) => <span key={k} className="chip soft">{k}</span>)}
          </p>
        )}
        <ol className="trace">
          {s.trace.map((t) => (
            <li key={t.step}><b>{toolLabel[t.tool] || t.tool}</b><span>{t.observation}</span></li>
          ))}
          {s.status === "running" && <li className="live"><b>Working…</b></li>}
        </ol>
        {s.status === "needs_input" && <p className="warn">{s.summary}</p>}
        {s.status === "failed" && <p className="error">The run failed: {s.error}</p>}
        {err && <p className="error">{err}</p>}
      </div>

      {s.results?.length > 0 && (
        <div className="panel">
          <div className="row between">
            <div><h2>{shortlisted} shortlisted of {s.results.length}</h2><p className="muted">{s.summary}</p></div>
            {locked
              ? <a className="btn primary" href={api.downloadUrl(s.id)}>Download Excel</a>
              : <button className="btn primary" onClick={approve}>Approve and create Excel</button>}
          </div>
          <table>
            <thead><tr><th>#</th><th>Candidate</th><th>Score</th><th>Experience</th>
              {s.results[0].checks.map((c) => <th key={c.requirement}>{c.requirement}</th>)}<th>Decision</th></tr></thead>
            <tbody>
              {s.results.map((r) => (
                <Fragment key={r.id}>
                  <tr className="clickable" onClick={() => setOpen(open === r.id ? null : r.id)}>
                    <td>{r.rank}</td><td><b>{r.name}</b><br /><small>{r.email}</small></td>
                    <td>{r.score}</td><td>{r.experience_years} yrs</td>
                    {r.checks.map((c) => <td key={c.requirement} className={c.met ? "yes" : "no"}>{c.candidate_value}</td>)}
                    <td onClick={(e) => e.stopPropagation()}>
                      <button className={"pill " + (r.shortlisted ? "on" : "")} disabled={locked} onClick={() => toggle(r)}>
                        {r.shortlisted ? "Shortlisted" : "Not shortlisted"}{r.overridden ? " *" : ""}
                      </button>
                    </td>
                  </tr>
                  {open === r.id && (
                    <tr><td colSpan={5 + r.checks.length} className="evidence">
                      {r.checks.map((c) => (
                        <div key={c.requirement} className="ev">
                          <b>{c.requirement}</b> <small>{c.required_value || (c.required ? "Required" : "Preferred")} · candidate: {c.candidate_value}</small>
                          <blockquote className={c.met ? "" : "miss"}>{c.evidence || "Not found anywhere in the resume"}</blockquote>
                        </div>
                      ))}
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
          <p className="muted">* changed by you. Click a row to see the resume lines behind every Yes/No.</p>
          <div className="row">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask: why was Rahul rejected? Who has the most experience?" />
            <button className="btn" disabled={!q.trim()} onClick={ask}>Ask</button>
          </div>
          {answer && <p className="answer">{answer}</p>}
        </div>
      )}
    </div>
  );
}
