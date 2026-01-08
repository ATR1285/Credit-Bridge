/* ═══════════════════════════════════════════════════════════════════════════
   CreditBridge - Main JavaScript
   Chart.js Integration & UI Enhancements
   ═══════════════════════════════════════════════════════════════════════════ */

// ─── Dark Mode Detection ────────────────────────────────────────────────────
function isDarkMode() {
    return document.body.classList.contains('dark-mode');
}

// ─── Chart.js Default Configuration ────────────────────────────────────────
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.padding = 20;

// Dynamic color settings based on theme
function getChartDefaults() {
    const dark = isDarkMode();
    return {
        textColor: dark ? '#f1f5f9' : '#64748b',
        gridColor: dark ? '#374151' : '#e5e7eb',
        tickColor: dark ? '#f1f5f9' : '#374151'
    };
}

// Apply defaults
Chart.defaults.color = getChartDefaults().textColor;

// Color palette - with light and dark variants
const chartColors = {
    primary: '#4f46e5',
    secondary: '#7c3aed',
    success: '#10b981',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#06b6d4',
    primaryAlpha: 'rgba(79, 70, 229, 0.2)',
    secondaryAlpha: 'rgba(124, 58, 237, 0.2)',
    successAlpha: 'rgba(16, 185, 129, 0.2)',
    warningAlpha: 'rgba(245, 158, 11, 0.2)',
    dangerAlpha: 'rgba(239, 68, 68, 0.2)',
    // Lighter versions for dark mode
    successLight: '#34D399',
    warningLight: '#FBBF24',
    dangerLight: '#F87171'
};

// Get scale options for Chart.js with dark mode support
function getChartScaleOptions() {
    const defaults = getChartDefaults();
    return {
        y: {
            ticks: { color: defaults.tickColor },
            grid: { color: defaults.gridColor }
        },
        x: {
            ticks: { color: defaults.tickColor },
            grid: { color: defaults.gridColor }
        }
    };
}

// Get legend options with dark mode support
function getChartLegendOptions() {
    const defaults = getChartDefaults();
    return {
        labels: { color: defaults.textColor }
    };
}

// Get risk chart colors based on theme
function getRiskChartColors() {
    const dark = isDarkMode();
    return {
        backgrounds: dark
            ? [chartColors.successLight, chartColors.warningLight, chartColors.dangerLight]
            : [chartColors.success, chartColors.warning, chartColors.danger],
        borders: dark
            ? ['#10b981', '#f59e0b', '#ef4444']
            : ['#059669', '#d97706', '#dc2626']
    };
}

// ─── Radar Chart (Behavioral Metrics) ──────────────────────────────────────
function createRadarChart(canvasId, features) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const defaults = getChartDefaults();
    const dark = isDarkMode();

    const labels = [
        'Income Stability',
        'Expense Control',
        'Payment Consistency',
        'Digital Activity',
        'Savings Discipline',
        'Entrepreneurial'
    ];

    const data = [
        (features.income_stability_index || 0) * 100,
        (features.expense_control_ratio || 0) * 100,
        (features.payment_consistency_score || 0) * 100,
        (features.digital_activity_score || 0) * 100,
        (features.savings_discipline_ratio || 0) * 100,
        (features.entrepreneurial_score || 0) * 100
    ];

    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Your Profile',
                data: data,
                backgroundColor: chartColors.primaryAlpha,
                borderColor: chartColors.primary,
                borderWidth: 2,
                pointBackgroundColor: chartColors.primary,
                pointBorderColor: dark ? '#1e293b' : '#fff',
                pointBorderWidth: 2,
                pointRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        stepSize: 20,
                        display: false,
                        color: defaults.tickColor
                    },
                    grid: {
                        color: defaults.gridColor
                    },
                    angleLines: {
                        color: defaults.gridColor
                    },
                    pointLabels: {
                        color: defaults.textColor,
                        font: {
                            size: 11,
                            weight: 500
                        }
                    }
                }
            }
        }
    });
}

// ─── Line Chart (Score History) ────────────────────────────────────────────
function createScoreHistoryChart(canvasId, historyData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const defaults = getChartDefaults();
    const dark = isDarkMode();
    const labels = historyData.map(item => item.date);
    const scores = historyData.map(item => item.score);

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Credit Score',
                data: scores,
                borderColor: chartColors.primary,
                backgroundColor: chartColors.primaryAlpha,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: chartColors.primary,
                pointBorderColor: dark ? '#1e293b' : '#fff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    min: 300,
                    max: 900,
                    ticks: { color: defaults.tickColor },
                    grid: { color: defaults.gridColor }
                },
                x: {
                    ticks: { color: defaults.tickColor },
                    grid: { display: false }
                }
            }
        }
    });
}

// ─── Pie Chart (Risk Distribution) ─────────────────────────────────────────
function createRiskPieChart(canvasId, riskData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    const defaults = getChartDefaults();
    const riskColors = getRiskChartColors();

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Low Risk', 'Medium Risk', 'High Risk'],
            datasets: [{
                data: [riskData.low || 0, riskData.medium || 0, riskData.high || 0],
                backgroundColor: riskColors.backgrounds,
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: defaults.textColor }
                }
            }
        }
    });
}

// ─── Bar Chart (Daily Assessments) ─────────────────────────────────────────
function createDailyAssessmentsChart(canvasId, dailyData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dailyData.labels || [],
            datasets: [{
                label: 'Assessments',
                data: dailyData.values || [],
                backgroundColor: chartColors.primaryAlpha,
                borderColor: chartColors.primary,
                borderWidth: 2,
                borderRadius: 8,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                        color: getChartDefaults().tickColor
                    },
                    grid: {
                        color: getChartDefaults().gridColor
                    }
                },
                x: {
                    ticks: { color: getChartDefaults().tickColor },
                    grid: { display: false }
                }
            }
        }
    });
}

// ─── Multi-line Chart (Analytics Trends) ───────────────────────────────────
function createTrendsChart(canvasId, trendsData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: trendsData.labels || [],
            datasets: [
                {
                    label: 'Low Risk',
                    data: trendsData.low || [],
                    borderColor: chartColors.success,
                    backgroundColor: 'transparent',
                    tension: 0.4,
                    pointRadius: 3
                },
                {
                    label: 'Medium Risk',
                    data: trendsData.medium || [],
                    borderColor: chartColors.warning,
                    backgroundColor: 'transparent',
                    tension: 0.4,
                    pointRadius: 3
                },
                {
                    label: 'High Risk',
                    data: trendsData.high || [],
                    borderColor: chartColors.danger,
                    backgroundColor: 'transparent',
                    tension: 0.4,
                    pointRadius: 3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: getChartDefaults().textColor }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: getChartDefaults().tickColor },
                    grid: { color: getChartDefaults().gridColor }
                },
                x: {
                    ticks: { color: getChartDefaults().tickColor },
                    grid: { display: false }
                }
            }
        }
    });
}

// ─── Form Validation Helpers ───────────────────────────────────────────────
function initFormValidation() {
    const forms = document.querySelectorAll('form[data-validate]');

    forms.forEach(form => {
        form.addEventListener('submit', function (e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });

        // Disable submit button after first click to prevent double submission
        form.addEventListener('submit', function () {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && form.checkValidity()) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
            }
        });
    });
}

// ─── File Upload Enhancement ───────────────────────────────────────────────
function initFileUpload() {
    const uploadZones = document.querySelectorAll('.upload-zone');

    uploadZones.forEach(zone => {
        const input = zone.querySelector('input[type="file"]');
        if (!input) return;

        // Click to upload
        zone.addEventListener('click', () => input.click());

        // Drag and drop
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });

        zone.addEventListener('dragleave', () => {
            zone.classList.remove('dragover');
        });

        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');

            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                updateFileDisplay(zone, e.dataTransfer.files[0]);
            }
        });

        // File selection
        input.addEventListener('change', () => {
            if (input.files.length) {
                updateFileDisplay(zone, input.files[0]);
            }
        });
    });
}

function updateFileDisplay(zone, file) {
    const fileNameEl = zone.querySelector('.file-name');
    const iconEl = zone.querySelector('.upload-icon');

    if (fileNameEl) {
        fileNameEl.textContent = file.name;
    }

    if (iconEl) {
        iconEl.classList.remove('bi-cloud-upload');
        iconEl.classList.add('bi-file-earmark-check');
    }

    zone.classList.add('has-file');
}

// ─── Tooltip Initialization ────────────────────────────────────────────────
function initTooltips() {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
}

// ─── Alert Auto-dismiss ────────────────────────────────────────────────────
function initAlertDismiss() {
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.add('fade');
            setTimeout(() => alert.remove(), 150);
        }, 5000);
    });
}

// ─── Number Formatting ─────────────────────────────────────────────────────
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0
    }).format(amount);
}

function formatNumber(num) {
    return new Intl.NumberFormat('en-IN').format(num);
}

// ─── Score Color Helper ────────────────────────────────────────────────────
function getScoreClass(score) {
    if (score >= 750) return 'score-high';
    if (score >= 600) return 'score-medium';
    return 'score-low';
}

function getRiskBadgeClass(category) {
    const cat = (category || '').toLowerCase();
    if (cat.includes('low')) return 'badge-low';
    if (cat.includes('medium')) return 'badge-medium';
    return 'badge-high';
}

// ─── Confirmation Dialogs ──────────────────────────────────────────────────
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// ─── API Helper ────────────────────────────────────────────────────────────
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    try {
        const response = await fetch(url, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        return { success: false, error: error.message };
    }
}

// ─── Delete Assessment (Bank Portal) ───────────────────────────────────────
function deleteAssessment(id) {
    confirmAction('Are you sure you want to delete this assessment?', async () => {
        const result = await apiRequest(`/api/bank/assessment/${id}`, 'DELETE');
        if (result.success) {
            window.location.reload();
        } else {
            alert('Failed to delete assessment: ' + (result.error || 'Unknown error'));
        }
    });
}

// ─── Document Status Update ────────────────────────────────────────────────
async function updateDocumentStatus(docId, status) {
    const result = await apiRequest(`/api/bank/document/${docId}/status`, 'POST', { status });
    if (result.success) {
        window.location.reload();
    } else {
        alert('Failed to update document status');
    }
}

// ─── Initialize Everything on DOM Ready ────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initFormValidation();
    initFileUpload();
    initTooltips();
    initAlertDismiss();

    // Add smooth scroll behavior
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // Add fade-in animation to cards
    document.querySelectorAll('.card').forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.classList.add('animate-fade-in');
    });
});

// ─── Export functions for global use ───────────────────────────────────────
window.CreditBridge = {
    createRadarChart,
    createScoreHistoryChart,
    createRiskPieChart,
    createDailyAssessmentsChart,
    createTrendsChart,
    formatCurrency,
    formatNumber,
    getScoreClass,
    getRiskBadgeClass,
    deleteAssessment,
    updateDocumentStatus,
    apiRequest
};
