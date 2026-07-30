const API_BASE = window.RAILBOT_API_BASE || "http://localhost:8000";
const nativeFetch = window.fetch.bind(window);
async function signOutUser(event) {
    if (event) event.preventDefault();
    if (window.railbotSignOut) await window.railbotSignOut();
    localStorage.removeItem('rail_assist_thread_id');
    window.location.reload();
}
window.signOutUser = signOutUser;
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('a').forEach((link) => {
        if (link.textContent.trim().includes('Sign Out')) link.addEventListener('click', signOutUser);
    });
});
window.fetch = async (url, options = {}) => {
    if (String(url).startsWith(API_BASE) && window.railbotAuthReady) {
        await window.railbotAuthReady;
        const token = await window.railbotAccessToken?.();
        options.headers = { ...(options.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
    }
    return nativeFetch(url, options);
};
const CLIENT_ID_KEY = "rail_assist_client_id";

function getClientId() {
    let clientId = localStorage.getItem(CLIENT_ID_KEY);
    if (!clientId) {
        clientId = window.crypto?.randomUUID?.() || Math.random().toString(36).slice(2);
        localStorage.setItem(CLIENT_ID_KEY, clientId);
    }
    return clientId;
}

const clientId = getClientId();
function createThreadId() {
    return `anon_${clientId}_${window.crypto?.randomUUID?.() || Math.random().toString(36).slice(2)}`;
}
let threadId = createThreadId();

const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const sendIcon = document.getElementById('send-icon');
const chatContainer = document.getElementById('chat-container');

// Allow long messages to wrap naturally in the composer. Enter creates a new
// line; Ctrl/Cmd+Enter submits the message.
chatInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        chatForm.requestSubmit();
    }
});
chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = `${Math.min(chatInput.scrollHeight, 128)}px`;
});

// --- Session & Recent History Manager ---
function getSavedSessions() {
    try {
        const data = localStorage.getItem('rail_assist_sessions');
        const sessions = data ? JSON.parse(data) : [];
        // Old session ids had no owner. Do not show them now that history is isolated.
        return Array.isArray(sessions)
            ? sessions.filter(s => s?.threadId?.startsWith(`anon_${clientId}_`))
            : [];
    } catch(e) {
        return [];
    }
}

async function migrateLegacyChatsForCurrentAccount() {
    try {
        const raw = JSON.parse(localStorage.getItem('rail_assist_sessions') || '[]');
        const legacyIds = Array.isArray(raw)
            ? raw.map(s => s?.threadId).filter(id => typeof id === 'string' && id.startsWith('session_'))
            : [];
        if (!legacyIds.length || localStorage.getItem('rail_assist_legacy_migrated')) return;
        const res = await fetch(`${API_BASE}/api/history/migrate-legacy`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ thread_ids: legacyIds })
        });
        if (res.ok) localStorage.setItem('rail_assist_legacy_migrated', 'true');
    } catch (e) { console.warn('Could not migrate legacy chat references', e); }
}

function saveSession(tId, firstMessageText) {
    let sessions = getSavedSessions();
    const existingIndex = sessions.findIndex(s => s.threadId === tId);
    
    let title = firstMessageText.trim();
    if (title.length > 28) {
        title = title.substring(0, 28) + '...';
    }
    
    if (existingIndex >= 0) {
        sessions[existingIndex].title = title;
        sessions[existingIndex].timestamp = Date.now();
    } else {
        sessions.unshift({ threadId: tId, title: title, timestamp: Date.now() });
    }
    
    if (sessions.length > 15) sessions = sessions.slice(0, 15);
    
    try {
        localStorage.setItem('rail_assist_sessions', JSON.stringify(sessions));
    } catch(e) {}

    sessions.sort((a, b) => {
        if (a.sortKey || b.sortKey) return String(b.sortKey || '').localeCompare(String(a.sortKey || ''));
        const aTime = Date.parse(a.updatedAt || '') || a.timestamp || 0;
        const bTime = Date.parse(b.updatedAt || '') || b.timestamp || 0;
        return bTime - aTime;
    });
    
    renderRecentHistorySidebar();
}

async function renderRecentHistorySidebar() {
    const listEl = document.getElementById('recent-history-list');
    if (!listEl) return;
    
    let sessions = getSavedSessions();

    try {
        const res = await fetch(`${API_BASE}/api/sessions?client_id=${encodeURIComponent(clientId)}`);
        if (res.ok) {
            const data = await res.json();
            if (data.status === "success" && data.sessions && data.sessions.length > 0) {
                const dbMap = new Map();
                data.sessions.forEach(s => dbMap.set(s.threadId, s));
                sessions.forEach(s => {
                    if (!dbMap.has(s.threadId)) dbMap.set(s.threadId, s);
                });
                sessions = Array.from(dbMap.values());
            }
        }
    } catch(e) {}

    if (sessions.length === 0) {
        listEl.innerHTML = `
            <a class="block text-on-primary-container hover:text-white font-body-sm text-body-sm truncate transition-colors py-1 cursor-pointer" onclick="quickActionText('What is the delay compensation policy?')"><span class="material-symbols-outlined text-[16px] mr-1 align-text-bottom">history</span>Delay compensation...</a>
            <a class="block text-on-primary-container hover:text-white font-body-sm text-body-sm truncate transition-colors py-1 cursor-pointer" onclick="quickActionText('Check Bhopal Shatabdi status')"><span class="material-symbols-outlined text-[16px] mr-1 align-text-bottom">history</span>Bhopal Shatabdi status</a>
        `;
        return;
    }
    
    listEl.innerHTML = sessions.map(s => `
        <div class="group/item relative flex items-center py-1">
            <a class="flex-1 text-on-primary-container hover:text-white font-body-sm text-body-sm truncate transition-colors cursor-pointer ${s.threadId === threadId ? 'font-bold text-secondary-fixed-dim' : ''}" onclick="loadSession('${s.threadId}', '${escapeHtml(s.title)}')">
                <span class="material-symbols-outlined text-[16px] mr-1 align-text-bottom">history</span>${escapeHtml(s.title)}
            </a>
            <button class="opacity-0 group-hover/item:opacity-100 transition-opacity shrink-0 w-6 h-6 flex items-center justify-center rounded-md hover:bg-white/20 text-on-primary-container hover:text-white cursor-pointer" onclick="toggleSessionMenu(event, '${s.threadId}')" title="Options">
                <span class="material-symbols-outlined text-[16px]">more_horiz</span>
            </button>
            <div id="menu-${s.threadId}" class="hidden absolute right-0 top-full mt-1 bg-surface-container-lowest border border-surface-variant rounded-lg shadow-xl z-50 min-w-[140px] overflow-hidden">
                <button class="w-full flex items-center gap-2 px-3 py-2 text-error hover:bg-error/10 font-body-sm text-body-sm transition-colors cursor-pointer" onclick="deleteSession('${s.threadId}')">
                    <span class="material-symbols-outlined text-[16px]">delete</span>
                    Delete
                </button>
            </div>
        </div>
    `).join('');
}

function toggleSessionMenu(event, sessionThreadId) {
    event.stopPropagation();
    document.querySelectorAll('[id^="menu-"]').forEach(m => {
        if (m.id !== `menu-${sessionThreadId}`) m.classList.add('hidden');
    });
    const menu = document.getElementById(`menu-${sessionThreadId}`);
    if (menu) menu.classList.toggle('hidden');
}

async function deleteSession(sessionThreadId) {
    const confirmed = window.confirm('Delete this conversation permanently? This cannot be undone.');
    if (!confirmed) return;

    try {
        const response = await fetch(`${API_BASE}/api/conversations/${encodeURIComponent(sessionThreadId)}`, {
            method: 'DELETE'
        });
        if (!response.ok && response.status !== 404) {
            throw new Error('Could not delete the conversation.');
        }
    } catch (error) {
        alert(error.message || 'Could not delete the conversation.');
        return;
    }

    let sessions = getSavedSessions();
    sessions = sessions.filter(s => s.threadId !== sessionThreadId);
    try {
        localStorage.setItem('rail_assist_sessions', JSON.stringify(sessions));
    } catch(e) {}
    
    if (sessionThreadId === threadId) {
        startNewInquiry();
    }
    await renderRecentHistorySidebar();
}

document.addEventListener('click', (e) => {
    if (!e.target.closest('[id^="menu-"]') && !e.target.closest('button[onclick^="toggleSessionMenu"]')) {
        document.querySelectorAll('[id^="menu-"]').forEach(m => m.classList.add('hidden'));
    }
});

function formatPillTimestamp(isoStr) {
    try {
        const d = isoStr ? new Date(isoStr) : new Date();
        if (isNaN(d.getTime())) throw new Error();
        const now = new Date();
        const isToday = d.toDateString() === now.toDateString();
        const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        if (isToday) {
            return `Today, ${timeStr}`;
        }
        const dateStr = d.toLocaleDateString([], { month: 'short', day: 'numeric' });
        return `${dateStr}, ${timeStr}`;
    } catch(e) {
        const now = new Date();
        return `Today, ${now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    }
}

function createDateDivider(timestampStr) {
    const div = document.createElement('div');
    div.className = 'flex justify-center my-4 date-divider shrink-0';
    const text = formatPillTimestamp(timestampStr);
    div.innerHTML = `
        <span class="bg-[#d7e3fd]/80 text-[#111c2d] font-body-sm text-[12px] font-semibold px-4 py-1.5 rounded-full shadow-xs border border-secondary-container/20">
            ${text}
        </span>
    `;
    return div;
}

async function loadSession(sThreadId, title) {
    threadId = sThreadId;
    renderRecentHistorySidebar();
    
    chatContainer.innerHTML = `<div class="h-36 shrink-0" id="scroll-anchor"></div>`;
    const anchor = getAnchor();
    const thinking = createThinkingBubble();
    chatContainer.insertBefore(thinking, anchor);
    
    try {
        const res = await fetch(`${API_BASE}/api/history/${encodeURIComponent(sThreadId)}?client_id=${encodeURIComponent(clientId)}`);
        thinking.remove();
        if (res.ok) {
            const data = await res.json();
            if (data.messages && data.messages.length > 0) {
                const firstMsg = data.messages[0];
                chatContainer.insertBefore(createDateDivider(firstMsg.timestamp), anchor);

                for (const msg of data.messages) {
                    if (msg.role === 'user') {
                        chatContainer.insertBefore(createUserBubble(msg.content), anchor);
                    } else {
                        const pnrMatch = msg.content.match(/\b\d{10}\b/);
                        const bubble = document.createElement('div');
                        bubble.className = 'flex items-start gap-sm mt-4';
                        bubble.innerHTML = `
                            <div class="w-8 h-8 rounded-full shrink-0 flex items-center justify-center border-secondary-container/50 overflow-hidden"><img alt="RailBot AI" class="w-full h-full object-cover" src="assets/logo-of-AI.png"/></div>
                            <div class="flex-1 space-y-3 max-w-[90%] lg:max-w-[75%]">
                                <div class="bg-surface-container-lowest border border-surface-variant px-4 py-3 rounded-2xl rounded-tl-none shadow-sm inline-block">
                                    <p class="font-body-md text-body-md text-on-surface">${formatMessageText(msg.content)}</p>
                                </div>
                                <div class="ticket-container"></div>
                            </div>
                        `;
                        chatContainer.insertBefore(bubble, anchor);
                        if (pnrMatch) {
                            renderTicketCard(pnrMatch[0], bubble.querySelector('.ticket-container'));
                        }
                    }
                }
                scrollToBottom();
                return;
            }
        }
    } catch(e) {
        if (thinking.parentNode) thinking.remove();
    }
}

function getAnchor() {
    return document.getElementById('scroll-anchor') || chatContainer.lastElementChild;
}

function scrollToBottom() {
    const anchor = getAnchor();
    if (anchor) {
        anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function startNewInquiry() {
    threadId = createThreadId();
    renderRecentHistorySidebar();
    chatContainer.innerHTML = `
        <div id="welcome-screen" class="flex-1 flex flex-col items-center justify-center text-center px-md py-xl">
            <div class="w-20 h-20 rounded-2xl overflow-hidden mb-md shadow-lg border-2 border-secondary-container/30">
                <img alt="Rail Assist AI" class="w-full h-full object-cover" src="assets/logo-of-AI.png"/>
            </div>
            <h2 class="font-headline-lg text-headline-lg text-on-surface mb-sm">Welcome to Rail Assist AI</h2>
            <p class="font-body-md text-body-md text-on-surface-variant max-w-md mb-lg">Your intelligent Indian Railways assistant. I can help you check PNR status, search trains, book tickets, check refund policies, and more.</p>
            <div class="flex flex-wrap justify-center gap-sm">
                <button onclick="quickAction(this)" class="bg-surface-container-lowest border border-surface-variant hover:border-secondary-container hover:bg-surface-bright text-on-surface-variant hover:text-on-surface font-label-md text-label-md px-4 py-2 rounded-full transition-all shadow-sm cursor-pointer">Check PNR Status</button>
                <button onclick="quickAction(this)" class="bg-surface-container-lowest border border-surface-variant hover:border-secondary-container hover:bg-surface-bright text-on-surface-variant hover:text-on-surface font-label-md text-label-md px-4 py-2 rounded-full transition-all shadow-sm cursor-pointer">Search Trains</button>
                <button onclick="quickAction(this)" class="bg-surface-container-lowest border border-surface-variant hover:border-secondary-container hover:bg-surface-bright text-on-surface-variant hover:text-on-surface font-label-md text-label-md px-4 py-2 rounded-full transition-all shadow-sm cursor-pointer">Refund Policy</button>
                <button onclick="quickAction(this)" class="bg-surface-container-lowest border border-surface-variant hover:border-secondary-container hover:bg-surface-bright text-on-surface-variant hover:text-on-surface font-label-md text-label-md px-4 py-2 rounded-full transition-all shadow-sm cursor-pointer">Book a Ticket</button>
            </div>
        </div>
        <div class="h-36 shrink-0" id="scroll-anchor"></div>
    `;
    chatInput.value = '';
    chatInput.focus();
}

function createThinkingBubble() {
    const div = document.createElement('div');
    div.id = 'thinking-bubble';
    div.className = 'flex items-start gap-sm mt-4';
    div.innerHTML = `
        <div class="w-8 h-8 rounded-full shrink-0 flex items-center justify-center border-secondary-container/50 overflow-hidden"><img alt="RailBot AI" class="w-full h-full object-cover" src="assets/logo-of-AI.png"/></div>
        <div class="bg-surface-container-lowest border border-surface-variant px-4 py-3 rounded-2xl rounded-tl-none shadow-sm inline-block">
            <div class="flex space-x-1.5 items-center h-4">
                <div class="w-2 h-2 bg-on-surface-variant/50 rounded-full animate-bounce" style="animation-delay: 0ms"></div>
                <div class="w-2 h-2 bg-on-surface-variant/50 rounded-full animate-bounce" style="animation-delay: 150ms"></div>
                <div class="w-2 h-2 bg-on-surface-variant/50 rounded-full animate-bounce" style="animation-delay: 300ms"></div>
            </div>
        </div>
    `;
    return div;
}

function createUserBubble(text) {
    const div = document.createElement('div');
    div.className = 'flex items-end justify-end gap-sm mt-4';
    div.innerHTML = `
        <div class="bg-primary-container text-on-primary-fixed px-4 py-3 rounded-2xl rounded-br-none max-w-[80%] lg:max-w-[60%] shadow-sm border border-primary-container/10" style="background-color: rgb(11, 23, 42); color: white;">
            <p class="font-body-md text-body-md">${escapeHtml(text)}</p>
        </div>
        <div class="w-8 h-8 rounded-full bg-primary-container shrink-0 flex items-center justify-center overflow-hidden border border-surface-container-high">
            <span class="material-symbols-outlined text-white text-[18px]" style="font-variation-settings: 'FILL' 1;">person</span>
        </div>
    `;
    return div;
}

function formatMessageText(text) {
    let formatted = escapeHtml(text).replace(/\n/g, '<br>');
    formatted = formatted.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-secondary font-semibold hover:underline inline-flex items-center gap-1">$1 <span class="material-symbols-outlined text-[14px]">open_in_new</span></a>');
    return formatted;
}

async function downloadTicket(event, pnr) {
    event.preventDefault();
    try {
        if (window.railbotAuthReady) await window.railbotAuthReady;
        const token = window.railbotAccessToken ? await window.railbotAccessToken() : null;
        if (!token) throw new Error('Your session has expired. Please sign in again.');
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const response = await fetch(`${API_BASE}/api/download-ticket/${encodeURIComponent(pnr)}`, { headers });
        if (!response.ok) {
            let detail = 'Ticket download failed.';
            try { detail = (await response.json()).detail || detail; } catch (_) {}
            throw new Error(detail);
        }
        const file = await response.blob();
        const url = URL.createObjectURL(file);
        const link = document.createElement('a');
        link.href = url;
        link.download = `ERS_Ticket_${pnr}.pdf`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        // Give the browser/IDM time to start the download before releasing the blob URL.
        setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (error) {
        console.error('Ticket download failed:', error);
        // Avoid a disruptive browser alert for transient download-manager errors.
        if (error.message && !/Failed to fetch/i.test(error.message)) {
            alert(error.message);
        }
    }
}

async function renderTicketCard(pnr, containerEl) {
    if (!containerEl) return;
    let d = null;
    try {
        const token = window.railbotAccessToken ? await window.railbotAccessToken() : null;
        const res = await fetch(`${API_BASE}/api/pnr-details/${pnr}`, {
            headers: token ? { Authorization: `Bearer ${token}` } : {}
        });
        if (!res.ok) return; // Do NOT render dummy card if PNR is invalid or deleted!
        const json = await res.json();
        if (json.data) {
            d = json.data;
        }
    } catch(e) {
        return;
    }

    if (!d) return;

    let rawStatus = (d.current_status || d.booking_status || 'CONFIRMED').toUpperCase();
    if (rawStatus === 'CNF') rawStatus = 'CONFIRMED';

    const html = `
        <div class="mt-4 bg-surface-container-lowest border border-secondary-container/30 rounded-2xl shadow-xl overflow-hidden relative max-w-xl">
            <div class="absolute inset-x-0 top-0 h-1.5 bg-gradient-to-r from-primary-container via-secondary-container to-primary-container opacity-70"></div>
            <div class="p-md">
                <div class="flex justify-between items-center mb-md bg-surface-container-low/50 p-4 -m-md rounded-t-2xl border-b border-surface-variant">
                    <div class="flex items-center gap-sm">
                        <div class="w-8 h-8 rounded-lg bg-primary-container flex items-center justify-center shrink-0">
                            <span class="material-symbols-outlined text-white text-[20px]">confirmation_number</span>
                        </div>
                        <div class="flex flex-col">
                            <h3 class="font-headline-md text-title-lg text-on-surface tracking-tight">PNR: ${d.pnr || pnr}</h3>
                            <p class="font-label-md text-label-md text-on-surface-variant/70">Passenger: ${d.passenger_name || 'Passenger'}</p>
                        </div>
                    </div>
                    <span class="bg-[#e6f4ea] text-[#137333] font-label-md text-[10px] px-3 py-1 rounded-full border border-[#ceead6] shadow-sm uppercase tracking-widest font-bold">${rawStatus}</span>
                </div>
                <div class="space-y-md mt-md">
                    <div class="bg-surface-container-low/30 p-md rounded-xl border border-surface-variant/50">
                        <div class="mb-md">
                            <p class="font-label-md text-[11px] text-on-surface-variant/70 uppercase tracking-wider mb-1">Train Details</p>
                            <p class="font-title-lg text-body-lg font-bold text-on-surface">${d.train_name || 'Express'} - <span class="text-secondary">${d.train_number || ''}</span></p>
                        </div>
                        <div class="flex items-center justify-between">
                            <div class="text-center">
                                <span class="block font-headline-md text-headline-md text-on-surface">${d.source || 'HWH'}</span>
                                <span class="flex items-center justify-center gap-xs text-[10px] text-on-surface-variant mt-1" title="Route map is not available yet">
                                    <span class="material-symbols-outlined text-[14px]">map</span>
                                    View Map
                                </span>
                                <span class="block font-label-md text-[11px] text-on-surface-variant/60">${d.source_name || d.source || ''}</span>
                            </div>
                            <div class="flex-1 flex flex-col items-center px-4 relative">
                                <div class="w-full h-px bg-outline-variant/40 absolute top-1/2 -translate-y-1/2"></div>
                                <div class="relative bg-surface-container-lowest px-3 py-1 rounded-full border border-surface-variant shadow-sm">
                                    <span class="material-symbols-outlined text-secondary text-[18px]">train</span>
                                </div>
                            </div>
                            <div class="text-center">
                                <span class="block font-headline-md text-headline-md text-on-surface">${d.destination || 'NDLS'}</span>
                                <span class="block font-label-md text-[11px] text-on-surface-variant/60">${d.destination_name || d.destination || ''}</span>
                            </div>
                        </div>
                        <div class="mt-4 pt-3 border-t border-surface-variant/30">
                            <p class="font-label-md text-[11px] text-on-surface-variant/70 uppercase tracking-wider mb-1">Boarding Info</p>
                            <p class="font-body-sm text-body-sm text-on-surface flex items-start gap-1">
                                <span class="material-symbols-outlined text-secondary text-[16px]">info</span>
                                Arrive 30 mins early. Check platform boards for final gate.
                            </p>
                        </div>
                    </div>
                    <div class="flex items-center gap-md bg-secondary-fixed/10 p-md rounded-xl border border-secondary-container/20">
                        <div class="w-12 h-12 rounded-xl bg-secondary-container/20 flex items-center justify-center shrink-0">
                            <span class="material-symbols-outlined text-secondary text-[24px]">airline_seat_recline_normal</span>
                        </div>
                        <div class="flex-1">
                            <p class="font-label-md text-[10px] uppercase tracking-widest text-on-secondary-fixed/60 mb-0.5">Seat Allocation</p>
                            <p class="font-body-md text-body-md text-on-surface">
                                Coach <strong class="text-secondary">${d.coach || 'B1'}</strong> • Seat <strong class="text-secondary">${d.seat || '42'}</strong>
                                <span class="text-body-sm text-on-surface-variant/70 ml-1">(${d.berth_type || 'Lower Berth'})</span>
                            </p>
                        </div>
                    </div>
                    <div class="pt-2 flex justify-end">
                        <a class="inline-flex items-center gap-xs bg-primary-container text-white hover:bg-secondary-container hover:text-on-secondary-container font-label-md text-label-md transition-all group px-4 py-2 rounded-lg shadow-sm active:scale-95 cursor-pointer" href="#" onclick="downloadTicket(event, '${d.pnr || pnr}')">
                            <span class="material-symbols-outlined text-[18px] group-hover:-translate-y-0.5 transition-transform">download</span>
                            <span>Download Ticket</span>
                        </a>
                    </div>
                </div>
            </div>
        </div>
    `;
    containerEl.innerHTML = html;
    scrollToBottom();
}

async function typeWriterAgentBubble(fullText) {
    const div = document.createElement('div');
    div.className = 'flex items-start gap-sm mt-4';
    
    const pnrMatch = fullText.match(/\b\d{10}\b/);

    div.innerHTML = `
        <div class="w-8 h-8 rounded-full shrink-0 flex items-center justify-center border-secondary-container/50 overflow-hidden"><img alt="RailBot AI" class="w-full h-full object-cover" src="assets/logo-of-AI.png"/></div>
        <div class="flex-1 space-y-3 max-w-[90%] lg:max-w-[75%]">
            <div class="bg-surface-container-lowest border border-surface-variant px-4 py-3 rounded-2xl rounded-tl-none shadow-sm inline-block">
                <p class="font-body-md text-body-md text-on-surface text-content"></p>
            </div>
            <div class="ticket-container"></div>
        </div>
    `;

    const textEl = div.querySelector('.text-content');
    const ticketContainer = div.querySelector('.ticket-container');

    const anchor = getAnchor();
    chatContainer.insertBefore(div, anchor);

    const words = fullText.split(' ');
    let currentText = '';

    for (let i = 0; i < words.length; i++) {
        currentText += (i === 0 ? '' : ' ') + words[i];
        textEl.innerHTML = formatMessageText(currentText) + '<span class="inline-block w-1.5 h-4 bg-secondary ml-1 animate-pulse align-middle"></span>';
        scrollToBottom();
        await new Promise(r => setTimeout(r, Math.max(10, Math.min(25, 600 / words.length))));
    }

    textEl.innerHTML = formatMessageText(fullText);

    if (pnrMatch) {
        renderTicketCard(pnrMatch[0], ticketContainer);
    }
    scrollToBottom();
}

function createApprovalCard(reason, instruction) {
    const cardId = 'approval-' + Date.now();
    const div = document.createElement('div');
    div.className = 'flex items-start gap-sm mt-4';
    div.innerHTML = `
        <div class="w-8 h-8 rounded-full shrink-0 flex items-center justify-center border-secondary-container/50 overflow-hidden"><img alt="RailBot AI" class="w-full h-full object-cover" src="assets/logo-of-AI.png"/></div>
        <div class="flex-1 max-w-[90%] lg:max-w-[70%]">
            <div id="${cardId}" class="bg-surface-container-lowest border border-secondary-container/50 rounded-2xl shadow-md overflow-hidden relative">
                <div class="p-md">
                    <div class="flex items-center gap-2 mb-4">
                        <span class="material-symbols-outlined text-secondary">pending_actions</span>
                        <h4 class="font-title-lg text-title-lg text-on-surface font-bold">Action Requires Approval</h4>
                    </div>
                    <div class="space-y-4 mb-6">
                        <div>
                            <p class="font-label-md text-[11px] text-on-surface-variant/70 uppercase tracking-wider mb-1 font-semibold">Reason</p>
                            <p class="font-body-md text-body-md text-on-surface">${escapeHtml(reason)}</p>
                        </div>
                        <div>
                            <p class="font-label-md text-[11px] text-on-surface-variant/70 uppercase tracking-wider mb-1 font-semibold">Instructions</p>
                            <p class="font-body-md text-body-md text-on-surface">${escapeHtml(instruction)}</p>
                        </div>
                    </div>
                    <div class="flex items-center justify-end gap-sm">
                        <button class="approval-btn px-4 py-2 rounded-lg border border-outline text-on-surface hover:bg-surface-variant transition-colors font-label-md text-label-md cursor-pointer" data-approved="false" data-card-id="${cardId}">
                            Reject
                        </button>
                        <button class="approval-btn px-4 py-2 rounded-lg bg-secondary-container text-on-secondary-container hover:bg-secondary-fixed-dim transition-colors font-label-md text-label-md shadow-sm font-semibold cursor-pointer" data-approved="true" data-card-id="${cardId}">
                            Approve
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    return div;
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function quickAction(btn) {
    chatInput.value = btn.textContent.trim();
    chatForm.dispatchEvent(new Event('submit'));
}

function quickActionText(text) {
    chatInput.value = text;
    if (text.endsWith(' ')) {
        chatInput.focus();
    } else {
        chatForm.dispatchEvent(new Event('submit'));
    }
}

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    saveSession(threadId, message);

    const welcomeScreen = document.getElementById('welcome-screen');
    const hasDateDivider = chatContainer.querySelector('.date-divider');
    if (welcomeScreen) welcomeScreen.remove();

    const anchor = getAnchor();
    if (!hasDateDivider) {
        chatContainer.insertBefore(createDateDivider(), anchor);
    }

    chatContainer.insertBefore(createUserBubble(message), anchor);
    chatInput.value = '';
    scrollToBottom();

    chatInput.disabled = true;
    sendBtn.disabled = true;
    sendIcon.textContent = 'hourglass_empty';
    const thinkingBubble = createThinkingBubble();
    chatContainer.insertBefore(thinkingBubble, anchor);
    scrollToBottom();

    try {
        const res = await fetch(`${API_BASE}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, thread_id: threadId, client_id: clientId })
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'The assistant could not process this request.');
        }
        
        thinkingBubble.remove();
        
        if (data.status === "success") {
            await typeWriterAgentBubble(data.agent_response);
        } else if (data.status === "requires_approval") {
            chatContainer.insertBefore(createApprovalCard(data.interrupt_data?.reason || '', data.interrupt_data?.instruction || ''), anchor);
            scrollToBottom();
        }
    } catch (err) {
        thinkingBubble.remove();
        await typeWriterAgentBubble(`Sorry, I could not complete that request: ${err.message || 'server connection failed.'}`);
    } finally {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        sendIcon.textContent = 'send';
        scrollToBottom();
        chatInput.focus();
    }
});

document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.approval-btn');
    if (!btn) return;

    const cardId = btn.getAttribute('data-card-id');
    const approved = btn.getAttribute('data-approved') === 'true';
    const cardEl = document.getElementById(cardId);
    if (!cardEl) return;

    const buttons = cardEl.querySelectorAll('.approval-btn');
    buttons.forEach(b => {
        b.disabled = true;
        b.classList.add('opacity-50', 'cursor-not-allowed');
    });

    try {
        const res = await fetch(`${API_BASE}/api/approve-complaint`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ thread_id: threadId, approved, client_id: clientId })
        });

        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned status ${res.status}`);
        }

        const data = await res.json();

        const statusText = approved ? '✅ Complaint Approved' : '❌ Complaint Rejected';
        const statusColor = approved ? 'bg-[#e6f4ea] text-[#137333] border-[#ceead6]' : 'bg-red-50 text-red-700 border-red-200';
        cardEl.innerHTML = `
            <div class="p-md text-center">
                <span class="inline-flex items-center gap-2 px-4 py-2 rounded-full ${statusColor} border font-label-md text-label-md font-bold">${statusText}</span>
            </div>
        `;

        const responseText = data.agent_response || (approved ? "Complaint has been filed successfully." : "Complaint filing was rejected.");
        await typeWriterAgentBubble(responseText);
    } catch (err) {
        console.error("HIL Approval Error:", err);
        const errDiv = document.createElement('div');
        errDiv.className = 'mt-2 text-error font-body-sm text-center font-semibold';
        errDiv.textContent = 'Failed to submit decision: ' + (err.message || 'Server connection failed');
        cardEl.querySelector('.p-md').appendChild(errDiv);
        buttons.forEach(b => {
            b.disabled = false;
            b.classList.remove('opacity-50', 'cursor-not-allowed');
        });
    }
});

// Initialize the history list, but always begin on a blank new conversation.
document.addEventListener('DOMContentLoaded', async () => {
    await migrateLegacyChatsForCurrentAccount();
    await renderRecentHistorySidebar();
});
