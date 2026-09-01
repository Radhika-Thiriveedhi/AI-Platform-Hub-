// AI Platform Hub - Interactive Controller
(function() {
    'use strict';

    // ── Sidebar Toggle (Mobile) ──────────────────────────
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggleBtn = document.getElementById('sidebarToggle');
    const closeBtn = document.getElementById('sidebarClose');

    function openSidebar() {
        if (sidebar) sidebar.classList.add('open');
        if (overlay) overlay.classList.add('open');
    }

    function closeSidebar() {
        if (sidebar) sidebar.classList.remove('open');
        if (overlay) overlay.classList.remove('open');
    }

    if (toggleBtn) toggleBtn.addEventListener('click', openSidebar);
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (overlay) overlay.addEventListener('click', closeSidebar);

    // ── Modals Controller ────────────────────────────────
    const registerModal = document.getElementById('registerModelModal');
    const userModal = document.getElementById('userAccountModal');

    function openModal(modal) {
        if (modal) {
            modal.classList.add('open');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeModal(modal) {
        if (modal) {
            modal.classList.remove('open');
            document.body.style.overflow = '';
        }
    }

    function closeAllModals() {
        closeModal(registerModal);
        closeModal(userModal);
    }

    // Open triggers
    document.querySelectorAll('.btn-open-register-model').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            openModal(registerModal);
        });
    });

    document.querySelectorAll('.btn-open-user-account').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            openModal(userModal);
        });
    });

    // Close triggers
    document.querySelectorAll('.modal-close-trigger').forEach(function(btn) {
        btn.addEventListener('click', function() {
            closeAllModals();
        });
    });

    // Close when clicking overlay backdrop
    [registerModal, userModal].forEach(function(modal) {
        if (modal) {
            modal.addEventListener('click', function(e) {
                if (e.target === modal) {
                    closeModal(modal);
                }
            });
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeSidebar();
            closeAllModals();
        }
    });

    // ── Copy API Key to Clipboard ────────────────────────
    const copyBtn = document.getElementById('copyApiKeyBtn');
    const apiKeyText = document.getElementById('apiKeyText');
    if (copyBtn && apiKeyText) {
        copyBtn.addEventListener('click', function() {
            const key = apiKeyText.textContent.trim();
            navigator.clipboard.writeText(key).then(function() {
                const originalText = copyBtn.textContent;
                copyBtn.textContent = 'Copied!';
                copyBtn.style.color = 'var(--color-success)';
                setTimeout(function() {
                    copyBtn.textContent = originalText;
                    copyBtn.style.color = '';
                }, 2000);
            }).catch(function() {
                alert('API Key: ' + key);
            });
        });
    }

    // ── Register Model Form Submission ───────────────────
    const regForm = document.getElementById('registerModelForm');
    if (regForm) {
        regForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const name = document.getElementById('regModelName').value.trim();
            const version = document.getElementById('regModelVersion').value.trim() || '1.0.0';
            const framework = document.getElementById('regModelFramework').value;
            const task = document.getElementById('regModelTask').value;
            const stage = document.getElementById('regModelStage').value;
            const traffic = document.getElementById('regModelTraffic').value;
            const accuracy = document.getElementById('regModelAccuracy').value.trim() || '98.0%';

            if (!name) {
                alert('Please enter a model identifier name.');
                return;
            }

            // Map stage class
            let stageClass = 'badge-stage-production';
            if (stage === 'Canary') stageClass = 'badge-stage-canary';
            if (stage === 'Staging') stageClass = 'badge-stage-staging';

            // Check if on Dashboard table
            const endpointsTableBody = document.querySelector('.table-section-card .data-table tbody');
            if (endpointsTableBody) {
                const newRow = document.createElement('tr');
                newRow.innerHTML = `
                    <td class="model-name-cell">${escapeHtml(name)} <span style="font-size:0.65rem;color:var(--color-success);font-weight:700;">(NEW)</span></td>
                    <td><span class="pill-version">${escapeHtml(version)}</span></td>
                    <td><span class="pill-framework">${escapeHtml(framework)}</span></td>
                    <td>${escapeHtml(task)}</td>
                    <td class="metric-accuracy">${escapeHtml(accuracy)}</td>
                    <td><span class="pill-traffic">${escapeHtml(traffic)}</span></td>
                    <td><span class="badge ${stageClass}">${escapeHtml(stage)}</span></td>
                    <td><a href="/chat/" class="btn-table-action">Test</a></td>
                `;
                endpointsTableBody.insertBefore(newRow, endpointsTableBody.firstChild);
            }

            // Increment active models badge if present
            const activeModelsVal = document.querySelector('.stat-card-telemetry .stat-card-value');
            if (activeModelsVal && !isNaN(parseInt(activeModelsVal.textContent))) {
                activeModelsVal.textContent = parseInt(activeModelsVal.textContent) + 1;
            }

            closeModal(registerModal);
            regForm.reset();

            // Display floating success toast
            showToast(`Model "${name}" successfully registered and deployed to ${stage} stage!`);
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function showToast(message) {
        let toast = document.getElementById('platformToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'platformToast';
            toast.style.cssText = 'position:fixed;bottom:24px;right:24px;background:#0f172a;color:#ffffff;padding:0.75rem 1.25rem;border-radius:8px;font-size:0.85rem;font-weight:500;box-shadow:0 10px 15px -3px rgba(0,0,0,0.2);z-index:9999;transition:all 0.25s ease;transform:translateY(100px);opacity:0;display:flex;align-items:center;gap:8px;border:1px solid #334155;';
            document.body.appendChild(toast);
        }
        toast.innerHTML = `<span style="color:#22c55e;font-size:1rem;">✓</span> <span>${escapeHtml(message)}</span>`;
        toast.style.transform = 'translateY(0)';
        toast.style.opacity = '1';

        setTimeout(function() {
            toast.style.transform = 'translateY(100px)';
            toast.style.opacity = '0';
        }, 4000);
    }
})();
