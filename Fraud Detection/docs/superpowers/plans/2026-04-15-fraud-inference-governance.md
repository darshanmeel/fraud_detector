# Real-Time Inference & Model Governance (Phase 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate ONNX Runtime for ML inference and implement Champion/Challenger routing in the `fraud-processor`.

**Architecture:** Replacing heuristic logic with `onnxruntime`. The agent scores every transaction using the production model (`champion`) and optionally a shadow model (`challenger`), emitting comparison metrics to Kafka.

**Tech Stack:** Python 3.11, ONNX Runtime (`onnxruntime`), Faust, Redpanda.

---

### Task 1: Shared Models & Model Artifacts

**Files:**
- Modify: `services/shared/models.py`
- Create: `models/champion.onnx` (Dummy model)
- Create: `models/challenger.onnx` (Dummy model)

- [ ] **Step 1: Add Performance Model**
Add `ModelPerformanceEvent` to `services/shared/models.py` to track side-by-side scores.

```python
class ModelPerformanceEvent(faust.Record, serializer='json'):
    transaction_id: str
    champion_score: float
    challenger_score: float
    champion_version: str
    challenger_version: str
```

- [ ] **Step 2: Create Dummy ONNX Models**
For the prototype, create small dummy ONNX models (e.g., using a simple script to export a scikit-learn model). If local generation is hard, use placeholders and provide the `onnx` bytes directly in the task.

- [ ] **Step 3: Commit**
```bash
git add services/shared/models.py models/
git commit -m "feat: add performance models and initial ONNX artifacts"
```

---

### Task 2: Implement ONNX Inference Engine

**Files:**
- Modify: `services/shared/inference.py`

- [ ] **Step 1: Replace HeuristicModel with ONNXInferenceEngine**
Update `services/shared/inference.py` to use `onnxruntime`.

```python
import onnxruntime as ort
import numpy as np

class ONNXInferenceEngine:
    def __init__(self, model_path: str, version: str):
        self.session = ort.InferenceSession(model_path)
        self.version = version
        self.input_name = self.session.get_inputs()[0].name

    def predict(self, features: dict) -> float:
        # Convert dict to numpy array (order must match model training)
        input_data = np.array([[
            features.get('txn_count_1m', 0),
            features.get('amount_cents', 0)
        ]], dtype=np.float32)
        
        outputs = self.session.run(None, {self.input_name: input_data})
        return float(outputs[0][0])
```

- [ ] **Step 2: Commit**
```bash
git add services/shared/inference.py
git commit -m "feat: implement ONNX inference engine"
```

---

### Task 3: Update Fraud Processor with Routing Logic

**Files:**
- Modify: `services/fraud-processor/app.py`

- [ ] **Step 1: Implement Champion/Challenger Routing**
Update the processing loop to handle two models and emit performance events.

```python
# Initialize models
CHAMPION_PATH = os.environ.get('CHAMPION_PATH', '/models/champion.onnx')
CHALLENGER_PATH = os.environ.get('CHALLENGER_PATH', '/models/challenger.onnx')

champion = ONNXInferenceEngine(CHAMPION_PATH, "v1-prod")
challenger = None
if os.path.exists(CHALLENGER_PATH):
    challenger = ONNXInferenceEngine(CHALLENGER_PATH, "v2-shadow")

performance_topic = app.topic('model.performance', value_type=ModelPerformanceEvent)

# Inside process agent:
score = champion.predict(features)
challenger_score = -1.0
if challenger:
    challenger_score = challenger.predict(features)
    await performance_topic.send(value=ModelPerformanceEvent(
        transaction_id=tx.transaction_id,
        champion_score=score,
        challenger_score=challenger_score,
        champion_version=champion.version,
        challenger_version=challenger.version
    ))
```

- [ ] **Step 2: Commit**
```bash
git add services/fraud-processor/app.py
git commit -m "feat: implement champion/challenger routing in fraud-processor"
```

---

### Task 4: Dynamic Model Reloading

**Files:**
- Modify: `services/fraud-processor/app.py`

- [ ] **Step 1: Add File Watcher**
Implement a background task in Faust to check for model file updates.

```python
@app.timer(interval=60.0)
async def reload_models():
    # Check modification time of model files
    # If changed, re-initialize ONNXInferenceEngine
    pass
```

- [ ] **Step 2: Commit**
```bash
git add services/fraud-processor/app.py
git commit -m "feat: add periodic model reload check"
```
