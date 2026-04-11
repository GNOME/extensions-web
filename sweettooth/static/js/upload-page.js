document.addEventListener("DOMContentLoaded", function () {
    const configNode = document.getElementById("upload-page-config");
    const form = document.getElementById("extension-upload-form");

    if (!configNode || !form) {
        return;
    }

    const config = {
        uploadApiUrl: configNode.dataset.uploadApiUrl,
        uploadFailedMessage: configNode.dataset.uploadFailedMessage,
    };
    const messages = document.getElementById("upload-messages");
    const submitButton = form.querySelector('button[type="submit"]');

    if (submitButton) {
        submitButton.disabled = false;
    }

    function clearErrors() {
        messages.replaceChildren();
        form.querySelectorAll("[data-field-group]").forEach(function (node) {
            node.classList.remove("has-error");
        });
        form.querySelectorAll("[data-field-errors]").forEach(function (node) {
            node.replaceChildren();
        });
    }

    function appendMessage(text, level) {
        const alert = document.createElement("div");
        alert.className = `alert alert-${level || "danger"}`;
        alert.textContent = text;
        messages.append(alert);
    }

    function appendFieldError(fieldName, text) {
        const container = form.querySelector(`[data-field-errors="${fieldName}"]`);
        const fieldGroup = form.querySelector(`[data-field-group="${fieldName}"]`);
        if (!container) {
            return false;
        }

        if (fieldGroup) {
            fieldGroup.classList.add("has-error");
        }

        const paragraph = document.createElement("p");
        paragraph.textContent = text;
        container.append(paragraph);
        return true;
    }

    async function parseJsonResponse(response) {
        const contentType = response.headers.get("content-type") || "";

        if (!contentType.includes("application/json")) {
            return null;
        }

        return response.json();
    }

    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        clearErrors();

        const formData = new FormData(form);
        submitButton.disabled = true;

        try {
            const response = await fetch(config.uploadApiUrl, {
                method: "POST",
                credentials: "same-origin",
                body: formData,
            });
            const payload = await parseJsonResponse(response);

            if (!response.ok) {
                if (Array.isArray(payload)) {
                    payload.forEach(function (error) {
                        appendMessage(error, "danger");
                    });
                    return;
                }

                if (payload && typeof payload === "object") {
                    let hasFieldErrors = false;

                    Object.entries(payload).forEach(function ([field, errors]) {
                        if (!Array.isArray(errors)) {
                            return;
                        }

                        errors.forEach(function (error) {
                            if (field === "non_field_errors") {
                                appendMessage(error, "danger");
                                return;
                            }

                            if (appendFieldError(field, error)) {
                                hasFieldErrors = true;
                                return;
                            }

                            appendMessage(error, "danger");
                        });
                    });

                    if (!hasFieldErrors) {
                        appendMessage(config.uploadFailedMessage, "danger");
                    }
                    return;
                }

                appendMessage(config.uploadFailedMessage, "danger");
                return;
            }

            window.location.href = payload.link;
        } finally {
            submitButton.disabled = false;
        }
    });
});
