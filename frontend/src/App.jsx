import { useEffect, useState } from "react";
import { api } from "./api";
import ResumePool from "./components/ResumePool.jsx";
import ScreenForm from "./components/ScreenForm.jsx";
import ScreeningView from "./components/ScreeningView.jsx";

// App = layout + "which screening is open". All data fetching is delegated to children.
export default function App() {
  const [current, setCurrent] = useState(null); // screening id, or null = new screening form
  const [history, setHistory] = useState([]);

  const loadHistory = () => api.screenings().then(setHistory).catch(() => {});
  useEffect(() => { loadHistory(); }, [current]);

  return (
    <div className="shell">
      <aside className="side">
        <h1>AI Recruiter</h1>
        <ResumePool />
        <section>
          <h2>Past screenings</h2>
          <button className={"nav" + (current === null ? " on" : "")} onClick={() => setCurrent(null)}>+ New screening</button>
          {history.map((s) => (
            <button key={s.id} className={"nav" + (current === s.id ? " on" : "")} onClick={() => setCurrent(s.id)}>
              <span>{s.title || `Screening #${s.id}`}</span>
              <small className={"tag " + s.status}>{s.status.replace("_", " ")}</small>
            </button>
          ))}
        </section>
      </aside>
      <main className="main">
        {current === null ? <ScreenForm onStarted={setCurrent} /> : <ScreeningView key={current} id={current} />}
      </main>
    </div>
  );
}
