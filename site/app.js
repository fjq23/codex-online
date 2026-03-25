const listNode = document.querySelector("#workspace-list");
const summaryNode = document.querySelector("#workspace-summary");
const workspaceStatusNode = document.querySelector("#workspace-status");
const formNode = document.querySelector("#workspace-form");
const inputNode = document.querySelector("#workspace-name");
const proxyLabelNode = document.querySelector("#proxy-label");
const proxyDetailNode = document.querySelector("#proxy-detail");
const proxyChipNode = document.querySelector("#proxy-chip");

function setWorkspaceStatus(message, isOk = false) {
  if (!workspaceStatusNode) {
    return;
  }
  workspaceStatusNode.textContent = message;
  workspaceStatusNode.classList.toggle("ok", isOk);
}

function workspaceServiceMessage(status) {
  if (status >= 500) {
    return "Workspace service is unavailable. Restart caddy and ttyd.";
  }
  return "";
}

function updateProxyStatus(proxy = {}) {
  if (!proxyLabelNode || !proxyDetailNode || !proxyChipNode) {
    return;
  }

  proxyLabelNode.textContent = proxy.label || "Unavailable";
  proxyDetailNode.textContent = proxy.detail || "";
  proxyChipNode.classList.toggle("ready", Boolean(proxy.ready));
  proxyChipNode.classList.toggle("pending", proxy.configured && !proxy.ready);
  proxyChipNode.classList.toggle("direct", proxy.configured === false);
}

async function fetchWorkspaces() {
  const response = await fetch("/api/workspaces");
  if (!response.ok) {
    throw new Error(workspaceServiceMessage(response.status) || `Failed to load workspaces: ${response.status}`);
  }
  return response.json();
}

async function openWorkspace(name) {
  setWorkspaceStatus("Opening workspace...");
  const response = await fetch("/api/workspaces/open", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ name })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(
      workspaceServiceMessage(response.status) ||
      payload.error ||
      "Failed to open workspace."
    );
  }

  window.location.href = "/terminal/";
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
    try {
      await openWorkspace(name);
    } catch (error) {
      setWorkspaceStatus(error.message || "Failed to open workspace.");
    }
  });
  return button;
}

async function refreshWorkspaces() {
  if (!listNode || !summaryNode) {
    return;
  }

  try {
    const payload = await fetchWorkspaces();
    const workspaces = payload.workspaces || [];
    const recent = payload.recent || "";
    const selected = payload.selected || "";
    updateProxyStatus(payload.proxy || {});

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
    updateProxyStatus({ label: "Unavailable", detail: "Workspace service is unavailable." });
    setWorkspaceStatus(error.message || "Failed to load workspaces.");
  }
}

formNode?.addEventListener("submit", async (event) => {
  event.preventDefault();
  const rawName = inputNode.value.trim();
  if (!rawName) {
    setWorkspaceStatus("Enter a workspace name first.");
    inputNode.focus();
    return;
  }

  try {
    await openWorkspace(rawName);
  } catch (error) {
    setWorkspaceStatus(error.message || "Failed to create workspace.");
  }
});

refreshWorkspaces();
