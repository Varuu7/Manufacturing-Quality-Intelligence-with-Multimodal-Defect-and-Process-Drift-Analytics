"""
PyTorch Dataset and DataLoaders for Multimodal Manufacturing Data
Handles paired tabular sensor vectors and optical defect inspection images.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import torch
from torch.utils.data import Dataset, DataLoader
import random
import numpy as np
import pandas as pd
from PIL import Image

def transform_image(img: Image.Image, is_train: bool = False) -> torch.Tensor:
    """
    Transforms PIL grayscale image to PyTorch normalized tensor (1, 64, 64) without torchvision dependency.
    """
    if is_train:
        if random.random() > 0.5:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if random.random() > 0.5:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            
    arr = np.array(img, dtype=np.float32) / 255.0
    # Normalize with mean=0.5, std=0.5 -> [-1.0, 1.0]
    arr = (arr - 0.5) / 0.5
    tensor = torch.tensor(arr, dtype=torch.float32).unsqueeze(0) # (1, H, W)
    return tensor


class ManufacturingMultimodalDataset(Dataset):
    def __init__(self, csv_file: str, preprocessor_path: str, images_dir: str = "data/raw/images", is_train: bool = False):
        self.df = pd.read_csv(csv_file)
        self.images_dir = images_dir
        
        # Load preprocessor
        from src.data.preprocessor import ManufacturingPreprocessor
        self.preprocessor = ManufacturingPreprocessor.load(preprocessor_path)
        self.X_tabular, _ = self.preprocessor.transform(self.df)
        self.y = self.df["defect_label"].values.astype(np.int64)
        self.image_files = self.df["image_filename"].values
        
        self.is_train = is_train
            
    def __len__(self):
        return len(self.df)
        
    def __getitem__(self, idx):
        # 1. Tabular features
        x_tab = torch.tensor(self.X_tabular[idx], dtype=torch.float32)
        
        # 2. Image scan
        img_name = self.image_files[idx]
        img_path = os.path.join(self.images_dir, img_name)
        if os.path.exists(img_path):
            img = Image.open(img_path).convert('L')
        else:
            img = Image.fromarray(np.full((64, 64), 175, dtype=np.uint8), mode='L')
            
        x_img = transform_image(img, is_train=self.is_train)
        
        # 3. Label
        label = torch.tensor(self.y[idx], dtype=torch.long)
        
        return x_tab, x_img, label


def get_dataloaders(
    train_csv: str = "data/processed/train.csv",
    val_csv: str = "data/processed/val.csv",
    test_csv: str = "data/processed/test.csv",
    preprocessor_path: str = "data/processed/preprocessor.joblib",
    images_dir: str = "data/raw/images",
    batch_size: int = 32
):
    train_ds = ManufacturingMultimodalDataset(train_csv, preprocessor_path, images_dir, is_train=True)
    val_ds = ManufacturingMultimodalDataset(val_csv, preprocessor_path, images_dir, is_train=False)
    test_ds = ManufacturingMultimodalDataset(test_csv, preprocessor_path, images_dir, is_train=False)
    
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)
    
    return train_loader, val_loader, test_loader
