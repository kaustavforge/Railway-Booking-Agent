async function renderTicketCard(pnr, containerEl) {
    if (!containerEl) return;
    let d = null;
    try {
        const res = await fetch(`${API_BASE}/api/pnr-details/${pnr}`);
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
                            <h3 class="font-headline-md text-title-lg text-on-surface tracking-tight">PNR: \${d.pnr || pnr}</h3>
                            <p class="font-label-md text-label-md text-on-surface-variant/70">Passenger: \${d.passenger_name || 'Passenger'}</p>
                        </div>
                    </div>
                    <span class="bg-[#e6f4ea] text-[#137333] font-label-md text-[10px] px-3 py-1 rounded-full border border-[#ceead6] shadow-sm uppercase tracking-widest font-bold">\${rawStatus}</span>
                </div>
                <div class="space-y-md mt-md">
                    <div class="bg-surface-container-low/30 p-md rounded-xl border border-surface-variant/50">
                        <div class="mb-md">
                            <p class="font-label-md text-[11px] text-on-surface-variant/70 uppercase tracking-wider mb-1">Train Details</p>
                            <p class="font-title-lg text-body-lg font-bold text-on-surface">\${d.train_name || 'Express'} - <span class="text-secondary">\${d.train_number || ''}</span></p>
                        </div>
                        <div class="flex items-center justify-between">
                            <div class="text-center">
                                <span class="block font-headline-md text-headline-md text-on-surface">\${d.source || 'HWH'}</span>
                                <span class="flex items-center justify-center gap-xs text-[10px] text-on-surface-variant mt-1" title="Route map is not available yet">
                                    <span class="material-symbols-outlined text-[14px]">map</span>
                                    View Map
                                </span>
                                <span class="block font-label-md text-[11px] text-on-surface-variant/60">\${d.source_name || d.source || ''}</span>
                            </div>
                            <div class="flex-1 flex flex-col items-center px-4 relative">
                                <div class="w-full h-px bg-outline-variant/40 absolute top-1/2 -translate-y-1/2"></div>
                                <div class="relative bg-surface-container-lowest px-3 py-1 rounded-full border border-surface-variant shadow-sm">
                                    <span class="material-symbols-outlined text-secondary text-[18px]">train</span>
                                </div>
                            </div>
                            <div class="text-center">
                                <span class="block font-headline-md text-headline-md text-on-surface">\${d.destination || 'NDLS'}</span>
                                <span class="block font-label-md text-[11px] text-on-surface-variant/60">\${d.destination_name || d.destination || ''}</span>
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
                                Coach <strong class="text-secondary">\${d.coach || 'B1'}</strong> • Seat <strong class="text-secondary">\${d.seat || '42'}</strong>
                                <span class="text-body-sm text-on-surface-variant/70 ml-1">(\${d.berth_type || 'Lower Berth'})</span>
                            </p>
                        </div>
                    </div>
                    <div class="pt-2 flex justify-end">
                        <a class="inline-flex items-center gap-xs bg-primary-container text-white hover:bg-secondary-container hover:text-on-secondary-container font-label-md text-label-md transition-all group px-4 py-2 rounded-lg shadow-sm active:scale-95 cursor-pointer" href="#" onclick="downloadTicket(event, '\${d.pnr || pnr}')">
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
