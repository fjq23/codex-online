const workspaceNode = document.querySelector("#terminal-workspace");
const keyStatusNode = document.querySelector("#terminal-key-status");
const keyStripNode = document.querySelector("#key-strip");
const frameNode = document.querySelector("#terminal-frame");

const extraKeyRows = [
  {
    className: "key-row-control",
    keys: [
      { label: "Esc", mode: "special", value: "Escape" },
      { label: "Tab", mode: "special", value: "Tab" },
      { label: "Enter", mode: "special", value: "Enter" },
      { label: "Ctrl+C", mode: "special", value: "C-c", wide: true },
      { label: "Ctrl+D", mode: "special", value: "C-d", wide: true },
      { label: "Ctrl+L", mode: "special", value: "C-l", wide: true },
      { label: "Paste", action: "paste", wide: true }
    ]
  },
  {
    className: "key-row-edit",
    keys: [
      { label: "Ctrl+A", mode: "special", value: "C-a", wide: true },
      { label: "Ctrl+E", mode: "special", value: "C-e", wide: true },
      { label: "Ctrl+W", mode: "special", value: "C-w", wide: true },
      { label: "Ctrl+U", mode: "special", value: "C-u", wide: true },
      {
        label: "[]",
        sequence: [
          { mode: "literal", value: "[]" },
          { mode: "special", value: "Left" }
        ]
      },
      {
        label: "()",
        sequence: [
          { mode: "literal", value: "()" },
          { mode: "special", value: "Left" }
        ]
      },
      {
        label: "{}",
        sequence: [
          { mode: "literal", value: "{}" },
          { mode: "special", value: "Left" }
        ]
      }
    ]
  },
  {
    className: "key-row-nav",
    keys: [
      { label: "←", mode: "special", value: "Left" },
      { label: "↓", mode: "special", value: "Down" },
      { label: "↑", mode: "special", value: "Up" },
      { label: "→", mode: "special", value: "Right" },
      { label: "/", mode: "literal", value: "/" },
      { label: "-", mode: "literal", value: "-" },
      { label: "_", mode: "literal", value: "_" },
      { label: ":", mode: "literal", value: ":" },
      { label: "|", mode: "literal", value: "|" },
      { label: "~", mode: "literal", value: "~" }
    ]
  }
];

function setStatus(message, isOk = false) {
  if (!keyStatusNode) {
    return;
  }
  keyStatusNode.textContent = message;
  keyStatusNode.classList.toggle("ok", isOk);
}

async function fetchWorkspaces() {
  const response = await fetch("/api/workspaces");
  if (!response.ok) {
    throw new Error(`Failed to load workspaces: ${response.status}`);
  }
  return response.json();
}

async function updateWorkspaceTitle() {
  if (!workspaceNode) {
    return;
  }

  try {
    const payload = await fetchWorkspaces();
    const selected = payload.selected || payload.recent || "";
    workspaceNode.textContent = selected || "No workspace selected";
  } catch (error) {
    workspaceNode.textContent = "Workspace unavailable";
    setStatus(error.message || "Failed to load workspace.", false);
  }
}

function focusTerminalFrame() {
  frameNode?.focus();
  frameNode?.contentWindow?.focus();
}

async function sendKeyPayload(payload) {
  const response = await fetch("/api/terminal/send-key", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Failed to send key.");
  }

  setStatus(`Sent to ${data.workspace}`, true);
  focusTerminalFrame();
}

async function handlePaste() {
  if (!navigator.clipboard?.readText) {
    const fallbackText = window.prompt("Paste text to send into the terminal:", "");
    if (!fallbackText) {
      throw new Error("Paste was cancelled.");
    }
    await sendKeyPayload({
      mode: "literal",
      value: fallbackText
    });
    return;
  }

  let text = "";
  try {
    text = await navigator.clipboard.readText();
  } catch (error) {
    const fallbackText = window.prompt("Paste text to send into the terminal:", "");
    if (!fallbackText) {
      throw error;
    }
    text = fallbackText;
  }

  if (!text) {
    throw new Error("Clipboard is empty.");
  }

  await sendKeyPayload({
    mode: "literal",
    value: text
  });
}

function renderKeyButton(keyDef) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "key-button";
  if (keyDef.wide) {
    button.classList.add("key-button-wide");
  }
  button.textContent = keyDef.label;
  button.addEventListener("click", async () => {
    setStatus(`Sending ${keyDef.label}...`);
    try {
      if (keyDef.action === "paste") {
        await handlePaste();
        return;
      }

      await sendKeyPayload(
        keyDef.sequence
          ? { sequence: keyDef.sequence }
          : { mode: keyDef.mode, value: keyDef.value }
      );
    } catch (error) {
      setStatus(error.message || "Failed to send key.");
    }
  });
  return button;
}

function renderKeyRow(rowDef) {
  const row = document.createElement("div");
  row.className = `key-row ${rowDef.className || ""}`.trim();
  rowDef.keys.forEach((keyDef) => {
    row.appendChild(renderKeyButton(keyDef));
  });
  return row;
}

function renderExtraKeys() {
  if (!keyStripNode) {
    return;
  }

  keyStripNode.innerHTML = "";
  extraKeyRows.forEach((rowDef) => {
    keyStripNode.appendChild(renderKeyRow(rowDef));
  });
}

frameNode?.addEventListener("load", () => {
  setStatus("Terminal ready.", true);
});

renderExtraKeys();
updateWorkspaceTitle();
