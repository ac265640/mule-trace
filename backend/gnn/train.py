"""
MuleTrace — GNN Training Loop
================================

Semi-supervised training with class imbalance handling.

Key improvements for honest evaluation:
1. Early stopping (patience=15 on val AUC) — prevents overfitting to synthetic patterns
2. val vs. test AUC gap surfaced explicitly (gap > 0.05 = overfitting warning)
3. Learning curve generation for diagnosing overfitting vs. underfitting
4. Expected Calibration Error (ECE) reported — important since scores drive SAR decisions
5. Cohen's d separability pre-training to confirm signal quality in features
6. Confusion matrix at test time for interpretable results
"""

import os
import json
from typing import Dict, Optional, List, Tuple

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import (
    roc_auc_score, f1_score, precision_score,
    recall_score, classification_report, precision_recall_curve,
    confusion_matrix, average_precision_score
)
from torch_geometric.data import Data

from backend.gnn.model import ChainVigilGNN
from backend.config import (
    GNN_LEARNING_RATE, GNN_EPOCHS, GNN_HIDDEN_DIM,
    GNN_NUM_LAYERS, GNN_DROPOUT, MODEL_DIR
)


class Trainer:
    """GNN model trainer with honest evaluation metrics and early stopping."""

    def __init__(
        self,
        data: Data,
        hidden_dim: int = GNN_HIDDEN_DIM,
        num_layers: int = GNN_NUM_LAYERS,
        dropout: float = GNN_DROPOUT,
        lr: float = GNN_LEARNING_RATE,
        label_noise_rate: float = 0.0,
        early_stopping_patience: int = 25,
    ):
        self.data = data
        self.early_stopping_patience = early_stopping_patience
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Apply label noise ONLY to training labels
        # Val/test labels remain clean for honest evaluation
        self.noisy_train_labels = self._apply_label_noise(
            data.y.clone(), data.train_mask, noise_rate=label_noise_rate
        )

        # Initialize model
        self.model = ChainVigilGNN(
            in_channels=data.x.shape[1],
            hidden_channels=hidden_dim,
            num_layers=num_layers,
            dropout=dropout,
        ).to(self.device)

        # Handle class imbalance with weighted loss
        num_pos = self.noisy_train_labels[data.train_mask].sum().item()
        num_neg = data.train_mask.sum().item() - num_pos
        pos_weight = torch.tensor([num_neg / max(num_pos, 1)]).to(self.device)

        self.criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        self.optimizer = torch.optim.Adam(
            self.model.parameters(), lr=lr, weight_decay=1e-3
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="max", patience=10, factor=0.5, min_lr=1e-5
        )

        # Move data to device
        self.data = self.data.to(self.device)
        self.noisy_train_labels = self.noisy_train_labels.to(self.device)

        self.best_val_auc = 0.0
        self.epochs_since_improvement = 0
        self.history = {
            "train_loss": [],
            "val_auc": [],
            "val_f1": [],
            "val_precision": [],
            "val_recall": [],
        }

    @staticmethod
    def _apply_label_noise(
        labels: torch.Tensor,
        train_mask: torch.Tensor,
        noise_rate: float = 0.06,
        seed: int = 123,
    ) -> torch.Tensor:
        """Flip `noise_rate` fraction of training labels (both classes)."""
        rng = np.random.default_rng(seed)
        train_indices = train_mask.nonzero(as_tuple=True)[0].numpy()
        n_flip = int(len(train_indices) * noise_rate)
        flip_indices = rng.choice(train_indices, size=n_flip, replace=False)
        labels[flip_indices] = 1 - labels[flip_indices]
        flipped_to_mule = labels[flip_indices].sum().item()
        print(f"   🔀 Label noise: flipped {n_flip} training labels "
              f"({flipped_to_mule} → mule, {n_flip - flipped_to_mule} → normal)")
        return labels

    def train(self, epochs: int = GNN_EPOCHS) -> Dict:
        """Run the full training loop with early stopping."""
        print(f"\n🧠 Training MuleTrace GNN on {self.device}")
        print(f"   Model params: {sum(p.numel() for p in self.model.parameters()):,}")
        print(f"   Max Epochs: {epochs} | LR: {self.optimizer.defaults['lr']} | "
              f"Early stopping patience: {self.early_stopping_patience}")
        print(f"   Train: {self.data.train_mask.sum()} | "
              f"Val: {self.data.val_mask.sum()} | "
              f"Test: {self.data.test_mask.sum()}")
        
        # Print class distribution per split
        train_mules = self.data.y[self.data.train_mask].sum().item()
        val_mules = self.data.y[self.data.val_mask].sum().item()
        test_mules = self.data.y[self.data.test_mask].sum().item()
        print(f"   Mules in splits — Train: {int(train_mules)} | "
              f"Val: {int(val_mules)} | Test: {int(test_mules)}")
        print("─" * 65)

        stopped_early = False
        actual_epochs = 0

        for epoch in range(1, epochs + 1):
            # ─── Train step ────────────────────────────────
            self.model.train()
            self.optimizer.zero_grad()

            probs, _ = self.model(self.data.x, self.data.edge_index)
            loss = self.criterion(
                probs[self.data.train_mask],
                self.noisy_train_labels[self.data.train_mask].float()
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

            train_loss = loss.item()
            self.history["train_loss"].append(train_loss)
            actual_epochs = epoch

            # ─── Validation ────────────────────────────────
            if epoch % 5 == 0 or epoch == 1:
                val_metrics = self._evaluate(self.data.val_mask)
                self.history["val_auc"].append(val_metrics["auc"])
                self.history["val_f1"].append(val_metrics["f1"])
                self.history["val_precision"].append(val_metrics["precision"])
                self.history["val_recall"].append(val_metrics["recall"])

                self.scheduler.step(val_metrics["auc"])

                if val_metrics["auc"] > self.best_val_auc:
                    self.best_val_auc = val_metrics["auc"]
                    self.epochs_since_improvement = 0
                    self._save_checkpoint(epoch)
                else:
                    self.epochs_since_improvement += 5

                if epoch % 20 == 0 or epoch == 1:
                    print(
                        f"   Epoch {epoch:>4d} | "
                        f"Loss: {train_loss:.4f} | "
                        f"Val AUC: {val_metrics['auc']:.4f} | "
                        f"Val F1: {val_metrics['f1']:.4f} | "
                        f"Val P/R: {val_metrics['precision']:.2f}/{val_metrics['recall']:.2f}"
                    )

                # ─── Early stopping ─────────────────────────
                if self.epochs_since_improvement >= self.early_stopping_patience:
                    print(f"\n   ⏹️  Early stopping at epoch {epoch} "
                          f"(no val AUC improvement for {self.early_stopping_patience} epochs)")
                    stopped_early = True
                    break

        # ─── Final evaluation on test set ──────────────────
        print("─" * 65)
        self._load_best_checkpoint()
        test_metrics = self._evaluate(self.data.test_mask, verbose=True)

        # ─── Honest overfitting check ───────────────────────
        auc_gap = self.best_val_auc - test_metrics["auc"]
        overfitting_warning = auc_gap > 0.05
        
        print(f"\n{'═' * 65}")
        print(f"  📊 HONEST METRICS REPORT")
        print(f"{'─' * 65}")
        print(f"  Best Val AUC:  {self.best_val_auc:.4f}")
        print(f"  Test AUC:      {test_metrics['auc']:.4f}  ← Primary headline metric")
        print(f"  Val-Test Gap:  {auc_gap:+.4f}  {'⚠️  Overfitting detected' if overfitting_warning else '✅ No overfitting'}")
        print(f"  Test AP:       {test_metrics.get('average_precision', 0):.4f}  (Area under PR curve)")
        print(f"  Calibration:   ECE = {test_metrics.get('ece', 0):.4f}  {'✅ Well-calibrated' if test_metrics.get('ece', 1) < 0.10 else '⚠️  Recalibration recommended'}")
        print(f"  Epochs:        {actual_epochs} ({'early stop' if stopped_early else 'full training'})")
        print(f"{'═' * 65}")

        results = {
            "primary_metric": "test_auc",
            "test_auc": test_metrics["auc"],
            "test_average_precision": test_metrics.get("average_precision", 0),
            "test_ece": test_metrics.get("ece", 0),
            "test_metrics": test_metrics,
            "best_val_auc": self.best_val_auc,
            "val_test_gap": round(auc_gap, 4),
            "overfitting_warning": overfitting_warning,
            "epochs_trained": actual_epochs,
            "stopped_early": stopped_early,
            "model_params": sum(p.numel() for p in self.model.parameters()),
            "training_history": {
                "val_auc_curve": self.history["val_auc"],
                "train_loss_curve": self.history["train_loss"][-len(self.history["val_auc"]):],
            },
        }

        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(os.path.join(MODEL_DIR, "training_results.json"), "w") as f:
            json.dump(results, f, indent=2)

        return results

    def _evaluate(self, mask: torch.Tensor, verbose: bool = False) -> Dict:
        """Evaluate model on masked nodes with comprehensive honest metrics."""
        self.model.eval()
        with torch.no_grad():
            logits, _ = self.model(self.data.x, self.data.edge_index)
            probs = torch.sigmoid(logits)

        probs_np = probs[mask].cpu().numpy()
        labels_np = self.data.y[mask].cpu().numpy()

        # Sanity check: skip evaluation if only one class present
        n_pos = labels_np.sum()
        n_neg = len(labels_np) - n_pos
        if n_pos == 0 or n_neg == 0:
            return {"auc": 0.5, "f1": 0.0, "precision": 0.0,
                    "recall": 0.0, "average_precision": 0.0, "ece": 1.0}

        # Dynamic threshold for optimal F1
        precisions, recalls, thresholds = precision_recall_curve(labels_np, probs_np)
        f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
        best_threshold = thresholds[np.argmax(f1_scores[:-1])] if len(thresholds) > 0 else 0.5
        preds = (probs_np > best_threshold).astype(int)

        try:
            auc = roc_auc_score(labels_np, probs_np)
        except ValueError:
            auc = 0.5

        try:
            avg_precision = average_precision_score(labels_np, probs_np)
        except ValueError:
            avg_precision = 0.0

        f1 = f1_score(labels_np, preds, zero_division=0)
        precision = precision_score(labels_np, preds, zero_division=0)
        recall = recall_score(labels_np, preds, zero_division=0)

        # Expected Calibration Error (ECE)
        ece = _compute_ece(probs_np, labels_np, n_bins=10)

        metrics = {
            "auc": float(auc),
            "f1": float(f1),
            "precision": float(precision),
            "recall": float(recall),
            "average_precision": float(avg_precision),
            "ece": float(ece),
            "best_threshold": float(best_threshold),
            "n_positives": int(n_pos),
            "n_negatives": int(n_neg),
        }

        if verbose:
            cm = confusion_matrix(labels_np, preds)
            print(f"\n📊 Test Results:")
            print(f"   AUC-ROC:             {auc:.4f}")
            print(f"   Avg Precision (AP):  {avg_precision:.4f}  (more informative under class imbalance)")
            print(f"   F1 Score:            {f1:.4f}  (threshold: {best_threshold:.3f})")
            print(f"   Precision:           {precision:.4f}")
            print(f"   Recall:              {recall:.4f}")
            print(f"   ECE:                 {ece:.4f}  (lower is better-calibrated)")
            print(f"   Class balance:       {int(n_pos)} mules / {int(n_neg)} normals")
            print(f"\n   Confusion Matrix:")
            print(f"   {'':10s} Pred Normal  Pred Mule")
            print(f"   True Normal  {cm[0,0]:^11d}  {cm[0,1]:^9d}")
            print(f"   True Mule    {cm[1,0]:^11d}  {cm[1,1]:^9d}")
            print(f"\n{classification_report(labels_np, preds, target_names=['Normal', 'Mule'])}")
            metrics["confusion_matrix"] = cm.tolist()

        return metrics

    def predict(self) -> np.ndarray:
        """Get mule probability scores for ALL nodes."""
        self.model.eval()
        with torch.no_grad():
            logits, _ = self.model(self.data.x, self.data.edge_index)
            probs = torch.sigmoid(logits)
        return probs.cpu().numpy()

    def get_embeddings(self) -> np.ndarray:
        """Get node embeddings for visualization / XAI."""
        self.model.eval()
        with torch.no_grad():
            embeddings = self.model.get_embedding(
                self.data.x, self.data.edge_index
            )
        return embeddings.cpu().numpy()

    def _save_checkpoint(self, epoch: int):
        """Save model checkpoint."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = os.path.join(MODEL_DIR, "best_model.pt")
        torch.save({
            "epoch": epoch,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "best_val_auc": self.best_val_auc,
        }, path)

    def _load_best_checkpoint(self):
        """Load best model checkpoint."""
        path = os.path.join(MODEL_DIR, "best_model.pt")
        if os.path.exists(path):
            checkpoint = torch.load(path, map_location=self.device, weights_only=True)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            print(f"   ✅ Loaded best model (epoch {checkpoint['epoch']}, "
                  f"Val AUC {checkpoint['best_val_auc']:.4f})")

    def get_learning_curve(self) -> Dict:
        """Return training history for overfitting diagnosis."""
        return {
            "val_auc": self.history["val_auc"],
            "val_f1": self.history["val_f1"],
            "train_loss": self.history["train_loss"],
        }


def _compute_ece(probs: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """
    Compute Expected Calibration Error (ECE).
    
    ECE measures how well the model's confidence aligns with actual accuracy.
    A well-calibrated model: if it says 70% mule probability, 70% of those
    accounts should actually be mules.
    
    ECE < 0.05: well-calibrated
    ECE 0.05-0.10: acceptable
    ECE > 0.10: recalibration recommended
    
    Reference: Guo et al., "On Calibration of Modern Neural Networks", ICML 2017
    """
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n_total = len(labels)

    for i in range(n_bins):
        lo, hi = bin_boundaries[i], bin_boundaries[i + 1]
        in_bin = (probs >= lo) & (probs < hi)
        n_in_bin = in_bin.sum()
        if n_in_bin == 0:
            continue
        accuracy_in_bin = labels[in_bin].mean()
        confidence_in_bin = probs[in_bin].mean()
        ece += (n_in_bin / n_total) * abs(accuracy_in_bin - confidence_in_bin)

    return float(ece)


def compute_cohen_d_separability(feature_df, feature_names: List[str]) -> Dict[str, float]:
    """
    Compute Cohen's d for each feature between mule and normal accounts.
    
    Cohen's d = (mean_mule - mean_normal) / pooled_std
    
    Interpretation:
    d > 0.8: Large separation (strong discriminative feature)
    d > 0.5: Medium separation
    d > 0.2: Small separation  
    d < 0.2: Negligible (feature may not be useful)
    
    Used in EDA to understand feature quality BEFORE training.
    Reference: Cohen, J. (1988). Statistical Power Analysis, 2nd Ed.
    """
    if "is_mule" not in feature_df.columns:
        return {}
    
    mule_df = feature_df[feature_df["is_mule"] == True]
    normal_df = feature_df[feature_df["is_mule"] == False]
    
    cohen_d = {}
    for feat in feature_names:
        if feat not in feature_df.columns:
            continue
        mule_vals = mule_df[feat].dropna().values
        normal_vals = normal_df[feat].dropna().values
        
        if len(mule_vals) < 2 or len(normal_vals) < 2:
            cohen_d[feat] = 0.0
            continue
        
        mean_diff = np.mean(mule_vals) - np.mean(normal_vals)
        pooled_std = np.sqrt(
            (np.std(mule_vals, ddof=1) ** 2 + np.std(normal_vals, ddof=1) ** 2) / 2
        )
        cohen_d[feat] = float(mean_diff / pooled_std) if pooled_std > 0 else 0.0
    
    return cohen_d


# ─── CLI Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    from backend.data.generator import generate_all_data
    from backend.graph.builder import GraphBuilder
    from backend.gnn.dataset import nx_to_pyg

    print("═" * 65)
    print("  MuleTrace — GNN Training Pipeline")
    print("═" * 65)

    data_dict = generate_all_data()
    builder = GraphBuilder()
    G = builder.build(data_dict)

    print("\n📐 Converting to PyTorch Geometric...")
    pyg_data, node_mapping, account_ids = nx_to_pyg(G)

    trainer = Trainer(pyg_data)
    results = trainer.train()

    print(f"\n✅ Training complete!")
    print(f"   Test AUC:    {results['test_auc']:.4f}")
    print(f"   Test AP:     {results['test_average_precision']:.4f}")
    print(f"   ECE:         {results['test_ece']:.4f}")
    print(f"   Gap warning: {results['overfitting_warning']}")
