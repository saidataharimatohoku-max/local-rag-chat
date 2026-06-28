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

  const label = document.createElement("span");
  label.className = "sources-label";
  label.textContent = "Sources:";
  wrap.appendChild(label);

  const seen = new Set();
  sources.forEach((s) => {
    if (seen.has(s.title)) return;
    seen.add(s.title);

    const details = document.createElement("details");
    details.className = "source";

    const summary = document.createElement("summary");
    summary.textContent = s.title;
    details.appendChild(summary);

    const snippet = document.createElement("div");
    snippet.className = "snippet";
    const text = s.content || "";
    snippet.textContent = text.length > 400 ? `${text.slice(0, 400)}…` : text;
    details.appendChild(snippet);

    wrap.appendChild(details);
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
  let answerText = "";
  let sources = [];
  let started = false;

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok || !response.body) {
      throw new Error(`Request failed: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const block of events) {
        const eventMatch = block.match(/^event: (.*)$/m);
        const dataMatch = block.match(/^data: (.*)$/m);
        if (!eventMatch || !dataMatch) continue;
        const type = eventMatch[1];
        const payload = JSON.parse(dataMatch[1]);

        if (type === "sources") {
          sources = payload;
        } else if (type === "token") {
          if (!started) {
            pending.textContent = "";
            started = true;
          }
          answerText += payload;
          pending.textContent = answerText;
          messages.scrollTop = messages.scrollHeight;
        }
      }
    }

    if (!started) pending.textContent = answerText || "(no answer)";
    addSources(pending, sources);
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
