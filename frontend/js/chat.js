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
    let formatted = escapeHtml(text).replace(/\\n/g, '<br>');
    formatted = formatted.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="text-secondary font-semibold hover:underline inline-flex items-center gap-1">$1 <span class="material-symbols-outlined text-[14px]">open_in_new</span></a>');
    return formatted;
}

async function typeWriterAgentBubble(fullText) {
    const div = document.createElement('div');
    div.className = 'flex items-start gap-sm mt-4';
    
    const pnrMatch = fullText.match(/\\b\\d{10}\\b/);

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
        await renderTicketCard(pnrMatch[0], ticketContainer);
    }
    scrollToBottom();
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
            body: JSON.stringify({ message, thread_id: threadId })
        });
        const data = await res.json();
        
        thinkingBubble.remove();
        
        if (data.status === "success") {
            await typeWriterAgentBubble(data.agent_response);
        } else if (data.status === "requires_approval") {
            chatContainer.insertBefore(createApprovalCard(data.interrupt_data?.reason || '', data.interrupt_data?.instruction || ''), anchor);
            scrollToBottom();
        }
    } catch (err) {
        thinkingBubble.remove();
        chatContainer.insertBefore(createUserBubble("Error: Failed to connect to server."), anchor);
    } finally {
        chatInput.disabled = false;
        sendBtn.disabled = false;
        sendIcon.textContent = 'send';
        scrollToBottom();
        chatInput.focus();
    }
});
