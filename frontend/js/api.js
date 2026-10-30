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
  
  
      try {
  
        const error =
          await response.json();
  
  
        if (error.detail) {
          message = error.detail;
        }
  
      } catch {
        // Keep default error message.
      }
  
  
      throw new Error(message);
  
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

  export function createLocalTracking(ticket) {
    return apiRequest("/api/tickets/tracking", {
      method: "POST",
      body: JSON.stringify({ ...ticket, confirmed: true })
    });
  }

  export function updateLocalTracking(ticketId, context) {
    return apiRequest(`/api/tickets/${encodeURIComponent(ticketId)}/tracking`, {
      method: "PATCH",
      body: JSON.stringify({ ...context, confirmed: true })
    });
  }

  export function syncLocalTracking(ticketId) {
    return apiRequest(`/api/tickets/${encodeURIComponent(ticketId)}/tracking/sync`, {
      method: "POST",
      body: JSON.stringify({ confirmed: true })
    });
  }

  export function closeLocalTracking(ticketId) {
    return apiRequest(`/api/tickets/${encodeURIComponent(ticketId)}/tracking/close`, {
      method: "POST",
      body: JSON.stringify({ confirmed: true })
    });
  }

  export function reactivateLocalTracking(ticketId) {
    return apiRequest(`/api/tickets/${encodeURIComponent(ticketId)}/tracking/reactivate`, {
      method: "POST",
      body: JSON.stringify({ confirmed: true })
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

export function getStartShiftPreflight(
  shiftDate
) {

  return apiRequest(
    `/api/start-shift/${shiftDate}`
  );

}

export function executeStartShift(
  shiftDate
) {

  return apiRequest(
    `/api/start-shift/${shiftDate}`,
    {
      method: "POST"
    }
  );

}

export function getEndShiftPreflight(
  shiftDate
) {

  return apiRequest(
    `/api/end-shift/${shiftDate}`
  );

}

export function generateHandover(
  shiftDate
) {

  return apiRequest(
    `/api/shifts/${shiftDate}/handover`,
    {
      method: "POST"
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
  recipient = null
) {

  return apiRequest(
    `/api/shifts/${shiftDate}/handover/send`,
    {
      method: "POST",
      body: JSON.stringify({
        recipient,
        confirmed: true
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
  shiftDate
) {

  return apiRequest(
    `/api/shifts/${shiftDate}/handover/regenerate`,
    {
      method: "POST"
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
  ticket
) {

  return apiRequest(
    "/api/jira/tickets/create",
    {
      method: "POST",
      body: JSON.stringify({
        ...ticket,
        confirmed: true
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
