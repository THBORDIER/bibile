// Elements
const textInput = document.getElementById('textInput');
const generateBtn = document.getElementById('generateBtn');
const clearBtn = document.getElementById('clearBtn');
const charCount = document.getElementById('charCount');
const statusMessage = document.getElementById('statusMessage');
const progressBar = document.getElementById('progressBar');
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const dropZoneProgress = document.getElementById('dropZoneProgress');

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
        const response = await fetch('/generer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texte: text })
        });

        // Check if the response is JSON (duplicate detection) or blob (Excel)
        const contentType = response.headers.get('Content-Type') || '';

        if (contentType.includes('application/json')) {
            const data = await response.json();

            if (data.erreur) {
                throw new Error(data.erreur);
            }

            if (data.doublons) {
                // Show duplicate modal
                hideProgress();
                generateBtn.disabled = false;
                generateBtn.innerHTML = 'Générer le fichier Excel';
                showDuplicateModal(data);
                return;
            }
        }

        if (!response.ok) {
            throw new Error('Erreur lors de la génération');
        }

        // Download the Excel blob
        downloadBlob(response);

    } catch (error) {
        console.error('Error:', error);
        showStatus(`Erreur : ${error.message}`, 'error');
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = 'Générer le fichier Excel';
        hideProgress();
    }
});

// Save to DB only (no Excel download)
const saveDbBtn = document.getElementById('saveDbBtn');
saveDbBtn.addEventListener('click', async () => {
    const text = textInput.value.trim();

    if (!text) {
        showStatus('Veuillez coller du texte ou importer un PDF', 'error');
        textInput.focus();
        return;
    }

    if (!text.includes('Enlèvement') && !text.includes('Enl\u00e8vement')) {
        showStatus('Le texte ne contient pas d\'informations d\'enlèvement.', 'error');
        return;
    }

    saveDbBtn.disabled = true;
    saveDbBtn.innerHTML = 'Sauvegarde...';
    showProgress();
    hideStatus();

    try {
        const response = await fetch('/sauvegarder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ texte: text })
        });

        const data = await response.json();

        if (data.erreur) throw new Error(data.erreur);

        let msg = `${data.nb_total} enlèvement(s) traité(s)`;
        if (data.nb_saved > 0) msg += ` — ${data.nb_saved} nouveau(x)`;
        if (data.nb_updated > 0) msg += ` — ${data.nb_updated} mis à jour`;
        if (data.erreurs_controle && data.erreurs_controle.length > 0) {
            msg += ` (${data.erreurs_controle.length} alerte(s))`;
        }
        showStatus(msg, 'success');
        clearDraft();

    } catch (error) {
        console.error('Save error:', error);
        showStatus(`Erreur : ${error.message}`, 'error');
    } finally {
        saveDbBtn.disabled = false;
        saveDbBtn.innerHTML = 'Sauvegarder en BDD';
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

// ===== Download Excel blob =====
async function downloadBlob(response) {
    const blob = await response.blob();
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = 'Enlevements.xlsx';
    if (contentDisposition) {
        const match = contentDisposition.match(/filename="?(.+)"?/);
        if (match) filename = match[1];
    }
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    showStatus('Fichier Excel généré avec succès ! Le téléchargement a commencé.', 'success');
}

// ===== Duplicate Modal =====
const duplicateModal = document.getElementById('duplicateModal');

function showDuplicateModal(data) {
    const msg = document.getElementById('duplicateMessage');
    const details = document.getElementById('duplicateDetails');

    msg.textContent = `${data.nb_doublons} enlèvement(s) sur ${data.nb_total} existent déjà en base. ${data.nb_nouveaux} nouveau(x).`;

    // Show some duplicate details
    if (data.details_doublons && data.details_doublons.length > 0) {
        let html = '<div style="margin-top: 8px;">';
        for (const d of data.details_doublons) {
            const date = new Date(d.extraction_date).toLocaleDateString('fr-FR');
            html += `<div style="padding: 4px 0;">Enlèvement ${d.num} — ${d.societe} <span style="color: var(--text-muted);">(${date})</span></div>`;
        }
        if (data.nb_doublons > 5) {
            html += `<div style="padding: 4px 0; color: var(--text-muted);">... et ${data.nb_doublons - 5} autre(s)</div>`;
        }
        html += '</div>';
        details.innerHTML = html;
    } else {
        details.innerHTML = '';
    }

    // Store session_id for confirmation
    duplicateModal.dataset.sessionId = data.session_id;
    duplicateModal.classList.add('visible');
}

// Handle modal button clicks
duplicateModal.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;

    const action = btn.dataset.action;
    const sessionId = duplicateModal.dataset.sessionId;

    duplicateModal.classList.remove('visible');

    if (action === 'cancel') return;

    // Send confirmation
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span class="btn-icon">⏳</span> Génération en cours...';
    showProgress();
    hideStatus();

    try {
        const response = await fetch('/generer/confirmer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, action: action })
        });

        const contentType = response.headers.get('Content-Type') || '';
        if (contentType.includes('application/json')) {
            const data = await response.json();
            if (data.erreur) throw new Error(data.erreur);
        }

        if (!response.ok) throw new Error('Erreur lors de la confirmation');

        await downloadBlob(response);

    } catch (error) {
        console.error('Error:', error);
        showStatus(`Erreur : ${error.message}`, 'error');
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = 'Générer le fichier Excel';
        hideProgress();
    }
});

// ===== PDF Drag-and-Drop =====

async function uploadPDF(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showStatus('Ce fichier n\'est pas un PDF.', 'error');
        return;
    }

    // Show loading state
    dropZone.classList.add('drop-zone-loading');
    dropZoneProgress.classList.remove('hidden');
    hideStatus();

    try {
        const formData = new FormData();
        formData.append('pdf', file);

        const response = await fetch('/upload-pdf', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.erreur || 'Erreur lors de l\'extraction du PDF');
        }

        // Fill textarea with extracted text
        textInput.value = data.texte;
        updateCharCount();
        showStatus('PDF importe avec succes. Verifiez le texte puis cliquez sur Generer.', 'success');

    } catch (error) {
        console.error('PDF upload error:', error);
        showStatus(`Erreur : ${error.message}`, 'error');
    } finally {
        dropZone.classList.remove('drop-zone-loading');
        dropZoneProgress.classList.add('hidden');
    }
}

async function uploadMultiplePDFs(files) {
    const pdfFiles = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfFiles.length === 0) {
        showStatus('Aucun fichier PDF detecte.', 'error');
        return;
    }

    // Single file → classic flow (textarea)
    if (pdfFiles.length === 1) {
        uploadPDF(pdfFiles[0]);
        return;
    }

    // Multiple files → batch import (upload + save to BDD directly)
    dropZone.classList.add('drop-zone-loading');
    dropZoneProgress.classList.remove('hidden');
    const progressText = dropZoneProgress.querySelector('p');
    hideStatus();

    let successes = 0;
    let failures = 0;
    let totalSaved = 0;
    let totalUpdated = 0;
    const errors = [];

    for (let i = 0; i < pdfFiles.length; i++) {
        const file = pdfFiles[i];
        progressText.textContent = `Import ${i + 1}/${pdfFiles.length} : ${file.name}...`;

        try {
            // Step 1: Upload PDF → extract text
            const formData = new FormData();
            formData.append('pdf', file);
            const uploadResp = await fetch('/upload-pdf', { method: 'POST', body: formData });
            const uploadData = await uploadResp.json();

            if (!uploadResp.ok) {
                throw new Error(uploadData.erreur || 'Extraction echouee');
            }

            const texte = uploadData.texte;
            if (!texte || texte.length < 50) {
                throw new Error('Texte extrait trop court');
            }

            // Step 2: Save to BDD
            const saveResp = await fetch('/sauvegarder', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ texte: texte })
            });
            const saveData = await saveResp.json();

            if (saveData.erreur) {
                throw new Error(saveData.erreur);
            }

            successes++;
            totalSaved += (saveData.nb_saved || 0);
            totalUpdated += (saveData.nb_updated || 0);

        } catch (error) {
            failures++;
            errors.push(`${file.name}: ${error.message}`);
            console.error(`Erreur import ${file.name}:`, error);
        }
    }

    dropZone.classList.remove('drop-zone-loading');
    dropZoneProgress.classList.add('hidden');
    progressText.textContent = 'Extraction du texte en cours...';

    // Build result message
    let msg = `${successes}/${pdfFiles.length} PDF importe(s)`;
    if (totalSaved > 0) msg += ` — ${totalSaved} enlevement(s) nouveau(x)`;
    if (totalUpdated > 0) msg += ` — ${totalUpdated} mis a jour`;
    if (failures > 0) msg += ` — ${failures} echec(s)`;

    showStatus(msg, failures === 0 ? 'success' : (successes > 0 ? 'success' : 'error'));

    if (errors.length > 0) {
        console.warn('Erreurs import batch:', errors);
    }
}

// Drag events
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drop-zone-active');
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drop-zone-active');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drop-zone-active');

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadMultiplePDFs(files);
    }
});

// File input (browse button)
fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
        uploadMultiplePDFs(fileInput.files);
        fileInput.value = ''; // Reset for re-upload
    }
});
