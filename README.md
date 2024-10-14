
# Changes:

New Task: `Gate/GateFlyThrough`

Consists on flying from a random initialized point `A` to point `B` pasing trougth a manhole, describe by the USD in "omni_drones/usd/manhole.usd"


```
    The drone is rewarded for flying through the gate and penalized for crashing.
    Observations:
        - Relative position to the target gate
        - Drone state
        - Obstacle position realtive to the drone (optional)
        - Time
        - Image from the camera (optional)
    Actions:
        - Drone actions
    Reward:
        - Reward for flying through the gate
        - Reward for staying upright
        - Reward for not spinning
        - Reward for effort
        - Penalty for collision
```

## Docker container

Modify the wandb key in `docker/Dockerfile` line 136:
```
ENV WANDB_API_KEY=<insert your wandb key>
```
To run the container:

```
cd docker
docker compose build
docker compose up
```
In a new terminal:

```
docker exec -it docker-isaacomnidrone-1 bash
```

To train a task use:
```
cd ./scrips
python train.py headless=false task=Gate/GateFlyThrough wandb.entity=dtu-projects eval_interval=200
```

With camera the number of parallel environments must be limited with ` task.env.num_envs=8` 


To play the model:
```
python play.py task=Hover algo=ppo headless=false task.env.num_envs=1 task.drone_model=crazyflie task.action_transform=rate algo.checkpoint_path=<path_to _model>.pt
```

For Sim2Real go to: `sim2real_omnidrones/README.md`

# Original Readme
![Visualization of OmniDrones](docs/source/_static/visualization.jpg)

---

# OmniDrones

[![IsaacSim](https://img.shields.io/badge/Isaac%20Sim-2023.1.0-orange.svg)](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/overview.html)
[![Python](https://img.shields.io/badge/python-3.10-blue.svg)](https://docs.python.org/3/whatsnew/3.7.html)
[![Docs status](https://img.shields.io/badge/docs-passing-brightgreen.svg)](https://omnidrones.readthedocs.io/en/latest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Discord Forum](https://dcbadge.vercel.app/api/server/J4QvXR6tQj)](https://discord.gg/J4QvXR6tQj)


*OmniDrones* is an open-source platform designed for reinforcement learning research on multi-rotor drone systems. Built on [Nvidia Isaac Sim](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/overview.html), *OmniDrones* features highly efficient and flxeible simulation that can be adopted for various research purposes. We also provide a suite of benchmark tasks and algorithm baselines to provide preliminary results for subsequent works.

For usage and more details, please refer to the [documentation](https://omnidrones.readthedocs.io/en/latest/). Unfortunately, it does not support Windows.

Welcome to join our [Discord](https://discord.gg/J4QvXR6tQj) for discussions and questions!

## Notice

The initial release of **OmniDrones** is developed based on Isaac Sim 2022.2.0. It can be found at the [release](https://github.com/btx0424/OmniDrones/tree/release) branch. The current version is developed based on Isaac Sim 2023.1.0. 


## Citation

Please cite [this paper](https://arxiv.org/abs/2309.12825) if you use *OmniDrones* in your work:

```
@misc{xu2023omnidrones,
    title={OmniDrones: An Efficient and Flexible Platform for Reinforcement Learning in Drone Control}, 
    author={Botian Xu and Feng Gao and Chao Yu and Ruize Zhang and Yi Wu and Yu Wang},
    year={2023},
    eprint={2309.12825},
    archivePrefix={arXiv},
    primaryClass={cs.RO}
}
```


## Ackowledgement

Some of the abstractions and implementation was heavily inspired by [Isaac Orbit](https://github.com/NVIDIA-Omniverse/Orbit).

