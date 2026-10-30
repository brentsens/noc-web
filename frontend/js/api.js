export async function apiRequest(
    path,
    options = {}
  ) {

    const response =
      await fetch(
        path,
        {
          headers: {
            "Content-Type": "application/json",
            ...(options.headers || {})
          },
          ...options
        }
      );


    if (!response.ok) {

      let message =
        `Request failed: ${response.status}`;
      let field;
      let code;


      try {

        const error =
          await response.json();


        if (typeof error.detail === "string") {
          message = error.detail;
        } else if (error.detail && typeof error.detail.message === "string") {
          message = error.detail.message;
          field = error.detail.field;
          code = error.detail.code;
        }

      } catch {
        // Keep default error message.
      }


      const requestError = new Error(message);
      requestError.field = field;
      requestError.code = code;
      throw requestError;

    }


    return response.json();
  }


  export function getDashboard(
    shiftDate
  ) {

    return apiRequest(
      `/api/dashboard/${shiftDate}`
    );

  }

  export function getTickets() {

    return apiRequest(
      "/api/tickets"
    );

  }

  export function createLocalTracking(ticket, confirmed = false) {
    return apiRequest("/api/tickets/tracking", {
      method: "POST",
      body: JSON.stringify({ ...ticket, confirmed })
    });
  }

  export function updateLocalTracking(ticketId, context, confirmed = false) {
    return apiRequest(`/api/tickets/${encodeURIComponent(ticketId)}/tracking`, {
      method: "PATCH",
      body: JSON.stringify({ ...context, confirmed })
    });
  }

  export function syncLocalTracking(ticketId, confirmed = false) {
    return apiRequest(`/api/tickets/${encodeURIComponent(ticketId)}/tracking/sync`, {
      method: "POST",
      body: JSON.stringify({ confirmed })
    });
  }

  export function closeLocalTracking(ticketId, confirmed = false) {
    return apiRequest(`/api/tickets/${encodeURIComponent(ticketId)}/tracking/close`, {
      method: "POST",
      body: JSON.stringify({ confirmed })
    });
  }

  export function reactivateLocalTracking(ticketId, confirmed = false) {
    return apiRequest(`/api/tickets/${encodeURIComponent(ticketId)}/tracking/reactivate`, {
      method: "POST",
      body: JSON.stringify({ confirmed })
    });
  }

  export function getShiftNotes(
    shiftDate
) {

    return apiRequest(
        `/api/shifts/${shiftDate}/notes`
    );

}

export function addShiftNote(
  shiftDate,
  category,
  text
) {

  return apiRequest(
    `/api/shifts/${shiftDate}/notes`,
    {
      method: "POST",
      body: JSON.stringify({
        category,
        text
      })
    }
  );

}

export function getInvestigations(
  shiftDate
) {

  return apiRequest(
      `/api/shifts/${shiftDate}/investigations`
  );

}


export function getInvestigation(
  shiftDate,
  investigationName
) {

  return apiRequest(
      `/api/shifts/${shiftDate}/investigations/${
          encodeURIComponent(
              investigationName
          )
      }`
  );

}

export function previewInvestigation(shiftDate, name, notebookUrl) {
  return apiRequest(`/api/shifts/${shiftDate}/investigations/preview`, {
    method: "POST",
    body: JSON.stringify({ name, notebookUrl })
  });
}

export function createInvestigation(
  shiftDate,
  name,
  notebookUrl,
  confirmed = false
) {
  return apiRequest(`/api/shifts/${shiftDate}/investigations`, {
    method: "POST",
    body: JSON.stringify({ name, notebookUrl, confirmed })
  });
}

export function reviewInvestigation(
  shiftDate,
  investigationName,
  finding,
  state,
  confirmed = false
) {
  return apiRequest(
    `/api/shifts/${shiftDate}/investigations/${encodeURIComponent(investigationName)}/review`,
    {
      method: "POST",
      body: JSON.stringify({
        confirmed,
        finding,
        state
      })
    }
  );
}

export function rejectInvestigation(shiftDate, investigationName, confirmed = false) {
  return apiRequest(
    `/api/shifts/${shiftDate}/investigations/${encodeURIComponent(investigationName)}/reject`,
    {
      method: "POST",
      body: JSON.stringify({ confirmed })
    }
  );
}

export function getAiReports(
  shiftDate
) {

  return apiRequest(
      `/api/shifts/${shiftDate}/ai-reports`
  );

}


export function getAiReport(
  shiftDate,
  reportName
) {

  return apiRequest(
      `/api/shifts/${shiftDate}/ai-reports/${
          encodeURIComponent(reportName)
      }`
  );

}

export function getHandover(
  shiftDate
) {

  return apiRequest(
      `/api/shifts/${shiftDate}/handover`
  );

}

export function getStatus(
  shiftDate
) {

  return apiRequest(
    `/api/status/${shiftDate}`
  );

}

export function getHealth(
  shiftDate
) {

  return apiRequest(
    `/api/health/${shiftDate}`
  );

}

export function getReadiness(shiftDate) {
  return apiRequest(`/api/readiness/${shiftDate}`);
}

const ASSISTANT_STATUSES = new Set(["complete", "limited", "unavailable"]);
const ASSISTANT_PROVIDERS = new Set(["github-copilot-cli"]);
const ASSISTANT_PROVIDER_STATUSES = new Set([
  "success",
  "unavailable",
  "timeout",
  "invalid",
  "not-invoked"
]);
const ASSISTANT_AVAILABILITY = new Set([
  "available",
  "unavailable",
  "stale",
  "malformed",
  "conflicting"
]);
const ASSISTANT_ROUTES = new Map([
  ["tickets.html", { label: "Open Tickets", requiresConfirmation: true }],
  ["investigations.html", { label: "Open Investigations", requiresConfirmation: true }],
  ["status.html", { label: "Open Status", requiresConfirmation: false }],
  ["index.html", { label: "Open Dashboard", requiresConfirmation: false }],
  ["end-shift.html", { label: "Open End Shift", requiresConfirmation: true }]
]);
const ASSISTANT_ACTIONS = new Map([
  ["analysis", { reportSlug: "shift-analysis", title: "Analyze Entire Shift" }],
  ["summary", { reportSlug: "shift-summary", title: "Summarize Current Shift" }],
  ["followups", { reportSlug: "followups", title: "Identify Follow-ups" }],
  ["handover", { reportSlug: "handover-review", title: "Review Handover Draft" }]
]);
const REPORT_SAVE_WARNING =
  "Analysis completed, but its advisory report could not be saved.";

function isAssistantItem(item, evidence, {
  reviewed = false,
  route = false,
  shiftDate,
  allowUnlinked = false
} = {}) {
  const allowedKeys = new Set([
    "text",
    "evidenceIds",
    ...(reviewed ? ["state"] : []),
    ...(route ? ["route"] : [])
  ]);
  if (!item || typeof item !== "object"
      || Object.keys(item).some(key => !allowedKeys.has(key))
      || typeof item.text !== "string"
      || !Array.isArray(item.evidenceIds)
      || (item.evidenceIds.length === 0 && !(route && allowUnlinked && item.route))
      || item.evidenceIds.some(id => !evidence.has(id))) {
    return false;
  }
  if (reviewed && typeof item.state !== "string") {
    return false;
  }
  if (route && item.route !== undefined) {
    if (!item.route || typeof item.route !== "object"
        || typeof item.route.href !== "string"
        || typeof item.route.requiresConfirmation !== "boolean") {
      return false;
    }
    let href;
    try {
      href = new URL(item.route.href, "https://noc-web.invalid");
    } catch {
      return false;
    }
    const file = href.pathname.slice(1);
    const expectedRoute = ASSISTANT_ROUTES.get(file);
    if (href.origin !== "https://noc-web.invalid"
        || !expectedRoute
        || [...href.searchParams.entries()].length !== 1
        || href.searchParams.get("shift") !== shiftDate) {
      return false;
    }
    if (item.route.label !== expectedRoute.label
        || item.route.requiresConfirmation !== expectedRoute.requiresConfirmation) {
      return false;
    }
    if (file === "investigations.html"
        && !item.evidenceIds.some(id => {
          const source = evidence.get(id);
          return source?.kind === "investigation"
            && ["noc-inv", "copilot-mcp"].includes(source.provenance)
            && source.availability === "available";
        })) {
      return false;
    }
  }
  return true;
}

function validateAssistantResponse(response, shiftDate) {
  if (!response || typeof response !== "object"
      || response.shiftDate !== shiftDate
      || !ASSISTANT_STATUSES.has(response.status)
      || !ASSISTANT_PROVIDERS.has(response.provider)
      || typeof response.providerInvoked !== "boolean"
      || !ASSISTANT_PROVIDER_STATUSES.has(response.providerStatus)
      || (response.providerStatus === "success" && !response.providerInvoked)
      || (["timeout", "invalid"].includes(response.providerStatus) && !response.providerInvoked)
      || (response.providerStatus === "not-invoked"
        && (response.providerInvoked || response.status !== "limited"))
      || !Array.isArray(response.evidence)
      || !Array.isArray(response.limitations)
      || response.limitations.some(item => typeof item !== "string")) {
    return false;
  }
  const evidence = new Map();
  for (const item of response.evidence) {
    if (!item || typeof item.id !== "string"
        || typeof item.kind !== "string"
        || typeof item.provenance !== "string"
        || !ASSISTANT_AVAILABILITY.has(item.availability)
        || !(item.reference === null || typeof item.reference === "string")
        || (item.freshness !== undefined
          && !["current", "stale", "unavailable", "malformed"].includes(item.freshness))
        || evidence.has(item.id)) {
      return false;
    }
    evidence.set(item.id, item);
  }
  const categories = [
    ["facts", { shiftDate }],
    ["reviewedFindings", { reviewed: true, shiftDate }],
    ["aiObservations", { shiftDate }],
    ["recommendations", { route: true, shiftDate }]
  ];
  return categories.every(([name, options]) =>
    Array.isArray(response[name])
    && response[name].every(item =>
      isAssistantItem(item, evidence, {
        ...options,
        allowUnlinked: name === "recommendations"
          && response.status === "limited"
          && response.evidence.length === 0
      })
      && item.evidenceIds.every(id =>
        evidence.get(id).availability === "available"
        || (name !== "reviewedFindings" && evidence.get(id).availability === "stale")
      )
    )
  );
}

export async function askAssistant(shiftDate, question, providerDisclosureAcknowledged = false) {
  const response = await apiRequest(`/api/shifts/${encodeURIComponent(shiftDate)}/assistant/questions`, {
    method: "POST",
    body: JSON.stringify({
      shiftDate,
      question,
      providerDisclosureAcknowledged
    })
  });
  if (!validateAssistantResponse(response, shiftDate)) {
    throw new Error("Assistant returned an invalid response.");
  }
  return response;
}

export async function runAssistantAction(
  shiftDate,
  actionType,
  providerDisclosureAcknowledged = false
) {
  const action = ASSISTANT_ACTIONS.get(actionType);
  if (!action) {
    throw new Error("Assistant action is not available.");
  }
  const result = await apiRequest(
    `/api/shifts/${encodeURIComponent(shiftDate)}/assistant/actions/${actionType}`,
    {
      method: "POST",
      body: JSON.stringify({ providerDisclosureAcknowledged })
    }
  );
  const reportPattern = new RegExp(
    `^ai-${action.reportSlug}-\\d{8}T\\d{12}Z-[0-9a-f]{8}\\.md$`
  );
  if (!result || typeof result !== "object"
      || Object.keys(result).length !== 3
      || !Object.hasOwn(result, "assistant")
      || !Object.hasOwn(result, "report")
      || !Object.hasOwn(result, "reportSaveWarning")
      || !validateAssistantResponse(result.assistant, shiftDate)
      || !(result.report === null
        || (result.report
          && Object.keys(result.report).length === 4
          && Object.hasOwn(result.report, "name")
          && Object.hasOwn(result.report, "title")
          && Object.hasOwn(result.report, "file")
          && Object.hasOwn(result.report, "available")
          && result.report.available === true
          && typeof result.report.name === "string"
          && result.report.name === result.report.file
          && result.report.title === action.title
          && reportPattern.test(result.report.file)))
      || !(result.reportSaveWarning === null
        || result.reportSaveWarning === REPORT_SAVE_WARNING)
      || (result.assistant.providerStatus === "success"
        && result.report === null
        && !result.reportSaveWarning)
      || (result.report !== null && result.reportSaveWarning !== null)
      || (result.assistant.providerStatus !== "success"
        && (result.report !== null || result.reportSaveWarning !== null))) {
    throw new Error("Assistant returned an invalid action response.");
  }
  return result;
}

export function getStartShiftPreflight(
  shiftDate
) {

  return apiRequest(
    `/api/start-shift/${shiftDate}`
  );

}

export function executeStartShift(
  shiftDate,
  confirmed = false
) {

  return apiRequest(
    `/api/start-shift/${shiftDate}`,
    {
      method: "POST",
      body: JSON.stringify({ confirmed })
    }
  );

}

export function requestErrorMessage(error) {
  return error instanceof Error ? error.message : "Request failed.";
}

export function getEndShiftPreflight(
  shiftDate
) {

  return apiRequest(
    `/api/end-shift/${shiftDate}`
  );

}

export function generateHandover(
shiftDate,
confirmed = false
) {

  return apiRequest(
    `/api/shifts/${shiftDate}/handover`,
    {
      method: "POST",
      body: JSON.stringify({ confirmed })
    }
  );

}

export function previewHandoverDelivery(
  shiftDate,
  recipient = null
) {

  return apiRequest(
    `/api/shifts/${shiftDate}/handover/preview`,
    {
      method: "POST",
      body: JSON.stringify({
        recipient
      })
    }
  );

}

export function sendHandoverDelivery(
  shiftDate,
recipient = null,
confirmed = false
) {

  return apiRequest(
    `/api/shifts/${shiftDate}/handover/send`,
    {
      method: "POST",
      body: JSON.stringify({
        recipient,
        confirmed
      })
    }
  );

}

export function syncAllTickets() {

  return apiRequest(
    "/api/ticket-sync/sync",
    {
      method: "POST"
    }
  );

}

export function getTicketSyncState() {

  return apiRequest(
    "/api/ticket-sync/sync"
  );

}

export function regenerateHandover(
shiftDate,
confirmed = false
) {

  return apiRequest(
    `/api/shifts/${shiftDate}/handover/regenerate`,
    {
      method: "POST",
      body: JSON.stringify({ confirmed })
    }
  );

}

export function previewJiraTicket(
  ticket
) {

  return apiRequest(
    "/api/jira/tickets/preview",
    {
      method: "POST",
      body: JSON.stringify(
        ticket
      )
    }
  );

}

export function createJiraTicket(
ticket,
confirmed = false
) {

  return apiRequest(
    "/api/jira/tickets/create",
    {
      method: "POST",
      body: JSON.stringify({
        ...ticket,
        confirmed
      })
    }
  );

}

export function getJiraTicketQueue() {

  return apiRequest(
    "/api/jira/ticket-queue"
  );

}

export function refreshJiraTicketQueue() {

  return apiRequest(
    "/api/jira/ticket-queue/refresh",
    {
      method: "POST"
    }
  );

}
