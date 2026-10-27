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