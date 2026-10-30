const RESOURCE_GROUPS = [
  {
    title: "SES ENVIRONMENTS",
    resources: [
      {
        name: "USPRI SES",
        url: "https://app.uspri.sesami.io/aaa/login?targetUrl=https://app.uspri.sesami.io/",
        environment: "production"
      },
      {
        name: "EU SES",
        url: "https://app.sesami.io/aaa/login?targetUrl=https://app.sesami.io/",
        environment: "production"
      },
      {
        name: "MEXPRI SES",
        url: "https://app.mexpri.sesami.io/",
        environment: "production"
      },
      {
        name: "DEMO SES",
        url: "https://app.demo.sesami.io/aaa/login?targetUrl=https://app.demo.sesami.io/",
        environment: "demo"
      }
    ]
  },
  {
    title: "TICKETS & SUPPORT",
    resources: [
      {
        name: "NOC Jira",
        url: "https://sesamidevel.atlassian.net/issues/?filter=22992",
        dashboardQuickLink: true
      },
      {
        name: "Salesforce",
        url: "https://sesami.lightning.force.com/lightning/o/Case/list?filterName=NOC_SES_Case",
        dashboardQuickLink: true
      },
      {
        name: "DevOps Ticket Portal",
        url: "https://sesamidevel.atlassian.net/servicedesk/customer/portal/199"
      }
    ]
  },
  {
    title: "DOCUMENTATION",
    resources: [
      {
        name: "NOC Confluence",
        url: "https://sesamidevel.atlassian.net/wiki/spaces/NOC/overview"
      },
      {
        name: "SES Confluence",
        url: "https://sesami-io.atlassian.net/wiki/home?cloudId=8986e79a-6c2a-4e0d-bb65-4a57e0f68db9&source=peopleMenu"
      },
      {
        name: "Atlassian Home",
        url: "https://home.atlassian.com/o/87e5c9f6-4c36-46da-a68f-a39ba95b7c5a/?cloudId=8986e79a-6c2a-4e0d-bb65-4a57e0f68db9"
      }
    ]
  },
  {
    title: "OBSERVABILITY",
    resources: [
      {
        name: "Datadog",
        url: "https://app.datadoghq.com/apm/home?env=%2A&graphType=service_map&shouldShowLegend=true&traceQuery=&view=services",
        dashboardQuickLink: true
      }
    ]
  }
];

export { RESOURCE_GROUPS };
