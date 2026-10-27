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

  export function getShiftNotes(
    shiftDate
) {

    return apiRequest(
        `/api/shifts/${shiftDate}/notes`
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
