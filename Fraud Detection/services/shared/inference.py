import onnxruntime as ort
import numpy as np

class ONNXInferenceEngine:
    def __init__(self, model_path: str, version: str):
        self.version = version
        try:
            self.session = ort.InferenceSession(model_path)
            self.input_name = self.session.get_inputs()[0].name
        except Exception:
            # For prototype if model is dummy
            self.session = None
            self.input_name = None

    def predict(self, features: dict) -> float:
        # Extract features with defaults to handle None or missing keys
        txn_count = features.get('txn_count_1m', 0)
        if txn_count is None:
            txn_count = 0
            
        amount = features.get('amount_cents', 0)
        if amount is None:
            amount = 0

        if not self.session:
            # Fallback mock for prototype since we have empty .onnx files
            score = 0.1
            if txn_count > 10:
                score = max(score, 0.9)
            if amount > 100000:
                score = max(score, 0.6)
            return score
            
        # Convert dict to numpy array (order must match model training)
        input_data = np.array([[
            float(txn_count),
            float(amount)
        ]], dtype=np.float32)
        
        outputs = self.session.run(None, {self.input_name: input_data})
        return float(outputs[0][0])

    def explain(self, features: dict):
        # Mock SHAP: Return top 3 contributing features
        return sorted(features.items(), key=lambda x: x[1], reverse=True)[:3]

