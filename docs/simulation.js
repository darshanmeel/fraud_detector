mermaid.initialize({ startOnLoad: true, flowchart: { useMaxWidth: true, htmlLabels: true } });

let blockedCount = 0;
const logContainer = document.getElementById('log-container');
const statBlocked = document.getElementById('stat-blocked');
const statLatency = document.getElementById('stat-latency');
const historyBody = document.getElementById('history-body');

function addLog(message, type = 'normal') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type === 'block' ? 'log-block' : type === 'review' ? 'log-review' : ''}`;
    const timestamp = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="text-gray-500">[${timestamp}]</span> ${message}`;
    logContainer.prepend(entry);
    
    if (logContainer.children.length > 50) {
        logContainer.removeChild(logContainer.lastChild);
    }
}

function addHistoryRow(id, amount, decision, reason) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-gray-50 transition-colors';
    const decisionBadge = decision === 'BLOCK' 
        ? '<span class="px-2 py-1 bg-red-100 text-red-700 rounded-full font-semibold">BLOCK</span>' 
        : decision === 'REVIEW' 
        ? '<span class="px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full font-semibold">REVIEW</span>' 
        : '<span class="px-2 py-1 bg-green-100 text-green-700 rounded-full font-semibold">ALLOW</span>';
    
    row.innerHTML = `
        <td class="px-3 py-3 font-mono text-[10px] text-gray-400">${id}</td>
        <td class="px-3 py-3 font-medium text-gray-700">€${(amount/100).toFixed(2)}</td>
        <td class="px-3 py-3">${decisionBadge}</td>
        <td class="px-3 py-3 text-gray-500 italic">${reason}</td>
    `;
    historyBody.prepend(row);
    if (historyBody.children.length > 10) {
        historyBody.removeChild(historyBody.lastChild);
    }
}

async function triggerScenario(type) {
    let amount = 5000; // €50
    let velocity = 1;
    let decision = 'ALLOW';
    let risk = 0.1;
    let reason = "Normal behavioral pattern.";
    
    if (type === 'velocity') {
        velocity = 21;
        decision = 'BLOCK';
        risk = 0.95;
        reason = "Velocity Alert: 21 transactions in 1 minute detected.";
    } else if (type === 'spike') {
        amount = 500000; // €5000
        decision = 'REVIEW';
        risk = 0.65;
        reason = "Amount Spike: Transaction exceeds profile threshold.";
    }

    const txId = Math.random().toString(36).substring(7).toUpperCase();
    
    // Step 1: User -> Bus
    addLog(`<b>New Event:</b> ID=${txId}, User trigger transaction...`);
    highlightNode('USER');
    await sleep(600);
    
    // Step 2: Bus -> Processor
    highlightNode('BUS');
    await sleep(600);
    
    // Step 3: Processor -> Feast
    addLog(`<b>Behavioral Lookup:</b> Account profile retrieval (txn_count=${velocity})`);
    highlightNode('BRAIN');
    highlightNode('KITCHEN');
    await sleep(800);
    
    // Step 4: Inference
    const latency = Math.floor(Math.random() * 15) + 5;
    addLog(`<b>Scoring:</b> ONNX Runtime (Champion v1), Score=${risk}, Latency=${latency}ms`);
    statLatency.innerText = `${latency}ms`;
    highlightNode('JUDGE');
    await sleep(600);
    
    // Step 5: Decision Result
    if (decision === 'BLOCK') {
        blockedCount++;
        statBlocked.innerText = blockedCount;
        addLog(`🛑 <b>DECISION: BLOCK</b> - ${reason}`, 'block');
        highlightNode('NO');
    } else if (decision === 'REVIEW') {
        addLog(`🔍 <b>DECISION: REVIEW</b> - ${reason}`, 'review');
        highlightNode('QM');
    } else {
        addLog(`✅ <b>DECISION: ALLOW</b> - ${reason}`);
        highlightNode('OK');
    }

    addHistoryRow(txId, amount, decision, reason);
}

function highlightNode(nodeId) {
    const svg = document.querySelector('.mermaid svg');
    if (!svg) return;

    // Use a more aggressive selector to find the node container
    // Mermaid nodes usually have IDs like 'flowchart-USER-xxx' or similar
    const nodes = svg.querySelectorAll('.node');
    nodes.forEach(node => {
        // Check if the node's text or ID matches our identifier
        const nodeLabel = node.querySelector('.nodeLabel') || node;
        if (nodeLabel.textContent.includes(nodeId) || node.id.includes(nodeId)) {
            const rect = node.querySelector('rect') || node.querySelector('circle') || node.querySelector('polygon') || node.querySelector('path');
            if (rect) {
                // Force a very visible highlight
                rect.classList.add('active-node');
                const originalFill = rect.style.fill;
                const originalStroke = rect.style.stroke;
                
                rect.style.fill = '#86efac'; // Green-300
                rect.style.stroke = '#16a34a'; // Green-600
                rect.style.strokeWidth = '5px';

                setTimeout(() => {
                    rect.style.fill = originalFill;
                    rect.style.stroke = originalStroke;
                    rect.style.strokeWidth = '2px';
                    rect.classList.remove('active-node');
                }, 1000);
            }
        }
    });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Auto-run one transaction on load to show user it works
window.addEventListener('load', () => {
    setTimeout(() => triggerScenario('normal'), 2000);
});
