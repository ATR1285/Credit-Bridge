// CreditBridge Custom JavaScript

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeCharts();
    initializeForms();
    initializeTooltips();
    initializeProgressBars();
});

// Chart initialization
function initializeCharts() {
    // Radar chart for behavioral features
    const radarChartElement = document.getElementById('behavioralRadarChart');
    if (radarChartElement) {
        const features = JSON.parse(radarChartElement.dataset.features || '{}');
        createRadarChart(radarChartElement, features);
    }

    // Score history chart
    const historyChartElement = document.getElementById('scoreHistoryChart');
    if (historyChartElement) {
        const history = JSON.parse(historyChartElement.dataset.history || '[]');
        createScoreHistoryChart(historyChartElement, history);
    }

    // Risk distribution pie chart
    const riskChartElement = document.getElementById('riskDistributionChart');
    if (riskChartElement) {
        const distribution = JSON.parse(riskChartElement.dataset.distribution || '{}');
        createRiskDistributionChart(riskChartElement, distribution);
    }

    // Score distribution histogram
    const scoreDistChartElement = document.getElementById('scoreDistributionChart');
    if (scoreDistChartElement) {
        const ranges = JSON.parse(scoreDistChartElement.dataset.ranges || '[]');
        createScoreDistributionChart(scoreDistChartElement, ranges);
    }
}

// Create radar chart for behavioral features
function createRadarChart(element, features) {
    const ctx = element.getContext('2d');
    
    const labels = [
        'Income Stability',
        'Expense Control',
        'Payment Consistency',
        'Digital Activity',
        'Savings Discipline',
        'Cashflow Health'
    ];
    
    const data = [
        (features.income_stability_index || 0) * 100,
        (features.expense_control_ratio || 0) * 100,
        (features.payment_consistency_score || 0) * 100,
        (features.digital_activity_score || 0) * 100,
        (features.savings_discipline_ratio || 0) * 100,
        (features.cashflow_health_score || 0) * 100
    ];

    new Chart(ctx, {
        type: 'radar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Your Score',
                data: data,
                backgroundColor: 'rgba(79, 70, 229, 0.2)',
                borderColor: 'rgba(79, 70, 229, 1)',
                borderWidth: 2,
                pointBackgroundColor: 'rgba(79, 70, 229, 1)',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: 'rgba(79, 70, 229, 1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: {
                        display: false
                    },
                    suggestedMin: 0,
                    suggestedMax: 100,
                    ticks: {
                        stepSize: 20,
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Create score history line chart
function createScoreHistoryChart(element, history) {
    const ctx = element.getContext('2d');
    
    const labels = history.map(entry => new Date(entry.created_at).toLocaleDateString());
    const scores = history.map(entry => entry.score);

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Credit Score',
                data: scores,
                borderColor: 'rgba(79, 70, 229, 1)',
                backgroundColor: 'rgba(79, 70, 229, 0.1)',
                borderWidth: 3,
                pointBackgroundColor: 'rgba(79, 70, 229, 1)',
                pointBorderColor: '#fff',
                pointBorderWidth: 2,
                pointRadius: 6,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: false,
                    min: 300,
                    max: 900,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Create risk distribution pie chart
function createRiskDistributionChart(element, distribution) {
    const ctx = element.getContext('2d');

    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Low Risk', 'Medium Risk', 'High Risk'],
            datasets: [{
                data: [
                    distribution.low || 0,
                    distribution.medium || 0,
                    distribution.high || 0
                ],
                backgroundColor: [
                    '#10b981',
                    '#f59e0b',
                    '#ef4444'
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        usePointStyle: true
                    }
                }
            }
        }
    });
}

// Create score distribution histogram
function createScoreDistributionChart(element, ranges) {
    const ctx = element.getContext('2d');
    
    const labels = ranges.map(range => range[0]);
    const data = ranges.map(range => range[1]);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Number of Assessments',
                data: data,
                backgroundColor: 'rgba(79, 70, 229, 0.7)',
                borderColor: 'rgba(79, 70, 229, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)'
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                }
            }
        }
    });
}

// Form validation and enhancement
function initializeForms() {
    // Add loading states to forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.classList.add('loading');
                submitButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            }
        });
    });

    // File upload validation
    const fileInputs = document.querySelectorAll('input[type="file"]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            validateFileUpload(e.target);
        });
    });

    // Number input formatting
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            formatNumberInput(e.target);
        });
    });
}

// File upload validation
function validateFileUpload(input) {
    const file = input.files[0];
    if (!file) return;

    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (!allowedTypes.includes(file.type)) {
        showAlert('error', 'Please select a PDF, JPG, or PNG file.');
        input.value = '';
        return;
    }

    if (file.size > maxSize) {
        showAlert('error', 'File size must be less than 10MB.');
        input.value = '';
        return;
    }

    // Show file info
    const fileInfo = document.createElement('small');
    fileInfo.className = 'text-muted';
    fileInfo.textContent = `Selected: ${file.name} (${formatFileSize(file.size)})`;
    
    const existingInfo = input.parentNode.querySelector('.file-info');
    if (existingInfo) {
        existingInfo.remove();
    }
    
    fileInfo.className += ' file-info';
    input.parentNode.appendChild(fileInfo);
}

// Number input formatting (add commas for Indian currency)
function formatNumberInput(input) {
    let value = input.value.replace(/,/g, '');
    if (value && !isNaN(value)) {
        input.value = parseInt(value).toLocaleString('en-IN');
    }
}

// Initialize tooltips
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Initialize progress bars
function initializeProgressBars() {
    const progressBars = document.querySelectorAll('.progress-bar');
    progressBars.forEach(bar => {
        const value = bar.getAttribute('aria-valuenow');
        setTimeout(() => {
            bar.style.width = value + '%';
        }, 500);
    });
}

// Utility functions
function showAlert(type, message, duration = 5000) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    const container = document.querySelector('.container') || document.body;
    container.insertBefore(alertDiv, container.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, duration);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR'
    }).format(amount);
}

// Auto-refresh for dashboards
function initializeAutoRefresh() {
    const refreshElements = document.querySelectorAll('[data-auto-refresh]');
    refreshElements.forEach(element => {
        const interval = parseInt(element.dataset.autoRefresh) || 30000;
        setInterval(() => {
            location.reload();
        }, interval);
    });
}

// Assessment form enhancements
function initializeAssessmentForm() {
    const form = document.getElementById('assessmentForm');
    if (!form) return;

    // Real-time score calculation preview
    const inputs = form.querySelectorAll('input[type="number"]');
    inputs.forEach(input => {
        input.addEventListener('input', calculatePreviewScore);
    });
}

function calculatePreviewScore() {
    // Basic preview calculation (simplified)
    const income = parseFloat(document.getElementById('monthly_income')?.value || 0);
    const expenses = parseFloat(document.getElementById('monthly_expenses')?.value || 0);
    
    if (income > 0) {
        const savingsRatio = Math.max(0, (income - expenses) / income);
        const previewScore = 300 + (savingsRatio * 400);
        
        const previewElement = document.getElementById('scorePreview');
        if (previewElement) {
            previewElement.textContent = Math.round(previewScore);
            previewElement.className = `badge ${getScoreClass(previewScore)}`;
        }
    }
}

function getScoreClass(score) {
    if (score >= 750) return 'bg-success';
    if (score >= 600) return 'bg-warning';
    return 'bg-danger';
}

// Document upload progress
function initializeDocumentUpload() {
    const uploadForm = document.getElementById('documentUploadForm');
    if (!uploadForm) return;

    uploadForm.addEventListener('submit', function(e) {
        const progressContainer = document.getElementById('uploadProgress');
        if (progressContainer) {
            progressContainer.style.display = 'block';
            simulateUploadProgress();
        }
    });
}

function simulateUploadProgress() {
    const progressBar = document.querySelector('#uploadProgress .progress-bar');
    if (!progressBar) return;

    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress >= 100) {
            progress = 100;
            clearInterval(interval);
        }
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', progress);
    }, 200);
}

// Bank portal specific functions
function deleteAssessment(id) {
    if (!confirm('Are you sure you want to delete this assessment?')) {
        return;
    }

    fetch(`/api/assessment/${id}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('success', 'Assessment deleted successfully');
            setTimeout(() => location.reload(), 1000);
        } else {
            showAlert('error', 'Failed to delete assessment: ' + data.error);
        }
    })
    .catch(error => {
        showAlert('error', 'Error deleting assessment: ' + error.message);
    });
}

// Export functionality
function exportData(type) {
    showAlert('info', 'Export functionality coming soon...');
}

// Print functionality
function printReport() {
    window.print();
}

// Initialize all components when page loads
document.addEventListener('DOMContentLoaded', function() {
    initializeAssessmentForm();
    initializeDocumentUpload();
    initializeAutoRefresh();
});