// Every backend call lives here, so components never build URLs or parse errors themselves.
const BASE = import.meta.env.VITE_API_URL || "/api";

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  candidates: () => req("/candidates"),
  upload: (files) => {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    return req("/candidates/upload", { method: "POST", body: fd });
  },
  startScreening: ({ hrRequest, jdText, jdFile }) => {
    const fd = new FormData();
    fd.append("hr_request", hrRequest);
    fd.append("jd_text", jdText || "");
    if (jdFile) fd.append("jd_file", jdFile);
    return req("/agent/screen", { method: "POST", body: fd });
  },
  reparseFailed: () => req("/candidates/reparse-failed", { method: "POST" }),
  ask: (id, question, history) =>
    req(`/agent/ask/${id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, history }) }),
  screenings: () => req("/screenings"),
  screening: (id) => req(`/screenings/${id}`),
  override: (sid, rid, shortlisted) =>
    req(`/screenings/${sid}/results/${rid}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ shortlisted }) }),
  approve: (id) => req(`/screenings/${id}/approve`, { method: "POST" }),
  downloadUrl: (id) => `${BASE}/screenings/${id}/download`,
};


// // Every backend call lives here, so components never build URLs or parse errors themselves.
// const BASE = import.meta.env.VITE_API_URL || "/api";

// async function req(path, opts = {}) {
//   const res = await fetch(BASE + path, opts);
//   if (!res.ok) {
//     let msg = res.statusText;
//     try { msg = (await res.json()).detail || msg; } catch {}
//     throw new Error(msg);
//   }
//   return res.json();
// }

// export const api = {
//   candidates: () => req("/candidates"),
//   upload: (files) => {
//     const fd = new FormData();
//     [...files].forEach((f) => fd.append("files", f));
//     return req("/candidates/upload", { method: "POST", body: fd });
//   },
//   startScreening: ({ hrRequest, jdText, jdFile }) => {
//     const fd = new FormData();
//     fd.append("hr_request", hrRequest);
//     fd.append("jd_text", jdText || "");
//     if (jdFile) fd.append("jd_file", jdFile);
//     return req("/agent/screen", { method: "POST", body: fd });
//   },
//   ask: (id, question) =>
//     req(`/agent/ask/${id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) }),
//   screenings: () => req("/screenings"),
//   screening: (id) => req(`/screenings/${id}`),
//   override: (sid, rid, shortlisted) =>
//     req(`/screenings/${sid}/results/${rid}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ shortlisted }) }),
//   approve: (id) => req(`/screenings/${id}/approve`, { method: "POST" }),
//   downloadUrl: (id) => `${BASE}/screenings/${id}/download`,
// };
