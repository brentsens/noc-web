export function readIncidentHandoff(storage) {
    let incidentHandoff = null;
    let incidentTitleHint = null;
    try {
        const rawHandoff = storage.getItem(
            "noc-web:incident-handoff"
        );
        storage.removeItem("noc-web:incident-handoff");
        if (rawHandoff) {
            const parsed = JSON.parse(rawHandoff);
            if (
                parsed
                && typeof parsed.incidentId === "string"
                && parsed.incidentId.trim()
                && parsed.incidentId.length <= 128
            ) {
                incidentHandoff = {
                    incidentId: parsed.incidentId.trim(),
                    title: typeof parsed.title === "string"
                        ? parsed.title
                        : ""
                };
            }
        }
        incidentTitleHint = storage.getItem(
            "noc-web:incident-title-handoff"
        );
        storage.removeItem("noc-web:incident-title-handoff");
    } catch {
        incidentHandoff = null;
        incidentTitleHint = null;
    }
    return { incidentHandoff, incidentTitleHint };
}


export function createInvestigationNameController({
    nameInput,
    displayTitleInput,
    onResetPreview
}) {
    let manuallyEdited = false;
    let currentIncidentId = null;
    let suppressInput = false;

    function setName(value) {
        suppressInput = true;
        nameInput.value = value;
        suppressInput = false;
    }

    nameInput.addEventListener("input", () => {
        if (suppressInput) {
            return;
        }
        manuallyEdited = true;
        onResetPreview?.();
    });

    return {
        resetForIncident(handoff) {
            const nextIncidentId = handoff
                && typeof handoff.incidentId === "string"
                ? handoff.incidentId
                : null;
            if (currentIncidentId !== nextIncidentId) {
                manuallyEdited = false;
                setName("");
            }
            currentIncidentId = nextIncidentId;
            displayTitleInput.value = handoff
                && typeof handoff.title === "string"
                ? handoff.title
                : "";
        },
        applyPreview(preview) {
            if (!preview || typeof preview !== "object") {
                return;
            }
            if (typeof preview.displayTitle === "string") {
                displayTitleInput.value = preview.displayTitle;
            }
            if (typeof preview.normalizedName === "string") {
                setName(preview.normalizedName);
            }
        },
        previewName() {
            return manuallyEdited ? nameInput.value : undefined;
        },
        isManuallyEdited() {
            return manuallyEdited;
        },
        reset() {
            manuallyEdited = false;
            currentIncidentId = null;
            setName("");
        }
    };
}
