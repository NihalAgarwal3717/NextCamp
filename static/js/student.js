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
        const banner = document.getElementById('studentFineBanner');
        const bannerText = document.getElementById('studentFineBannerText');
        const nameEl = document.getElementById('studentProfileName');
        const repPointsEl = document.getElementById('studentReputationPoints');
        const headerRep = document.getElementById('headerReputationScore');
        const headerBadge = document.getElementById('headerUserBadge');

        if (nameEl && student.name) nameEl.innerText = student.name;
        if (repPointsEl && student.reputation_points !== undefined) repPointsEl.innerText = student.reputation_points;
        if (headerRep && student.reputation !== undefined) headerRep.innerText = `⭐ ${parseFloat(student.reputation).toFixed(1)}`;
        if (headerBadge && student.badge) headerBadge.innerText = student.badge;

        if (fineEl) {
            fineEl.innerText = `₹${student.fine_amount || 0}`;
            if ((student.fine_amount || 0) > 0) {
                fineEl.className = 'text-lg font-bold font-mono text-rose-400 animate-pulse';
            } else {
                fineEl.className = 'text-lg font-bold font-mono text-emerald-400';
            }
        }

        if (badge) {
            badge.innerText = student.status || 'Good Standing 🟢';
            if (student.status && student.status.includes('Action Required')) {
                badge.className = 'px-3 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse';
            } else {
                badge.className = 'px-3 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40';
            }
        }

        if (banner) {
            if (student.status && student.status.includes('Action Required')) {
                banner.classList.remove('hidden');
                if (bannerText) {
                    bannerText.innerHTML = `<b>⚠️ Disciplinary Notice:</b> An administrative fine of ₹${student.fine_amount || 500} has been issued. Status: <b>Action Required 🔴</b>.`;
                }
            } else {
                banner.classList.add('hidden');
            }
        }
    } catch (err) {
        console.error('Error fetching student profile:', err);
    }
}

// Clear / Pay Fine
async function payStudentFine() {
    try {
        const res = await fetch('/api/student/pay-fine', { method: 'POST' });
        const data = await res.json();

        if (res.ok) {
            showToast('Fine cleared successfully! Status restored to Good Standing 🟢', 'success');
            fetchStudentProfile();
        } else {
            showToast(data.error || 'Failed to pay fine.', 'error');
        }
    } catch (err) {
        console.error('Error paying fine:', err);
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
            // CLASH DETECTED -> SHOW INLINE ALERT BLOCKING SUBMISSION
            const msg = data.message || `⚠️ TIME CLASH DETECTED: ${venue} is already booked`;
            if (alertBox && alertText) {
                alertText.innerText = msg;
                alertBox.classList.remove('hidden');
            }
            showToast(msg, 'error', 6000);
        } else if (res.ok) {
            // SUCCESS
            if (alertBox) alertBox.classList.add('hidden');
            showToast(data.message || `Venue booked successfully!`, 'success');
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
// FILTERABLE ANNOUNCEMENTS FEED (Academic, Hostel, Events)
// =============================================================================

async function fetchAnnouncements() {
    try {
        const res = await fetch('/api/announcements');
        allAnnouncementsCache = await res.json();
        renderAnnouncements();
    } catch (err) {
        console.error('Error fetching announcements:', err);
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

    let items = allAnnouncementsCache;
    if (currentCategoryFilter !== 'all') {
        items = items.filter(a => a.category.toLowerCase() === currentCategoryFilter.toLowerCase());
    }

    if (!items || items.length === 0) {
        container.innerHTML = `
            <div class="col-span-full p-8 text-center bg-slate-950/40 rounded-2xl border border-slate-800">
                <p class="text-xs text-slate-400">No announcements in ${currentCategoryFilter}.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = items.map(a => {
        const badgeBg = a.category === 'Academic' 
            ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
            : a.category === 'Hostel'
            ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
            : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';

        return `
            <div class="bg-slate-950/80 border border-slate-800 rounded-2xl p-4 space-y-3 hover:border-slate-700 transition-all">
                <div class="flex items-start justify-between gap-2">
                    <span class="px-2 py-0.5 rounded text-[10px] font-bold border ${badgeBg}">
                        ${a.category}
                    </span>
                    <span class="text-[11px] font-mono text-slate-500">${a.date}</span>
                </div>

                <h4 class="text-xs font-bold text-white leading-snug">${a.title}</h4>
                <p class="text-xs text-slate-300 leading-relaxed">${a.content}</p>

                <div class="pt-2 border-t border-slate-900 flex items-center justify-between text-[10px] text-slate-400 font-mono">
                    <span>${a.time}</span>
                    <span class="text-slate-300">${a.venue}</span>
                </div>
            </div>
        `;
    }).join('');

    if (window.lucide) lucide.createIcons();
}

async function fetchAlerts() {
    showToast('Campus alerts synchronized.', 'info', 2000);
}


// =============================================================================
// INITIALIZATION
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    fetchStudentProfile();
    fetchStudentTickets();
    fetchAnnouncements();
});
