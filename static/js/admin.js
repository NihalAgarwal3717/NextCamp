/**
 * NextCamp - Admin Panel Logic
 * Handles CCTV damage review & fine issuance (₹500),
 * Worker Management CRUD (Add, Edit, List, Delete),
 * Dedicated Worker Reviews Log, and Problem Ticket dispatch board.
 */

let allWorkersCache = [];
let allAdminTicketsCache = [];
let allReviewsCache = [];

// =============================================================================
// CCTV DAMAGE REVIEW & DISCIPLINARY FINE ISSUANCE
// =============================================================================

// =============================================================================
// CAMPUS FINE MANAGEMENT & DISCIPLINARY SYSTEM
// =============================================================================

let allAdminStudentsCache = [];
let allAdminFinesCache = [];

async function fetchAdminStudentStatus() {
    try {
        const res = await fetch('/api/student/profile');
        if (!res.ok) return;
        const student = await res.json();

        const badge = document.getElementById('adminStudentStandingBadge');
        const fineText = document.getElementById('adminStudentFineText');

        if (fineText) fineText.innerText = `₹${student.fine_amount || 0}`;

        if (badge) {
            badge.innerText = student.status || 'Good Standing 🟢';
            if (student.status && student.status.includes('Action Required')) {
                badge.className = 'text-xs font-bold text-rose-400 animate-pulse';
            } else {
                badge.className = 'text-xs font-bold text-emerald-400';
            }
        }
    } catch (err) {
        console.error('Error fetching student standing for admin:', err);
    }
}

// Fetch students for dropdowns
// Fetch students for dropdowns
async function fetchAdminStudentsDropdown() {
    const fineSelect = document.getElementById('adminFineStudentSelect');
    const historySelect = document.getElementById('adminHistoryStudentSelect');
    const cctvSelect = document.getElementById('cctvStudentSelect');

    try {
        const res = await fetch('/api/admin/students');
        if (!res.ok) return;
        allAdminStudentsCache = await res.json();

        if (fineSelect) {
            if (allAdminStudentsCache.length === 0) {
                fineSelect.innerHTML = `<option value="">No student accounts found</option>`;
            } else {
                fineSelect.innerHTML = allAdminStudentsCache.map(s => `
                    <option value="${s.id}">${s.name} (${s.student_id || s.email}) — Dues: ₹${s.fine_amount || 0} [${s.status || 'Good Standing'}]</option>
                `).join('');
            }
        }

        if (historySelect) {
            const currentSelected = historySelect.value;
            if (allAdminStudentsCache.length === 0) {
                historySelect.innerHTML = `<option value="">No students available</option>`;
            } else {
                historySelect.innerHTML = `
                    <option value="">-- Choose a student to inspect history --</option>
                    ${allAdminStudentsCache.map(s => `
                        <option value="${s.id}" ${currentSelected == s.id ? 'selected' : ''}>${s.name} (${s.student_id || s.email})</option>
                    `).join('')}
                `;
            }
        }

        if (cctvSelect) {
            const currentSelected = cctvSelect.value;
            if (allAdminStudentsCache.length === 0) {
                cctvSelect.innerHTML = `<option value="">No students found in database</option>`;
            } else {
                cctvSelect.innerHTML = `
                    <option value="">-- Select Student to Hold Responsible --</option>
                    ${allAdminStudentsCache.map(s => `
                        <option value="${s.id}" ${currentSelected == s.id ? 'selected' : ''} data-name="${s.name}" data-sid="${s.student_id || s.email}">${s.name} (${s.student_id || s.email})</option>
                    `).join('')}
                `;
            }
            onCctvStudentChange();
        }
    } catch (err) {
        console.error('Error loading students dropdown:', err);
    }
}

// Dynamic CCTV Damage Review Controls
function onCctvStudentChange() {
    const select = document.getElementById('cctvStudentSelect');
    const label = document.getElementById('cctvIncidentTargetLabel');
    const targetText = document.getElementById('cctvTargetStudentText');

    if (!select || !select.value) {
        if (label) label.innerText = 'Selected Student: None';
        if (targetText) targetText.innerText = 'Select a student above';
        return;
    }

    const selectedOpt = select.options[select.selectedIndex];
    const name = selectedOpt.getAttribute('data-name') || selectedOpt.text;
    const sid = selectedOpt.getAttribute('data-sid') || '';

    if (label) label.innerText = `Selected Student: ${name} (${sid})`;
    if (targetText) targetText.innerText = `${name} (${sid})`;
}

function setCctvFineAmount(amount) {
    const input = document.getElementById('cctvFineAmountInput');
    if (input) {
        input.value = amount;
        updateCctvFineButton();
    }
}

function updateCctvFineButton() {
    const input = document.getElementById('cctvFineAmountInput');
    const display = document.getElementById('cctvFineAmountDisplay');
    const btnText = document.getElementById('btnIssueCctvFineText');

    const amount = input && input.value ? parseInt(input.value, 10) : 0;
    const formatted = amount > 0 ? `₹${amount}` : '₹0';

    if (display) display.innerText = formatted;
    if (btnText) btnText.innerText = `Review & Issue Fine ${formatted}`;
}

function openCctvReviewConfirmationModal() {
    const select = document.getElementById('cctvStudentSelect');
    const amountInput = document.getElementById('cctvFineAmountInput');
    const modal = document.getElementById('cctvReviewModal');

    if (!select || !select.value) {
        showToast('Please select a student from the database first.', 'error');
        if (select) select.focus();
        return;
    }

    const amount = amountInput ? parseInt(amountInput.value, 10) : 0;
    if (!amount || amount <= 0) {
        showToast('Please enter a valid fine amount greater than ₹0.', 'error');
        if (amountInput) amountInput.focus();
        return;
    }

    const selectedOpt = select.options[select.selectedIndex];
    const name = selectedOpt.getAttribute('data-name') || selectedOpt.text;
    const sid = selectedOpt.getAttribute('data-sid') || '';

    const modalName = document.getElementById('modalCctvStudentName');
    const modalId = document.getElementById('modalCctvStudentId');
    const modalAmount = document.getElementById('modalCctvFineAmount');

    if (modalName) modalName.innerText = name;
    if (modalId) modalId.innerText = sid;
    if (modalAmount) modalAmount.innerText = `₹${amount}`;

    if (modal) modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
}

function closeCctvReviewConfirmationModal() {
    const modal = document.getElementById('cctvReviewModal');
    if (modal) modal.classList.add('hidden');
}

async function confirmIssueCctvFine() {
    const select = document.getElementById('cctvStudentSelect');
    const amountInput = document.getElementById('cctvFineAmountInput');
    const confirmBtn = document.getElementById('btnConfirmIssueCctvFine');

    if (!select || !select.value) {
        showToast('Please select a student.', 'error');
        return;
    }

    const userId = parseInt(select.value, 10);
    const amount = amountInput ? parseInt(amountInput.value, 10) : 500;
    const selectedOpt = select.options[select.selectedIndex];
    const studentName = selectedOpt ? (selectedOpt.getAttribute('data-name') || selectedOpt.text) : 'Student';

    if (confirmBtn) {
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Issuing Penalty...</span>`;
        if (window.lucide) lucide.createIcons();
    }

    try {
        const res = await fetch('/api/issue-fine', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                amount: amount,
                reason: "Classroom 204 — 3:20 PM - Damaged Chair"
            })
        });

        const data = await res.json();

        if (res.ok) {
            closeCctvReviewConfirmationModal();
            showToast(`₹${amount} fine successfully issued to ${studentName}! Disciplinary status updated.`, 'success', 6000);
            fetchAdminStudentStatus();
            fetchAdminStudentsDropdown();
            fetchAdminAllFines();

            // Refresh history inspector if viewing this student
            const historySelect = document.getElementById('adminHistoryStudentSelect');
            if (historySelect && historySelect.value == userId) {
                fetchAdminStudentFineHistory(userId);
            }
        } else {
            showToast(data.error || 'Failed to issue fine.', 'error');
        }
    } catch (err) {
        console.error('Error issuing fine:', err);
        showToast('Network error while issuing fine.', 'error');
    } finally {
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = `<i data-lucide="check" class="w-4 h-4"></i><span>Confirm & Issue Penalty</span>`;
            if (window.lucide) lucide.createIcons();
        }
    }
}

function setAdminFineAmount(amount) {
    const input = document.getElementById('adminFineAmountInput');
    if (input) input.value = amount;
}

// Assign Fine to selected student
async function handleAdminAssignFine(event) {
    event.preventDefault();
    const select = document.getElementById('adminFineStudentSelect');
    const amountInput = document.getElementById('adminFineAmountInput');
    const reasonInput = document.getElementById('adminFineReasonInput');
    const btn = document.getElementById('btnAdminAssignFine');

    if (!select || !select.value) {
        showToast('Please select a student from the database.', 'error');
        return;
    }

    const userId = parseInt(select.value, 10);
    const amount = parseInt(amountInput.value, 10);
    const reason = reasonInput.value.trim();

    if (!amount || amount <= 0) {
        showToast('Please enter a valid fine amount greater than zero.', 'error');
        return;
    }
    if (!reason) {
        showToast('Please enter a reason for the fine.', 'error');
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Assigning Fine...</span>`;
        if (window.lucide) lucide.createIcons();
    }

    try {
        const res = await fetch('/api/admin/fines', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                amount: amount,
                reason: reason
            })
        });

        const data = await res.json();

        if (res.ok) {
            showToast(`₹${amount} fine successfully assigned!`, 'success');
            if (reasonInput) reasonInput.value = '';
            fetchAdminStudentStatus();
            fetchAdminStudentsDropdown();
            fetchAdminAllFines();

            // If history inspector is currently looking at this student, refresh it
            const historySelect = document.getElementById('adminHistoryStudentSelect');
            if (historySelect && historySelect.value == userId) {
                fetchAdminStudentFineHistory(userId);
            }
        } else {
            showToast(data.error || 'Failed to assign fine.', 'error');
        }
    } catch (err) {
        console.error('Error assigning fine:', err);
        showToast('Network error while assigning fine.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="gavel" class="w-4 h-4"></i><span>Assign Fine & Update Standing</span>`;
            if (window.lucide) lucide.createIcons();
        }
    }
}

// Student History Inspector
function onAdminHistoryStudentChange() {
    const historySelect = document.getElementById('adminHistoryStudentSelect');
    if (!historySelect || !historySelect.value) {
        resetAdminHistoryDisplay();
        return;
    }
    fetchAdminStudentFineHistory(historySelect.value);
}

function refreshAdminFineHistory() {
    const historySelect = document.getElementById('adminHistoryStudentSelect');
    if (historySelect && historySelect.value) {
        fetchAdminStudentFineHistory(historySelect.value);
    } else {
        fetchAdminStudentsDropdown();
        showToast('Select a student to audit fine history.', 'info');
    }
}

function resetAdminHistoryDisplay() {
    const countEl = document.getElementById('adminHistoryTotalCount');
    const pendingSumEl = document.getElementById('adminHistoryPendingSum');
    const paidSumEl = document.getElementById('adminHistoryPaidSum');
    const tbody = document.getElementById('adminStudentHistoryTableBody');

    if (countEl) countEl.innerText = '0';
    if (pendingSumEl) pendingSumEl.innerText = '₹0';
    if (paidSumEl) paidSumEl.innerText = '₹0';
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="py-6 text-center text-xs text-slate-500">
                    Select a student from the dropdown above to view fine history.
                </td>
            </tr>
        `;
    }
}

async function fetchAdminStudentFineHistory(userId) {
    const countEl = document.getElementById('adminHistoryTotalCount');
    const pendingSumEl = document.getElementById('adminHistoryPendingSum');
    const paidSumEl = document.getElementById('adminHistoryPaidSum');
    const tbody = document.getElementById('adminStudentHistoryTableBody');

    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="py-6 text-center text-xs text-slate-400">
                    <i data-lucide="loader-2" class="w-4 h-4 animate-spin mx-auto mb-1 text-amber-400"></i>
                    Loading student fine records...
                </td>
            </tr>
        `;
        if (window.lucide) lucide.createIcons();
    }

    try {
        const res = await fetch(`/api/admin/students/${userId}/fines`);
        if (!res.ok) throw new Error('Failed to retrieve student fine history');
        const data = await res.json();

        const fines = data.fines || [];
        if (countEl) countEl.innerText = data.total_fines !== undefined ? data.total_fines : fines.length;
        if (pendingSumEl) pendingSumEl.innerText = `₹${data.total_pending_amount !== undefined ? data.total_pending_amount : 0}`;
        if (paidSumEl) paidSumEl.innerText = `₹${data.total_paid_amount !== undefined ? data.total_paid_amount : 0}`;

        if (tbody) {
            if (fines.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6" class="py-6 text-center text-xs text-emerald-400 font-semibold">
                            ✓ No fine history on record for this student.
                        </td>
                    </tr>
                `;
            } else {
                tbody.innerHTML = fines.map(f => {
                    const isPaid = f.status === 'Paid';
                    const statusBadge = isPaid ?
                        `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">Paid 🟢</span>` :
                        `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30 animate-pulse">Pending 🔴</span>`;

                    return `
                        <tr class="hover:bg-slate-900/60 transition-colors">
                            <td class="py-2.5 px-3 font-mono font-bold text-amber-400 text-xs">${f.fine_id || ('#FINE-' + f.id)}</td>
                            <td class="py-2.5 px-3 text-slate-200">${f.reason || 'Penalty'}</td>
                            <td class="py-2.5 px-3 font-mono font-bold ${isPaid ? 'text-slate-300' : 'text-rose-400'}">₹${f.amount}</td>
                            <td class="py-2.5 px-3 font-mono text-slate-400 text-[11px]">${f.date_assigned || f.created_at || '-'}</td>
                            <td class="py-2.5 px-3">${statusBadge}</td>
                            <td class="py-2.5 px-3 font-mono text-slate-400 text-[11px]">${f.paid_at || '—'}</td>
                        </tr>
                    `;
                }).join('');
            }
        }
        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error fetching student fine history:', err);
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="py-4 text-center text-xs text-rose-400">
                        Error fetching student fine records.
                    </td>
                </tr>
            `;
        }
    }
}

// Master Campus Fines Ledger
async function fetchAdminAllFines() {
    const tbody = document.getElementById('adminAllFinesTableBody');
    if (!tbody) return;

    try {
        const res = await fetch('/api/admin/fines');
        if (!res.ok) throw new Error('Failed to retrieve master fines');
        const data = await res.json();

        allAdminFinesCache = Array.isArray(data) ? data : (data.fines || []);

        if (allAdminFinesCache.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="py-8 text-center text-xs text-slate-400">
                        No fines have been issued campus-wide.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = allAdminFinesCache.map(f => {
            const isPaid = f.status === 'Paid';
            const statusBadge = isPaid ?
                `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">PAID 🟢</span>` :
                `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30 animate-pulse">PENDING 🔴</span>`;

            return `
                <tr class="hover:bg-slate-900/60 transition-colors">
                    <td class="py-3 px-4 font-mono font-bold text-teal-400 text-xs">${f.fine_id || ('#FINE-' + f.id)}</td>
                    <td class="py-3 px-4">
                        <div class="font-bold text-white text-xs">${f.student_name}</div>
                        <div class="font-mono text-[10px] text-slate-400">${f.student_id || f.student_email || ''}</div>
                    </td>
                    <td class="py-3 px-4 text-xs text-slate-200 max-w-xs truncate">${f.reason || 'Penalty'}</td>
                    <td class="py-3 px-4 font-mono font-bold ${isPaid ? 'text-slate-300' : 'text-rose-400'} text-xs">₹${f.amount}</td>
                    <td class="py-3 px-4 font-mono text-slate-400 text-xs">${f.date_assigned || f.created_at || '-'}</td>
                    <td class="py-3 px-4">${statusBadge}</td>
                    <td class="py-3 px-4 font-mono text-slate-400 text-xs">${f.paid_at || '—'}</td>
                </tr>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error fetching master fines ledger:', err);
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="py-6 text-center text-xs text-rose-400">
                        Error fetching master campus fines ledger.
                    </td>
                </tr>
            `;
        }
    }
}

// Review & Issue Fine (CCTV Dynamic Trigger)
async function issueCctvFine(targetUserId = null, fineAmt = null) {
    const select = document.getElementById('cctvStudentSelect');
    const amountInput = document.getElementById('cctvFineAmountInput');

    const userId = targetUserId || (select && select.value ? parseInt(select.value, 10) : null);
    const amount = fineAmt || (amountInput && amountInput.value ? parseInt(amountInput.value, 10) : 500);

    const btn = document.getElementById('btnIssueCctvFine');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Issuing Penalty...</span>`;
        if (window.lucide) lucide.createIcons();
    }

    try {
        const payload = {
            amount: amount,
            reason: "Classroom 204 — 3:20 PM - Damaged Chair"
        };
        if (userId) payload.user_id = userId;

        const res = await fetch('/api/issue-fine', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (res.ok) {
            const studentName = (data.student && data.student.name) || (data.fine && data.fine.student_name) || 'Student';
            showToast(`₹${amount} Fine issued to ${studentName}! Status updated to 'Action Required 🔴'`, 'error', 6000);
            fetchAdminStudentStatus();
            fetchAdminStudentsDropdown();
            fetchAdminAllFines();
        } else {
            showToast(data.error || 'Failed to issue fine.', 'error');
        }
    } catch (err) {
        console.error('Error issuing fine:', err);
        showToast('Network error while issuing fine.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            updateCctvFineButton();
        }
        if (window.lucide) lucide.createIcons();
    }
}


// =============================================================================
// WORKER MANAGEMENT (CRUD)
// =============================================================================

async function fetchWorkers() {
    const tbody = document.getElementById('workersTableBody');
    if (!tbody) return;

    try {
        const res = await fetch('/api/workers');
        allWorkersCache = await res.json();

        if (!allWorkersCache || allWorkersCache.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="py-8 text-center text-xs text-slate-400">
                        No technical solvers found in directory.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = allWorkersCache.map(w => {
            const catBadge = w.category === 'Electrical' 
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                : w.category === 'IT'
                ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
                : w.category === 'Hardware'
                ? 'bg-teal-500/15 text-teal-300 border-teal-500/30'
                : 'bg-slate-800 text-slate-300 border-slate-700';

            return `
                <tr class="hover:bg-slate-800/40 transition-colors">
                    <td class="py-3.5 px-4">
                        <div class="flex items-center space-x-2.5">
                            <div class="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 text-teal-400 flex items-center justify-center font-bold text-xs">
                                ${w.name.split(' ').map(n=>n[0]).join('')}
                            </div>
                            <div>
                                <span class="font-bold text-white block">${w.name}</span>
                                <span class="font-mono text-[10px] text-slate-400">${w.id}</span>
                            </div>
                        </div>
                    </td>
                    <td class="py-3.5 px-4">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${catBadge}">
                            ${w.category}
                        </span>
                    </td>
                    <td class="py-3.5 px-4 text-center font-mono font-bold text-slate-200">
                        ${w.tasks_solved || 0}
                    </td>
                    <td class="py-3.5 px-4 text-center">
                        <span class="px-2 py-0.5 rounded-lg text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20">
                            ⭐ ${parseFloat(w.rating).toFixed(1)}
                        </span>
                    </td>
                    <td class="py-3.5 px-4 text-right">
                        <div class="inline-flex items-center space-x-1.5">
                            <button onclick="openEditWorkerModal('${w.id}')" title="Edit Worker"
                                class="px-2.5 py-1 rounded-lg bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 border border-indigo-500/30 text-xs font-semibold flex items-center space-x-1 transition-all">
                                <i data-lucide="edit-3" class="w-3.5 h-3.5"></i>
                                <span>Edit</span>
                            </button>
                            <button onclick="deleteWorker('${w.id}')" title="Delete Worker"
                                class="p-1 rounded-lg bg-slate-800 hover:bg-rose-950/50 text-slate-400 hover:text-rose-400 transition-colors">
                                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error fetching workers:', err);
    }
}

// Add Worker Modal Handlers
function openAddWorkerModal() {
    const modal = document.getElementById('addWorkerModal');
    if (modal) modal.classList.remove('hidden');
}

function closeAddWorkerModal() {
    const modal = document.getElementById('addWorkerModal');
    if (modal) modal.classList.add('hidden');
    const form = document.getElementById('addWorkerForm');
    if (form) form.reset();
}

async function submitAddWorker(event) {
    event.preventDefault();

    const name = document.getElementById('addWorkerName').value.trim();
    const category = document.getElementById('addWorkerCategory').value;

    if (!name) {
        showToast('Worker name is required.', 'warning');
        return;
    }

    try {
        const res = await fetch('/api/workers', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                category: category
            })
        });

        const data = await res.json();

        if (res.ok) {
            showToast(data.message || `Worker ${name} added!`, 'success');
            closeAddWorkerModal();
            fetchWorkers();
        } else {
            showToast(data.error || 'Failed to add worker.', 'error');
        }
    } catch (err) {
        console.error('Error adding worker:', err);
    }
}

// Edit Worker Modal Handlers
function openEditWorkerModal(workerId) {
    const worker = allWorkersCache.find(w => w.id === workerId);
    if (!worker) return;

    document.getElementById('editWorkerId').value = worker.id;
    document.getElementById('editWorkerName').value = worker.name;
    document.getElementById('editWorkerCategory').value = worker.category;
    document.getElementById('editWorkerRating').value = worker.rating;

    const modal = document.getElementById('editWorkerModal');
    if (modal) modal.classList.remove('hidden');
}

function closeEditWorkerModal() {
    const modal = document.getElementById('editWorkerModal');
    if (modal) modal.classList.add('hidden');
}

async function submitEditWorker(event) {
    event.preventDefault();

    const id = document.getElementById('editWorkerId').value;
    const name = document.getElementById('editWorkerName').value.trim();
    const category = document.getElementById('editWorkerCategory').value;
    const rating = document.getElementById('editWorkerRating').value;

    try {
        const res = await fetch(`/api/workers/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                category: category,
                rating: rating
            })
        });

        const data = await res.json();

        if (res.ok) {
            showToast(data.message || `Worker updated!`, 'success');
            closeEditWorkerModal();
            fetchWorkers();
        } else {
            showToast(data.error || 'Failed to update worker.', 'error');
        }
    } catch (err) {
        console.error('Error editing worker:', err);
    }
}

// Delete Worker
async function deleteWorker(workerId) {
    if (!confirm(`Are you sure you want to remove worker ${workerId}?`)) return;

    try {
        const res = await fetch(`/api/workers/${workerId}`, { method: 'DELETE' });
        const data = await res.json();

        if (res.ok) {
            showToast(data.message || 'Worker deleted.', 'info');
            fetchWorkers();
        } else {
            showToast(data.error || 'Failed to delete worker.', 'error');
        }
    } catch (err) {
        console.error('Error deleting worker:', err);
    }
}


// =============================================================================
// WORKER REVIEWS LOG (STUDENT STAR RATINGS & FEEDBACK)
// =============================================================================

async function fetchWorkerReviews() {
    const tbody = document.getElementById('reviewsTableBody');
    if (!tbody) return;

    try {
        const res = await fetch('/api/reviews');
        allReviewsCache = await res.json();

        if (!allReviewsCache || allReviewsCache.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="py-8 text-center text-xs text-slate-400">
                        No service reviews submitted yet.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = allReviewsCache.map(r => {
            const catBadge = r.worker_category === 'Electrical' 
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                : r.worker_category === 'IT'
                ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
                : 'bg-teal-500/15 text-teal-300 border-teal-500/30';

            return `
                <tr class="hover:bg-slate-800/40 transition-colors">
                    <td class="py-3.5 px-4">
                        <div>
                            <span class="font-bold text-white block">${r.worker_name}</span>
                            <span class="px-2 py-0.2 rounded text-[10px] font-mono border ${catBadge}">
                                ${r.worker_category}
                            </span>
                        </div>
                    </td>
                    <td class="py-3.5 px-4">
                        <div>
                            <span class="font-semibold text-slate-200 block">${r.student_name}</span>
                            <span class="text-[10px] font-mono text-slate-400">${r.student_roll || 'Student'} • ${r.timestamp}</span>
                        </div>
                    </td>
                    <td class="py-3.5 px-4 text-center font-bold text-amber-400">
                        ⭐ ${r.response_time}
                    </td>
                    <td class="py-3.5 px-4 text-center font-bold text-amber-400">
                        ⭐ ${r.quality}
                    </td>
                    <td class="py-3.5 px-4 text-center font-bold text-amber-400">
                        ⭐ ${r.behavior}
                    </td>
                    <td class="py-3.5 px-4 text-center">
                        <span class="px-2 py-0.5 rounded-lg text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20">
                            ⭐ ${parseFloat(r.avg_rating).toFixed(2)}
                        </span>
                    </td>
                    <td class="py-3.5 px-4 text-xs text-slate-300 max-w-xs">
                        <p class="italic text-slate-300">"${r.suggestion || 'No feedback.'}"</p>
                    </td>
                </tr>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error fetching worker reviews:', err);
    }
}


// =============================================================================
// ADMIN PROBLEM TICKETS DISPATCH BOARD
// =============================================================================

async function fetchAdminTickets() {
    const container = document.getElementById('adminTicketsContainer');
    if (!container) return;

    try {
        const res = await fetch('/api/tickets');
        allAdminTicketsCache = await res.json();

        if (!allAdminTicketsCache || allAdminTicketsCache.length === 0) {
            container.innerHTML = `
                <div class="p-8 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                    <p class="text-xs text-slate-400">No tickets found.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = allAdminTicketsCache.map(ticket => {
            const isResolved = ticket.status === 'Resolved';
            const statusClass = isResolved 
                ? 'badge-status-resolved' 
                : ticket.status === 'In Progress' 
                ? 'badge-status-inprogress' 
                : 'badge-status-assigned';

            return `
                <div class="bg-slate-950/80 border border-slate-800 rounded-2xl p-4 space-y-3 hover:border-slate-700 transition-all">
                    <div class="flex items-start justify-between gap-2">
                        <div class="flex items-center space-x-2">
                            <span class="font-mono text-xs font-bold text-teal-400 bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/20">${ticket.id}</span>
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300">${ticket.urgency}</span>
                            <span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-900 text-teal-300 border border-slate-800">${ticket.category}</span>
                        </div>
                        <div class="flex items-center space-x-2">
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold ${statusClass}">${ticket.status}</span>
                            <span class="text-xs text-slate-500 font-mono">${ticket.reported_at}</span>
                        </div>
                    </div>

                    <h4 class="text-xs font-bold text-white">${ticket.title}</h4>
                    <p class="text-xs text-slate-300 leading-relaxed">${ticket.description}</p>

                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] text-slate-400 pt-2 border-t border-slate-900">
                        <div class="flex items-center space-x-3">
                            <span class="flex items-center gap-1">
                                <i data-lucide="map-pin" class="w-3 h-3 text-slate-500"></i>
                                <span>${ticket.location}</span>
                            </span>
                            <span class="font-bold text-teal-300">
                                ${ticket.solver_display || `Assigned to: ${ticket.solver_name}`}
                            </span>
                        </div>

                        ${!isResolved ? `
                            <button onclick="adminResolveTicket('${ticket.id}')"
                                class="px-2.5 py-1 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-[11px] font-bold flex items-center space-x-1 transition-all self-end sm:self-auto">
                                <i data-lucide="check" class="w-3 h-3"></i>
                                <span>Mark Resolved</span>
                            </button>
                        ` : `
                            <span class="text-emerald-400 font-semibold text-[11px]">✓ Resolution Verified</span>
                        `}
                    </div>
                </div>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error fetching admin tickets:', err);
    }
}

async function adminResolveTicket(ticketId) {
    try {
        const res = await fetch(`/api/tickets/${ticketId}/resolve`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast(`Ticket ${ticketId} marked as Resolved. Student can now review the solution!`, 'success');
            fetchAdminTickets();
        } else {
            showToast(data.error || 'Failed to resolve ticket.', 'error');
        }
    } catch (err) {
        console.error('Error in adminResolveTicket:', err);
    }
}


// =============================================================================
// USER MANAGEMENT (VIEW, ADD, TOGGLE ACTIVE STATUS, DELETE)
// =============================================================================

let allUsersCache = [];

async function fetchAdminUsers() {
    const tbody = document.getElementById('usersTableBody');
    if (!tbody) return;

    try {
        const res = await fetch('/api/admin/users', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!res.ok) {
            if (res.status === 401) {
                console.warn('Admin session required.');
            }
            return;
        }
        allUsersCache = await res.json();

        if (!allUsersCache || allUsersCache.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="py-8 text-center text-xs text-slate-400">
                        No registered campus users found.
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = allUsersCache.map(u => {
            const roleBadge = u.role === 'Admin'
                ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30'
                : 'bg-teal-500/15 text-teal-300 border-teal-500/30';

            const isActive = u.is_active !== 0;
            const statusBadge = isActive
                ? '<span class="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-[10px] font-bold">Active 🟢</span>'
                : '<span class="px-2 py-0.5 rounded-full bg-rose-500/15 text-rose-300 border border-rose-500/30 text-[10px] font-bold">Deactivated ⛔</span>';

            const toggleBtnText = isActive ? 'Deactivate' : 'Activate';
            const toggleBtnClass = isActive
                ? 'bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border-rose-500/30'
                : 'bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border-emerald-500/30';
            const toggleIcon = isActive ? 'user-x' : 'user-check';

            return `
                <tr class="hover:bg-slate-800/40 transition-colors">
                    <td class="py-3.5 px-4">
                        <div class="flex items-center space-x-2.5">
                            <div class="w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 text-cyan-400 flex items-center justify-center font-bold text-xs">
                                ${u.name ? u.name.split(' ').map(n=>n[0]).join('').substring(0,2).toUpperCase() : 'U'}
                            </div>
                            <div>
                                <span class="font-bold text-white block">${u.name}</span>
                                <span class="font-mono text-[10px] text-slate-400">ID: #${u.id}</span>
                            </div>
                        </div>
                    </td>
                    <td class="py-3.5 px-4 font-mono text-slate-300 text-[11px]">
                        ${u.email}
                    </td>
                    <td class="py-3.5 px-4 font-mono text-slate-300 text-[11px]">
                        ${u.student_id || 'N/A'}
                    </td>
                    <td class="py-3.5 px-4 text-center">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${roleBadge}">
                            ${u.role}
                        </span>
                    </td>
                    <td class="py-3.5 px-4 text-center">
                        ${statusBadge}
                    </td>
                    <td class="py-3.5 px-4 text-right">
                        <div class="inline-flex items-center space-x-1.5">
                            <button onclick="toggleUserStatus(${u.id}, '${u.name.replace(/'/g, "\\'")}', ${isActive ? 1 : 0})" title="${toggleBtnText} User"
                                class="px-2.5 py-1 rounded-lg border text-xs font-semibold flex items-center space-x-1 transition-all ${toggleBtnClass}">
                                <i data-lucide="${toggleIcon}" class="w-3.5 h-3.5"></i>
                                <span>${toggleBtnText}</span>
                            </button>
                            <button onclick="deleteAdminUser(${u.id}, '${u.name.replace(/'/g, "\\'")}', '${u.email}')" title="Delete User"
                                class="p-1 rounded-lg bg-slate-800 hover:bg-rose-950/50 text-slate-400 hover:text-rose-400 transition-colors">
                                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error fetching admin users:', err);
    }
}

function openAddUserModal() {
    const modal = document.getElementById('addUserModal');
    if (modal) modal.classList.remove('hidden');
}

function closeAddUserModal() {
    const modal = document.getElementById('addUserModal');
    if (modal) modal.classList.add('hidden');
    const form = document.getElementById('addUserForm');
    if (form) form.reset();
}

async function submitAddUser(event) {
    event.preventDefault();

    const name = document.getElementById('addUserName').value.trim();
    const email = document.getElementById('addUserEmail').value.trim().toLowerCase();
    const studentId = document.getElementById('addUserStudentId').value.trim();
    const role = document.getElementById('addUserRole').value;
    const password = document.getElementById('addUserPassword').value;

    if (!name || !email || !password) {
        showToast('Name, email, and password are required.', 'warning');
        return;
    }

    if (!email.endsWith('@sst.scaler.com')) {
        showToast('Email must strictly end with @sst.scaler.com', 'error');
        return;
    }

    try {
        const res = await fetch('/api/admin/users', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                name: name,
                email: email,
                student_id: studentId,
                role: role,
                password: password
            })
        });

        let data = {};
        const text = await res.text();
        try {
            data = JSON.parse(text);
        } catch (e) {
            console.error('Non-JSON response from server:', text);
        }

        if (res.ok) {
            showToast(data.message || `User '${name}' created successfully!`, 'success');
            closeAddUserModal();
            fetchAdminUsers();
        } else {
            const errorMsg = data.error || (res.status === 401 ? 'Administrator authentication required. Please log in again.' : `Error (${res.status}): Failed to create user.`);
            showToast(errorMsg, 'error');
            if (res.status === 401) {
                setTimeout(() => { window.location.href = '/login?next=/admin'; }, 2000);
            }
        }
    } catch (err) {
        console.error('Error adding user:', err);
        showToast('Network error while creating user: ' + err.message, 'error');
    }
}

async function toggleUserStatus(userId, userName, currentActive) {
    try {
        const res = await fetch(`/api/admin/users/${userId}/toggle-status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        let data = {};
        try { data = await res.json(); } catch (e) {}

        if (res.ok) {
            showToast(data.message || `User status updated!`, 'info');
            fetchAdminUsers();
        } else {
            showToast(data.error || 'Failed to update user status.', 'error');
        }
    } catch (err) {
        console.error('Error toggling user status:', err);
    }
}

async function deleteAdminUser(userId, userName, userEmail) {
    if (!confirm(`Are you sure you want to delete user '${userName}' (${userEmail})? This action cannot be undone.`)) {
        return;
    }

    try {
        const res = await fetch(`/api/admin/users/${userId}`, {
            method: 'DELETE',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        let data = {};
        try { data = await res.json(); } catch (e) {}

        if (res.ok) {
            showToast(data.message || `User deleted successfully!`, 'success');
            fetchAdminUsers();
        } else {
            showToast(data.error || 'Failed to delete user.', 'error');
        }
    } catch (err) {
        console.error('Error deleting user:', err);
    }
}


// =============================================================================
// EVENT REGISTRATION & RSVP ROSTER MANAGEMENT
// =============================================================================

function escapeAdminHtml(unsafe) {
    if (!unsafe) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

let adminEventsCache = [];

async function populateAdminEventDropdown() {
    const select = document.getElementById('adminEventSelect');
    if (!select) return;

    try {
        const res = await fetch('/api/events', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!res.ok) return;

        adminEventsCache = await res.json();
        if (!adminEventsCache || adminEventsCache.length === 0) {
            select.innerHTML = '<option value="">No events scheduled</option>';
            return;
        }

        const currentVal = select.value;
        select.innerHTML = adminEventsCache.map(e => `
            <option value="${e.id}">${escapeAdminHtml(e.name)} (${escapeAdminHtml(e.venue)})</option>
        `).join('');

        if (currentVal && adminEventsCache.some(e => e.id === currentVal)) {
            select.value = currentVal;
        } else {
            select.value = adminEventsCache[0].id;
        }

        fetchAdminEventRegistrations();
    } catch (err) {
        console.error('Error populating admin events:', err);
    }
}

function onAdminEventSelectChange() {
    fetchAdminEventRegistrations();
}

async function fetchAdminEventRegistrations() {
    const select = document.getElementById('adminEventSelect');
    const tableBody = document.getElementById('eventRegistrationsTableBody');
    const banner = document.getElementById('adminEventSummaryBanner');
    if (!select || !tableBody) return;

    const eventId = select.value;
    if (!eventId) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" class="py-8 text-center text-slate-500">
                    Please select an event to view registrations.
                </td>
            </tr>
        `;
        if (banner) banner.classList.add('hidden');
        return;
    }

    try {
        const res = await fetch(`/api/admin/events/${eventId}/registrations`, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        if (!res.ok) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="py-8 text-center text-rose-400">
                        Failed to load registrations.
                    </td>
                </tr>
            `;
            return;
        }

        const data = await res.json();
        const event = data.event || {};
        const registrations = data.registrations || [];

        // Update Summary Banner
        if (banner) {
            banner.classList.remove('hidden');
            const nameEl = document.getElementById('adminSummaryEventName');
            const venueEl = document.getElementById('adminSummaryVenue');
            const dateEl = document.getElementById('adminSummaryDate');
            const timeEl = document.getElementById('adminSummaryTime');
            const capEl = document.getElementById('adminSummaryCapacity');
            const regEl = document.getElementById('adminSummaryRegistered');

            if (nameEl) nameEl.textContent = event.name || 'Campus Event';
            if (venueEl) venueEl.textContent = event.venue || 'Campus Venue';
            if (dateEl) dateEl.textContent = event.date || 'Today';
            if (timeEl) timeEl.textContent = `${event.start_time || '09:00'} - ${event.end_time || '17:00'}`;
            if (capEl) capEl.textContent = event.capacity || 100;
            if (regEl) regEl.textContent = `${registrations.length} / ${event.capacity || 100}`;
        }

        // Render Table
        if (registrations.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5" class="py-8 text-center text-slate-400">
                        <i data-lucide="inbox" class="w-6 h-6 mx-auto mb-2 text-slate-500 opacity-60"></i>
                        No students have registered for this event yet.
                    </td>
                </tr>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        tableBody.innerHTML = registrations.map((r, idx) => `
            <tr class="hover:bg-slate-800/40 transition-colors">
                <td class="py-3 px-4 font-mono text-slate-500">${idx + 1}</td>
                <td class="py-3 px-4 font-bold text-white">${escapeAdminHtml(r.student_name)}</td>
                <td class="py-3 px-4 font-mono text-teal-300 font-semibold">${escapeAdminHtml(r.student_id || 'N/A')}</td>
                <td class="py-3 px-4 font-mono text-slate-300">${escapeAdminHtml(r.student_email)}</td>
                <td class="py-3 px-4 font-mono text-slate-400">${escapeAdminHtml(r.registered_at)}</td>
            </tr>
        `).join('');

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error loading event registrations:', err);
    }
}


// =============================================================================
// CAMPUS ANNOUNCEMENTS & BROADCAST CONTROL
// =============================================================================

let adminAnnouncementsCache = [];

async function fetchAdminAnnouncements() {
    const container = document.getElementById('adminAnnouncementsContainer');
    const countBadge = document.getElementById('adminAnnouncementsCount');
    if (!container) return;

    try {
        const res = await fetch('/api/admin/announcements', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!res.ok) {
            container.innerHTML = `
                <div class="p-6 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                    <p class="text-xs text-rose-400">Failed to load announcements.</p>
                </div>
            `;
            return;
        }

        adminAnnouncementsCache = await res.json();
        if (countBadge) {
            countBadge.textContent = `${adminAnnouncementsCache.length} Total`;
        }
        renderAdminAnnouncements(adminAnnouncementsCache);
    } catch (err) {
        console.error('Error fetching admin announcements:', err);
        container.innerHTML = `
            <div class="p-6 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                <p class="text-xs text-rose-400">Network error while loading announcements.</p>
            </div>
        `;
    }
}

function renderAdminAnnouncements(announcements) {
    const container = document.getElementById('adminAnnouncementsContainer');
    if (!container) return;

    if (!announcements || announcements.length === 0) {
        container.innerHTML = `
            <div class="p-8 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                <i data-lucide="inbox" class="w-8 h-8 mx-auto mb-2 text-slate-500 opacity-60"></i>
                <p class="text-xs text-slate-400">No active announcements published. Use the form on the left to broadcast a new notice.</p>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    container.innerHTML = announcements.map(a => {
        const isUrgent = (a.priority || '').toLowerCase() === 'urgent';
        const isImportant = (a.priority || '').toLowerCase() === 'important';

        const priorityBadge = isUrgent
            ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">🚨 Urgent</span>'
            : isImportant
            ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">⚠️ Important</span>'
            : '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">Normal</span>';

        const category = a.category || 'General';
        const catBadge = category === 'Academic'
            ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
            : category === 'Hostel'
            ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
            : category === 'Events'
            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
            : 'bg-teal-500/20 text-teal-300 border-teal-500/30';

        return `
            <div class="bg-slate-950/80 border border-slate-800/90 rounded-2xl p-4 space-y-3 hover:border-slate-700 transition-all">
                <div class="flex items-start justify-between gap-3">
                    <div class="space-y-1 flex-1">
                        <div class="flex flex-wrap items-center gap-1.5">
                            <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${catBadge}">
                                ${escapeAdminHtml(category)}
                            </span>
                            ${priorityBadge}
                            <span class="text-[10px] font-mono text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                                👥 ${escapeAdminHtml(a.audience || 'All')}
                            </span>
                        </div>
                        <h4 class="text-xs font-bold text-white leading-snug">${escapeAdminHtml(a.title)}</h4>
                    </div>

                    <button onclick="deleteAdminAnnouncement('${a.id}', '${escapeAdminHtml(a.title)}')"
                        class="px-2.5 py-1 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-[11px] font-medium flex items-center space-x-1 transition-colors cursor-pointer"
                        title="Delete Announcement">
                        <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                        <span>Delete</span>
                    </button>
                </div>

                <p class="text-xs text-slate-300 leading-relaxed bg-slate-900/60 p-3 rounded-xl border border-slate-800/80">
                    ${escapeAdminHtml(a.content || a.message || '')}
                </p>

                <div class="flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-slate-400 pt-1 border-t border-slate-900">
                    <span>📍 ${escapeAdminHtml(a.venue || 'Campus-wide')}</span>
                    <span>🕒 ${escapeAdminHtml(a.created_at || a.date || 'Today')}</span>
                </div>
            </div>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

async function submitCreateAnnouncement(event) {
    event.preventDefault();

    const title = document.getElementById('annTitle').value.trim();
    const content = document.getElementById('annContent').value.trim();
    const category = document.getElementById('annCategory').value;
    const priority = document.getElementById('annPriority').value;
    const audience = document.getElementById('annAudience').value;
    const venue = document.getElementById('annVenue').value.trim() || 'Campus-wide';
    const btn = document.getElementById('btnSubmitAnnouncement');

    if (!title || !content) {
        showToast('Please enter both title and message.', 'error');
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Publishing...</span>`;
    }
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/admin/announcements', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                title: title,
                content: content,
                category: category,
                priority: priority,
                audience: audience,
                venue: venue
            })
        });

        const data = await res.json();
        if (res.status === 201 || data.success) {
            showToast(data.message || '📢 Announcement published successfully!', 'success');
            document.getElementById('createAnnouncementForm').reset();
            fetchAdminAnnouncements();
        } else {
            showToast(data.error || 'Failed to publish announcement.', 'error');
        }
    } catch (err) {
        console.error('Error publishing announcement:', err);
        showToast('Network error while publishing announcement.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="send" class="w-4 h-4"></i><span>Publish Announcement</span>`;
        }
        if (window.lucide) lucide.createIcons();
    }
}

async function deleteAdminAnnouncement(annId, annTitle) {
    if (!confirm(`Are you sure you want to delete announcement '${annTitle}'?`)) {
        return;
    }

    try {
        const res = await fetch(`/api/admin/announcements/${annId}`, {
            method: 'DELETE',
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        const data = await res.json();
        if (res.ok || data.success) {
            showToast(data.message || 'Announcement deleted.', 'success');
            fetchAdminAnnouncements();
        } else {
            showToast(data.error || 'Failed to delete announcement.', 'error');
        }
    } catch (err) {
        console.error('Error deleting announcement:', err);
        showToast('Network error while deleting announcement.', 'error');
    }
}


// =============================================================================
// TAB NAVIGATION MANAGEMENT
// =============================================================================

const ADMIN_TABS = ['dashboard', 'announcements', 'events', 'users', 'tickets', 'profile'];

function switchAdminTab(tabId) {
    if (!ADMIN_TABS.includes(tabId)) {
        tabId = 'dashboard';
    }

    // Update section visibility
    ADMIN_TABS.forEach(tab => {
        const sec = document.getElementById(`admin-section-${tab}`);
        if (sec) {
            if (tab === tabId) {
                sec.classList.remove('hidden');
                sec.classList.add('animate-fadeIn');
            } else {
                sec.classList.add('hidden');
            }
        }
    });

    // Update top nav and subnav button styles
    document.querySelectorAll('[data-admin-tab]').forEach(btn => {
        const target = btn.getAttribute('data-admin-tab');
        if (target === tabId) {
            btn.classList.add('bg-indigo-500/20', 'text-indigo-300', 'border-indigo-500/30');
            btn.classList.remove('text-slate-400', 'hover:text-slate-200', 'hover:bg-slate-800/60');
        } else {
            btn.classList.remove('bg-indigo-500/20', 'text-indigo-300', 'border-indigo-500/30');
            btn.classList.add('text-slate-400', 'hover:text-slate-200', 'hover:bg-slate-800/60');
        }
    });

    // Update URL hash without reload
    if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', `#${tabId}`);
    }

    // Refresh icons
    if (window.lucide) lucide.createIcons();
}

// Make switchAdminTab globally accessible
window.switchAdminTab = switchAdminTab;


// =============================================================================
// INITIALIZATION
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Check initial tab from window hash or server template attribute
    const mainEl = document.getElementById('adminMainContent');
    const hash = window.location.hash.replace('#', '').toLowerCase();
    const activeTab = (hash && ADMIN_TABS.includes(hash))
        ? hash
        : ((mainEl && mainEl.getAttribute('data-active-tab')) || 'dashboard');

    switchAdminTab(activeTab);

    // Listen for hash changes
    window.addEventListener('hashchange', () => {
        const newHash = window.location.hash.replace('#', '').toLowerCase();
        if (newHash && ADMIN_TABS.includes(newHash)) {
            switchAdminTab(newHash);
        }
    });

    fetchAdminStudentStatus();
    fetchAdminStudentsDropdown();
    fetchAdminAllFines();
    fetchAdminUsers();
    fetchWorkers();
    fetchWorkerReviews();
    fetchAdminTickets();
    populateAdminEventDropdown();
    fetchAdminAnnouncements();
});

