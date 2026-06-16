"use strict";

const form = document.getElementById("gen-form");
const typeSelect = document.getElementById("document_type");
const formatHint = document.getElementById("format-hint");
const statusEl = document.getElementById("status");
const submitBtn = document.getElementById("submit-btn");

let formats = [];

// Populate the format dropdown from the API on load.
async function loadFormats() {
  try {
    const res = await fetch("/api/formats");
    const data = await res.json();
    formats = data.formats || [];
    typeSelect.innerHTML = "";
    for (const f of formats) {
      const opt = document.createElement("option");
      opt.value = f.name;
      opt.textContent = f.name.toUpperCase();
      typeSelect.appendChild(opt);
    }
    updateHint();
  } catch (err) {
    setStatus("Could not load formats: " + err, "err");
  }
}

function currentFormat() {
  return formats.find((f) => f.name === typeSelect.value);
}

function updateHint() {
  const f = currentFormat();
  formatHint.textContent = f ? f.description : "";
}

function setStatus(msg, kind) {
  statusEl.textContent = msg;
  statusEl.className = "status" + (kind ? " " + kind : "");
}

// Pull the filename out of a Content-Disposition header if present.
function filenameFromHeader(header, fallback) {
  if (!header) return fallback;
  const match = /filename\*?=(?:UTF-8'')?["']?([^"';]+)/i.exec(header);
  return match ? decodeURIComponent(match[1]) : fallback;
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

typeSelect.addEventListener("change", updateHint);

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  setStatus("Generating…", "");
  submitBtn.disabled = true;

  try {
    const fd = new FormData(form);
    const res = await fetch("/api/generate", { method: "POST", body: fd });

    if (!res.ok) {
      let msg;
      try {
        const j = await res.json();
        msg = j.error || JSON.stringify(j);
      } catch {
        msg = `HTTP ${res.status}`;
      }
      setStatus("Error: " + msg, "err");
      return;
    }

    const blob = await res.blob();
    const fmt = currentFormat();
    const fallback = "document." + (fmt ? fmt.extension : "bin");
    const name = filenameFromHeader(res.headers.get("Content-Disposition"), fallback);
    triggerDownload(blob, name);
    setStatus("Downloaded " + name, "ok");
  } catch (err) {
    setStatus("Request failed: " + err, "err");
  } finally {
    submitBtn.disabled = false;
  }
});

loadFormats();
