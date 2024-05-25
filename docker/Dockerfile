# Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Reference:
# https://gitlab.com/nvidia/container-images/vulkan/-/blob/master/docker/Dockerfile.ubuntu
# https://github.com/NVIDIA-Omniverse/IsaacSim-dockerfiles
#
# Build the image:
# docker login nvcr.io
# docker build --pull -t \
#   isaac-sim:2023.1.0-ubuntu22.04 \
#   --build-arg ISAACSIM_VERSION=2023.1.0 \
#   --file Dockerfile.2023.1.0-ubuntu22.04 .
#
# Run container:
# docker run --name isaac-sim --entrypoint bash -it --gpus all -e "ACCEPT_EULA=Y" --rm --network=host \
#   -e "PRIVACY_CONSENT=Y" -e "PRIVACY_USERID=<email>" \
#   -v ~/docker/isaac-sim/cache/kit:/isaac-sim/kit/cache:rw \
#   -v ~/docker/isaac-sim/cache/ov:/root/.cache/ov:rw \
#   -v ~/docker/isaac-sim/cache/pip:/root/.cache/pip:rw \
#   -v ~/docker/isaac-sim/cache/glcache:/root/.cache/nvidia/GLCache:rw \
#   -v ~/docker/isaac-sim/cache/computecache:/root/.nv/ComputeCache:rw \
#   -v ~/docker/isaac-sim/logs:/root/.nvidia-omniverse/logs:rw \
#   -v ~/docker/isaac-sim/data:/root/.local/share/ov/data:rw \
#   -v ~/docker/isaac-sim/documents:/root/Documents:rw \
# 	isaac-sim:2023.1.0-ubuntu22.04 \
# 	./isaac-sim.headless.native.sh --allow-root
#
# More info:
# https://developer.nvidia.com/isaac-sim
#
ARG DEBIAN_FRONTEND=noninteractive
ARG ISAACSIM_VERSION=2023.1.0-hotfix.1

# https://catalog.ngc.nvidia.com/orgs/nvidia/containers/isaac-sim
FROM nvcr.io/nvidia/isaac-sim:${ISAACSIM_VERSION} as isaacomnidrone

# ENV OMNI_SERVER http://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/2023.1.0
# ENV OMNI_SERVER omniverse://localhost/NVIDIA/Assets/Isaac/2023.1.0
# ENV OMNI_USER admin
# ENV OMNI_PASS admin
ENV MIN_DRIVER_VERSION 525.60.11

WORKDIR /isaac-sim

# Add symlink
RUN ln -s exts/omni.isaac.examples/omni/isaac/examples extension_examples

# Default entrypoint to launch headless with streaming
# ENTRYPOINT /isaac-sim/runheadless.native.sh 

ENV PATH="/root/miniconda3/bin:${PATH}"
ARG PATH="/root/miniconda3/bin:${PATH}"

WORKDIR /home/ubuntu

RUN apt-get update

RUN apt-get install -y wget git nano cmake build-essential && rm -rf /var/lib/apt/lists/*

# https://repo.anaconda.com/miniconda/Miniconda3-py37_23.1.0-1-Linux-x86_64.sh
# https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
# https://repo.anaconda.com/miniconda/Miniconda3-py310_24.1.2-0-Linux-x86_64.sh

RUN wget \
    https://repo.anaconda.com/miniconda/Miniconda3-py310_24.1.2-0-Linux-x86_64.sh \
    && mkdir /root/.conda \
    && bash Miniconda3-py310_24.1.2-0-Linux-x86_64.sh -b \
    && rm -f Miniconda3-py310_24.1.2-0-Linux-x86_64.sh 
RUN /root/miniconda3/bin/activate
#RUN conda --version

ENV ISAACSIM_PATH /isaac-sim
ENV ISAACSIM_PYTHON_EXE /isaac-sim/python.sh

#RUN conda install python=3.7
RUN conda init
#RUN conda activate sim
# Set the shell to bash
SHELL ["/bin/bash", "-c"]

#RUN git clone https://github.com/btx0424/OmniDrones.git
COPY OmniDrones OmniDrones

RUN source /root/miniconda3/bin/activate && \
    cp -r /home/ubuntu/OmniDrones/conda_setup/etc /root/miniconda3

#RUN git clone https://github.com/btx0424/tensordict.git
RUN git clone https://github.com/pytorch/tensordict.git
RUN cd /home/ubuntu/tensordict && source /root/miniconda3/bin/activate && pip install tomli && python setup.py develop

RUN git clone https://github.com/pytorch/rl.git
RUN cd /home/ubuntu/rl && source /root/miniconda3/bin/activate && python setup.py develop

COPY orbit orbit
RUN source /root/miniconda3/bin/activate && cd orbit && ln -s ${ISAACSIM_PATH} _isaac_sim && \ 
    ./orbit.sh -i && ./orbit.sh -e

#RUN git clone https://github.com/btx0424/OmniDrones.git
#RUN cd /home/ubuntu/OmniDrones

# ## Tensordict
# RUN git clone https://github.com/btx0424/tensordict.git
# WORKDIR /home/ubuntu/tensordict
# RUN python setup.py develop

# ## Tensor rl
# RUN git clone https://github.com/pytorch/rl.git
# WORKDIR /home/ubuntu/rl
# RUN python setup.py develop
RUN /bin/bash -c "source /root/.bashrc"




WORKDIR /home/ubuntu/OmniDrones

RUN source /root/miniconda3/bin/activate && pip install -e .

# # Source and activate Conda environment, then install packages
# RUN source /root/miniconda3/bin/activate && \
#     pip install tensordict-nightly torchrl-nightly

#Set WANDB authorization
ENV WANDB_API_KEY=e70c39b8904a17fc4e2079946a9fb9842b60ebc1

RUN git config --global --add safe.directory /home/ubuntu/OmniDrones

ENTRYPOINT /root/.bashrc
