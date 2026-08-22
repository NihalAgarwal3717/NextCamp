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

// Review & Issue Fine ₹500
async function issueCctvFine() {
    const btn = document.getElementById('btnIssueCctvFine');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Issuing Penalty...</span>`;
    }
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/issue-fine', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                amount: 500,
                reason: "Classroom 204 — 3:20 PM - Damaged Chair"
            })
        });

        const data = await res.json();

        if (res.ok) {
            showToast(`₹500 Fine issued to student Sameer Verma! Status updated to 'Action Required 🔴'`, 'error', 6000);
            fetchAdminStudentStatus();
        } else {
            showToast(data.error || 'Failed to issue fine.', 'error');
        }
    } catch (err) {
        console.error('Error issuing fine:', err);
        showToast('Network error while issuing fine.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="gavel" class="w-4 h-4"></i><span>Review & Issue Fine ₹500</span>`;
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
// INITIALIZATION
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    fetchAdminStudentStatus();
    fetchAdminUsers();
    fetchWorkers();
    fetchWorkerReviews();
    fetchAdminTickets();
});

