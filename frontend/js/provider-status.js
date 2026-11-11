import { probeOllamaProvider } from "./api.js";

const READINESS_LABELS = new Map([
  ["ready", "Ready"],
  ["notReady", "Not ready"],
  ["notConfigured", "Not configured"]
]);

export function providerReadinessLabel(provider) {
  if (!provider || typeof provider !== "object") {
    return "Unknown";
  }
  return READINESS_LABELS.get(provider.readiness) || "Unknown";
}

export function providerIdentityLabel(provider) {
  if (!provider || typeof provider !== "object") {
    return "Not configured";
  }
  const label = typeof provider.label === "string" && provider.label
    ? provider.label
    : (typeof provider.configuredProvider === "string"
      ? provider.configuredProvider
      : "Not configured");
  return provider.model ? `${label} (${provider.model})` : label;
}

export function localEndpointLabel(provider) {
  if (!provider || typeof provider !== "object" || !provider.endpointConfigured) {
    return "Endpoint not configured";
  }
  return "Endpoint configured";
}

export function localProbeLabel(probe) {
  if (!probe || typeof probe !== "object") {
    return "No explicit probe run.";
  }
  if (probe.available === true) {
    return `Available at ${probe.probedAt || "the last probe"}.`;
  }
  return `Unavailable: ${probe.reason || "unknown"}.`;
}

export function localRetryAvailability(response) {
  const retry = response && response.localRetry;
  if (!retry || retry.available !== true || typeof retry.retryToken !== "string") {
    return null;
  }
  return retry;
}

export function localRetryLabel(retry) {
  if (!retry) {
    return "";
  }
  return `Retry with Local AI is available using ${retry.provider} (${retry.model}).`;
}

export async function probeLocalProvider() {
  return probeOllamaProvider();
}
