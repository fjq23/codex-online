const workspaceNode = document.querySelector("#terminal-workspace");
const keyStatusNode = document.querySelector("#terminal-key-status");
const keyStripNode = document.querySelector("#key-strip");
const frameNode = document.querySelector("#terminal-frame");
const frameShellNode = document.querySelector("#terminal-frame-shell");
const topbarNode = document.querySelector(".terminal-topbar");
const terminalKeysNode = document.querySelector(".terminal-keys");
const syncButtonNode = document.querySelector("#sync-terminal");
const terminalCpuNode = document.querySelector("#terminal-system-cpu");
const terminalMemoryNode = document.querySelector("#terminal-system-memory");
const terminalDiskNode = document.querySelector("#terminal-system-disk");
const terminalLoadNode = document.querySelector("#terminal-system-load");
const rootNode = document.documentElement;

let lockedViewportHeight = 0;
let lockedViewportWidth = 0;
let lockedFrameHeight = 0;

const extraKeyRows = [
  {
    className: "key-row-control",
    keys: [
      {
        label: "Codex",
        wide: true,
        sequence: [
          { mode: "literal", value: "codex" },
          { mode: "special", value: "Enter" }
        ]
      },
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
    className: "key-row-scroll",
    keys: [
      { label: "PgUp", tmuxAction: "page-up", wide: true },
      { label: "PgDn", tmuxAction: "page-down", wide: true },
      { label: "Top", tmuxAction: "top" },
      { label: "Bottom", tmuxAction: "bottom", wide: true },
      { label: "Live", tmuxAction: "live", wide: true }
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

function measureFrameHeight(height) {
  if (!topbarNode || !terminalKeysNode) {
    return Math.max(height - 180, 240);
  }

  const topbarHeight = Math.ceil(topbarNode.getBoundingClientRect().height);
  const keysHeight = Math.ceil(terminalKeysNode.getBoundingClientRect().height);
  return Math.max(height - topbarHeight - keysHeight, 240);
}

function applyLockedViewport(width, height) {
  lockedViewportWidth = width;
  lockedViewportHeight = height;
  lockedFrameHeight = measureFrameHeight(height);
  rootNode.classList.remove("keyboard-open");
  rootNode.style.setProperty("--app-height", `${height}px`);
  rootNode.style.setProperty("--terminal-frame-height", `${lockedFrameHeight}px`);
}

function updateLockedViewport(force = false) {
  const width = window.innerWidth;
  const height = window.innerHeight;

  if (!lockedViewportHeight || !lockedViewportWidth || force) {
    applyLockedViewport(width, height);
    return;
  }

  const widthChanged = Math.abs(width - lockedViewportWidth) > 80;
  const heightExpanded = height > lockedViewportHeight + 96;
  const roughlySame = Math.abs(height - lockedViewportHeight) < 80;
  const likelyKeyboardShrink = height < lockedViewportHeight - 120;

  if (widthChanged || heightExpanded || roughlySame) {
    applyLockedViewport(width, height);
    return;
  }

  if (likelyKeyboardShrink) {
    rootNode.classList.add("keyboard-open");
    return;
  }

  rootNode.classList.remove("keyboard-open");
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
    updateSystemStatus(payload.system || {});
  } catch (error) {
    workspaceNode.textContent = "Workspace unavailable";
    setStatus(error.message || "Failed to load workspace.", false);
  }
}

function updateSystemStatus(system = {}) {
  if (!terminalCpuNode || !terminalMemoryNode || !terminalDiskNode || !terminalLoadNode) {
    return;
  }

  const memory = system.memory || {};
  const disk = system.disk || {};
  const load = system.load || {};

  terminalCpuNode.textContent = typeof system.cpu_percent === "number"
    ? `CPU ${system.cpu_percent.toFixed(1)}%`
    : "CPU --";
  terminalMemoryNode.textContent = typeof memory.percent === "number"
    ? `Mem ${memory.percent.toFixed(1)}%`
    : "Mem --";
  terminalDiskNode.textContent = typeof disk.percent === "number"
    ? `Disk ${disk.percent.toFixed(1)}%`
    : "Disk --";
  terminalLoadNode.textContent = typeof load.one === "number"
    ? `Load ${load.one.toFixed(2)}`
    : "Load --";
}

function focusTerminalFrame() {
  frameNode?.focus();
  frameNode?.contentWindow?.focus();
}

function syncTerminalViewport(reloadFrame = true) {
  updateLockedViewport(true);
  if (reloadFrame && frameNode) {
    setStatus("Syncing terminal...", false);
    frameNode.src = "/terminal/session/";
  }
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

async function sendTmuxAction(action) {
  const response = await fetch("/api/terminal/tmux-action", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ action })
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Failed to control tmux.");
  }

  setStatus(`tmux ${data.action}`, true);
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
      if (keyDef.tmuxAction) {
        await sendTmuxAction(keyDef.tmuxAction);
        return;
      }

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
  updateLockedViewport(true);
});

window.addEventListener("resize", () => {
  updateLockedViewport(false);
});

window.visualViewport?.addEventListener("resize", () => {
  updateLockedViewport(false);
});

window.addEventListener("orientationchange", () => {
  window.setTimeout(() => {
    rootNode.classList.remove("keyboard-open");
    syncTerminalViewport(true);
  }, 120);
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    rootNode.classList.remove("keyboard-open");
    updateLockedViewport(true);
    updateWorkspaceTitle();
  }
});

syncButtonNode?.addEventListener("click", () => {
  syncTerminalViewport(true);
});

updateLockedViewport(true);
renderExtraKeys();
updateWorkspaceTitle();
window.setInterval(updateWorkspaceTitle, 10000);
