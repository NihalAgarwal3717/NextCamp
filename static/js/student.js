/**
 * NextCamp - Student Portal Logic
 * Handles problem reporting, smart solver display, announcements filtering,
 * accountability standing / fines, event booking with time clash detection,
 * and Post-Resolution Rating System (+5 Reputation Points).
 */

let allAnnouncementsCache = [];
let allStudentTicketsCache = [];
let currentCategoryFilter = 'all';

// =============================================================================
// STUDENT PROFILE & ACCOUNTABILITY STANDING
// =============================================================================

async function fetchStudentProfile() {
    try {
        const res = await fetch('/api/student/profile');
        if (!res.ok) return;
        const student = await res.json();

        const badge = document.getElementById('studentStandingBadge');
        const fineEl = document.getElementById('studentFineAmount');
        const profileFinesText = document.getElementById('profilePendingFinesText');
        const banner = document.getElementById('studentFineBanner');
        const bannerText = document.getElementById('studentFineBannerText');
        const nameEl = document.getElementById('studentProfileName');
        const repPointsEl = document.getElementById('studentReputationPoints');
        const headerRep = document.getElementById('headerReputationScore');
        const headerBadge = document.getElementById('headerUserBadge');

        // Current Fine & Standing Summary Card Elements
        const currentFineIconBox = document.getElementById('studentCurrentFineIconBox');
        const currentFineBadge = document.getElementById('studentCurrentFineStatusBadge');
        const currentFineDesc = document.getElementById('studentCurrentFineDescription');
        const currentFineDetailsRow = document.getElementById('studentCurrentFineDetailsRow');
        const currentFineDate = document.getElementById('studentCurrentFineDate');
        const currentFineAmountText = document.getElementById('studentCurrentFineAmountText');
        const currentFineStatusText = document.getElementById('studentCurrentFineStatusText');
        const btnCurrentFinePay = document.getElementById('btnCurrentFinePay');

        if (nameEl && student.name) nameEl.innerText = student.name;
        if (repPointsEl && student.reputation_points !== undefined) repPointsEl.innerText = student.reputation_points;
        if (headerRep && student.reputation !== undefined) headerRep.innerText = `⭐ ${parseFloat(student.reputation).toFixed(1)}`;
        if (headerBadge && student.badge) headerBadge.innerText = student.badge;

        // Dynamic Profile Tab & Avatar elements
        const profName = document.getElementById('profileTabName');
        const profEmail = document.getElementById('profileTabEmail');
        const profRoll = document.getElementById('profileTabRoll');
        const rollEl = document.getElementById('studentProfileRoll');
        const avatar1 = document.getElementById('studentAvatarInitials');
        const avatar2 = document.getElementById('profileTabAvatarInitials');

        if (profName && student.name) profName.innerText = student.name;
        if (profEmail && student.email) profEmail.innerText = student.email;
        if (student.student_id || student.roll) {
            const rollVal = student.student_id || student.roll;
            if (profRoll) profRoll.innerText = rollVal;
            if (rollEl) rollEl.innerText = `${rollVal} • Hostel Block B, Room 204`;
        }

        if (student.name) {
            const parts = student.name.trim().split(/\s+/);
            const initials = (parts[0] ? parts[0][0] : 'S') + (parts.length > 1 && parts[1] ? parts[1][0] : '');
            if (avatar1) avatar1.innerText = initials.toUpperCase();
            if (avatar2) avatar2.innerText = initials.toUpperCase();
        }

        const fineAmount = student.fine_amount || 0;
        const isActionRequired = (student.status && student.status.includes('Action Required')) || fineAmount > 0;

        if (fineEl) {
            fineEl.innerText = `₹${fineAmount}`;
            fineEl.className = isActionRequired ? 'text-base font-bold font-mono text-rose-400 animate-pulse' : 'text-base font-bold font-mono text-emerald-400';
        }

        if (profileFinesText) {
            profileFinesText.innerText = isActionRequired ? `₹${fineAmount} Pending` : '₹0 Pending';
            profileFinesText.className = isActionRequired ? 'text-lg font-bold font-mono text-rose-400' : 'text-lg font-bold font-mono text-emerald-400';
        }

        if (badge) {
            badge.innerText = isActionRequired ? 'Action Required 🔴' : (student.status || 'Good Standing 🟢');
            badge.className = isActionRequired ?
                'px-3 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse' :
                'px-3 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40';
        }

        // Update Current Fine Card
        if (currentFineBadge && currentFineDesc) {
            if (isActionRequired && student.current_pending_fine) {
                const pend = student.current_pending_fine;
                if (currentFineIconBox) {
                    currentFineIconBox.className = 'w-12 h-12 rounded-2xl bg-rose-500/15 text-rose-400 border border-rose-500/30 flex items-center justify-center shadow-lg shadow-rose-500/10 flex-shrink-0';
                    currentFineIconBox.innerHTML = `<i data-lucide="alert-triangle" class="w-6 h-6 animate-pulse"></i>`;
                }
                currentFineBadge.innerText = 'Action Required 🔴';
                currentFineBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 animate-pulse';
                currentFineDesc.innerHTML = `<span class="text-rose-200 font-semibold">Violation:</span> ${pend.reason || 'Campus administrative penalty'}`;

                if (currentFineDetailsRow) {
                    currentFineDetailsRow.classList.remove('hidden');
                    currentFineDetailsRow.classList.add('flex');
                }
                if (currentFineDate) currentFineDate.innerText = pend.created_at || pend.date_assigned || 'Recently';
                if (currentFineAmountText) currentFineAmountText.innerText = `₹${pend.amount || fineAmount}`;
                if (currentFineStatusText) currentFineStatusText.innerText = pend.status || 'Pending';
                if (btnCurrentFinePay) btnCurrentFinePay.classList.remove('hidden');
            } else {
                if (currentFineIconBox) {
                    currentFineIconBox.className = 'w-12 h-12 rounded-2xl bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center justify-center shadow-lg shadow-emerald-500/10 flex-shrink-0';
                    currentFineIconBox.innerHTML = `<i data-lucide="shield-check" class="w-6 h-6"></i>`;
                }
                currentFineBadge.innerText = 'Good Standing 🟢';
                currentFineBadge.className = 'px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
                currentFineDesc.innerText = 'No pending fines on your student account. Clean disciplinary standing.';
                if (currentFineDetailsRow) {
                    currentFineDetailsRow.classList.add('hidden');
                    currentFineDetailsRow.classList.remove('flex');
                }
                if (btnCurrentFinePay) btnCurrentFinePay.classList.add('hidden');
            }
        }

        if (banner) {
            if (isActionRequired) {
                banner.classList.remove('hidden');
                if (bannerText) {
                    const reason = (student.current_pending_fine && student.current_pending_fine.reason) ? student.current_pending_fine.reason : 'Disciplinary penalty';
                    bannerText.innerHTML = `<b>⚠️ Disciplinary Notice:</b> An administrative fine of ₹${fineAmount} has been issued (${reason}). Status: <b>Action Required 🔴</b>.`;
                }
            } else {
                banner.classList.add('hidden');
            }
        }

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error fetching student profile:', err);
    }
}

// Clear / Pay Fine
async function payStudentFine(fineId = null) {
    try {
        const url = fineId ? `/api/student/fines/${fineId}/pay` : '/api/student/pay-fine';
        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();

        if (res.ok) {
            showToast('Fine cleared successfully! Status restored to Good Standing 🟢', 'success');
            fetchStudentProfile();
            // If modal is open, refresh modal history
            const modal = document.getElementById('studentFineHistoryModal');
            if (modal && !modal.classList.contains('hidden')) {
                loadStudentFineHistory();
            }
        } else {
            showToast(data.error || 'Failed to pay fine.', 'error');
        }
    } catch (err) {
        console.error('Error paying fine:', err);
    }
}

// =============================================================================
// STUDENT FINE HISTORY MODAL
// =============================================================================

async function openStudentFineHistoryModal() {
    const modal = document.getElementById('studentFineHistoryModal');
    if (modal) {
        modal.classList.remove('hidden');
        await loadStudentFineHistory();
        if (window.lucide) lucide.createIcons();
    }
}

function closeStudentFineHistoryModal() {
    const modal = document.getElementById('studentFineHistoryModal');
    if (modal) modal.classList.add('hidden');
}

async function loadStudentFineHistory() {
    const countEl = document.getElementById('studentHistoryTotalCount');
    const pendingSumEl = document.getElementById('studentHistoryPendingSum');
    const paidSumEl = document.getElementById('studentHistoryPaidSum');
    const tbody = document.getElementById('studentFineHistoryTableBody');
    const emptyState = document.getElementById('studentFineHistoryEmptyState');

    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="py-8 text-center text-xs text-slate-400">
                    <i data-lucide="loader-2" class="w-5 h-5 animate-spin mx-auto mb-2 text-teal-400"></i>
                    Fetching student fine records...
                </td>
            </tr>
        `;
        if (window.lucide) lucide.createIcons();
    }

    try {
        const res = await fetch('/api/student/fines');
        if (!res.ok) throw new Error('Failed to fetch fine history');
        const data = await res.json();

        const fines = data.fines || [];
        const totalCount = data.total_fines !== undefined ? data.total_fines : fines.length;
        const pendingSum = data.total_pending_amount !== undefined ? data.total_pending_amount : 0;
        const paidSum = data.total_paid_amount !== undefined ? data.total_paid_amount : 0;

        if (countEl) countEl.innerText = totalCount;
        if (pendingSumEl) pendingSumEl.innerText = `₹${pendingSum}`;
        if (paidSumEl) paidSumEl.innerText = `₹${paidSum}`;

        if (totalCount === 0 || fines.length === 0) {
            if (tbody) tbody.innerHTML = '';
            if (emptyState) emptyState.classList.remove('hidden');
            return;
        }

        if (emptyState) emptyState.classList.add('hidden');

        if (tbody) {
            tbody.innerHTML = fines.map(fine => {
                const isPaid = fine.status === 'Paid';
                const statusBadge = isPaid ?
                    `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">Paid 🟢</span>` :
                    `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/15 text-rose-300 border border-rose-500/30 animate-pulse">Pending 🔴</span>`;

                const actionBtn = isPaid ?
                    `<span class="text-[11px] text-emerald-400 font-mono font-semibold">Settled</span>` :
                    `<button onclick="payStudentFine(${fine.id})" class="px-2.5 py-1 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-[10px] shadow-sm transition-all cursor-pointer">Pay Now</button>`;

                return `
                    <tr class="hover:bg-slate-900/60 transition-colors">
                        <td class="py-3 px-3 font-mono font-bold text-teal-400 text-xs">${fine.fine_id || ('#FINE-' + fine.id)}</td>
                        <td class="py-3 px-3 font-medium text-slate-200">${fine.reason || 'Administrative penalty'}</td>
                        <td class="py-3 px-3 font-mono font-bold ${isPaid ? 'text-slate-300' : 'text-rose-400'}">₹${fine.amount}</td>
                        <td class="py-3 px-3 text-slate-400 text-[11px] font-mono">${fine.date_assigned || fine.created_at || '-'}</td>
                        <td class="py-3 px-3">${statusBadge}</td>
                        <td class="py-3 px-3 text-slate-400 text-[11px] font-mono">${fine.paid_at || '—'}</td>
                        <td class="py-3 px-3 text-right">${actionBtn}</td>
                    </tr>
                `;
            }).join('');
        }

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error loading fine history:', err);
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="py-6 text-center text-xs text-rose-400">
                        Failed to retrieve fine records from server.
                    </td>
                </tr>
            `;
        }
    }
}


// =============================================================================
// REPORT PROBLEM FORM & SMART ALLOCATION
// =============================================================================

function fillProblem(category, location, description, urgency) {
    const locInput = document.getElementById('reportLocation');
    const catInput = document.getElementById('reportCategory');
    const descInput = document.getElementById('reportDescription');
    const urgInput = document.getElementById('reportUrgency');

    if (locInput) locInput.value = location;
    if (catInput) catInput.value = category;
    if (descInput) descInput.value = description;
    if (urgInput) urgInput.value = urgency;
}

async function submitReportProblem(event) {
    event.preventDefault();

    const location = document.getElementById('reportLocation').value.trim();
    const category = document.getElementById('reportCategory').value;
    const urgency = document.getElementById('reportUrgency').value;
    const description = document.getElementById('reportDescription').value.trim();
    const btn = document.getElementById('btnSubmitProblem');

    if (!location || !description) {
        showToast('Please fill in location and description.', 'warning');
        return;
    }

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Smart Allocating Solver...</span>`;
    }
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/report-problem', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                location: location,
                category: category,
                urgency: urgency,
                description: description,
                title: `${category} Issue at ${location}`
            })
        });

        const data = await res.json();

        if (res.ok) {
            showToast(data.message || `Problem reported! ${data.solver_display}`, 'success', 5000);
            
            // Show result card
            const resultCard = document.getElementById('assignmentResultCard');
            const resTicketId = document.getElementById('resTicketId');
            const resSolverInfo = document.getElementById('resSolverInfo');

            if (resultCard && resTicketId && resSolverInfo) {
                resTicketId.innerText = data.ticket.id;
                resSolverInfo.innerHTML = `
                    <div class="flex items-center space-x-2 text-white text-sm">
                        <span class="font-bold text-teal-400">${data.solver_display}</span>
                    </div>
                    <p class="text-xs text-slate-300 mt-1">Specialist solver matched automatically based on category rating & efficiency.</p>
                `;
                resultCard.classList.remove('hidden');
            }

            // Refresh ticket feed
            fetchStudentTickets();
        } else {
            showToast(data.error || 'Failed to submit problem report.', 'error');
        }
    } catch (err) {
        console.error('Error submitting report:', err);
        showToast('Network error while reporting problem.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="send" class="w-4 h-4"></i><span>Submit & Auto-Assign Solver</span>`;
        }
        if (window.lucide) lucide.createIcons();
    }
}

// Modal Problem Reporting
function openReportModal() {
    const modal = document.getElementById('reportProblemModal');
    if (modal) modal.classList.remove('hidden');
}

function closeReportModal() {
    const modal = document.getElementById('reportProblemModal');
    if (modal) modal.classList.add('hidden');
}

async function submitModalReportProblem(event) {
    event.preventDefault();
    const location = document.getElementById('modalReportLocation').value.trim();
    const category = document.getElementById('modalReportCategory').value;
    const urgency = document.getElementById('modalReportUrgency').value;
    const description = document.getElementById('modalReportDescription').value.trim();

    try {
        const res = await fetch('/api/report-problem', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                location, category, urgency, description,
                title: `${category} Issue at ${location}`
            })
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`Problem reported! ${data.solver_display}`, 'success');
            closeReportModal();
            fetchStudentTickets();
        } else {
            showToast(data.error || 'Failed to submit.', 'error');
        }
    } catch (err) {
        console.error(err);
    }
}


// =============================================================================
// ACTIVE PROBLEM TICKETS LIST & RATING ACTIONS
// =============================================================================

async function fetchStudentTickets() {
    const container = document.getElementById('studentTicketsList');
    if (!container) return;

    try {
        const res = await fetch('/api/tickets');
        allStudentTicketsCache = await res.json();

        if (!allStudentTicketsCache || allStudentTicketsCache.length === 0) {
            container.innerHTML = `
                <div class="p-8 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                    <p class="text-xs text-slate-400">No active tickets reported yet.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = allStudentTicketsCache.map(ticket => {
            const urgencyClass = ticket.urgency === 'Critical' 
                ? 'badge-urgency-critical' 
                : ticket.urgency === 'High' 
                ? 'badge-urgency-high' 
                : 'badge-urgency-medium';

            const isResolved = ticket.status === 'Resolved';
            const statusClass = isResolved 
                ? 'badge-status-resolved' 
                : ticket.status === 'In Progress' 
                ? 'badge-status-inprogress' 
                : 'badge-status-assigned';

            // Post-Resolution Rating Button or Status
            let ratingActionHtml = '';
            if (isResolved) {
                if (ticket.rated) {
                    ratingActionHtml = `
                        <span class="inline-flex items-center gap-1 text-[11px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/25 px-2.5 py-1 rounded-xl">
                            <i data-lucide="check-circle" class="w-3.5 h-3.5 text-amber-400"></i>
                            <span>Rated ⭐ ${ticket.rating_score || '5.0'} (Reviewed)</span>
                        </span>
                    `;
                } else {
                    ratingActionHtml = `
                        <button onclick="openRateModal('${ticket.id}')"
                            class="px-3 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-teal-500 hover:from-amber-400 hover:to-teal-400 text-slate-950 font-black text-xs shadow-md shadow-amber-500/20 flex items-center space-x-1.5 transition-all transform active:scale-95">
                            <span>⭐ Rate & Review Solution</span>
                            <span class="text-[10px] bg-slate-950/30 px-1 py-0.2 rounded font-mono">+5 Rep</span>
                        </button>
                    `;
                }
            } else {
                // Allow user/tester to resolve ticket for demonstration
                ratingActionHtml = `
                    <button onclick="markTicketResolved('${ticket.id}')" title="Simulate issue resolution by solver"
                        class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-[11px] font-semibold flex items-center space-x-1 transition-all border border-slate-700">
                        <i data-lucide="check" class="w-3 h-3 text-emerald-400"></i>
                        <span>Mark Resolved</span>
                    </button>
                `;
            }

            return `
                <div class="bg-slate-950/80 border border-slate-800/90 rounded-2xl p-4 space-y-3 hover:border-slate-700 transition-all">
                    <div class="flex items-start justify-between gap-2">
                        <div class="space-y-1">
                            <div class="flex items-center space-x-2">
                                <span class="font-mono text-[11px] font-bold text-teal-400">${ticket.id}</span>
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold ${urgencyClass}">${ticket.urgency}</span>
                                <span class="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300">${ticket.category}</span>
                            </div>
                            <h4 class="text-xs font-bold text-white">${ticket.title}</h4>
                        </div>
                        <span class="px-2.5 py-1 rounded-lg text-[10px] font-bold ${statusClass}">${ticket.status}</span>
                    </div>

                    <p class="text-xs text-slate-300 leading-relaxed">${ticket.description}</p>

                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px] text-slate-400 pt-2 border-t border-slate-900">
                        <div class="flex items-center space-x-3">
                            <span class="flex items-center gap-1">
                                <i data-lucide="map-pin" class="w-3 h-3 text-slate-500"></i>
                                <span>${ticket.location}</span>
                            </span>
                            <span class="font-bold text-teal-300 bg-teal-500/10 border border-teal-500/20 px-2 py-0.5 rounded-md">
                                ${ticket.solver_display || `Assigned to: ${ticket.solver_name} (⭐ ${ticket.solver_rating || '5.0'})`}
                            </span>
                        </div>
                        
                        <!-- Rating Action / Button -->
                        <div class="self-end sm:self-auto">
                            ${ratingActionHtml}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error fetching tickets:', err);
    }
}

// Mark Ticket Resolved
async function markTicketResolved(ticketId) {
    try {
        const res = await fetch(`/api/tickets/${ticketId}/resolve`, { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast(`Ticket ${ticketId} marked as Resolved. You can now rate the service!`, 'success');
            fetchStudentTickets();
        } else {
            showToast(data.error || 'Failed to resolve ticket.', 'error');
        }
    } catch (err) {
        console.error('Error resolving ticket:', err);
    }
}


// =============================================================================
// POST-RESOLUTION RATING MODAL & SUBMISSION SYSTEM
// =============================================================================

function setupInteractiveStars(containerId, hiddenInputId, defaultValue = 5) {
    const container = document.getElementById(containerId);
    const hiddenInput = document.getElementById(hiddenInputId);
    if (!container || !hiddenInput) return;

    hiddenInput.value = defaultValue;

    function renderStars(currentVal) {
        container.innerHTML = [1, 2, 3, 4, 5].map(val => `
            <button type="button" data-val="${val}" class="star-btn p-1 text-lg transition-transform hover:scale-125 focus:outline-none ${val <= currentVal ? 'text-amber-400' : 'text-slate-600'}">
                ★
            </button>
        `).join('');

        container.querySelectorAll('.star-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const selectedVal = parseInt(btn.getAttribute('data-val'));
                hiddenInput.value = selectedVal;
                renderStars(selectedVal);
            });
        });
    }

    renderStars(defaultValue);
}

function openRateModal(ticketId) {
    const ticket = allStudentTicketsCache.find(t => t.id === ticketId);
    if (!ticket) return;

    document.getElementById('rateTicketId').value = ticket.id;
    document.getElementById('rateSolverName').value = ticket.solver_name || 'Ravi';
    document.getElementById('rateSolverId').value = ticket.solver_id || '';
    document.getElementById('rateCategory').value = ticket.category || 'Electrical';

    const subtitle = document.getElementById('ratingModalSubtitle');
    if (subtitle) {
        subtitle.innerText = `Assigned Solver: ${ticket.solver_name || 'Ravi'} (${ticket.category}) • Ticket ${ticket.id}`;
    }

    // Initialize 3 star rating categories with default 5 stars
    setupInteractiveStars('starGroupResponse', 'valResponseTime', 5);
    setupInteractiveStars('starGroupQuality', 'valQuality', 5);
    setupInteractiveStars('starGroupBehavior', 'valBehavior', 5);

    const modal = document.getElementById('rateServiceModal');
    if (modal) modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
}

function closeRateModal() {
    const modal = document.getElementById('rateServiceModal');
    if (modal) modal.classList.add('hidden');
}

async function submitServiceRating(event) {
    event.preventDefault();

    const ticketId = document.getElementById('rateTicketId').value;
    const solverName = document.getElementById('rateSolverName').value;
    const solverId = document.getElementById('rateSolverId').value;
    const category = document.getElementById('rateCategory').value;
    const responseTime = parseFloat(document.getElementById('valResponseTime').value || 5);
    const quality = parseFloat(document.getElementById('valQuality').value || 5);
    const behavior = parseFloat(document.getElementById('valBehavior').value || 5);
    const suggestion = document.getElementById('rateSuggestion').value.trim();
    const btn = document.getElementById('btnSubmitRating');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Submitting Review...</span>`;
    }
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/submit-rating', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ticket_id: ticketId,
                solver_name: solverName,
                worker_id: solverId,
                category: category,
                response_time: responseTime,
                quality: quality,
                behavior: behavior,
                suggestion: suggestion
            })
        });

        const data = await res.json();

        if (res.ok) {
            showToast(`⭐ Review submitted! +5 Reputation Points awarded! (Score: ⭐ ${data.avg_rating})`, 'success', 6000);
            closeRateModal();
            fetchStudentProfile();
            fetchStudentTickets();
        } else {
            showToast(data.error || 'Failed to submit rating.', 'error');
        }
    } catch (err) {
        console.error('Error submitting rating:', err);
        showToast('Network error while submitting rating.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<span>⭐ Submit Rating & Claim +5 Rep</span>`;
        }
    }
}


// =============================================================================
// EVENT BOOKING & TIME CLASH DETECTION
// =============================================================================

function fillEventClashSample() {
    const nameInput = document.getElementById('bookEventName');
    const venueInput = document.getElementById('bookEventVenue');
    const dateInput = document.getElementById('bookEventDate');
    const startInput = document.getElementById('bookEventStart');
    const endInput = document.getElementById('bookEventEnd');

    if (nameInput) nameInput.value = 'Autonomous Robotics Demo';
    if (venueInput) venueInput.value = 'Main Auditorium';
    if (dateInput) dateInput.value = 'Today';
    if (startInput) startInput.value = '11:00';
    if (endInput) endInput.value = '14:00';
}

async function submitEventBooking(event) {
    event.preventDefault();

    const name = document.getElementById('bookEventName').value.trim();
    const venue = document.getElementById('bookEventVenue').value;
    const date = document.getElementById('bookEventDate').value.trim();
    const start = document.getElementById('bookEventStart').value.trim();
    const end = document.getElementById('bookEventEnd').value.trim();
    const alertBox = document.getElementById('inlineClashAlert');
    const alertText = document.getElementById('inlineClashAlertText');
    const btn = document.getElementById('btnSubmitEventBooking');

    if (alertBox) alertBox.classList.add('hidden');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Validating Venue Schedule...</span>`;
    }
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch('/api/events/book', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                venue: venue,
                date: date,
                start_time: start,
                end_time: end
            })
        });

        const data = await res.json();

        if (res.status === 409 || data.clash) {
            // CLASH DETECTED -> SHOW INLINE ALERT WITH DATABASE DETAILS
            let msg = data.message;
            if (!msg && data.conflicting_event) {
                const c = data.conflicting_event;
                msg = `⚠️ Schedule Conflict: "${c.name}" conducted by "${c.organizer}" is already scheduled in "${c.venue}" from ${c.start_time} to ${c.end_time} on ${c.date}. Please choose another area or time.`;
            }
            if (!msg) {
                msg = `⚠️ Schedule Conflict: ${venue} is already booked for the selected time.`;
            }

            if (alertBox && alertText) {
                alertText.innerText = msg;
                alertBox.classList.remove('hidden');
            }
            showToast(msg, 'error', 7000);
            // Keep entered form data intact for quick adjustments
        } else if (res.ok) {
            // SUCCESS
            if (alertBox) alertBox.classList.add('hidden');
            showToast(data.message || `Venue '${venue}' booked successfully for '${name}'!`, 'success');
            fetchEvents(); // Real-time immediate refresh of confirmed events schedule
        } else {
            showToast(data.error || 'Failed to book venue.', 'error');
        }
    } catch (err) {
        console.error('Error booking event:', err);
        showToast('Network error while booking event.', 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="calendar-plus" class="w-4 h-4"></i><span>Check Availability & Book Venue</span>`;
        }
        if (window.lucide) lucide.createIcons();
    }
}


// =============================================================================
// CONFIRMED CAMPUS EVENTS & SCHEDULE FEED
// =============================================================================

function escapeEventHtml(unsafe) {
    if (!unsafe) return '';
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function fetchEvents() {
    const container = document.getElementById('scheduledEventsList');
    if (!container) return;

    try {
        const res = await fetch('/api/events');
        if (!res.ok) {
            console.error('Failed to fetch events, status:', res.status);
            container.innerHTML = `
                <div class="p-4 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                    <p class="text-xs text-rose-400">Unable to load events at this moment.</p>
                </div>
            `;
            return;
        }

        const events = await res.json();
        renderScheduledEvents(events);
    } catch (err) {
        console.error('Error loading events:', err);
        container.innerHTML = `
            <div class="p-4 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                <p class="text-xs text-rose-400">Network error while loading events schedule.</p>
            </div>
        `;
    }
}

function renderScheduledEvents(events) {
    const container = document.getElementById('scheduledEventsList');
    if (!container) return;

    if (!events || events.length === 0) {
        container.innerHTML = `
            <div class="p-6 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                <p class="text-xs text-slate-400">No upcoming events scheduled.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = events.map(e => {
        const venue = e.venue || 'Campus Venue';
        const name = e.name || 'Campus Event';
        const organizer = e.organizer || 'Student Council';
        const date = e.date || 'Upcoming';
        const startTime = e.start_time || '09:00';
        const endTime = e.end_time || '17:00';
        const status = e.status || 'Confirmed 🟢';
        const registeredCount = e.registered_count || 0;
        const capacity = e.capacity || 100;
        const isRegistered = Boolean(e.is_registered);
        const isFull = registeredCount >= capacity;

        let rsvpBtnHtml = '';
        if (isRegistered) {
            rsvpBtnHtml = `
                <button disabled class="px-3 py-1.5 rounded-xl bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 text-xs font-bold flex items-center space-x-1 cursor-default">
                    <i data-lucide="check" class="w-3.5 h-3.5"></i>
                    <span>✓ Registered</span>
                </button>
            `;
        } else if (isFull) {
            rsvpBtnHtml = `
                <button disabled class="px-3 py-1.5 rounded-xl bg-slate-800 text-slate-500 text-xs font-bold flex items-center space-x-1 cursor-not-allowed">
                    <span>Event Full</span>
                </button>
            `;
        } else {
            rsvpBtnHtml = `
                <button onclick="registerForEvent('${e.id}')" id="btnRegister-${e.id}"
                    class="px-3.5 py-1.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 text-xs font-bold flex items-center space-x-1.5 transition-all shadow-md shadow-teal-500/20 cursor-pointer">
                    <i data-lucide="ticket" class="w-3.5 h-3.5"></i>
                    <span>Register</span>
                </button>
            `;
        }

        return `
            <div class="bg-slate-950/80 border border-slate-800/90 rounded-2xl p-3.5 space-y-2.5 hover:border-slate-700 transition-all">
                <div class="flex items-start justify-between gap-3">
                    <div class="space-y-0.5 flex-1">
                        <h4 class="text-xs font-bold text-white leading-tight">${escapeEventHtml(name)}</h4>
                        <p class="text-[11px] text-slate-400">Organized by <span class="text-teal-300 font-medium">${escapeEventHtml(organizer)}</span></p>
                    </div>
                    <div class="flex items-center space-x-2">
                        <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 whitespace-nowrap">
                            ${escapeEventHtml(status)}
                        </span>
                        ${rsvpBtnHtml}
                    </div>
                </div>
                <div class="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-slate-300 pt-1 border-t border-slate-900">
                    <div class="flex flex-wrap items-center gap-2">
                        <span class="flex items-center gap-1 bg-slate-900/90 px-2 py-0.5 rounded-lg border border-slate-800">
                            <i data-lucide="map-pin" class="w-3 h-3 text-teal-400"></i>
                            <span>${escapeEventHtml(venue)}</span>
                        </span>
                        <span class="flex items-center gap-1 bg-slate-900/90 px-2 py-0.5 rounded-lg border border-slate-800">
                            <i data-lucide="calendar" class="w-3 h-3 text-indigo-400"></i>
                            <span>${escapeEventHtml(date)}</span>
                        </span>
                        <span class="flex items-center gap-1 bg-slate-900/90 px-2 py-0.5 rounded-lg border border-slate-800">
                            <i data-lucide="clock" class="w-3 h-3 text-amber-400"></i>
                            <span>${escapeEventHtml(startTime)} - ${escapeEventHtml(endTime)}</span>
                        </span>
                    </div>
                    <span class="text-[10px] text-slate-400 flex items-center gap-1 bg-slate-900/60 px-2 py-0.5 rounded-lg border border-slate-800/80">
                        <i data-lucide="users" class="w-3 h-3 text-teal-400"></i>
                        <span>${registeredCount} / ${capacity}</span>
                    </span>
                </div>
            </div>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

async function registerForEvent(eventId) {
    const btn = document.getElementById(`btnRegister-${eventId}`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Registering...</span>`;
    }
    if (window.lucide) lucide.createIcons();

    try {
        const res = await fetch(`/api/events/${eventId}/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ event_id: eventId })
        });
        const data = await res.json();

        if (res.status === 201 || data.success) {
            showToast(data.message || '🎉 Successfully registered for event!', 'success');
            fetchEvents();
            fetchMyRegistrations();
        } else {
            showToast(data.message || data.error || 'Failed to register for event.', 'error');
            fetchEvents();
        }
    } catch (err) {
        console.error('Error registering for event:', err);
        showToast('Network error while registering for event.', 'error');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="ticket" class="w-3.5 h-3.5"></i><span>Register</span>`;
        }
    }
}


// =============================================================================
// MY REGISTERED EVENTS (RSVP) FEED
// =============================================================================

async function fetchMyRegistrations() {
    const container = document.getElementById('myRegisteredEventsList');
    if (!container) return;

    try {
        const res = await fetch('/api/student/my-registrations');
        if (!res.ok) {
            console.error('Failed to fetch my registrations, status:', res.status);
            container.innerHTML = `
                <div class="p-4 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                    <p class="text-xs text-rose-400">Unable to load registered events.</p>
                </div>
            `;
            return;
        }

        const registrations = await res.json();
        renderMyRegistrations(registrations);
    } catch (err) {
        console.error('Error loading my registrations:', err);
        container.innerHTML = `
            <div class="p-4 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                <p class="text-xs text-rose-400">Network error while loading registered events.</p>
            </div>
        `;
    }
}

function renderMyRegistrations(registrations) {
    const container = document.getElementById('myRegisteredEventsList');
    if (!container) return;

    if (!registrations || registrations.length === 0) {
        container.innerHTML = `
            <div class="p-6 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                <p class="text-xs text-slate-400">You have not registered for any events yet. Check out the upcoming events schedule above to RSVP!</p>
            </div>
        `;
        return;
    }

    container.innerHTML = registrations.map(r => {
        const eventName = r.event_name || 'Campus Event';
        const venue = r.venue || 'Campus Venue';
        const date = r.date || 'Upcoming';
        const startTime = r.start_time || '09:00';
        const endTime = r.end_time || '17:00';
        const organizer = r.organizer || 'Campus Body';
        const registeredAt = r.registered_at || 'Recently';

        return `
            <div class="bg-slate-950/80 border border-slate-800/90 rounded-2xl p-3.5 space-y-2 hover:border-emerald-500/40 transition-all">
                <div class="flex items-start justify-between gap-2">
                    <div class="space-y-0.5">
                        <h4 class="text-xs font-bold text-white leading-tight flex items-center gap-1.5">
                            <span>${escapeEventHtml(eventName)}</span>
                        </h4>
                        <p class="text-[11px] text-slate-400">Organized by <span class="text-teal-300 font-medium">${escapeEventHtml(organizer)}</span></p>
                    </div>
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 whitespace-nowrap">
                        <i data-lucide="check" class="w-3 h-3 text-emerald-400"></i>
                        <span>Confirmed RSVP</span>
                    </span>
                </div>
                <div class="flex flex-wrap items-center gap-2 text-[11px] font-mono text-slate-300 pt-1 border-t border-slate-900">
                    <span class="flex items-center gap-1 bg-slate-900/90 px-2 py-0.5 rounded-lg border border-slate-800">
                        <i data-lucide="map-pin" class="w-3 h-3 text-teal-400"></i>
                        <span>${escapeEventHtml(venue)}</span>
                    </span>
                    <span class="flex items-center gap-1 bg-slate-900/90 px-2 py-0.5 rounded-lg border border-slate-800">
                        <i data-lucide="calendar" class="w-3 h-3 text-indigo-400"></i>
                        <span>${escapeEventHtml(date)}</span>
                    </span>
                    <span class="flex items-center gap-1 bg-slate-900/90 px-2 py-0.5 rounded-lg border border-slate-800">
                        <i data-lucide="clock" class="w-3 h-3 text-amber-400"></i>
                        <span>${escapeEventHtml(startTime)} - ${escapeEventHtml(endTime)}</span>
                    </span>
                    <span class="ml-auto text-[10px] text-slate-500">Registered: ${escapeEventHtml(registeredAt)}</span>
                </div>
            </div>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}


// =============================================================================
// FILTERABLE ANNOUNCEMENTS FEED (Academic, Hostel, Events)
// =============================================================================

async function fetchAnnouncements() {
    try {
        const res = await fetch('/api/announcements');
        if (!res.ok) {
            allAnnouncementsCache = [];
        } else {
            allAnnouncementsCache = await res.json();
        }
        renderAnnouncements();
    } catch (err) {
        console.error('Error fetching announcements:', err);
        allAnnouncementsCache = [];
        renderAnnouncements();
    }
}

function filterAnnouncements(category) {
    currentCategoryFilter = category;

    ['all', 'Academic', 'Hostel', 'Events'].forEach(cat => {
        const tab = document.getElementById(`tabAnn${cat}`);
        if (!tab) return;

        if (cat.toLowerCase() === category.toLowerCase()) {
            tab.className = 'px-3.5 py-1.5 rounded-xl font-bold bg-teal-500/20 text-teal-300 transition-all';
        } else {
            tab.className = 'px-3.5 py-1.5 rounded-xl text-slate-400 hover:text-white transition-all font-medium';
        }
    });

    renderAnnouncements();
}

function renderAnnouncements() {
    const container = document.getElementById('announcementsList');
    if (!container) return;

    let items = allAnnouncementsCache || [];
    if (currentCategoryFilter !== 'all') {
        items = items.filter(a => (a.category || '').toLowerCase() === currentCategoryFilter.toLowerCase());
    }

    if (!items || items.length === 0) {
        container.innerHTML = `
            <div class="col-span-full p-8 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                <p class="text-xs text-slate-400">No announcements in ${escapeEventHtml(currentCategoryFilter)}.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = items.map(a => {
        const category = a.category || 'General';
        const badgeBg = category === 'Academic' 
            ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
            : category === 'Hostel'
            ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
            : category === 'Events'
            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
            : 'bg-teal-500/20 text-teal-300 border-teal-500/30';

        const priorityBadge = a.priority === 'Urgent'
            ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">Urgent 🚨</span>'
            : a.priority === 'Important'
            ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">Important ⚠️</span>'
            : '';

        return `
            <div class="bg-slate-950/80 border border-slate-800 rounded-2xl p-4 space-y-3 hover:border-slate-700 transition-all">
                <div class="flex items-start justify-between gap-2">
                    <div class="flex items-center space-x-1.5">
                        <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${badgeBg}">
                            ${escapeEventHtml(category)}
                        </span>
                        ${priorityBadge}
                    </div>
                    <span class="text-[11px] font-mono text-slate-500">${escapeEventHtml(a.date || 'Today')}</span>
                </div>

                <h4 class="text-xs font-bold text-white leading-snug">${escapeEventHtml(a.title)}</h4>
                <p class="text-xs text-slate-300 leading-relaxed">${escapeEventHtml(a.content)}</p>

                <div class="pt-2 border-t border-slate-900 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                    <span>${escapeEventHtml(a.time || a.created_at || '')}</span>
                    <span class="text-slate-300">${escapeEventHtml(a.venue || 'Campus')}</span>
                </div>
            </div>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

async function fetchAlerts() {
    const container = document.getElementById('alertsContainer');
    if (!container) return;

    try {
        const res = await fetch('/api/alerts');
        if (!res.ok) {
            container.innerHTML = `
                <div class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 text-center text-slate-400">
                    <p class="text-xs flex items-center justify-center gap-2">
                        <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i>
                        <span>No critical campus alerts at the moment.</span>
                    </p>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        const alerts = await res.json();
        if (!alerts || alerts.length === 0) {
            container.innerHTML = `
                <div class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 text-center text-slate-400">
                    <p class="text-xs flex items-center justify-center gap-2">
                        <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i>
                        <span>No critical campus alerts at the moment.</span>
                    </p>
                </div>
            `;
            if (window.lucide) lucide.createIcons();
            return;
        }

        container.innerHTML = alerts.map(a => {
            const isUrgent = (a.priority || '').toLowerCase() === 'urgent';
            const bgGradient = isUrgent
                ? 'from-rose-950/90 to-red-950/80 border-rose-500/60 shadow-rose-950/40 text-rose-400'
                : 'from-amber-950/90 to-orange-950/80 border-amber-500/60 shadow-amber-950/40 text-amber-400';
            const badgeBg = isUrgent
                ? 'bg-rose-500 text-slate-950'
                : 'bg-amber-500 text-slate-950';
            const textColor = isUrgent ? 'text-rose-200/90' : 'text-amber-200/90';
            const dateColor = isUrgent ? 'text-rose-300/80' : 'text-amber-300/80';

            return `
                <div class="p-5 rounded-2xl bg-gradient-to-r ${bgGradient} border-2 shadow-2xl relative overflow-hidden">
                    <div class="flex items-start space-x-3.5">
                        <div class="w-10 h-10 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/40 flex items-center justify-center flex-shrink-0 animate-pulse">
                            <i data-lucide="alert-triangle" class="w-5 h-5"></i>
                        </div>
                        <div class="space-y-1 flex-1">
                            <div class="flex flex-wrap items-center gap-2">
                                <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold ${badgeBg} uppercase tracking-wide">
                                    ${escapeEventHtml(a.priority || 'URGENT')} NOTICE
                                </span>
                                <h3 class="text-sm font-bold text-white">${escapeEventHtml(a.title)}</h3>
                                <span class="text-xs ${dateColor}">• ${escapeEventHtml(a.timestamp || 'Today')}</span>
                            </div>
                            <p class="text-xs ${textColor} leading-relaxed">
                                ${escapeEventHtml(a.message || a.content || '')}
                            </p>
                            ${a.location ? `<div class="text-[11px] font-mono text-slate-300 pt-1">📍 ${escapeEventHtml(a.location)}</div>` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error('Error fetching alerts:', err);
        container.innerHTML = `
            <div class="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 text-center text-slate-400">
                <p class="text-xs flex items-center justify-center gap-2">
                    <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i>
                    <span>No critical campus alerts at the moment.</span>
                </p>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
    }
}


// =============================================================================
// TAB NAVIGATION MANAGEMENT
// =============================================================================

const STUDENT_TABS = ['dashboard', 'announcements', 'events', 'registrations', 'tickets', 'profile'];

function switchStudentTab(tabId) {
    if (!STUDENT_TABS.includes(tabId)) {
        tabId = 'dashboard';
    }

    // Update section visibility
    STUDENT_TABS.forEach(tab => {
        const sec = document.getElementById(`section-${tab}`);
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
    document.querySelectorAll('[data-student-tab]').forEach(btn => {
        const target = btn.getAttribute('data-student-tab');
        if (target === tabId) {
            btn.classList.add('bg-teal-500/20', 'text-teal-300', 'border-teal-500/30');
            btn.classList.remove('text-slate-400', 'hover:text-slate-200', 'hover:bg-slate-800/60');
        } else {
            btn.classList.remove('bg-teal-500/20', 'text-teal-300', 'border-teal-500/30');
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

// Make switchStudentTab globally accessible
window.switchStudentTab = switchStudentTab;


// =============================================================================
// INITIALIZATION
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Check initial tab from window hash or server template attribute
    const mainEl = document.getElementById('studentMainContent');
    const hash = window.location.hash.replace('#', '').toLowerCase();
    const activeTab = (hash && STUDENT_TABS.includes(hash))
        ? hash
        : ((mainEl && mainEl.getAttribute('data-active-tab')) || 'dashboard');

    switchStudentTab(activeTab);

    // Listen for hash changes
    window.addEventListener('hashchange', () => {
        const newHash = window.location.hash.replace('#', '').toLowerCase();
        if (newHash && STUDENT_TABS.includes(newHash)) {
            switchStudentTab(newHash);
        }
    });

    fetchStudentProfile();
    fetchStudentTickets();
    fetchAlerts();
    fetchAnnouncements();
    fetchEvents();
    fetchMyRegistrations();
});
