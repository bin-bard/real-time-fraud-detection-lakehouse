import mlflow
from mlflow.tracking import MlflowClient

mlflow.set_tracking_uri("http://localhost:5000")
client = MlflowClient()

print("=== CHECKING MLFLOW MODELS ===\n")

# Check registered models
models = client.search_registered_models()
print(f"Found {len(models)} registered models:")
for model in models:
    print(f"\n📦 Model: {model.name}")
    
    # Get versions
    versions = client.search_model_versions(f"name='{model.name}'")
    print(f"   Versions: {len(versions)}")
    for v in versions:
        print(f"   - Version {v.version}: Stage='{v.current_stage}', Status={v.status}")
        print(f"     Run ID: {v.run_id}")
        print(f"     Source: {v.source}")

print("\n=== EXPERIMENTS ===\n")
experiments = client.search_experiments()
for exp in experiments:
    print(f"- Experiment {exp.experiment_id}: {exp.name}")
    runs = client.search_runs(exp.experiment_id, max_results=3)
    print(f"  Latest runs: {len(runs)}")
    for run in runs[:3]:
        print(f"  - Run {run.info.run_id[:8]}: Status={run.info.status}")
