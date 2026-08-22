/**
 * NextCamp Core Application Script
 * Global state, toast notifications, and utility helpers.
 */

// Toast Notification System
function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `pointer-events-auto flex items-center space-x-3 px-4 py-3 rounded-2xl shadow-2xl border backdrop-blur-md transition-all transform duration-300 translate-y-2 opacity-0 text-xs font-medium z-50 ${
        type === 'success' 
            ? 'bg-emerald-950/90 border-emerald-500/40 text-emerald-200' 
            : type === 'error' 
            ? 'bg-rose-950/90 border-rose-500/40 text-rose-200' 
            : type === 'warning'
            ? 'bg-amber-950/90 border-amber-500/40 text-amber-200'
            : 'bg-slate-900/90 border-teal-500/40 text-slate-100'
    }`;

    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    if (type === 'error') iconName = 'alert-triangle';
    if (type === 'warning') iconName = 'alert-circle';

    toast.innerHTML = `
        <div class="flex-shrink-0">
            <i data-lucide="${iconName}" class="w-4 h-4"></i>
        </div>
        <div class="flex-1 leading-snug">${message}</div>
        <button onclick="this.parentElement.remove()" class="text-slate-400 hover:text-white ml-2">
            <i data-lucide="x" class="w-3.5 h-3.5"></i>
        </button>
    `;

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    // Trigger transition
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-2', 'opacity-0');
    });

    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
