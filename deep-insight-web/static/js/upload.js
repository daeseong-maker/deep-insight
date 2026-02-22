// ==================== Drag & Drop ====================
function initUpload() {
    const dropZone = document.getElementById("drop-zone");
    const dataFileInput = document.getElementById("data-file");

    dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("dragover"); });
    dropZone.addEventListener("dragleave", () => { dropZone.classList.remove("dragover"); });
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            dataFileInput.files = e.dataTransfer.files;
            showSelectedFile(e.dataTransfer.files[0].name);
        }
    });
    dataFileInput.addEventListener("change", () => {
        if (dataFileInput.files.length > 0) {
            showSelectedFile(dataFileInput.files[0].name);
        }
    });

    // Column definition drag & drop
    const coldefZone = document.getElementById("drop-zone-coldef");
    const coldefInput = document.getElementById("col-def");

    coldefZone.addEventListener("dragover", (e) => { e.preventDefault(); coldefZone.classList.add("dragover"); });
    coldefZone.addEventListener("dragleave", () => { coldefZone.classList.remove("dragover"); });
    coldefZone.addEventListener("drop", (e) => {
        e.preventDefault();
        coldefZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            coldefInput.files = e.dataTransfer.files;
            showSelectedColdef(e.dataTransfer.files[0].name);
        }
    });
    coldefInput.addEventListener("change", () => {
        if (coldefInput.files.length > 0) {
            showSelectedColdef(coldefInput.files[0].name);
        }
    });

    // Upload form submission
    uploadForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const dataFile = document.getElementById("data-file").files[0];
        if (!dataFile) return;

        const formData = new FormData();
        formData.append("data_file", dataFile);
        const colDef = document.getElementById("col-def").files[0];
        if (colDef) formData.append("column_definitions", colDef);

        uploadBtn.disabled = true;
        statusDiv.textContent = translations[currentLang].status_uploading;
        statusDiv.style.color = "var(--text-muted)";

        try {
            const res = await fetch("/upload", { method: "POST", body: formData });
            const data = await res.json();
            if (data.success) {
                currentUploadId = data.upload_id;
                const fileNames = colDef ? dataFile.name + ", " + colDef.name : dataFile.name;
                statusDiv.textContent = translations[currentLang].status_upload_complete + data.upload_id + "\n📄 " + fileNames;
                statusDiv.style.whiteSpace = "pre-line";
                statusDiv.style.color = "var(--green)";
                analyzeSection.classList.remove("hidden");
                analyzeBtn.disabled = false;
                analyzeSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                statusDiv.textContent = translations[currentLang].status_upload_failed + (data.error || "Unknown error");
                statusDiv.style.color = "var(--red)";
            }
        } catch (err) {
            statusDiv.textContent = translations[currentLang].status_upload_failed + err.message;
            statusDiv.style.color = "var(--red)";
        } finally {
            uploadBtn.disabled = false;
        }
    });
}

function showSelectedFile(name) {
    const t = translations[currentLang];
    const selectedFileDiv = document.getElementById("selected-file");
    const dropZone = document.getElementById("drop-zone");
    const span = document.createElement("span");
    span.className = "file-selected";
    span.textContent = "📄 " + (t.file_selected || "") + name + " ";
    const removeBtn = document.createElement("span");
    removeBtn.className = "remove-file";
    removeBtn.addEventListener("click", clearFile);
    removeBtn.title = "Remove";
    removeBtn.textContent = "✕";
    span.appendChild(removeBtn);
    selectedFileDiv.textContent = "";
    selectedFileDiv.appendChild(span);
    selectedFileDiv.classList.remove("hidden");
    dropZone.classList.add("hidden");
}

function clearFile() {
    const dataFileInput = document.getElementById("data-file");
    const selectedFileDiv = document.getElementById("selected-file");
    const dropZone = document.getElementById("drop-zone");
    dataFileInput.value = "";
    selectedFileDiv.textContent = "";
    selectedFileDiv.classList.add("hidden");
    dropZone.classList.remove("hidden");
}

function showSelectedColdef(name) {
    const t = translations[currentLang];
    const selectedDiv = document.getElementById("selected-coldef");
    const coldefZone = document.getElementById("drop-zone-coldef");
    selectedDiv.textContent = "";
    const span = document.createElement("span");
    span.className = "file-selected";
    span.textContent = "📄 " + (t.file_selected || "") + name + " ";
    const removeBtn = document.createElement("span");
    removeBtn.className = "remove-file";
    removeBtn.title = "Remove";
    removeBtn.textContent = "✕";
    removeBtn.addEventListener("click", clearColdef);
    span.appendChild(removeBtn);
    selectedDiv.appendChild(span);
    selectedDiv.classList.remove("hidden");
    coldefZone.classList.add("hidden");
}

function clearColdef() {
    const coldefInput = document.getElementById("col-def");
    const selectedDiv = document.getElementById("selected-coldef");
    const coldefZone = document.getElementById("drop-zone-coldef");
    coldefInput.value = "";
    selectedDiv.textContent = "";
    selectedDiv.classList.add("hidden");
    coldefZone.classList.remove("hidden");
}

// ==================== Sample Data ====================
let allSampleDatasets = [];

async function loadSampleData() {
    try {
        const res = await fetch("/sample-data");
        const data = await res.json();
        allSampleDatasets = data.datasets || [];
    } catch (err) {
        allSampleDatasets = [];
    }
    renderSampleDataLinks();
}

function renderSampleDataLinks() {
    const container = document.getElementById("sample-data-links");
    const t = translations[currentLang];
    const suffix = currentLang === "ko" ? "-kr" : "-en";
    const filtered = allSampleDatasets.filter(ds => ds.name.endsWith(suffix));
    if (filtered.length === 0) {
        container.innerHTML = `<span style="color:var(--text-muted)">${t.sample_none}</span>`;
        return;
    }
    container.innerHTML = "";
    for (const ds of filtered) {
        for (const file of ds.files) {
            const a = document.createElement("a");
            a.className = "sample-link";
            a.href = `/sample-data/${encodeURIComponent(ds.name)}/${encodeURIComponent(file)}`;
            a.download = file;
            a.textContent = file;
            container.appendChild(a);
        }
    }
}

// ==================== Sample Reports ====================
let allSampleReports = [];

async function loadSampleReports() {
    try {
        const res = await fetch("/sample-reports");
        const data = await res.json();
        allSampleReports = data.reports || [];
    } catch (err) {
        allSampleReports = [];
    }
    renderSampleReportsLinks();
}

function renderSampleReportsLinks() {
    const container = document.getElementById("sample-reports-links");
    const t = translations[currentLang];
    const langTag = currentLang === "ko" ? "_kr_" : "_en_";
    const filtered = allSampleReports.filter(name => name.includes(langTag));
    if (filtered.length === 0) {
        container.innerHTML = `<span style="color:var(--text-muted)">${t.sample_reports_none}</span>`;
        return;
    }
    container.innerHTML = "";
    for (const file of filtered) {
        const a = document.createElement("a");
        a.className = "sample-link";
        a.href = `/sample-reports/${encodeURIComponent(file)}`;
        a.download = file;
        a.textContent = file;
        container.appendChild(a);
    }
}
