import {
  getDatadogIncidents,
  refreshDatadogIncidents
} from "./api.js";

const REFRESH_POLL_MS = 1000;
const REFRESH_INTERVAL_MS = 60 * 1000;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (text !== undefined) {
    element.textContent = text;
  }
  return element;
}

function relativeAge(value) {
  if (typeof value !== "string") {
    return null;
  }
  const elapsed = Math.max(0, Date.now() - Date.parse(value));
  if (!Number.isFinite(elapsed)) {
    return null;
  }
  if (elapsed < 60_000) {
    return `${Math.floor(elapsed / 1000)} seconds ago`;
  }
  if (elapsed < 3_600_000) {
    return `${Math.floor(elapsed / 60_000)} minutes ago`;
  }
  return `${Math.floor(elapsed / 3_600_000)} hours ago`;
}

function safeDatadogUrl(value) {
  if (typeof value !== "string") {
    return null;
  }
  try {
    const url = new URL(value);
    const host = url.hostname;
    if (url.protocol !== "https:"
        || url.username
        || url.password
        || !(host === "datadoghq.com"
          || host.endsWith(".datadoghq.com")
          || host === "datadoghq.eu"
          || host.endsWith(".datadoghq.eu"))
        || !url.pathname.startsWith("/incidents/")) {
      return null;
    }
    return url.href;
  } catch {
    return null;
  }
}

function startedTime(value) {
  if (typeof value !== "string") {
    return null;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? null
    : `Started ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function renderIncident(incident, allowCreateInvestigation) {
  const card = node("article", "active-incident");
  const heading = node("div", "active-incident-heading");
  const titleGroup = node("div", "active-incident-title-group");
  if (incident.severity) {
    titleGroup.appendChild(
      node("span", "incident-severity", incident.severity)
    );
  }
  titleGroup.appendChild(
    node("strong", "active-incident-title", incident.title)
  );
  heading.append(
    titleGroup,
    node("span", "incident-state", incident.state)
  );
  card.appendChild(heading);

  const metadata = [`ID ${incident.id}`];
  const start = startedTime(incident.createdAt);
  if (start) {
    metadata.push(start);
  }
  if (incident.updatedAt) {
    metadata.push(`Updated ${incident.updatedAt}`);
  }
  if (metadata.length) {
    card.appendChild(node("div", "active-incident-meta", metadata.join(" · ")));
  }
  if (incident.summary) {
    card.appendChild(node("p", "active-incident-summary", incident.summary));
  }

  const actions = node("div", "active-incident-actions");
  const url = safeDatadogUrl(incident.url);
  if (url) {
    const datadogLink = node("a", "incident-datadog-link", "View in Datadog ↗");
    datadogLink.href = url;
    datadogLink.target = "_blank";
    datadogLink.rel = "noopener noreferrer";
    actions.appendChild(datadogLink);
  }
  if (allowCreateInvestigation) {
    const createButton = node("button", "button incident-create-button", "Create Investigation");
    createButton.type = "button";
    createButton.addEventListener("click", () => {
      try {
        window.sessionStorage.setItem(
          "noc-web:incident-title-handoff",
          incident.title
        );
      } catch {
        // The existing form remains usable without the optional title prefill.
      }
      window.location.href = "investigations.html";
    });
    actions.appendChild(createButton);
  }
  if (actions.childElementCount) {
    card.appendChild(actions);
  }
  return card;
}

function render(
  container,
  snapshot,
  allowCreateInvestigation,
  showViewIncidents
) {
  container.replaceChildren();

  const header = node("div", "active-incidents-header");
  const heading = node("div", "active-incidents-heading");
  heading.append(
    node("h2", "", "Datadog Incidents"),
    node("span", `incident-freshness freshness-${snapshot.freshness}`,
      snapshot.freshness.toUpperCase())
  );
  const headerActions = node("div", "active-incidents-controls");
  if (showViewIncidents) {
    const viewLink = node("a", "active-incidents-view-link", "View Incidents →");
    viewLink.href = "investigations.html";
    headerActions.appendChild(viewLink);
  }
  const refreshButton = node("button", "button", "Refresh Incidents");
  refreshButton.type = "button";
  refreshButton.dataset.action = "refresh-incidents";
  refreshButton.disabled = snapshot.freshness === "refreshing";
  headerActions.appendChild(refreshButton);
  header.append(heading, headerActions);
  container.appendChild(header);

  const summary = node("div", "active-incidents-summary");
  if (snapshot.freshness === "unavailable") {
    summary.textContent = "Incident data is unavailable.";
  } else if (snapshot.count === null || snapshot.count === undefined) {
    summary.textContent = "Checking current Datadog incidents...";
  } else {
    summary.textContent = `${snapshot.count} Current Datadog Incident${
      snapshot.count === 1 ? "" : "s"
    }`;
    const severities = new Map();
    for (const incident of snapshot.incidents) {
      if (incident.severity) {
        severities.set(
          incident.severity,
          (severities.get(incident.severity) || 0) + 1
        );
      }
    }
    for (const [severity, count] of severities) {
      summary.appendChild(node("span", "incident-severity-count", `${count} ${severity}`));
    }
  }
  container.appendChild(summary);

  const refreshed = relativeAge(snapshot.lastSuccessfulAt);
  const refreshLabel = refreshed
    ? `Last refreshed ${refreshed}`
    : "No successful refresh yet";
  const refreshTime = node("div", "active-incidents-refresh-time", refreshLabel);
  if (snapshot.lastSuccessfulAt) {
    refreshTime.title = new Date(snapshot.lastSuccessfulAt).toLocaleString();
  }
  container.appendChild(refreshTime);

  if (snapshot.freshness === "stale") {
    container.appendChild(
      node("p", "incident-state-message stale-message",
        "Refresh failed or is overdue; showing the last successful snapshot.")
    );
  } else if (snapshot.freshness === "unavailable") {
    container.appendChild(
      node("p", "incident-state-message unavailable-message",
        "No successful incident snapshot is available. You can try refreshing.")
    );
  } else if (snapshot.freshness === "refreshing") {
    container.appendChild(
      node("p", "incident-state-message refreshing-message",
        "Retrieving current Datadog incidents.")
    );
  }

  const list = node("div", "active-incidents-list");
  if (snapshot.count === null || snapshot.count === undefined) {
    if (snapshot.freshness === "refreshing") {
      list.appendChild(
        node("div", "notes-empty", "Waiting for the first successful incident refresh.")
      );
    }
  } else if (snapshot.incidents.length === 0) {
    list.appendChild(node("div", "notes-empty", "No current Datadog incidents."));
  } else {
    for (const incident of snapshot.incidents) {
      list.appendChild(renderIncident(incident, allowCreateInvestigation));
    }
  }
  container.appendChild(list);
  return refreshButton;
}

export function mountActiveIncidents(container, {
  allowCreateInvestigation = false,
  showViewIncidents = false
} = {}) {
  let stopped = false;
  let timer = null;
  let latestSnapshot = null;

  const schedule = delay => {
    clearTimeout(timer);
    timer = setTimeout(load, delay);
  };

  const handleRefreshClick = async event => {
    const refreshButton = event.target?.closest?.(
      'button[data-action="refresh-incidents"]'
    );
    if (
      stopped
      || !refreshButton
      || !container.contains(refreshButton)
      || refreshButton.disabled
    ) {
      return;
    }

    refreshButton.disabled = true;
    try {
      latestSnapshot = await refreshDatadogIncidents();
      render(
        container,
        latestSnapshot,
        allowCreateInvestigation,
        showViewIncidents
      );
      schedule(latestSnapshot.freshness === "refreshing"
        ? REFRESH_POLL_MS
        : REFRESH_INTERVAL_MS);
    } catch {
      latestSnapshot = {
        ...(latestSnapshot || {
          incidents: [],
          count: null,
          lastAttemptedAt: null,
          lastSuccessfulAt: null
        }),
        freshness: latestSnapshot?.lastSuccessfulAt ? "stale" : "unavailable",
        error: "refresh-failed"
      };
      render(
        container,
        latestSnapshot,
        allowCreateInvestigation,
        showViewIncidents
      );
      schedule(REFRESH_INTERVAL_MS);
    }
  };

  container.addEventListener("click", handleRefreshClick);

  const load = async () => {
    if (stopped) {
      return;
    }
    try {
      latestSnapshot = await getDatadogIncidents();
      render(
        container,
        latestSnapshot,
        allowCreateInvestigation,
        showViewIncidents
      );
      schedule(latestSnapshot.freshness === "refreshing"
        ? REFRESH_POLL_MS
        : REFRESH_INTERVAL_MS);
    } catch {
      if (latestSnapshot?.lastSuccessfulAt) {
        latestSnapshot = {
          ...latestSnapshot,
          freshness: "stale",
          error: "request-failed"
        };
      } else {
        latestSnapshot = {
          incidents: [],
          count: null,
          lastAttemptedAt: null,
          lastSuccessfulAt: null,
          freshness: "unavailable",
          error: "request-failed"
        };
      }
      render(
        container,
        latestSnapshot,
        allowCreateInvestigation,
        showViewIncidents
      );
      schedule(REFRESH_INTERVAL_MS);
    }
  };

  load();
  return () => {
    stopped = true;
    clearTimeout(timer);
    container.removeEventListener("click", handleRefreshClick);
  };
}
