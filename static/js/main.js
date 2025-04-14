// Create floating particles
function createParticles() {
    const container = document.getElementById('particles');
    if (!container) return;

    for (let i = 0; i < 50; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + 'vw';
        particle.style.top = Math.random() * 100 + 'vh';
        particle.style.animationDelay = Math.random() * 20 + 's';
        container.appendChild(particle);
    }
}

// Initialize particles on load
window.addEventListener('load', createParticles);

// File upload preview
function updateFileName(input) {
    if (!input) return;
    
    const fileName = input.files[0]?.name;
    const selectedFile = document.getElementById('selected-file');
    const uploadBtn = document.getElementById('upload-btn');
    
    if (selectedFile) {
        selectedFile.textContent = fileName || '';
    }
    if (uploadBtn) {
        uploadBtn.disabled = !fileName;
    }
}

// Drag and drop functionality
function initializeDragAndDrop() {
    const uploadArea = document.querySelector('.upload-area');
    if (!uploadArea) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, unhighlight, false);
    });

    uploadArea.addEventListener('drop', handleDrop, false);
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function highlight(e) {
    const uploadArea = e.currentTarget;
    uploadArea.classList.add('border-primary');
}

function unhighlight(e) {
    const uploadArea = e.currentTarget;
    uploadArea.classList.remove('border-primary');
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    const fileInput = document.getElementById('scan-file');
    
    if (fileInput) {
        fileInput.files = files;
        updateFileName(fileInput);
    }
}

// Flash messages auto-dismiss
function initializeFlashMessages() {
    const flashMessages = document.querySelectorAll('.alert-dismissible');
    flashMessages.forEach(message => {
        setTimeout(() => {
            const closeButton = message.querySelector('.btn-close');
            if (closeButton) {
                closeButton.click();
            }
        }, 5000);
    });
}

// Initialize all functionality
document.addEventListener('DOMContentLoaded', () => {
    createParticles();
    initializeDragAndDrop();
    initializeFlashMessages();
}); 