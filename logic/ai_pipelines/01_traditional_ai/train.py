import os
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import time

# --- CONFIGURATION ---
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
TARGET_BUILDING = 'Bull_lodging_Melissa'
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'model.pth')
EPOCHS = 50
BATCH_SIZE = 64
LEARNING_RATE = 0.01

# --- 1. MODEL DEFINITION ---
class EnergyPredictor(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1) # Output: Target building consumption
        )
        
    def forward(self, x):
        return self.net(x)

def load_and_preprocess_data():
    """Loads CSVs, merges on timestamp, and prepares tensors."""
    print("[1/4] Loading Datasets...")
    path_e = os.path.join(DATA_DIR, "electricity.csv")
    path_w = os.path.join(DATA_DIR, "weather.csv")
    
    if not os.path.exists(path_e) or not os.path.exists(path_w):
        print("Error: Missing CSV files in data directory.")
        return None, None
        
    df_e = pd.read_csv(path_e)
    df_w = pd.read_csv(path_w)
    
    # Preprocess
    df_e['timestamp'] = pd.to_datetime(df_e['timestamp'])
    df_w['timestamp'] = pd.to_datetime(df_w['timestamp'])
    
    # Sort for merge_asof
    df_e = df_e.sort_values('timestamp')
    df_w = df_w.sort_values('timestamp')

    # Since weather might be per site, we just take the first site's weather to simplify for educational purposes
    df_w_site_0 = df_w[df_w['site_id'] == 0].copy()
    
    # Merge data
    df = pd.merge_asof(df_e, df_w_site_0, on='timestamp', tolerance=pd.Timedelta('2 hours'), direction='nearest')
    df = df.dropna(subset=[TARGET_BUILDING, 'airTemperature', 'windSpeed'])
    
    # Feature Engineering
    df['hour'] = df['timestamp'].dt.hour
    
    # PREVENT DATA LEAKAGE: ONLY USE THE FIRST 50% OF THE DATASET FOR TRAINING
    half_idx = int(len(df) * 0.5)
    df_training_half = df.iloc[:half_idx]
    
    # X and y
    X = df_training_half[['airTemperature', 'windSpeed', 'hour']].values
    y = df_training_half[[TARGET_BUILDING]].values
    
    tensor_X = torch.tensor(X, dtype=torch.float32)
    tensor_y = torch.tensor(y, dtype=torch.float32)
    
    # Simple Train/Test split of that 50% historical data (80/20)
    split_idx = int(len(tensor_X) * 0.8)
    train_data = TensorDataset(tensor_X[:split_idx], tensor_y[:split_idx])
    val_data = TensorDataset(tensor_X[split_idx:], tensor_y[split_idx:])
    
    return train_data, val_data

def train_model():
    print("=== TRADITIONAL AI PIPELINE: TRAINING PHASE ===")
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device selected: {device}")
    
    train_data, val_data = load_and_preprocess_data()
    if not train_data: return
    
    train_loader = DataLoader(train_data, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_data, batch_size=BATCH_SIZE, shuffle=False)
    
    model = EnergyPredictor().to(device)
    criterion = nn.L1Loss() # Mean Absolute Error (MAE) for readability in units
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
            print(f"Epoch {epoch+1:03d}/{EPOCHS} | Train MAE: {train_loss:.2f} kWh | Val MAE: {val_loss:.2f} kWh")
            
    print(f"[3/4] Training completed in {time.time() - start_time:.2f}s")
    
    # Save Model
    print(f"[4/4] Saving model to {MODEL_PATH}")
    torch.save(model.state_dict(), MODEL_PATH)
    
if __name__ == "__main__":
    train_model()
