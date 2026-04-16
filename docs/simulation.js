mermaid.initialize({ startOnLoad: true, flowchart: { useMaxWidth: true, htmlLabels: true } });

let blockedCount = 0;

function getElements() {
    return {
        logContainer: document.getElementById('log-container'),
        statBlocked: document.getElementById('stat-blocked'),
        statLatency: document.getElementById('stat-latency'),
        historyBody: document.getElementById('history-body')
    };
}

function addLog(message, type = 'normal') {
    const { logContainer } = getElements();
    const entry = document.createElement('div');
    entry.className = `log-entry ${type === 'block' ? 'log-block' : type === 'review' ? 'log-review' : ''}`;
    const timestamp = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="text-gray-500">[${timestamp}]</span> ${message}`;
    logContainer.prepend(entry);
    if (logContainer.children.length > 50) logContainer.removeChild(logContainer.lastChild);
}

function addHistoryRow(id, amount, decision, reason) {
    const { historyBody } = getElements();
    if (!historyBody) return;
    
    const row = document.createElement('tr');
    row.className = 'hover:bg-gray-50 transition-all duration-500 bg-blue-50'; // Start with blue highlight
    
    const decisionBadge = decision === 'BLOCK' 
        ? '<span class="px-2 py-1 bg-red-100 text-red-700 rounded-full font-bold">BLOCK</span>' 
        : decision === 'REVIEW' 
        ? '<span class="px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full font-bold">REVIEW</span>' 
        : '<span class="px-2 py-1 bg-green-100 text-green-700 rounded-full font-bold">APPROVE</span>';
    
    row.innerHTML = `
        <td class="px-3 py-3 font-mono text-[10px] text-gray-400">${id}</td>
        <td class="px-3 py-3 font-bold text-gray-700 text-sm">€${(amount/100).toFixed(2)}</td>
        <td class="px-3 py-3">${decisionBadge}</td>
        <td class="px-3 py-3 text-gray-600 text-xs">${reason}</td>
    `;
    
    historyBody.prepend(row);
    
    // Remove blue highlight after a second
    setTimeout(() => {
        row.classList.remove('bg-blue-50');
    }, 2000);

    if (historyBody.children.length > 10) {
        historyBody.removeChild(historyBody.lastChild);
    }
}

async function triggerScenario(type) {
    const { statBlocked, statLatency } = getElements();
    
    let amount = 5000; // €50
    let velocity = 1;
    let decision = 'ALLOW';
    let risk = 0.1;
    let reason = "Normal behavioral pattern.";
    
    if (type === 'velocity') {
        velocity = 21;
        decision = 'BLOCK';
        risk = 0.95;
        reason = "User had 20 txn/min; 21st triggered BLOCK.";
    } else if (type === 'spike') {
        amount = 500000; // €5000
        decision = 'REVIEW';
        risk = 0.65;
        reason = "€5,000 exceeds user profile threshold.";
    }

    const txId = "TXN-" + Math.random().toString(36).substring(7).toUpperCase();
    
    // STEP 1: TRANSACTION INBOUND
    addLog(`<b>[INBOUND]</b> ${txId} for €${(amount/100).toFixed(2)} detected.`);
    highlightNode('USER');
    await sleep(1000); // SLOW
    
    // STEP 2: BUS (REDPANDA)
    addLog(`<b>[BUS]</b> Event routed to Kafka/Redpanda topic: <code>tx.raw.hot</code>`);
    highlightNode('BUS');
    await sleep(1000);
    
    // STEP 3: FRAUD PROCESSOR START
    addLog(`<b>[PROCESSOR]</b> Faust agent consuming event...`);
    highlightNode('BRAIN');
    await sleep(800);
    
    // STEP 4: PULL HISTORY (FEAST)
    addLog(`<b>[FEAST]</b> Pulling online features: <code>txn_count_1m</code> = ${velocity}`);
    highlightNode('KITCHEN');
    await sleep(1200);
    
    // STEP 5: DRIFT CHECK
    addLog(`<b>[DRIFT]</b> Comparing against global distribution... No drift.`);
    highlightNode('DRIFT');
    await sleep(1000);
    
    // STEP 6: MODEL PREDICTION (ONNX)
    const latency = Math.floor(Math.random() * 15) + 5;
    addLog(`<b>[ONNX]</b> Running Champion Model. Inference Score = ${risk}`);
    statLatency.innerText = `${latency}ms`;
    highlightNode('JUDGE');
    await sleep(1000);
    
    // STEP 7: FINAL DECISION
    if (decision === 'BLOCK') {
        blockedCount++;
        statBlocked.innerText = blockedCount;
        addLog(`🛑 <b>RESULT: BLOCK</b> - ${reason}`, 'block');
        highlightNode('NO');
    } else if (decision === 'REVIEW') {
        addLog(`🔍 <b>RESULT: REVIEW</b> - ${reason}`, 'review');
        highlightNode('QM');
    } else {
        addLog(`✅ <b>RESULT: APPROVE</b> - ${reason}`);
        highlightNode('OK');
    }

    // STEP 8: UPDATE TABLE
    addHistoryRow(txId, amount, decision, reason);
}

function highlightNode(nodeId) {
    const svg = document.querySelector('.mermaid svg');
    if (!svg) return;

    // Use a more robust selector that works with Mermaid's idiosyncratic naming
    const nodes = svg.querySelectorAll('.node');
    nodes.forEach(node => {
        const text = node.textContent || "";
        const id = node.id || "";
        
        // Match our node identifiers
        const isMatch = (nodeId === 'USER' && (text.includes('User') || id.includes('USER'))) ||
                        (nodeId === 'BUS' && (text.includes('Redpanda') || id.includes('BUS'))) ||
                        (nodeId === 'BRAIN' && (text.includes('Processor') || id.includes('BRAIN'))) ||
                        (nodeId === 'KITCHEN' && (text.includes('Feast') || id.includes('KITCHEN'))) ||
                        (nodeId === 'DRIFT' && (text.includes('Monitor') || id.includes('DRIFT'))) ||
                        (nodeId === 'JUDGE' && (text.includes('Decision') || id.includes('JUDGE'))) ||
                        (nodeId === 'OK' && (text.includes('Approved') || id.includes('OK'))) ||
                        (nodeId === 'NO' && (text.includes('Blocked') || id.includes('NO'))) ||
                        (nodeId === 'QM' && (text.includes('Review') || id.includes('QM')));

        if (isMatch) {
            const shape = node.querySelector('rect, circle, polygon, path, ellipse');
            if (shape) {
                // Save original styles
                const originalFill = shape.style.fill;
                const originalStroke = shape.style.stroke;
                const originalWidth = shape.style.strokeWidth;

                // Apply highlight
                shape.style.transition = 'all 0.4s ease';
                shape.style.fill = '#4ade80'; // Bright Green
                shape.style.stroke = '#166534';
                shape.style.strokeWidth = '8px';

                setTimeout(() => {
                    shape.style.fill = originalFill;
                    shape.style.stroke = originalStroke;
                    shape.style.strokeWidth = originalWidth;
                }, 1500);
            }
        }
    });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Ensure the page is fully loaded before starting
window.addEventListener('load', () => {
    console.log("Simulator Loaded.");
    // Wait for Mermaid to finish rendering
    setTimeout(() => {
        triggerScenario('normal');
    }, 2500);
});
