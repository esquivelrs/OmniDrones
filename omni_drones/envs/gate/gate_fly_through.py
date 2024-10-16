# MIT License
# 
# Copyright (c) 2023 Botian Xu, Tsinghua University
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import torch
import torch.distributions as D
from tensordict.tensordict import TensorDict, TensorDictBase
from torchrl.data import (
    UnboundedContinuousTensorSpec, 
    CompositeSpec,
    BinaryDiscreteTensorSpec,
    DiscreteTensorSpec
)

import omni.isaac.core.utils.torch as torch_utils
import omni.isaac.core.utils.prims as prim_utils
import omni.physx.scripts.utils as script_utils
import omni.isaac.core.objects as objects
from omni.isaac.debug_draw import _debug_draw
from torchvision.io import write_video

import omni_drones.utils.kit as kit_utils
from omni_drones.utils.torch import euler_to_quaternion
from omni_drones.envs.isaac_env import AgentSpec, IsaacEnv
from omni_drones.robots.drone import MultirotorBase
from omni_drones.views import RigidPrimView
from omni_drones.sensors.camera import Camera, PinholeCameraCfg
import dataclasses

from ..utils import create_obstacle, create_obstacle_path
from .utils import attach_payload

class GateFlyThrough(IsaacEnv):
    r"""
    The drone is rewarded for flying through the gate and penalized for crashing.
    Observations:
        - Relative position to the target gate
        - Drone state
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
        
    """
    def __init__(self, cfg, headless):
        self.reward_effort_weight = cfg.task.reward_effort_weight
        self.reward_distance_scale = cfg.task.reward_distance_scale
        self.time_encoding = cfg.task.time_encoding
        self.reset_on_collision = cfg.task.reset_on_collision
        self.obstacle_spacing = cfg.task.obstacle_spacing
        self.camera_resolution = cfg.task.camera.resolution
        super().__init__(cfg, headless)

        self.drone.initialize()

        self.obstacles = RigidPrimView(
            "/World/envs/env_*/obstacle_*",
            reset_xform_properties=False,
            shape=[self.num_envs, -1],
            track_contact_forces=True
        )
        self.obstacles.initialize()
        # self.payload = RigidPrimView(
        #     f"/World/envs/env_*/{self.drone.name}_*/payload",
        #     reset_xform_properties=False,
        # )
        # self.payload.initialize()

        self.target_vis = RigidPrimView(
            "/World/envs/env_*/target",
            reset_xform_properties=False
        )
        self.target_vis.initialize()

        self.camera_cfg = PinholeCameraCfg(
            sensor_tick=cfg.task.camera.sensor_tick,
            resolution=tuple(self.camera_resolution),
            data_types=cfg.task.camera.data_types,
            usd_params=PinholeCameraCfg.UsdCameraCfg(
                        focal_length=cfg.task.camera.focal_length,
                        focus_distance=cfg.task.camera.focus_distance,
                        horizontal_aperture=cfg.task.camera.horizontal_aperture,
                        clipping_range=tuple(cfg.task.camera.clipping_range),
                    ),
            )
        # cameras used as sensors
        self.camera_sensor = Camera(self.camera_cfg)

        # # Print all prims in the scene
           

        ## add camera to the environment
        self.camera_sensor.spawn([
            f"/World/envs/env_0/{self.drone.name}_0/base_link/Camera"
        ])



        # # for i in range(self.num_envs):
        # #     prim_path = f"/World/envs/env_{i}/{self.drone.name}_0/base_link/Camera"
        # #     if self.camera_sensor.exists(prim_path):
        # #         self.camera_sensor.delete(prim_path)
        # #     self.camera_sensor.spawn(prim_path)

        self.camera_sensor.initialize(f"/World/envs/env_*/{self.drone.name}_*/base_link/Camera")
        self.frames_sensor = []

        self.init_vels = torch.zeros_like(self.drone.get_velocities())
        self.init_joint_pos = self.drone.get_joint_positions(True)
        self.init_joint_vels = torch.zeros_like(self.drone.get_joint_velocities())
        self.obstacle_pos = self.get_env_poses(self.obstacles.get_world_poses())[0]

        self.init_pos_dist = D.Uniform(
            torch.tensor([-2.5, -1., 0.5], device=self.device),
            torch.tensor([-1.0, 1., 1.2], device=self.device)
        )
        self.init_rpy_dist = D.Uniform(
            torch.tensor([-.1, -.2, -.2], device=self.device) * torch.pi,
            torch.tensor([.2, .2, .2], device=self.device) * torch.pi
        )
        self.obstacle_spacing_dist = D.Uniform(
            torch.tensor(self.obstacle_spacing[0], device=self.device),
            torch.tensor(self.obstacle_spacing[1], device=self.device)
        )
        self.target_pos_dist = D.Uniform(
            torch.tensor([1.3, 0., 0.5], device=self.device),
            torch.tensor([1.5, 0., 1.2], device=self.device)
        )
        # payload_mass_scale = self.cfg.task.payload_mass_scale
        # self.payload_mass_dist = D.Uniform(
        #     torch.as_tensor(payload_mass_scale[0] * self.drone.MASS_0, device=self.device),
        #     torch.as_tensor(payload_mass_scale[1] * self.drone.MASS_0, device=self.device)
        # )

        self.target_pos = torch.zeros(self.num_envs, 3, device=self.device)
        self.alpha = 0.8

        self.draw = _debug_draw.acquire_debug_draw_interface()
        self.payload_traj_vis = []
        self.drone_traj_vis = []

    def _design_scene(self):
        drone_model = MultirotorBase.REGISTRY[self.cfg.task.drone_model]
        cfg = drone_model.cfg_cls()
        self.drone: MultirotorBase = drone_model(cfg=cfg)

        kit_utils.create_ground_plane(
            "/World/defaultGroundPlane",
            static_friction=1.0,
            dynamic_friction=1.0,
            restitution=0.0,
        )
        
        # create_obstacle(
        #     "/World/envs/env_0/obstacle_0", 
        #     prim_type="Capsule",
        #     translation=(0., 0., 1.2),
        #     attributes={"axis": "Y", "radius": 0.04, "height": 5}
        # )

        #omniverse://localhost/Users/isaacsim/gate.usd
        #omniverse://localhost/Users/isaacsim/Collected_manhole_cage/manhole_cage.usd
        #/home/isaacsim/Documents/manhole_cage_08/parts/Part_1_JHD.usd
        
        create_obstacle_path(
            usd_path = "/home/isaacsim/Documents//manhole.usd",
            prim_path = "/World/envs/env_0/obstacle_0", 
            translation=(0., 0., 0.)
        )



        create_obstacle(
            "/World/envs/env_0/obstacle_1", 
            prim_type="Capsule",
            translation=(0., 0., 2.2),
            attributes={"axis": "Y", "radius": 0.04, "height": 5}
        )

        self.drone.spawn(translations=[(0.0, 0.0, 2.)])
        #attach_payload(f"/World/envs/env_0/{self.drone.name}_0", self.cfg.task.bar_length,  payload_radius=0.004,payload_mass=0.03)

        sphere = objects.DynamicSphere(
            "/World/envs/env_0/target",
            translation=(1.5, 0., 1.),
            radius=0.02,
            color=torch.tensor([1., 0., 0.])
        )
        kit_utils.set_collision_properties(sphere.prim_path, collision_enabled=False)
        kit_utils.set_rigid_body_properties(sphere.prim_path, disable_gravity=True)
        return ["/World/defaultGroundPlane"]

    def _set_specs(self):
        drone_state_dim = self.drone.state_spec.shape[-1]
        observation_dim = drone_state_dim + 4
        if self.time_encoding:
            self.time_encoding_dim = 4
            observation_dim += self.time_encoding_dim
        self.observation_spec = CompositeSpec({
            "agents": {
                "observation": UnboundedContinuousTensorSpec((1, observation_dim)),
                "image": UnboundedContinuousTensorSpec((1, 1, self.camera_resolution[1], self.camera_resolution[0]))
            }
        }).expand(self.num_envs).to(self.device)
        self.action_spec = CompositeSpec({
            "agents": {
                "action": self.drone.action_spec.unsqueeze(0),
            }
        }).expand(self.num_envs).to(self.device)
        self.reward_spec = CompositeSpec({
            "agents": {
                "reward": UnboundedContinuousTensorSpec((1, 1))
            }
        }).expand(self.num_envs).to(self.device)
        self.done_spec = CompositeSpec({
            "done": DiscreteTensorSpec(2, (1,), dtype=torch.bool)
        }).expand(self.num_envs).to(self.device)
        self.agent_spec["drone"] = AgentSpec(
            "drone", 1,
            observation_key=("agents", "observation"),
            action_key=("agents", "action"),
            reward_key=("agents", "reward"),
        )
        stats_spec = CompositeSpec({
            "return": UnboundedContinuousTensorSpec(1),
            "episode_len": UnboundedContinuousTensorSpec(1),
            "drone_pos_error": UnboundedContinuousTensorSpec(1),
            "drone_uprightness": UnboundedContinuousTensorSpec(1),
            "drone_spin": UnboundedContinuousTensorSpec(1),
            "collision": UnboundedContinuousTensorSpec(1),
            "success": BinaryDiscreteTensorSpec(1, dtype=bool),
        }).expand(self.num_envs).to(self.device)
        self.observation_spec["stats"] = stats_spec
        self.stats = stats_spec.zero()        

    def _reset_idx(self, env_ids: torch.Tensor):
        self.drone._reset_idx(env_ids)
        
        drone_pos = self.init_pos_dist.sample((*env_ids.shape, 1))
        drone_rpy = self.init_rpy_dist.sample((*env_ids.shape, 1))
        drone_rot = euler_to_quaternion(drone_rpy)
        self.drone.set_world_poses(
            drone_pos + self.envs_positions[env_ids].unsqueeze(1), drone_rot, env_ids
        )
        self.drone.set_velocities(self.init_vels[env_ids], env_ids)
        self.drone.set_joint_positions(self.init_joint_pos[env_ids], env_ids)
        self.drone.set_joint_velocities(self.init_joint_vels[env_ids], env_ids)

        target_pos = self.target_pos_dist.sample(env_ids.shape)
        self.target_pos[env_ids] = target_pos
        self.target_vis.set_world_poses(
            target_pos + self.envs_positions[env_ids], 
            env_indices=env_ids
        )
        # payload_mass = self.payload_mass_dist.sample(env_ids.shape)
        # self.payload.set_masses(payload_mass, env_ids)

        obstacle_spacing = self.obstacle_spacing_dist.sample(env_ids.shape)
        obstacle_pos = torch.zeros(len(env_ids), 2, 3, device=self.device)
        obstacle_pos[:, :, 2] = 0.0
        #obstacle_pos[:, 1, 2] += obstacle_spacing
        self.obstacles.set_world_poses(
            obstacle_pos + self.envs_positions[env_ids].unsqueeze(1), env_indices=env_ids
        )
        self.obstacle_pos[env_ids] = obstacle_pos

        self.stats.exclude("success")[env_ids] = 0.
        self.stats["success"][env_ids] = False

        if (env_ids == self.central_env_idx).any():
            self.payload_traj_vis.clear()
            self.drone_traj_vis.clear()
            self.draw.clear_lines()

            
        # if len(self.frames_sensor) > 0:
        #     for image_type, arrays in torch.stack(self.frames_sensor).items():
        #         print(f"Writing {image_type} of shape {arrays.shape}.")
        #         for drone_id, arrays_drone in enumerate(arrays.unbind(1)):
        #             if drone_id < 2:
        #                 if image_type == "rgb":
        #                     arrays_drone = arrays_drone.permute(0, 2, 3, 1)[..., :3]
        #                     write_video(f"demo_rgb_{drone_id}.mp4", arrays_drone, fps=1/0.016)

    def _pre_sim_step(self, tensordict: TensorDictBase):
        actions = tensordict[("agents", "action")]
        self.effort = self.drone.apply_action(actions)

    def _compute_state_and_obs(self):
        self.drone_state = self.drone.get_state()
        self.drone_up = self.drone_state[..., 16:19]
        # self.payload_pos = self.get_env_poses(self.payload.get_world_poses())[0]
        # self.payload_vels = self.payload.get_velocities()
        self.drone_pos = self.get_env_poses(self.drone.get_world_poses())[0]
        # heading
        #self.drone_heading = prim_utils.get_heading(self.drone_state[..., 16:19])

        # relative position and heading
        #self.drone_payload_rpos = self.drone_state[..., :3] - self.target_pos.unsqueeze(1)


        self.target_rpos = self.target_pos.unsqueeze(1) - self.drone_state[..., :3]
        obstacle_drone_rpos = self.obstacle_pos[..., [0, 2]] - self.drone_state[..., [0, 2]]

        # camera sensor
        # self.frames_sensor.append(self.camera_sensor.get_images().cpu())
        
        obs = [
            self.target_rpos,
            self.drone_state[..., 3:],
            obstacle_drone_rpos.flatten(start_dim=-2).unsqueeze(1),
        ]

        ## print shapes of all observations
        # for ob in obs:
        #     print(ob.shape)


        if self.time_encoding:
            t = (self.progress_buf / self.max_episode_length).unsqueeze(-1)
            obs.append(t.expand(-1, self.time_encoding_dim).unsqueeze(1))
        
        obs = torch.cat(obs, dim=-1)

        self.drone_pos_error = torch.norm(self.target_rpos, dim=-1)
        self.stats["drone_pos_error"].lerp_(self.drone_pos_error, (1-self.alpha))
        self.stats["drone_uprightness"].lerp_(self.drone_up[..., 2], (1-self.alpha))
        # also add spining
        self.stats["drone_spin"].lerp_(self.drone_state[..., 19], (1-self.alpha))

        if self._should_render(0):
            central_env_pos = self.envs_positions[self.central_env_idx]
            drone_pos = (self.drone.pos[self.central_env_idx, 0]+central_env_pos).tolist()
            #payload_pos = (self.drone_pos[self.central_env_idx]+central_env_pos).tolist()
            
            if len(self.payload_traj_vis)>1:
                point_list_0 = [self.payload_traj_vis[-1], self.drone_traj_vis[-1]]
                point_list_1 = [drone_pos, drone_pos]
                colors = [(1., .1, .1, 1.), (.1, 1., .1, 1.)]
                sizes = [1.5, 1.5]
                self.draw.draw_lines(point_list_0, point_list_1, colors, sizes)
            
            self.drone_traj_vis.append(drone_pos)
            self.payload_traj_vis.append(drone_pos)
            

        #################################
        # image in 3x240x320
        image = self.camera_sensor.get_images()
        image_float = image["rgb"].float()  # Convert to float
        image_grey = image_float.mean(dim=1, keepdim=True) / 255.


        #image = image["rgb"].permute(0, 3, 1, 2).float() / 255.
        #print(image_grey.shape)


        return TensorDict({
            "agents": {
                "observation": obs,
                "image": image_grey
            },
            "stats": self.stats,
            # "info": self.info
        }, self.batch_size)

    def _compute_reward_and_done(self):
        
        reward_pos = 1.0 / (1.0 + torch.square(self.reward_distance_scale * self.drone_pos_error))
        # pose_reward = torch.exp(-distance * self.reward_distance_scale)

        reward_up = torch.square((self.drone_up[..., 2] + 1) / 2)

        reward_effort = self.reward_effort_weight * torch.exp(-self.effort)

        spin = torch.square(self.drone.vel[..., -1])
        reward_spin = 1.0 / (1.0 + torch.square(spin))

        # swing = torch.norm(self.payload_vels[..., :3], dim=-1, keepdim=True)
        # reward_swing = 0.5 * torch.exp(-swing)
        
        collision = (
            self.obstacles
            .get_net_contact_forces()
            .any(-1)
            .any(-1, keepdim=True)
        )
        collision_reward = collision.float()

        self.stats["collision"].add_(collision_reward)
        assert reward_pos.shape == reward_up.shape == reward_spin.shape
        reward = (
            reward_pos 
            + reward_pos * (reward_up + reward_spin) 
            + reward_effort
        ) * (1 - collision_reward)
        
        misbehave = (
            (self.drone.pos[..., 2] < 0.2) 
            | (self.drone.pos[..., 2] > 1.5)
            | (self.drone.pos[..., 1].abs() > 1.)
        )
        hasnan = torch.isnan(self.drone_state).any(-1)

        terminated = misbehave | hasnan
        truncated = (self.progress_buf >= self.max_episode_length).unsqueeze(-1)
        
        if self.reset_on_collision:
            terminated = terminated | collision

        done = terminated | truncated
        
        self.stats["success"].bitwise_or_(self.drone_pos_error < 0.2)
        self.stats["return"].add_(reward)
        self.stats["episode_len"][:] = self.progress_buf.unsqueeze(1)



        return TensorDict(
            {
                "agents": {
                    "reward": reward.unsqueeze(-1)
                },
                "done": done,
                "terminated": terminated,
                "truncated": truncated,
            },
            self.batch_size,
        )
