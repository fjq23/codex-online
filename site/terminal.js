const listNode = document.querySelector("#workspace-list");
const summaryNode = document.querySelector("#workspace-summary");
const statusNode = document.querySelector("#workspace-status");
const formNode = document.querySelector("#workspace-form");
const inputNode = document.querySelector("#workspace-name");

function setStatus(message, isOk = false) {
  statusNode.textContent = message;
  statusNode.classList.toggle("ok", isOk);
}

function renderWorkspaceButton(name, badgeText = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "workspace-button";
  button.innerHTML = `
    <span class="workspace-name">${name}</span>
    <span class="workspace-meta">${badgeText || "Open terminal"}</span>
  `;
  button.addEventListener("click", async () => {
    await openWorkspace(name);
  });
  return button;
}

async function fetchWorkspaces() {
  const response = await fetch("/api/workspaces");
  if (!response.ok) {
    throw new Error(`Failed to load workspaces: ${response.status}`);
  }
  return response.json();
}

async function openWorkspace(name) {
  setStatus("Opening workspace...");
  const response = await fetch("/api/workspaces/open", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ name })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.error || "Failed to open workspace.");
  }

  window.location.href = "/terminal/session/";
}

async function refreshWorkspaces() {
  try {
    const payload = await fetchWorkspaces();
    const workspaces = payload.workspaces || [];
    const recent = payload.recent || "";
    const selected = payload.selected || "";

    listNode.innerHTML = "";

    if (workspaces.length === 0) {
      summaryNode.textContent = "No workspace yet";
      const empty = document.createElement("div");
      empty.className = "empty-state";
      empty.textContent = "No workspace yet. Create one below.";
      listNode.appendChild(empty);
      return;
    }

    summaryNode.textContent = `${workspaces.length} workspace${workspaces.length > 1 ? "s" : ""}`;

    workspaces.forEach((name) => {
      let badge = "Open terminal";
      if (name === selected) {
        badge = "Selected";
      } else if (name === recent) {
        badge = "Recent";
      }
      listNode.appendChild(renderWorkspaceButton(name, badge));
    });
  } catch (error) {
    summaryNode.textContent = "Unavailable";
    setStatus(error.message || "Failed to load workspaces.");
  }
}

formNode?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const rawName = inputNode.value.trim();
  if (!rawName) {
    setStatus("Enter a workspace name first.");
    inputNode.focus();
    return;
  }

  try {
    await openWorkspace(rawName);
  } catch (error) {
    setStatus(error.message || "Failed to create workspace.");
  }
});

refreshWorkspaces();
