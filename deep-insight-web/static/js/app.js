// ==================== State ====================
let currentUploadId = null;
let currentSessionId = null;
let currentRequestId = null;
let countdownTimer = null;
let analysisStartTime = null;
let elapsedTimer = null;
let firstOutputReceived = false;

// ==================== DOM References ====================
let uploadForm, uploadBtn, statusDiv, analyzeSection, analyzeBtn, queryInput;
let outputSection, outputDiv, downloadSection, downloadList;
let planModal, planText, modalRevision, modalMax, modalCountdown;
let feedbackInput, approveBtn, rejectBtn;

function initDOMRefs() {
    uploadForm = document.getElementById("upload-form");
    uploadBtn = document.getElementById("upload-btn");
    statusDiv = document.getElementById("status");
    analyzeSection = document.getElementById("analyze-section");
    analyzeBtn = document.getElementById("analyze-btn");
    queryInput = document.getElementById("query");
    outputSection = document.getElementById("output-section");
    outputDiv = document.getElementById("output");
    downloadSection = document.getElementById("download-section");
    downloadList = document.getElementById("download-list");
    planModal = document.getElementById("plan-modal");
    planText = document.getElementById("plan-text");
    modalRevision = document.getElementById("modal-revision");
    modalMax = document.getElementById("modal-max");
    modalCountdown = document.getElementById("modal-countdown");
    feedbackInput = document.getElementById("feedback-input");
    approveBtn = document.getElementById("approve-btn");
    rejectBtn = document.getElementById("reject-btn");
}

// ==================== Init ====================
document.addEventListener("DOMContentLoaded", () => {
    initDOMRefs();
    applyLanguage();
    loadSampleData();
    loadSampleReports();
    initUpload();
    initAnalyze();
    initPlanModal();
});
