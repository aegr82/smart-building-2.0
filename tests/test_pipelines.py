import os
import sys
import importlib.util

# Updated Base path to point to 'logic/ai_pipelines' from 'tests/' folder
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logic', 'ai_pipelines')

def load_module(name, rel_path):
    file_path = os.path.join(BASE_DIR, rel_path)
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_traditional_ai():
    print("Testing Traditional AI...")
    try:
        import torch
        train_mod = load_module("train", "01_traditional_ai/train.py")
        model = train_mod.EnergyPredictor()
        # dummy input: [airTemperature, dewTemperature, windSpeed, hour]
        dummy_input = torch.tensor([[15.0, 5.0, 5.0, 10]], dtype=torch.float32)
        output = model(dummy_input)
        assert output is not None, "Model output is None"
        print("✅ Traditional AI Model initialized and forward pass successful.")
    except Exception as e:
        print(f"❌ Traditional AI failed: {e}")
        raise e

def test_agentic_ai():
    print("Testing Agentic AI...")
    try:
        inf_mod = load_module("agent_inference", "03_agentic_ai/inference.py")
        inf_mod.agentic_inference()
        print("✅ Agentic AI inference executed successfully.")
    except Exception as e:
        print(f"❌ Agentic AI failed: {e}")
        raise e

if __name__ == "__main__":
    print(f"Starting simple integration tests for AI Pipelines linking to: {BASE_DIR}\n")
    test_traditional_ai()
    print("\n------------------\n")
    test_agentic_ai()
    print("\n✅ All tests attempted.")
