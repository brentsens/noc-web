const STEPS = [
    ["start-shift", "Start Shift", "start-shift.html"],
    ["dashboard", "Dashboard", "index.html"],
    ["tickets", "Tickets", "tickets.html"],
    ["investigations", "Investigations", "investigations.html"],
    ["status", "Status", "status.html"],
    ["end-shift", "End Shift", "end-shift.html"]
];

function isIsoDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) {
        return false;
    }

    const parsed = new Date(`${value}T00:00:00Z`);
    return !Number.isNaN(parsed.getTime())
        && parsed.toISOString().slice(0, 10) === value;
}

function localToday() {
    const now = new Date();
    const offset = now.getTimezoneOffset() * 60000;
    return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

export function getWorkflowContext() {
    const url = new URL(window.location.href);
    const supplied = url.searchParams.get("shift");

    if (supplied === null) {
        const shift = localToday();
        url.searchParams.set("shift", shift);
        window.history.replaceState({}, "", url);
        return { shift, valid: true, normalized: true };
    }

    if (!isIsoDate(supplied)) {
        return { shift: null, valid: false, error: "Select a valid shift date (YYYY-MM-DD) before loading this view." };
    }

    return { shift: supplied, valid: true, normalized: false };
}

export function workflowLink(filename, shift) {
    return `${filename}?shift=${encodeURIComponent(shift)}`;
}

export function renderStatePanel(container, { source, kind, message, updatedAt }) {
    if (!container) {
        return;
    }

    const panel = document.createElement("div");
    panel.className = `workflow-state workflow-state-${kind}`;
    panel.setAttribute("role", "status");
    panel.textContent = `${source}: ${message}${updatedAt ? ` Updated ${updatedAt}.` : ""}`;
    container.replaceChildren(panel);
}

export function renderStatePanels(container, states) {
    if (!container) {
        return;
    }
    container.replaceChildren();
    states.forEach(state => {
        const panel = document.createElement("div");
        panel.className = `workflow-state workflow-state-${state.kind}`;
        panel.setAttribute("role", "status");
        panel.textContent = `${state.source}: ${state.message}${state.updatedAt ? ` Updated ${state.updatedAt}.` : ""}`;
        container.appendChild(panel);
    });
}

export function initializeWorkflow({ step, dateInput, onInvalid }) {
    const context = getWorkflowContext();
    const content = document.querySelector(".content");
    const bar = document.createElement("nav");
    bar.className = "workflow-bar";
    bar.setAttribute("aria-label", "Daily NOC workflow");

    if (!context.valid) {
        renderStatePanel(bar, {
            source: "Shift context",
            kind: "error",
            message: context.error
        });
        content?.prepend(bar);
        dateInput?.setAttribute("disabled", "disabled");
        onInvalid?.(context);
        return context;
    }

    const activeIndex = STEPS.findIndex(([id]) => id === step);
    const next = STEPS[activeIndex + 1];
    const links = STEPS.map(([id, label, file]) => {
        const active = id === step ? " workflow-step-active" : "";
        return `<a class="workflow-step${active}" href="${workflowLink(file, context.shift)}" ${id === step ? 'aria-current="page"' : ""}>${label}</a>`;
    }).join("");
    bar.innerHTML = `<span class="workflow-context">Shift ${context.shift}</span>${links}${next ? `<a class="workflow-next" href="${workflowLink(next[2], context.shift)}">Next: ${next[1]} →</a>` : ""}<span class="workflow-read-only">Inspection is read-only</span>`;
    content?.prepend(bar);
    const workflowFiles = new Set(STEPS.map(([, , file]) => file));
    document.querySelectorAll("a[href]").forEach(link => {
        const href = link.getAttribute("href");
        if (workflowFiles.has(href)) {
            link.href = workflowLink(href, context.shift);
            if (link.closest(".sidebar")) {
                link.classList.add("workflow-nav-redundant");
            }
        }
    });

    if (dateInput) {
        dateInput.value = context.shift;
        dateInput.addEventListener("change", () => {
            if (!isIsoDate(dateInput.value)) {
                renderStatePanel(bar, {
                    source: "Shift context",
                    kind: "error",
                    message: "Select a valid shift date (YYYY-MM-DD)."
                });
                return;
            }
            window.location.assign(workflowLink(window.location.pathname.split("/").pop(), dateInput.value));
        });
    }

    return context;
}

export async function confirmOperation({ action, scope, execute }) {
    const confirmed = window.confirm(`${action}\n\nScope: ${scope}.`);
    if (!confirmed) {
        return { cancelled: true };
    }
    return execute();
}
