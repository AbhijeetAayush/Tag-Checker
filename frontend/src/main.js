/** @type {HTMLElement | null} */
const el = document.querySelector("#api-status");
const base = import.meta.env.VITE_API_URL?.replace(/\/$/, "") ?? "";

if (!base) {
  if (el) el.textContent = "VITE_API_URL not set — skipping API check.";
} else {
  fetch(`${base}/health`)
    .then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    })
    .then((j) => {
      if (el) el.textContent = `API OK: ${JSON.stringify(j)}`;
    })
    .catch((e) => {
      if (el)
        el.textContent = `API check failed (${base}/health): ${e.message}. Mixed-content? Use HTTPS API.`;
    });
}
