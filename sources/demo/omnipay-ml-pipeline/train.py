"""Training script using Hydra configuration."""

import os
import numpy as np
import torch
import torch.nn as nn
from omegaconf import OmegaConf


def load_config():
    """Load configuration using Hydra defaults."""
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.yaml")
    if os.path.exists(config_path):
        config = OmegaConf.load(config_path)
    else:
        config = OmegaConf.create({})
    return config


def generate_synthetic_data(n_samples=1000):
    """Generate synthetic transaction data for training."""
    np.random.seed(42)
    X = np.random.randn(n_samples, 4)
    y = (X[:, 0] * 0.5 + X[:, 1] * 0.3 + np.random.randn(n_samples) * 0.2 > 0).astype(float)
    return X, y


class Trainer:
    """Simple trainer for the risk model."""

    def __init__(self, config):
        self.config = config
        self.model = nn.Sequential(
            nn.Linear(4, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

    def train(self, X, y, epochs=10):
        """Train the model."""
        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.float32).unsqueeze(1)

        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        criterion = nn.BCELoss()

        for epoch in range(epochs):
            optimizer.zero_grad()
            predictions = self.model(X_tensor)
            loss = criterion(predictions, y_tensor)
            loss.backward()
            optimizer.step()
            print(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}")

    def save(self, path):
        """Save the model."""
        torch.save(self.model.state_dict(), path)
        print(f"Model saved to {path}")


def main():
    """Main training entry point."""
    print("Loading configuration...")
    config = load_config()

    training_config = config.get("training", {})
    epochs = training_config.get("epochs", 10)

    print(f"Training config: {training_config}")

    print("\nGenerating synthetic training data...")
    X, y = generate_synthetic_data(n_samples=1000)

    print(f"Training model for {epochs} epochs...")
    trainer = Trainer(config)
    trainer.train(X, y, epochs=epochs)

    model_path = os.path.join(os.path.dirname(__file__), "model.pt")
    trainer.save(model_path)

    print("\nTraining complete!")


if __name__ == "__main__":
    main()
