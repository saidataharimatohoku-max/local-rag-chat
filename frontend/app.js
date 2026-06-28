const form = document.getElementById("chat-form");
const input = document.getElementById("question");
const messages = document.getElementById("messages");
const button = form.querySelector("button");
const fileInput = document.getElementById("file-input");
const uploadButton = document.getElementById("upload-button");
const uploadStatus = document.getElementById("upload-status");

function addBubble(text, role) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;
  bubble.textContent = text;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function addSources(bubble, sources) {
  if (!sources || sources.length === 0) return;
  const wrap = document.createElement("div");
  wrap.className = "sources";
  wrap.textContent = "Sources: ";
  const seen = new Set();
  sources.forEach((s) => {
    if (seen.has(s.title)) return;
    seen.add(s.title);
    const tag = document.createElement("span");
    tag.textContent = s.title;
    wrap.appendChild(tag);
  });
  bubble.appendChild(wrap);
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  addBubble(question, "user");
  input.value = "";
  button.disabled = true;

  const pending = addBubble("Thinking…", "bot");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) throw new Error(`Request failed: ${response.status}`);
    const data = await response.json();
    pending.textContent = data.answer;
    addSources(pending, data.sources);
  } catch (error) {
    pending.textContent = `Error: ${error.message}`;
  } finally {
    button.disabled = false;
    input.focus();
  }
});

uploadButton.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  if (!file) return;

  fileInput.disabled = true;
  uploadButton.classList.add("disabled");
  uploadStatus.className = "upload-status";
  uploadStatus.textContent = `Indexing “${file.name}”…`;

  const body = new FormData();
  body.append("file", file);

  try {
    const response = await fetch("/api/upload", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Failed: ${response.status}`);
    uploadStatus.classList.add("ok");
    uploadStatus.textContent = data.message;
  } catch (error) {
    uploadStatus.classList.add("error");
    uploadStatus.textContent = `Error: ${error.message}`;
  } finally {
    fileInput.disabled = false;
    uploadButton.classList.remove("disabled");
    fileInput.value = "";
  }
});
