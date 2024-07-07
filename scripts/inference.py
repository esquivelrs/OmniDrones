import logging
import os
import time

import hydra
import torch
import numpy as np
import pandas as pd
import wandb
import matplotlib.pyplot as plt

from tqdm import tqdm
from omegaconf import OmegaConf

from omni_drones import init_simulation_app
from torchrl.data import CompositeSpec
from torchrl.envs.utils import set_exploration_type, ExplorationType
from omni_drones.utils.torchrl import SyncDataCollector
from omni_drones.utils.torchrl.transforms import (
    FromMultiDiscreteAction, 
    FromDiscreteAction,
    ravel_composite,
    VelController,
    AttitudeController,
    RateController,
    History
)
from omni_drones.utils.wandb import init_wandb
from omni_drones.utils.torchrl import RenderCallback, EpisodeStats
from omni_drones.learning import ALGOS

from setproctitle import setproctitle
from torchrl.envs.transforms import TransformedEnv, InitTracker, Compose

@hydra.main(config_path=os.path.dirname(__file__), config_name="train")
def inference(cfg):
    OmegaConf.register_new_resolver("eval", eval)
    OmegaConf.resolve(cfg)
    OmegaConf.set_struct(cfg, False)

    print(OmegaConf.to_yaml(cfg))
    simulation_app = init_simulation_app(cfg)

    from omni_drones.envs.isaac_env import IsaacEnv
    # # Initialize the simulation app
    # simulation_app = init_simulation_app(cfg)
    
    # # Create the environment
    env_class = IsaacEnv.REGISTRY[cfg.task.name]
    base_env = env_class(cfg, headless=True)
    # env = TransformedEnv(base_env, Compose())  # You may need to add relevant transforms here
    
    # # Create the policy
    # policy = ALGOS[cfg.algo.name.lower()](
    #     cfg.algo, 
    #     env.observation_spec, 
    #     env.action_spec, 
    #     env.reward_spec, 
    #     device=base_env.device
    # )
    
    # # Load the trained model
    # ckpt_path = os.path.join(cfg.wandb.dir, "checkpoint_final.pt")
    # policy.load_state_dict(torch.load(ckpt_path))
    # policy.eval()
    
    # # Generate a random observation
    # random_obs = env.observation_spec.rand()
    
    # # Perform inference
    # with torch.no_grad():
    #     action = policy(random_obs)
    
    # print("Random observation:", random_obs)
    # print("Model output (action):", action)
    
    # simulation_app.close()

if __name__ == "__main__":
    inference()