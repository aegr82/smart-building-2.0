import os
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import time

# --- CONFIGURATION ---
try:
    from app.config import DATA_DIR
except ImportError:
    DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data')
TARGET_BUILDING = 'Eagle_office_Marisela' # We use Eagle because it has both huge CW and electricity to prove the point
EPOCHS = 50
BATCH_SIZE = 64
LEARNING_RATE = 0.01

# --- 1. MODEL DEFINITION ---
class EnergyPredictor(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(4, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1) # Output: Target building consumption
        )
        
    def forward(self, x):
        return self.net(x)

def load_and_preprocess_data(target_csv: str):
    """Loads a specific CSV, merges on timestamp with weather, and prepares tensors."""
    print(f"[1/4] Loading Dataset: {target_csv}...")
    path_target = os.path.join(DATA_DIR, target_csv)
    path_w = os.path.join(DATA_DIR, "weather.csv")
    
    if not os.path.exists(path_target) or not os.path.exists(path_w):
        print(f"Error: Missing CSV files for {target_csv}.")
        return None, None
        
    df_t = pd.read_csv(path_target)
    df_w = pd.read_csv(path_w)
    
    # Preprocess
    df_t['timestamp'] = pd.to_datetime(df_t['timestamp'])
    df_w['timestamp'] = pd.to_datetime(df_w['timestamp'])
    
    # Sort for merge_asof
    df_t = df_t.sort_values('timestamp')
    df_w = df_w.sort_values('timestamp')

    # Get Site ID from metadata or fallback to 0 (For simplicity, we know Eagle is Site 2, but we'll lookup if possible)
    try:
        df_m = pd.read_csv(os.path.join(DATA_DIR, "metadata.csv"))
        site_id = df_m[df_m['building_id'] == TARGET_BUILDING]['site_id'].iloc[0]
    except:
        site_id = 0

    df_w_site = df_w[df_w['site_id'] == site_id].copy()
    
    # Merge data
    df = pd.merge_asof(df_t, df_w_site, on='timestamp', tolerance=pd.Timedelta('2 hours'), direction='nearest')
    
    # If the building has no data in this CSV, return None
    if TARGET_BUILDING not in df.columns:
        print(f"Building {TARGET_BUILDING} not found in {target_csv}")
        return None, None

    df = df.dropna(subset=[TARGET_BUILDING, 'airTemperature', 'dewTemperature', 'windSpeed'])
    
    # Feature Engineering
    df['hour'] = df['timestamp'].dt.hour
    
    # PREVENT DATA LEAKAGE: ONLY USE THE FIRST 50% OF THE DATASET FOR TRAINING
    half_idx = int(len(df) * 0.5)
    df_training_half = df.iloc[:half_idx]
    
    # X and y: Purely independent variables to prevent Circular Inference Deadlock
    X = df_training_half[['airTemperature', 'dewTemperature', 'windSpeed', 'hour']].values
    y = df_training_half[[TARGET_BUILDING]].values
    
    tensor_X = torch.tensor(X, dtype=torch.float32)
    tensor_y = torch.tensor(y, dtype=torch.float32)
    
    # Simple Train/Test split of that 50% historical data (80/20)
    split_idx = int(len(tensor_X) * 0.8)
    train_data = TensorDataset(tensor_X[:split_idx], tensor_y[:split_idx])
    val_data = TensorDataset(tensor_X[split_idx:], tensor_y[split_idx:])
    
    return train_data, val_data

def train_model(target_csv: str, model_filename: str):
    print(f"\n--- Training Model for {target_csv} ---")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    train_data, val_data = load_and_preprocess_data(target_csv)
    if not train_data: return None
    
    train_loader = DataLoader(train_data, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=BATCH_SIZE, shuffle=False)
    
    model = EnergyPredictor().to(device)
    criterion = nn.L1Loss() # Mean Absolute Error (MAE)
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    print(f"[2/4] Started training for {EPOCHS} epochs...")
    start_time = time.time()
    
    for epoch in range(EPOCHS):
        model.train()
        train_loss = 0.0
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            predictions = model(batch_X)
            loss = criterion(predictions, batch_y)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * batch_X.size(0)
            
        train_loss /= len(train_loader.dataset)
        
        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                predictions = model(batch_X)
                loss = criterion(predictions, batch_y)
                val_loss += loss.item() * batch_X.size(0)
        val_loss /= len(val_loader.dataset)
        
        if (epoch+1) % 10 == 0:
            print(f"Epoch {epoch+1:03d}/{EPOCHS} | Train MAE: {train_loss:.2f} | Val MAE: {val_loss:.2f}")
    
    duration = time.time() - start_time
    print(f"[3/4] Training completed in {duration:.2f}s")
    
    # Save Model
    model_path = os.path.join(os.path.dirname(__file__), model_filename)
    print(f"[4/4] Saving model to {model_path}")
    torch.save(model.state_dict(), model_path)
    
    return {
        "train_mae": round(train_loss, 4),
        "val_mae": round(val_loss, 4),
        "duration_s": round(duration, 2),
        "epochs": EPOCHS,
        "train_samples": len(train_data),
        "val_samples": len(val_data)
    }

if __name__ == "__main__":
    print("=== TRADITIONAL AI PIPELINE: DUAL TRAINING PHASE ===")
    train_model("electricity.csv", "model_elec.pth")
    train_model("chilledwater.csv", "model_cw.pth")
