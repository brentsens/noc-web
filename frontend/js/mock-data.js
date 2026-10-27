export const dashboard = {
    shiftDate: "2026-10-26",
    status: "ready",
    openTickets: 5,
    investigations: 1,
    needsReview: 0,
    handover: "pending"
  };
  
  export const tickets = [
    {
      id: "NOC-545",
      summary: "Consillion integration issue",
      status: "Escalated",
      environment: "EU",
      nextAction: "Pending test from Josh Keogh"
    },
    {
      id: "NOC-555",
      summary: "Brinks missing transaction",
      status: "Re Open",
      environment: "USPRI",
      nextAction: "Contact Chris Shelton"
    },
    {
      id: "NOC-556",
      summary: "Superior US deposits",
      status: "Escalated",
      environment: "USPRI",
      nextAction: ""
    },
    {
      id: "NOC-575",
      summary: "Bargain Max transmissions",
      status: "Escalated",
      environment: "EU",
      nextAction: "Pending Dev investigation"
    },
    {
      id: "NOC-580",
      summary: "Valvoline bill rejects",
      status: "Escalated",
      environment: "USPRI",
      nextAction: "Check reject details"
    }
  ];
  
  export const activity = [
    {
      time: "14:12",
      text: "Added alerting tags to Platform Services monitor"
    },
    {
      time: "13:45",
      text: "Reviewed NOC-545 status"
    },
    {
      time: "13:10",
      text: "Contacted Chris Shelton for NOC-555"
    },
    {
      time: "12:48",
      text: "Created investigation IR-16"
    },
    {
      time: "12:03",
      text: "Shift started"
    }
  ];