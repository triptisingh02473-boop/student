const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("csv-input");
const filenameLabel = document.getElementById("selected-filename");
const uploadBtn = document.getElementById("upload-btn");
const form = document.getElementById("upload-form");
const progressEl = document.getElementById("upload-progress");
const successEl = document.getElementById("upload-success");
const errorEl = document.getElementById("upload-error");
const errorMsgEl = document.getElementById("upload-error-message");
const errorListEl = document.getElementById("upload-error-list");
const warningsEl = document.getElementById("upload-warnings");
const warningsListEl = document.getElementById("upload-warnings-list");

dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        updateSelectedFile();
    }
});

fileInput.addEventListener("change", updateSelectedFile);

function updateSelectedFile() {
    if (fileInput.files.length) {
        filenameLabel.textContent = fileInput.files[0].name;
        uploadBtn.disabled = false;
    } else {
        filenameLabel.textContent = "No file selected";
        uploadBtn.disabled = true;
    }
    hideAlerts();
}

function hideAlerts() {
    successEl.style.display = "none";
    errorEl.style.display = "none";
    warningsEl.style.display = "none";
}

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!fileInput.files.length) return;

    hideAlerts();
    progressEl.style.display = "block";
    uploadBtn.disabled = true;

    const formData = new FormData();
    formData.append("csv_file", fileInput.files[0]);

    try {
        const res = await fetch("/api/upload", {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        progressEl.style.display = "none";
        uploadBtn.disabled = false;

        if (!res.ok || !data.success) {
            errorEl.style.display = "block";
            errorMsgEl.textContent = data.error || "Upload failed.";
            errorListEl.innerHTML = "";
            (data.validation_errors || []).forEach(msg => {
                const li = document.createElement("li");
                li.textContent = msg;
                errorListEl.appendChild(li);
            });
            return;
        }

        successEl.style.display = "block";
        successEl.textContent = data.message;

        if (data.warnings && data.warnings.length) {
            warningsEl.style.display = "block";
            warningsListEl.innerHTML = "";
            data.warnings.forEach(w => {
                const li = document.createElement("li");
                li.textContent = w;
                warningsListEl.appendChild(li);
            });
        }

        fileInput.value = "";
        filenameLabel.textContent = "No file selected";
        uploadBtn.disabled = true;
        
    } catch (err) {
        progressEl.style.display = "none";
        uploadBtn.disabled = false;
        errorEl.style.display = "block";
        errorMsgEl.textContent = "Could not reach the server. Please try again.";
    }
});

document.getElementById("download-sample").addEventListener("click", () => {
    window.location.href = "/api/sample-csv";
});
