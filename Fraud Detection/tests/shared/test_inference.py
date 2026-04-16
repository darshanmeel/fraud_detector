from services.shared.inference import HeuristicModel

def test_heuristic_velocity_burst():
    model = HeuristicModel()
    assert model.predict({'txn_count_1m': 15}) == 0.9

def test_heuristic_normal():
    model = HeuristicModel()
    assert model.predict({'txn_count_1m': 2}) == 0.1
