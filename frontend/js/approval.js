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
            body: JSON.stringify({ thread_id: threadId, approved })
        });

        if (!res.ok) {
            const errJson = await res.json().catch(() => ({}));
            throw new Error(errJson.detail || `Server returned status ${res.status}`);
        }

        const data = await res.json();

        // Replace the approval card with a status badge
        const statusText = approved ? '✅ Complaint Approved' : '❌ Complaint Rejected';
        const statusColor = approved ? 'bg-[#e6f4ea] text-[#137333] border-[#ceead6]' : 'bg-red-50 text-red-700 border-red-200';
        cardEl.innerHTML = `
            <div class="p-md text-center">
                <span class="inline-flex items-center gap-2 px-4 py-2 rounded-full ${statusColor} border font-label-md text-label-md font-bold">${statusText}</span>
            </div>
        `;

        // Show agent response as a typewriter bubble below
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
