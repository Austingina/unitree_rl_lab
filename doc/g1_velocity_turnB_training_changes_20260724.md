# G1 velocity turnB 训练改动记录

更新时间：2026-07-24
分支：`velocity-turnB-trained-20260724`
相关提交：`a4d57ee`

## 1. 这次训练的目标

这次训练的目标不是单纯把 G1 的 velocity policy 继续训练，而是让它**真正学会左右转**，避免只会小角度摆头或主要只会直走。

从代码改动看，核心思路是：

1. 扩大训练阶段的角速度命令范围；
2. 扩大 play / deploy 阶段允许的转向范围，避免训练分布和使用分布不一致；
3. 提高 yaw 跟踪奖励权重；
4. 加入角速度 curriculum；
5. 调小 PPO 初始噪声和探索强度，让策略更稳定；
6. 补齐评测脚本、checkpoint 兼容加载和部署链路。

---

## 2. 最关键的训练改动

### 2.1 训练命令范围扩大

文件：
- `source/unitree_rl_lab/unitree_rl_lab/tasks/locomotion/robots/g1/29dof/velocity_env_cfg.py`

`CommandsCfg.base_velocity.ranges` 从接近“几乎不转”的小范围，改成了更真实的转向训练范围：

- `lin_vel_x`: `(-0.1, 0.1)` → `(-0.25, 0.5)`
- `lin_vel_y`: 保持较小横移范围
- `ang_vel_z`: `(-0.1, 0.1)` → `(-0.4, 0.4)`

意义：
- 训练阶段终于能持续看到“明确左转 / 明确右转”的命令；
- 不再只是小扰动级别的 yaw 学习。

### 2.2 play / deploy 的命令上限也同步放宽

同文件中的 `limit_ranges` 也被放宽：

- `ang_vel_z`: `(-0.2, 0.2)` → `(-0.7, 0.7)`
- `lin_vel_y`: `(-0.3, 0.3)` → `(-0.15, 0.15)`

意义：
- 避免“训练只见过很小的 yaw，实际播放或部署却给更大 yaw”的 OOD 问题；
- 让训练出来的左右转能力在实际运行时能真正用出来。

代码注释里也明确强调：如果训练时只用 ±0.1，而 play 用更大范围，会导致严重分布不一致。

---

## 3. 奖励函数改动

仍然在：
- `source/unitree_rl_lab/unitree_rl_lab/tasks/locomotion/robots/g1/29dof/velocity_env_cfg.py`

### 3.1 角速度跟踪奖励加权翻倍

- `track_ang_vel_z` 权重：`0.5` → `1.0`

意义：
- 明确提高“跟住左右转命令”的重要性；
- 这是这次 turn 能力提升最直接的奖励层改动之一。

### 3.2 手臂偏离惩罚加重

- `joint_deviation_arms`：`-0.1` → `-0.28`

意义：
- 抑制转向时上肢乱甩；
- 帮助策略在转弯时保持姿态更收敛、更稳定。

---

## 4. Curriculum 改动

文件：
- `source/unitree_rl_lab/unitree_rl_lab/tasks/locomotion/robots/g1/29dof/velocity_env_cfg.py`

新增：
- `ang_vel_cmd_levels = CurrTerm(mdp.ang_vel_cmd_levels)`

意义：
- 角速度命令强度不是一上来就给满，而是逐步升级；
- 更适合 locomotion / turning 任务，能降低一开始学崩的风险。

训练结束时监控里也能看到这个课程量级：
- `Curriculum/ang_vel_cmd_levels: 0.7000`

---

## 5. PPO 超参数改动

文件：
- `source/unitree_rl_lab/unitree_rl_lab/tasks/locomotion/agents/rsl_rl_ppo_cfg.py`
- 训练导出的部署参数：`deploy/robots/g1_29dof/config/policy/velocity/v0/params/agent.yaml`

### 5.1 初始噪声变小

- `init_noise_std`: `1.0` → `0.25`
- 新增：`noise_std_type = "log"`

意义：
- 降低策略初期动作抖动；
- 让 velocity / turning 控制更容易学稳。

### 5.2 熵系数变小

- `entropy_coef`: `0.01` → `0.005`

意义：
- 减少过强的随机探索；
- 后期更容易收敛到稳定动作。

### 5.3 KL 目标更保守

- `desired_kl`: `0.01` → `0.005`

意义：
- 每次更新步子更小；
- 降低策略突然发散的风险。

---

## 6. 训练 / 播放脚本改动

### 6.1 `train.py` 新增 `--network`

文件：
- `scripts/rsl_rl/train.py`

新增参数：
- `-n`, `--network`

作用：
- 设置 `UNITREE_NETWORK_INTERFACE`；
- 方便实机或部署时指定网卡。

### 6.2 `play.py` 新增 `--network`

文件：
- `scripts/rsl_rl/play.py`

同样支持：
- `-n`, `--network`

作用：
- 方便部署 / robot 链路直接复用。

### 6.3 `play.py` 增加 checkpoint 噪声参数兼容加载

文件：
- `scripts/rsl_rl/play.py`

新增函数：
- `_align_actor_noise_state_dict()`
- `_load_policy_weights_for_play()`

作用：
- 兼容老 checkpoint 的 `std` 和当前配置的 `log_std`；
- 避免训练好的模型在 play 时因为噪声参数格式变化而加载失败。

这属于工程兼容补丁，但对“训练完能顺利测和用”很关键。

---

## 7. 新增左右转专项评测脚本

文件：
- `scripts/rsl_rl/eval_turning_checkpoint.py`

功能：
- 先站立；
- 再给固定左转命令；
- 再给固定右转命令；
- 记录轨迹、heading、yaw_rate；
- 支持录视频。

默认关键参数：
- `left_yaw = 0.6`
- `right_yaw = -0.6`
- `phase_steps = 300`

意义：
- 这次训练不是只看 reward；
- 还专门补了一个 turn 能力验收脚本，用来检查模型是不是真的会左右转。

---

## 8. 部署侧参数同步改动

文件：
- `deploy/robots/g1_29dof/config/policy/velocity/v0/params/deploy.yaml`

### 8.1 部署侧 yaw 命令范围放宽

- `ang_vel_z`: `(-0.2, 0.2)` → `(-0.45, 0.45)`

意义：
- 训练出的左右转能力可以在部署时真正释放出来。

### 8.2 部署侧刚度 / 阻尼调整

`deploy.yaml` 中上肢相关 stiffness / damping 有同步修改，尤其一些上肢 damping 从较大值降到了更低值。

意义：
- 更偏部署调参；
- 目标通常是减少动作僵硬和异常摆动，提高转向时的整体顺滑度。

---

## 9. 这次上传中包含但不属于“turn 训练核心”的附带改动

下面这些文件也在提交里，但它们更多是部署工程或其他任务配套，不是左右转能力提升的核心原因：

### 9.1 实机编译 / ONNX / 型号兼容
- `deploy/robots/g1_29dof/CMakeLists.txt`
- `deploy/robots/g1_29dof/main.cpp`

主要内容：
- ONNX Runtime 路径与 ARM/x86 兼容；
- 根据机器人上报的 `mode_machine` 自动匹配；
- 修复部署编译链。

### 9.2 FSM 和 mimic 动作扩展
- `deploy/robots/g1_29dof/config/config.yaml`

新增多个 Mimic 状态，例如：
- `Mimic_Revenge`
- `Mimic_Shakehand`
- `Mimic_Wave`
- `Mimic_Dance102_Gangnam_Repeat2`

这些更偏舞蹈 / 实机流程扩展，不是这次 velocity turnB 的主因。

### 9.3 资源路径 / URDF / 数据转换配套
- `source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py`
- `scripts/mimic/csv_to_npz.py`
- `unitree_rl_lab.sh`

这些主要是在修：
- 机器人资源路径；
- URDF / USD 使用方式；
- mimic 数据生成和环境配套。

---

## 10. 这次训练跑出来的最终结果（监控记录）

来源：
- `logs/manual_watch/g1_velocity_turnB_train_stdout.log`

最终监控摘要：

- iteration: `49999/50000`
- mean reward: `60.51`
- yaw 跟踪奖励: `0.8809`
- xy 跟踪奖励: `0.9248`
- yaw 误差: `0.2967`
- xy 误差: `0.2292`
- mean episode length: `995.56`
- bad_orientation 终止率: `0.0052`
- curriculum: `lin=1.0000, ang=0.7000, terrain=1.6930`
- 已训练时长: `14:16:27`

对应 checkpoint：
- `logs/rsl_rl/unitree_g1_29dof_velocity/2026-07-23_09-02-04/model_49999.pt`

---

## 11. 一句话总结

这次训练真正决定左右转能力的关键改动是：

1. **把 yaw 训练命令范围从很小的 ±0.1 提到 ±0.4；**
2. **把 yaw 跟踪奖励权重从 0.5 提到 1.0；**
3. **加入角速度 curriculum；**
4. **把 PPO 噪声和更新激进度调小，让策略更稳；**
5. **让部署和评测链路同步支持更大的左右转命令。**

所以这不是单纯“继续训一个 velocity 模型”，而是一次明确面向**稳定左转 / 右转能力**的训练与工程配套修改。
