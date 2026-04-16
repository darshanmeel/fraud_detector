mermaid.initialize({ startOnLoad: true });

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

function addHistoryRow(id, amount, action, decision, reason) {
    const row = document.createElement('tr');
    const decisionColor = decision === 'BLOCK' ? 'text-red-600 font-semibold' : decision === 'REVIEW' ? 'text-yellow-600 font-semibold' : 'text-green-600 font-semibold';
    
    row.innerHTML = `
        <td class="px-4 py-3 font-mono text-xs text-gray-500">${id}</td>
        <td class="px-4 py-3">$${(amount/100).toFixed(2)}</td>
        <td class="px-4 py-3">${action}</td>
        <td class="px-4 py-3 ${decisionColor}">${decision}</td>
        <td class="px-4 py-3 text-gray-600">${reason}</td>
    `;
    historyBody.prepend(row);
}

async function triggerScenario(type) {
    let amount = 5000; // $50
    let velocity = 1;
    let decision = 'ALLOW';
    let risk = 0.1;
    let action = "Bought Coffee";
    let reason = "Normal behavioral pattern.";
    
    if (type === 'velocity') {
        velocity = 21;
        decision = 'BLOCK';
        risk = 0.95;
        action = "Scripted transactions";
        reason = "User had 20 transactions in 1 minute; 21st triggered velocity block.";
    } else if (type === 'spike') {
        amount = 500000; // $5000
        decision = 'REVIEW';
        risk = 0.65;
        action = "Bought Rolex";
        reason = "Unusually large amount spike for this account profile.";
    }

    const txId = Math.random().toString(36).substring(7);
    
    // Step 1: User -> Redpanda
    addLog(`<b>Transaction Created:</b> ID=${txId}, User Action="${action}"`);
    animateNode('U');
    await sleep(600);
    
    // Step 2: Redpanda -> Processor
    animateNode('B');
    await sleep(600);
    
    // Step 3: Processor -> Feast
    addLog(`<b>Hydrating Features:</b> txn_count_1m=${velocity}`);
    animateNode('P');
    animateNode('F');
    await sleep(800);
    
    // Step 4: Inference
    const latency = Math.floor(Math.random() * 15) + 5;
    addLog(`<b>ML Inference:</b> ONNX Runtime, Score=${risk}, Latency=${latency}ms`);
    statLatency.innerText = `${latency}ms`;
    await sleep(600);
    
    // Step 5: Decision
    animateNode('D');
    await sleep(400);

    if (decision === 'BLOCK') {
        blockedCount++;
        statBlocked.innerText = blockedCount;
        addLog(`🛑 <b>DECISION: BLOCK</b> - ${reason}`, 'block');
        animateNode('R');
    } else if (decision === 'REVIEW') {
        addLog(`🔍 <b>DECISION: REVIEW</b> - ${reason}`, 'review');
        animateNode('M');
    } else {
        addLog(`✅ <b>DECISION: ALLOW</b> - ${reason}`);
        animateNode('A');
    }

    addHistoryRow(txId, amount, action, decision, reason);
}

function animateNode(id) {
    const svg = document.querySelector('.mermaid svg');
    if (!svg) return;
    
    // Mermaid uses specific ID patterns like "flowchart-U-..."
    // We search for elements that contain the letter in their text content or ID
    const nodes = svg.querySelectorAll('g.node');
    nodes.forEach(node => {
        const textElement = node.querySelector('span.nodeLabel') || node.querySelector('div') || node;
        const nodeText = textElement.textContent || "";
        
        // Match specific node identifiers from the Mermaid graph definition
        const isMatch = (id === 'U' && nodeText.includes('User')) ||
                        (id === 'B' && nodeText.includes('Redpanda')) ||
                        (id === 'P' && nodeText.includes('Processor')) ||
                        (id === 'F' && nodeText.includes('Feast')) ||
                        (id === 'D' && nodeText.includes('Decision')) ||
                        (id === 'A' && nodeText.includes('✅')) ||
                        (id === 'R' && nodeText.includes('🛑')) ||
                        (id === 'M' && nodeText.includes('🔍'));

        if (isMatch) {
            // Apply a stronger highlight
            const rect = node.querySelector('rect') || node.querySelector('polygon') || node.querySelector('path');
            if (rect) {
                const originalFill = rect.style.fill;
                const originalStroke = rect.style.stroke;
                const originalStrokeWidth = rect.style.strokeWidth;

                rect.style.transition = 'all 0.3s ease';
                rect.style.fill = '#4ade80';
                rect.style.stroke = '#166534';
                rect.style.strokeWidth = '4px';

                setTimeout(() => {
                    rect.style.fill = originalFill;
                    rect.style.stroke = originalStroke;
                    rect.style.strokeWidth = originalStrokeWidth;
                }, 1000);
            }
        }
    });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
