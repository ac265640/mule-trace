"""
MuleTrace — Hybrid GraphSAGE + GAT Mule Detection Neural Network
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv, GATConv


class MuleGNN(nn.Module):
    def __init__(self, in_channels: int = 10, hidden_channels: int = 32, num_classes: int = 2):
        super(MuleGNN, self).__init__()
        self.sage1 = SAGEConv(in_channels, hidden_channels)
        self.gat2 = GATConv(hidden_channels, hidden_channels, heads=2, concat=False)
        self.classifier = nn.Linear(hidden_channels, num_classes)
        self.dropout = nn.Dropout(0.3)

    def forward(self, x, edge_index):
        h = self.sage1(x, edge_index)
        h = F.relu(h)
        h = self.dropout(h)

        h = self.gat2(h, edge_index)
        h = F.relu(h)

        out = self.classifier(h)
        return out, h
