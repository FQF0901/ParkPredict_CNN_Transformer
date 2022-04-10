import torch
from torchvision import transforms
from torch.utils.data import DataLoader
from torch import nn
import matplotlib.pyplot as plt
import os
from datetime import datetime
import random
import numpy as np

from functools import partial
from ray import tune
from ray.tune import CLIReporter
from ray.tune.schedulers import ASHAScheduler
from sympy import divisors
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm


from parksim.trajectory_predict.intent_transformer.dataset import IntentTransformerDataset
from parksim.trajectory_predict.intent_transformer.network import TrajectoryPredictorWithIntent
from parksim.intent_predict.cnnV2.pytorchtools import EarlyStopping

_CURRENT = os.path.abspath(os.path.dirname(__file__))


def count_datasize(dataset_nums):

    val_proportion = 0.1
    total_size = 0
    for ds_num in tqdm(dataset_nums):
        dataset = IntentTransformerDataset([ds_num], img_transform=transforms.ToTensor())
        total_size += len(dataset)
    
    val_size = int(val_proportion * total_size)
    train_size = total_size - val_size

    return train_size, train_size, total_size



RUN_LABEL = 'v1'
if __name__ == '__main__':
    dataset_nums = dataset_nums = ["../data/DJI_" + str(i).zfill(4) for i in range(7, 23)]
    train_size, val_size, total_size = count_datasize(dataset_nums=dataset_nums)
    print(f"Train Size: {train_size}\nValidation Size: {val_size}\nTotal Size: {total_size}")

 