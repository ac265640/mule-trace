"""
MuleTrace — PyTorch Geometric GNN Trainer
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import roc_auc_score, f1_score

from backend.config import MODEL_DIR
from backend.gnn.model import MuleGNN


class Trainer:
    def __init__(self, data, lr: float = 0.01, in_channels: int = 10, hidden_channels: int = 32):
        self.data = data
        self.model = MuleGNN(in_channels=in_channels, hidden_channels=hidden_channels)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr, weight_decay=5e-4)

        # Handle class imbalance (mules are minority ~10-15%)
        pos_weight = torch.tensor([3.5])
        self.criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    def train(self, epochs: int = 40):
        self.model.train()
        best_val_auc = 0.0
        history = []

        for epoch in range(1, epochs + 1):
            self.optimizer.zero_grad()
            out, _ = self.model(self.data.x, self.data.edge_index)

            # Compute loss on train mask
            train_logits = out[self.data.train_mask][:, 1] - out[self.data.train_mask][:, 0]
            train_labels = self.data.y[self.data.train_mask].float()

            loss = self.criterion(train_logits, train_labels)
            loss.backward()
            self.optimizer.step()

            # Validation
            self.model.eval()
            with torch.no_grad():
                val_out, _ = self.model(self.data.x, self.data.edge_index)
                val_probs = torch.softmax(val_out[self.data.val_mask], dim=1)[:, 1].numpy()
                val_y = self.data.y[self.data.val_mask].numpy()

                try:
                    val_auc = float(roc_auc_score(val_y, val_probs))
                except ValueError:
                    val_auc = 0.5

            history.append({"epoch": epoch, "loss": float(loss.item()), "val_auc": val_auc})

            if val_auc > best_val_auc:
                best_val_auc = val_auc
                torch.save(self.model.state_dict(), os.path.join(MODEL_DIR, "best_mule_gnn.pt"))

            self.model.train()

        return {
            "epochs": epochs,
            "best_val_auc": best_val_auc,
            "final_loss": history[-1]["loss"] if history else 0.0,
            "history": history
        }
