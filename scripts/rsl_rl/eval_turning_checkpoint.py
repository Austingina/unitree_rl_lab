import argparse
import os
import time
from importlib.metadata import version

from isaaclab.app import AppLauncher

import cli_args  # isort: skip

parser = argparse.ArgumentParser(description="Evaluate a checkpoint on fixed left/right turning commands.")
parser.add_argument("--video", action="store_true", default=True, help="Record videos during evaluation.")
parser.add_argument("--video_length", type=int, default=900, help="Length of the recorded video (in steps).")
parser.add_argument("--disable_fabric", action="store_true", default=False)
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--task", type=str, default="Unitree-G1-29dof-Velocity")
parser.add_argument("--real-time", action="store_true", default=False)
parser.add_argument("--left_yaw", type=float, default=0.6)
parser.add_argument("--right_yaw", type=float, default=-0.6)
parser.add_argument("--forward_x", type=float, default=0.0)
parser.add_argument("--phase_steps", type=int, default=300, help="Steps per left/right phase.")
cli_args.add_rsl_rl_args(parser)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
if args_cli.video:
    args_cli.enable_cameras = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import csv
import gymnasium as gym
import numpy as np
import torch

from rsl_rl.runners import OnPolicyRunner

import isaaclab_tasks  # noqa: F401
from isaaclab.envs import DirectMARLEnv, multi_agent_to_single_agent
from isaaclab.utils.assets import retrieve_file_path
from isaaclab.utils.dict import print_dict
from isaaclab_rl.rsl_rl import RslRlOnPolicyRunnerCfg, RslRlVecEnvWrapper

import unitree_rl_lab.tasks  # noqa: F401
from unitree_rl_lab.utils.parser_cfg import parse_env_cfg


def _align_actor_noise_state_dict(model_sd: dict, policy: torch.nn.Module) -> dict:
    target = policy.state_dict()
    out = dict(model_sd)
    if "log_std" in target and "std" in out and "log_std" not in out:
        std = out.pop("std")
        out["log_std"] = torch.log(std.clamp(min=1e-8))
    elif "std" in target and "log_std" in out and "std" not in out:
        log_std = out.pop("log_std")
        out["std"] = torch.exp(log_std)
    return out


def _load_policy_weights_for_play(runner, path: str, device: str) -> None:
    loaded = torch.load(path, weights_only=False, map_location=device)
    msd = loaded["model_state_dict"]
    policy = runner.alg.policy
    msd = _align_actor_noise_state_dict(msd, policy)
    policy.load_state_dict(msd, strict=True)
    runner.current_learning_iteration = loaded.get("iter", 0)


def set_fixed_command(env, lin_x: float, lin_y: float, yaw: float):
    cmd_term = env.unwrapped.command_manager.get_term("base_velocity")
    cmd_term.vel_command_b[:, 0] = lin_x
    cmd_term.vel_command_b[:, 1] = lin_y
    cmd_term.vel_command_b[:, 2] = yaw
    cmd_term.is_standing_env[:] = False
    if hasattr(cmd_term, "is_heading_env"):
        cmd_term.is_heading_env[:] = False


def main():
    env_cfg = parse_env_cfg(
        args_cli.task,
        device=args_cli.device,
        num_envs=args_cli.num_envs,
        use_fabric=not args_cli.disable_fabric,
        entry_point_key="play_env_cfg_entry_point",
    )
    agent_cfg: RslRlOnPolicyRunnerCfg = cli_args.parse_rsl_rl_cfg(args_cli.task, args_cli)
    resume_path = retrieve_file_path(args_cli.checkpoint)
    log_dir = os.path.dirname(resume_path)
    traj_csv = os.path.join(log_dir, "videos", "turn_eval", "turn_eval_traj.csv")

    env = gym.make(args_cli.task, cfg=env_cfg, render_mode="rgb_array" if args_cli.video else None)
    if isinstance(env.unwrapped, DirectMARLEnv):
        env = multi_agent_to_single_agent(env)

    if args_cli.video:
        video_folder = os.path.join(log_dir, "videos", "turn_eval")
        os.makedirs(video_folder, exist_ok=True)
        video_kwargs = {
            "video_folder": video_folder,
            "step_trigger": lambda step: step == 0,
            "video_length": args_cli.video_length,
            "disable_logger": True,
        }
        print("[INFO] Recording videos during eval.")
        print_dict(video_kwargs, nesting=4)
        env = gym.wrappers.RecordVideo(env, **video_kwargs)

    env = RslRlVecEnvWrapper(env, clip_actions=agent_cfg.clip_actions)
    runner = OnPolicyRunner(env, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    _load_policy_weights_for_play(runner, resume_path, agent_cfg.device)
    policy = runner.get_inference_policy(device=env.unwrapped.device)

    if version("rsl-rl-lib").startswith("2.3."):
        obs, _ = env.get_observations()
    else:
        obs = env.get_observations()

    timestep = 0
    dt = env.unwrapped.step_dt
    robot = env.unwrapped.scene["robot"]
    os.makedirs(os.path.dirname(traj_csv), exist_ok=True)
    with open(traj_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["step", "phase", "cmd_x", "cmd_yaw", "pos_x", "pos_y", "heading", "yaw_rate"])
        while simulation_app.is_running():
            start_time = time.time()
            if timestep < args_cli.phase_steps:
                cmd = (0.0, 0.0, 0.0)
                phase = "stand"
            elif timestep < args_cli.phase_steps * 2:
                cmd = (args_cli.forward_x, 0.0, args_cli.left_yaw)
                phase = "left"
            else:
                cmd = (args_cli.forward_x, 0.0, args_cli.right_yaw)
                phase = "right"
            set_fixed_command(env, *cmd)
            root_pos = robot.data.root_pos_w[0, :3].detach().cpu().numpy()
            env.unwrapped.sim.set_camera_view(eye=root_pos + np.array([2.5, 2.5, 1.2]), target=root_pos + np.array([0.0, 0.0, 0.7]))
            heading = float(robot.data.heading_w[0].item())
            yaw_rate = float(robot.data.root_ang_vel_b[0, 2].item())
            writer.writerow([timestep, phase, cmd[0], cmd[2], float(root_pos[0]), float(root_pos[1]), heading, yaw_rate])
            if timestep % 100 == 0:
                print(f"[EVAL] step={timestep} phase={phase} cmd={cmd} heading={heading:.3f} yaw_rate={yaw_rate:.3f}")
            with torch.inference_mode():
                actions = policy(obs)
                obs, _, _, _ = env.step(actions)
            timestep += 1
            if args_cli.video and timestep >= args_cli.video_length:
                break
            sleep_time = dt - (time.time() - start_time)
            if args_cli.real_time and sleep_time > 0:
                time.sleep(sleep_time)
    print(f"[INFO] saved trajectory to {traj_csv}")
    env.close()


if __name__ == "__main__":
    main()
    simulation_app.close()
