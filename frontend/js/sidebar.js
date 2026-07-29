function getSavedSessions() {
    try {
        const data = localStorage.getItem('rail_assist_sessions');
        return data ? JSON.parse(data) : [];
    } catch(e) {
        return [];
    }
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
    
    renderRecentHistorySidebar();
}

function renderRecentHistorySidebar() {
    const listEl = document.getElementById('recent-history-list');
    if (!listEl) return;
    
    const sessions = getSavedSessions();
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
    // Close all other open menus first
    document.querySelectorAll('[id^="menu-"]').forEach(m => {
        if (m.id !== `menu-${sessionThreadId}`) m.classList.add('hidden');
    });
    const menu = document.getElementById(`menu-${sessionThreadId}`);
    if (menu) menu.classList.toggle('hidden');
}

function deleteSession(sessionThreadId) {
    let sessions = getSavedSessions();
    sessions = sessions.filter(s => s.threadId !== sessionThreadId);
    try {
        localStorage.setItem('rail_assist_sessions', JSON.stringify(sessions));
    } catch(e) {}
    
    // If the deleted session was the active one, start a new inquiry
    if (sessionThreadId === threadId) {
        startNewInquiry();
    }
    renderRecentHistorySidebar();
}

// Close session menus when clicking outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('[id^="menu-"]') && !e.target.closest('button[onclick^="toggleSessionMenu"]')) {
        document.querySelectorAll('[id^="menu-"]').forEach(m => m.classList.add('hidden'));
    }
});

async function syncSessionsFromBackend() {
    try {
        const res = await fetch(`${API_BASE}/api/sessions`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === 'success' && Array.isArray(data.sessions)) {
            let localSessions = getSavedSessions();
            let changed = false;
            for (const bs of data.sessions) {
                if (!localSessions.some(s => s.threadId === bs.threadId)) {
                    localSessions.push({ threadId: bs.threadId, title: bs.title, timestamp: Date.now() });
                    changed = true;
                }
            }
            if (changed) {
                if (localSessions.length > 20) localSessions = localSessions.slice(0, 20);
                localStorage.setItem('rail_assist_sessions', JSON.stringify(localSessions));
                renderRecentHistorySidebar();
            }
        }
    } catch(e) {}
}

// Auto-sync sessions from backend database when sidebar loads
setTimeout(syncSessionsFromBackend, 1000);

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
        const res = await fetch(`${API_BASE}/api/history/${sThreadId}`);
        thinking.remove();
        if (res.ok) {
            const data = await res.json();
            if (data.messages && Array.isArray(data.messages) && data.messages.length > 0) {
                // Render date/time pill header at the top
                const firstMsg = data.messages[0];
                chatContainer.insertBefore(createDateDivider(firstMsg.timestamp), anchor);

                for (const msg of data.messages) {
                    try {
                        const contentStr = typeof msg?.content === 'string' ? msg.content : JSON.stringify(msg?.content || '');
                        if (!contentStr.trim()) continue;

                        if (msg.role === 'user') {
                            chatContainer.insertBefore(createUserBubble(contentStr), anchor);
                        } else {
                            const pnrMatch = contentStr.match(/\b\d{10}\b/);
                            const bubble = document.createElement('div');
                            bubble.className = 'flex items-start gap-sm mt-4';
                            bubble.innerHTML = `
                                <div class="w-8 h-8 rounded-full shrink-0 flex items-center justify-center border-secondary-container/50 overflow-hidden"><img alt="RailBot AI" class="w-full h-full object-cover" src="assets/logo-of-AI.png"/></div>
                                <div class="flex-1 space-y-3 max-w-[90%] lg:max-w-[75%]">
                                    <div class="bg-surface-container-lowest border border-surface-variant px-4 py-3 rounded-2xl rounded-tl-none shadow-sm inline-block">
                                        <p class="font-body-md text-body-md text-on-surface">${formatMessageText(contentStr)}</p>
                                    </div>
                                    <div class="ticket-container"></div>
                                </div>
                            `;
                            chatContainer.insertBefore(bubble, anchor);
                            if (pnrMatch) {
                                renderTicketCard(pnrMatch[0], bubble.querySelector('.ticket-container'));
                            }
                        }
                    } catch(msgErr) {
                        console.error("Error rendering message:", msgErr);
                    }
                }
                scrollToBottom();
                return;
            } else {
                // Handle session with no completed messages cleanly without blanking screen
                const emptyNotice = document.createElement('div');
                emptyNotice.className = 'flex justify-center my-8';
                emptyNotice.innerHTML = `
                    <div class="bg-surface-container-low px-6 py-4 rounded-2xl border border-surface-variant text-center max-w-md shadow-sm">
                        <span class="material-symbols-outlined text-secondary text-[28px] mb-2">history_toggle_off</span>
                        <h4 class="font-title-md text-title-md text-on-surface mb-1">No Messages Found</h4>
                        <p class="font-body-sm text-body-sm text-on-surface-variant">This conversation session has no completed messages yet. Type in the box below to start chatting in this thread!</p>
                    </div>
                `;
                chatContainer.insertBefore(emptyNotice, anchor);
                scrollToBottom();
                return;
            }
        }
        startNewInquiry();
    } catch(e) {
        thinking.remove();
        startNewInquiry();
    }
}

function startNewInquiry() {
    threadId = "session_" + Math.random().toString(36).substring(2, 9);
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
