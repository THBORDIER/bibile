// Elements
const textInput = document.getElementById('textInput');
const generateBtn = document.getElementById('generateBtn');
const clearBtn = document.getElementById('clearBtn');
const charCount = document.getElementById('charCount');
const statusMessage = document.getElementById('statusMessage');
const progressBar = document.getElementById('progressBar');

// Update character count
function updateCharCount() {
    const count = textInput.value.length;
    charCount.textContent = `${count.toLocaleString()} caractères`;
}

// Show status message
function showStatus(message, type) {
    statusMessage.textContent = message;
    statusMessage.className = `status-message ${type}`;
    statusMessage.classList.remove('hidden');

    if (type === 'success') {
        setTimeout(() => {
            statusMessage.classList.add('hidden');
        }, 5000);
    }
}

// Hide status message
function hideStatus() {
    statusMessage.classList.add('hidden');
}

// Show/hide progress bar
function showProgress() {
    progressBar.classList.remove('hidden');
}

function hideProgress() {
    progressBar.classList.add('hidden');
}

// Clear text
clearBtn.addEventListener('click', () => {
    if (textInput.value.length > 0) {
        if (confirm('Êtes-vous sûr de vouloir effacer tout le texte ?')) {
            textInput.value = '';
            updateCharCount();
            hideStatus();
        }
    }
});

// Update character count on input
textInput.addEventListener('input', updateCharCount);

// Generate Excel file
generateBtn.addEventListener('click', async () => {
    const text = textInput.value.trim();

    // Validation
    if (!text) {
        showStatus('❌ Veuillez coller du texte avant de générer le fichier', 'error');
        textInput.focus();
        return;
    }

    if (text.length < 100) {
        showStatus('⚠️ Le texte semble trop court. Avez-vous copié tout le contenu du PDF ?', 'error');
        return;
    }

    if (!text.includes('Enlèvement')) {
        showStatus('❌ Le texte ne semble pas contenir d\'informations d\'enlèvement. Vérifiez que vous avez copié le bon document.', 'error');
        return;
    }

    // Disable button and show progress
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span class="btn-icon">⏳</span> Génération en cours...';
    showProgress();
    hideStatus();

    try {
        // Send request to server
        const response = await fetch('/generer', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ texte: text })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.erreur || 'Erreur lors de la génération');
        }

        // Get the blob
        const blob = await response.blob();

        // Get filename from header
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = 'Enlevements.xlsx';

        if (contentDisposition) {
            const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
            if (filenameMatch) {
                filename = filenameMatch[1];
            }
        }

        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();

        // Cleanup
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        // Show success message
        showStatus('✅ Fichier Excel généré avec succès ! Le téléchargement a commencé.', 'success');

        // Optional: Clear text after successful generation
        // textInput.value = '';
        // updateCharCount();

    } catch (error) {
        console.error('Error:', error);
        showStatus(`❌ Erreur : ${error.message}`, 'error');
    } finally {
        // Re-enable button
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<span class="btn-icon">⚡</span> Générer le fichier Excel';
        hideProgress();
    }
});

// Initialize
updateCharCount();

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl+Enter to generate
    if (e.ctrlKey && e.key === 'Enter') {
        generateBtn.click();
    }
});

// Auto-save text to localStorage (optional feature)
const STORAGE_KEY = 'bibile_draft';

// Load draft on page load
window.addEventListener('load', () => {
    const draft = localStorage.getItem(STORAGE_KEY);
    if (draft && !textInput.value) {
        if (confirm('Un brouillon a été trouvé. Voulez-vous le restaurer ?')) {
            textInput.value = draft;
            updateCharCount();
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    }
});

// Save draft periodically
let saveTimeout;
textInput.addEventListener('input', () => {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
        if (textInput.value.length > 50) {
            localStorage.setItem(STORAGE_KEY, textInput.value);
        }
    }, 1000);
});

// Clear draft after successful generation
function clearDraft() {
    localStorage.removeItem(STORAGE_KEY);
}
