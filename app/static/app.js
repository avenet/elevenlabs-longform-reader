const form = document.getElementById("reading-form");
const submitBtn = document.getElementById("submit-btn");
const formError = document.getElementById("form-error");
const voiceSelect = document.getElementById("voice_id");
const textInput = document.getElementById("text");
const textField = document.getElementById("text-field");
const fileInput = document.getElementById("file");
const fileField = document.getElementById("file-field");
const fileChosen = document.getElementById("file-chosen");
const fileName = document.getElementById("file-name");
const fileClear = document.getElementById("file-clear");
const playerPanel = document.getElementById("player-panel");
const readingTitle = document.getElementById("reading-title");
const readingStatus = document.getElementById("reading-status");
const sectionList = document.getElementById("section-list");
const audio = document.getElementById("audio");

let currentReadingId = null;
let pollTimer = null;
let playIndex = 0;
let autoAdvance = true;

function syncSourceInputs() {
  const hasFile = Boolean(fileInput.files && fileInput.files[0]);
  const hasText = Boolean(textInput.value.trim());

  textInput.disabled = hasFile;
  textField.classList.toggle("is-disabled", hasFile);
  fileInput.disabled = hasText && !hasFile;
  fileField.classList.toggle("is-disabled", hasText && !hasFile);

  if (hasFile) {
    fileChosen.hidden = false;
    fileName.textContent = fileInput.files[0].name;
  } else {
    fileChosen.hidden = true;
    fileName.textContent = "";
  }
}

function clearSelectedFile() {
  fileInput.value = "";
  syncSourceInputs();
}

async function loadVoices() {
  try {
    const response = await fetch("/api/voices");
    const voices = await response.json();
    voiceSelect.innerHTML = "";
    for (const voice of voices) {
      const option = document.createElement("option");
      option.value = voice.voice_id;
      option.textContent = voice.name;
      voiceSelect.appendChild(option);
    }
  } catch {
    voiceSelect.innerHTML = '<option value="">Default voice</option>';
  }
}

function showError(message) {
  formError.hidden = !message;
  formError.textContent = message || "";
}

function statusLabel(status) {
  const labels = {
    queued: "Queued",
    processing: "Generating speech…",
    ready: "Ready",
    partial: "Partially ready",
    failed: "Failed",
    pending: "Pending",
  };
  return labels[status] || status;
}

function renderSections(reading) {
  sectionList.innerHTML = "";
  for (const section of reading.sections) {
    const item = document.createElement("li");
    item.dataset.index = String(section.index);
    if (section.index === playIndex) {
      item.classList.add("active");
    }

    const indexEl = document.createElement("span");
    indexEl.className = "section-index";
    indexEl.textContent = String(section.index + 1).padStart(2, "0");

    const body = document.createElement("div");
    const preview = document.createElement("p");
    preview.className = "section-preview";
    preview.textContent = section.preview || "";
    const meta = document.createElement("p");
    meta.className = "section-meta";
    meta.textContent = `${section.char_count} chars`;
    body.append(preview, meta);

    const badge = document.createElement("span");
    badge.className = `badge ${section.status}`;
    badge.textContent = statusLabel(section.status);

    item.append(indexEl, body, badge);
    item.addEventListener("click", () => {
      if (section.status === "ready") {
        autoAdvance = true;
        playSection(reading.id, section.index);
      }
    });
    sectionList.appendChild(item);
  }
}

function playSection(readingId, index) {
  playIndex = index;
  audio.src = `/api/readings/${readingId}/sections/${index}/audio?t=${Date.now()}`;
  audio.play().catch(() => {});
  for (const item of sectionList.querySelectorAll("li")) {
    item.classList.toggle("active", Number(item.dataset.index) === index);
  }
}

function maybeStartPlayback(reading) {
  if (!autoAdvance) {
    return;
  }
  const firstReady = reading.sections.find((section) => section.status === "ready");
  if (!firstReady) {
    return;
  }
  const hasSource = Boolean(audio.getAttribute("src"));
  if (!hasSource || audio.paused) {
    const next = reading.sections.find(
      (section) => section.index >= playIndex && section.status === "ready"
    );
    if (next && (!hasSource || next.index !== playIndex || audio.paused)) {
      playSection(reading.id, next.index);
    }
  }
}

async function pollReading(readingId) {
  const response = await fetch(`/api/readings/${readingId}`);
  if (!response.ok) {
    throw new Error("Could not load reading status");
  }
  const reading = await response.json();
  readingTitle.textContent = reading.title;
  readingStatus.textContent = statusLabel(reading.status);
  renderSections(reading);
  maybeStartPlayback(reading);

  const unfinished = reading.sections.some(
    (section) => section.status === "pending" || section.status === "processing"
  );
  if (unfinished) {
    pollTimer = setTimeout(() => pollReading(readingId), 1500);
  }
}

audio.addEventListener("ended", async () => {
  if (!currentReadingId || !autoAdvance) {
    return;
  }
  const response = await fetch(`/api/readings/${currentReadingId}`);
  if (!response.ok) {
    return;
  }
  const reading = await response.json();
  const next = reading.sections.find(
    (section) => section.index === playIndex + 1 && section.status === "ready"
  );
  if (next) {
    playSection(reading.id, next.index);
    return;
  }
  const laterPending = reading.sections.some(
    (section) =>
      section.index > playIndex &&
      (section.status === "pending" || section.status === "processing")
  );
  if (laterPending) {
    pollTimer = setTimeout(() => pollReading(currentReadingId), 1200);
  }
});

textInput.addEventListener("input", syncSourceInputs);
fileInput.addEventListener("change", syncSourceInputs);
fileClear.addEventListener("click", clearSelectedFile);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError("");
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }

  const text = textInput.value.trim();
  const file = fileInput.files[0];
  if (!text && !file) {
    showError("Paste some text or upload a .txt / .pdf file.");
    return;
  }

  const data = new FormData();
  const title = document.getElementById("title").value.trim();
  if (title) {
    data.append("title", title);
  }
  if (voiceSelect.value) {
    data.append("voice_id", voiceSelect.value);
  }
  if (file) {
    data.append("file", file);
  } else {
    data.append("text", text);
  }

  submitBtn.disabled = true;
  try {
    const response = await fetch("/api/readings", {
      method: "POST",
      body: data,
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Failed to create reading");
    }

    currentReadingId = payload.id;
    playIndex = 0;
    autoAdvance = true;
    audio.removeAttribute("src");
    playerPanel.hidden = false;
    readingTitle.textContent = payload.title;
    readingStatus.textContent = statusLabel(payload.status);
    renderSections(payload);
    await pollReading(payload.id);
  } catch (error) {
    showError(error.message || "Something went wrong");
  } finally {
    submitBtn.disabled = false;
  }
});

syncSourceInputs();
loadVoices();
