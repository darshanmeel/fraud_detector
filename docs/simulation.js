mermaid.initialize({ startOnLoad: true });

let blockedCount = 0;
const logContainer = document.getElementById('log-container');
const statBlocked = document.getElementById('stat-blocked');
const statLatency = document.getElementById('stat-latency');

function addLog(message, type = 'normal') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type === 'block' ? 'log-block' : type === 'review' ? 'log-review' : ''}`;
    const timestamp = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="text-gray-500">[${timestamp}]</span> ${message}`;
    logContainer.prepend(entry);
    
    // Keep logs manageable
    if (logContainer.children.length > 50) {
        logContainer.removeChild(logContainer.lastChild);
    }
}

async function triggerScenario(type) {
    let amount = 5000; // $50
    let velocity = 1;
    let decision = 'ALLOW';
    let risk = 0.1;
    
    if (type === 'velocity') {
        velocity = 51;
        decision = 'BLOCK';
        risk = 0.95;
    } else if (type === 'spike') {
        amount = 500000; // $5000
        decision = 'REVIEW';
        risk = 0.65;
    }

    const txId = Math.random().toString(36).substring(7);
    
    // Phase 1: User -> Redpanda
    addLog(`<b>Transaction Created:</b> ID=${txId}, Amount=$${(amount/100).toFixed(2)}`);
    animateNode('U');
    await sleep(500);
    
    // Phase 2: Redpanda -> Processor
    animateNode('B');
    await sleep(500);
    
    // Phase 3: Processor -> Feast
    addLog(`<b>Hydrating Features:</b> txn_count_1m=${velocity}`);
    animateNode('P');
    animateNode('F');
    await sleep(800);
    
    // Phase 4: Inference
    const latency = Math.floor(Math.random() * 15) + 5;
    addLog(`<b>ML Inference:</b> Champion Model (v1), Score=${risk}, Latency=${latency}ms`);
    statLatency.innerText = `${latency}ms`;
    await sleep(500);
    
    // Phase 5: Decision
    if (decision === 'BLOCK') {
        blockedCount++;
        statBlocked.innerText = blockedCount;
        addLog(`🛑 <b>DECISION: BLOCK</b> - High risk detected!`, 'block');
        animateNode('R');
    } else if (decision === 'REVIEW') {
        addLog(`🔍 <b>DECISION: REVIEW</b> - Manual check required.`, 'review');
        animateNode('M');
    } else {
        addLog(`✅ <b>DECISION: ALLOW</b> - Pass through.`);
        animateNode('A');
    }
}

function animateNode(id) {
    const svg = document.querySelector('.mermaid svg');
    if (!svg) return;
    
    // Find node in Mermaid SVG (selectors vary, this is a best-effort for Mermaid)
    const nodes = svg.querySelectorAll('.node');
    nodes.forEach(node => {
        if (node.id.includes(id) || node.textContent.trim().includes(id)) {
            node.classList.add('active-node');
            setTimeout(() => node.classList.remove('active-node'), 1000);
        }
    });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
