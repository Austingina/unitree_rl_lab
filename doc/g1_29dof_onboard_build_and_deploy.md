# G1-29DOF 机载编译与部署完整指南

本文档覆盖从零开始在 **G1 机载 aarch64 电脑**上完成编译、排障与运行的全过程，包含实际踩坑记录与修复方式。

适用机型：G1-29DOF（`mode_machine = 5` 或 `6`，见下文）  
仓库路径（机载）：`~/unitree/unitree_rl_lab`

---

## 目录

1. [依赖安装](#一依赖安装)
2. [ARM64 ONNX Runtime 准备](#二arm64-onnx-runtime-准备)
3. [CMakeLists 配置说明](#三cmakelists-配置说明)
4. [编译步骤与常见报错](#四编译步骤与常见报错)
5. [运行前检查](#五运行前检查)
6. [mode_machine 不匹配排查](#六mode_machine-不匹配排查)
7. [启动与按键操作](#七启动与按键操作)

---

## 一、依赖安装

### 系统依赖

```bash
sudo apt-get update
sudo apt-get install -y \
    libyaml-cpp-dev \
    libboost-all-dev \
    libeigen3-dev \
    libspdlog-dev \
    libfmt-dev
```

验证 `fmt` 库：

```bash
ls /usr/lib/aarch64-linux-gnu/libfmt*
```

### Unitree SDK2

```bash
cd ~/unitree/unitree_sdk2
mkdir -p build && cd build
cmake .. -DBUILD_EXAMPLES=OFF
sudo make install
```

验证：

```bash
ls /usr/local/include/unitree/dds_wrapper/robots/go2/go2.h
ls /usr/local/lib | grep unitree_sdk2
```

---

## 二、ARM64 ONNX Runtime 准备

仓库自带的 `deploy/thirdparty/onnxruntime-linux-x64-1.22.0` 是 **x86_64 专用**，在 G1（aarch64）上链接会报：

```
error adding symbols: file in wrong format
```

必须单独下载 ARM64 版本。

### 下载与解压

```bash
cd ~/unitree          # 注意：cd 到 ~/unitree 再解压，路径为 $HOME/unitree/onnxruntime-...
wget https://github.com/microsoft/onnxruntime/releases/download/v1.23.1/onnxruntime-linux-aarch64-1.23.1.tgz
tar -xzf onnxruntime-linux-aarch64-1.23.1.tgz
```

解压后目录结构（**用户名 `unitree` 时完整绝对路径**）：

```text
/home/unitree/unitree/onnxruntime-linux-aarch64-1.23.1
  ├── include/
  │   └── onnxruntime_cxx_api.h   ← CMake 检查此文件是否存在
  └── lib/
      └── libonnxruntime.so
```

> **常见路径错误**：若在 `~` 下解压（而非 `~/unitree`），路径是 `/home/unitree/onnxruntime-linux-aarch64-1.23.1`（少一层 `unitree`）。  
> 实际解压位置以 `find "$HOME" -name onnxruntime_cxx_api.h 2>/dev/null` 的输出为准。

---

## 三、CMakeLists 配置说明

`deploy/robots/g1_29dof/CMakeLists.txt` 已支持 aarch64 自动识别与 `-DONNXRUNTIME_ROOT` 覆盖。

### 关键逻辑

```cmake
# 声明为缓存变量，使 -DONNXRUNTIME_ROOT=... 被 CMake 识别（不再报 "unused variable"）
set(ONNXRUNTIME_ROOT "" CACHE PATH "...")

# 用 CMAKE_SYSTEM_PROCESSOR + uname -m 回退判断 ARM64
string(TOLOWER "${CMAKE_SYSTEM_PROCESSOR}" _ort_cpu)
if(_ort_cpu MATCHES "^(aarch64|arm64|armv8)")
  set(_ORT_ARM64 TRUE)
endif()

# aarch64 默认路径；x64 用仓库自带 thirdparty
if(_ORT_ARM64)
  if(NOT ONNXRUNTIME_ROOT)
    set(ONNXRUNTIME_ROOT "$ENV{HOME}/unitree/onnxruntime-linux-aarch64-1.23.1")
  endif()
else()
  ...
endif()
```

**配置成功时输出（必须出现这三行）**：

```
-- ORT host cpu: CMAKE_SYSTEM_PROCESSOR=aarch64 -> aarch64 (arm64=TRUE)
-- ONNXRUNTIME_ROOT=/home/unitree/unitree/onnxruntime-linux-aarch64-1.23.1
-- ONNXRUNTIME_LIB=/home/unitree/unitree/onnxruntime-linux-aarch64-1.23.1/lib/libonnxruntime.so
```

若出现 `Manually-specified variables were not used: ONNXRUNTIME_ROOT`，说明机载 `CMakeLists.txt` 仍是旧版，需同步最新文件（见下文校验方法）。

### 校验脚本

`deploy/robots/g1_29dof/check_cmake_ort.sh` 可在配置前验证 CMakeLists 是否已是最新版本：

```bash
cd ~/unitree/unitree_rl_lab/deploy/robots/g1_29dof
bash check_cmake_ort.sh
# 输出 OK: ... 方可继续
```

---

## 四、编译步骤与常见报错

### 标准编译流程

```bash
cd ~/unitree/unitree_rl_lab/deploy/robots/g1_29dof
rm -rf build && mkdir build && cd build

# 若 ONNX 解压位置与默认一致（$HOME/unitree/onnxruntime-linux-aarch64-1.23.1）：
cmake ..

# 若解压位置不同，显式指定（注意：必须是含 include/onnxruntime_cxx_api.h 的那一层目录）：
cmake .. -DONNXRUNTIME_ROOT=/home/unitree/unitree/onnxruntime-linux-aarch64-1.23.1

make -j"$(nproc)"
```

编译成功输出：

```
[ 60%] Built target g1_29dof_controller_lib
[100%] Built target g1_ctrl
```

---

### 报错1：`file in wrong format`（最常见）

**完整报错**：

```
/usr/bin/ld: ../../../thirdparty/onnxruntime-linux-x64-1.22.0/lib/libonnxruntime.so.1.22.0:
error adding symbols: file in wrong format
```

**原因**：CMake 走了 x64 分支，链接的是 x86_64 的 `.so`，无法在 aarch64 上使用。

**根因排查**：

```bash
# 检查 cmake 输出中是否有这三行：
# -- ORT host cpu: ...  (arm64=TRUE)
# -- ONNXRUNTIME_ROOT=...
# -- ONNXRUNTIME_LIB=...

# 若没有，说明机载 CMakeLists.txt 是旧版，需同步
grep -E 'ONNXRUNTIME_ROOT "" CACHE|ORT host cpu' \
    ~/unitree/unitree_rl_lab/deploy/robots/g1_29dof/CMakeLists.txt
```

**修复**：将开发机上最新的 `CMakeLists.txt` 同步到机载相同路径，再清理重配：

```bash
# 开发机推送
scp /path/to/unitree_rl_lab/deploy/robots/g1_29dof/CMakeLists.txt \
    unitree@ROBOT_IP:~/unitree/unitree_rl_lab/deploy/robots/g1_29dof/CMakeLists.txt

# 机载重编
cd ~/unitree/unitree_rl_lab/deploy/robots/g1_29dof/build
rm -rf * && cmake .. -DONNXRUNTIME_ROOT=/home/unitree/unitree/onnxruntime-linux-aarch64-1.23.1
make -j"$(nproc)"
```

---

### 报错2：`ONNX Runtime not found`

**完整报错**：

```
CMake Error: ONNX Runtime not found at:
  /home/unitree/onnxruntime-linux-aarch64-1.23.1
```

**原因**：`-DONNXRUNTIME_ROOT` 路径不含 `include/onnxruntime_cxx_api.h`，通常是路径少写了一层目录（如写了 `/home/unitree/onnxruntime-...` 而实际在 `/home/unitree/unitree/onnxruntime-...`）。

**排查**：

```bash
find "$HOME" -name onnxruntime_cxx_api.h 2>/dev/null
# 输出示例：/home/unitree/unitree/onnxruntime-linux-aarch64-1.23.1/include/onnxruntime_cxx_api.h
# ONNXRUNTIME_ROOT 应设为 include 的上一级：
# /home/unitree/unitree/onnxruntime-linux-aarch64-1.23.1
```

---

### 报错3：`Manually-specified variables were not used: ONNXRUNTIME_ROOT`

**原因**：机载 `CMakeLists.txt` 是未修改的旧版本，完全不认识 `ONNXRUNTIME_ROOT` 变量。  
此时 `-DONNXRUNTIME_ROOT=...` 形同虚设，程序仍链接 `thirdparty/onnxruntime-linux-x64-1.22.0`，最终导致 **报错1**。

**修复**：同步最新 `CMakeLists.txt`（同报错1修复流程）。

---

## 五、运行前检查

### 检查并关闭原厂控制程序

G1 机载会开机自启 `junior_ctrl`（原厂底层控制），它会占用 `lowcmd` 通道，导致程序报 `The other process is using the lowcmd channel`。

```bash
# 查看是否存在
ps aux | grep -E 'junior_ctrl|sport|ctrl' | grep -v grep
```

若看到类似：

```
unitree  2461  18.6%  .../junior_ctrl eth0
```

执行关闭：

```bash
pkill -f junior_ctrl
pkill -f start_junior_ctrl.sh
sleep 1
# 确认已退出
ps aux | grep junior_ctrl | grep -v grep
```

检查是否由 systemd 管理（防止自动重启）：

```bash
sudo systemctl list-units --type=service | grep -i 'junior\|ctrl\|unitree'
# 若有匹配项：
sudo systemctl stop <service_name>
```

> **安全提示**：关闭 `junior_ctrl` 后机器人无控制，关节会松弛。请提前让机器人处于安全姿态（坐/趴/有支撑），再执行关闭操作。

---

## 六、mode_machine 不匹配排查

### 现象

```
[info] Connected to robot.
[critical] Unmatched robot type.
Aborted
```

### 原因

`deploy/robots/g1_29dof/main.cpp` 中硬编码了期望的机器类型：

```cpp
FSMState::lowcmd->msg_.mode_machine() = 5; // 29dof_rev_1_0
```

若机器人实际 `mode_machine` 与此值不符，则程序退出。

### 确认机器人实际 mode_machine

**方法1（推荐）**：Unitree App → **设备 → 数据 → 机器人 → Machine Type**

**方法2**：让程序打印实际值（修改 `main.cpp` 加日志后重编），`Connected to robot` 后会输出：

```
[info] Robot reported mode_machine = 6
[critical] Unmatched robot type: robot mode_machine=6, expected=5.
```

### mode_machine 对照表

| `mode_machine` | 机型 | 髋关节齿比 | 腕关节 | 锁腰 |
|:-:|---|---|---|---|
| 4  | `g1_23dof_rev_1_0` | 14.3 : 22.5 | 无 | — |
| **5**  | `g1_29dof_rev_1_0` | 14.3 : 22.5 | 4010 | 否 |
| **6**  | `g1_29dof_lock_waist_rev_1_0` | 14.3 : 22.5 | 4010 | **是** |
| 11 | `g1_29dof_mode_11` | 22.5 : 22.5 | 4010 | 否 |
| 12 | `g1_29dof_mode_12` | 22.5 : 22.5 | 4010 | 是 |
| 13 | `g1_29dof_mode_13` | 14.3 : 22.5 | 5010（新） | 否 |
| 14 | `g1_29dof_mode_14` | 14.3 : 22.5 | 5010（新） | 是 |
| 15 | `g1_29dof_mode_15` | 22.5 : 22.5 | 5010（新） | 否 |
| 16 | `g1_29dof_mode_16` | 22.5 : 22.5 | 5010（新） | 是 |

### 修复

在机器人上用 `sed` 直接替换（以实际值为 `6` 为例）：

```bash
# 确认当前值
grep 'mode_machine()' ~/unitree/unitree_rl_lab/deploy/robots/g1_29dof/main.cpp

# 替换（将 5 改为机器人实际上报的值）
sed -i 's/msg_.mode_machine() = 5;/msg_.mode_machine() = 6;/' \
    ~/unitree/unitree_rl_lab/deploy/robots/g1_29dof/main.cpp

# 确认替换成功
grep 'mode_machine()' ~/unitree/unitree_rl_lab/deploy/robots/g1_29dof/main.cpp

# 重编
cd ~/unitree/unitree_rl_lab/deploy/robots/g1_29dof/build
make -j"$(nproc)"
```

> **锁腰版（mode 6）策略兼容性**：仓库默认策略按非锁腰版（mode 5）训练。FixStand 和行走一般可兼容；舞蹈动作若出现腰部抖动或异常力矩，需用 `g1_29dof_lock_waist_rev_1_0` URDF 重新训练策略。

---

## 七、启动与按键操作

### 启动程序

```bash
cd ~/unitree/unitree_rl_lab/deploy/robots/g1_29dof/build
./g1_ctrl --network eth0
```

成功启动输出：

```
[info] Waiting for connection to robot...
[info] Connected to robot.
FSM: Start Passive
```

### 按键说明

| 符号 | 对应按键 |
|------|---------|
| `LT` | 左扳机（Left Trigger） |
| `LB` | 左肩键 L1（Left Bumper） |
| `RB` | 右肩键 R1（Right Bumper） |
| `↑↓←→` | 十字方向键 |
| `A / B / X / Y` | 右侧功能键 |
| `(2s)` | 长按约 2 秒后再按另一键 |

### 状态切换全表

#### Passive（启动后默认状态）

| 目标状态 | 操作 |
|---------|------|
| FixStand | `LT` + `↑` |

#### FixStand（站立准备）

| 目标状态 | 操作 |
|---------|------|
| Passive | `LT` + `B` |
| Velocity（速度控制/行走） | `RB` + `X` |

#### Velocity（速度控制，所有舞蹈入口）

| 目标状态 | 操作 |
|---------|------|
| Passive | `LT` + `B` |
| **Mimic_Dance_102** | 长按 `LB` 2s + `↓` |
| **Mimic_Gangnam_Style** | 长按 `LB` 2s + `↑` |
| **Mimic_Dance_102_X2** | 长按 `LB` 2s + `←` |
| **Mimic_Gangnam_Style_X2** | 长按 `LB` 2s + `→` |
| **Mimic_Shakehand** | 长按 `LB` 2s + `A` |
| **Mimic_Wave** | 长按 `LB` 2s + `Y` |
| **Mimic_Dance102_Gangnam_Repeat2** | 长按 `LB` 2s + `X` |

#### 任意 Mimic 状态

| 目标状态 | 操作 |
|---------|------|
| Passive | `LT` + `B` |
| Velocity | `RB` + `X` |

### 标准操作流程

```
程序启动
    │
    ▼
[Passive] ─── LT + ↑ ───► [FixStand] ─── RB + X ───► [Velocity]
    ▲                           │                           │
    │                        LT + B                         ├─ LB(2s)+↓ ──► Mimic_Dance_102
    │                           ▼                           ├─ LB(2s)+↑ ──► Mimic_Gangnam_Style
    │                        [Passive]                      ├─ LB(2s)+← ──► Mimic_Dance_102_X2
    │                                                       ├─ LB(2s)+→ ──► Mimic_Gangnam_Style_X2
    │                                                       ├─ LB(2s)+A ──► Mimic_Shakehand
    │                                                       ├─ LB(2s)+Y ──► Mimic_Wave
    │                                                       └─ LB(2s)+X ──► Mimic_Dance102_Gangnam_Repeat2
    │                                                                │
    │                                                    LT+B ◄──── │ ────► RB+X
    └─────────────────────────────────────────────────────┘         │
                                                                     ▼
                                                                [Velocity]
```

### 各舞蹈有效时段

| 舞蹈 | 起始 | 结束 | 时长 |
|------|:---:|:---:|:---:|
| Mimic_Dance_102 | 2.8s | 24.0s | ~21s |
| Mimic_Gangnam_Style | 5.2s | 25.5s | ~20s |
| Mimic_Dance_102_X2 | 2.8s | 24.0s | ~21s |
| Mimic_Gangnam_Style_X2 | 5.2s | 25.5s | ~20s |
| Mimic_Shakehand | 0.0s | 3.85s | ~4s |
| Mimic_Wave | 0.0s | 60.0s | ~60s |
| Mimic_Dance102_Gangnam_Repeat2 | 0.0s | 83.7s | ~84s |

---

## 附：文件修改汇总

| 文件 | 改动内容 |
|------|---------|
| `deploy/robots/g1_29dof/CMakeLists.txt` | 添加 `ONNXRUNTIME_ROOT` CACHE 变量；用 `CMAKE_SYSTEM_PROCESSOR` + `uname -m` 回退区分 aarch64/x64；通配查找 `libonnxruntime.so*`；配置失败时打印友好错误提示 |
| `deploy/robots/g1_29dof/main.cpp` | 在校验前打印 `Robot reported mode_machine = X`；校验失败时同时打印期望值与实际值 |
| `deploy/robots/g1_29dof/check_cmake_ort.sh` | 新增：配置前自检 CMakeLists 是否包含 ONNX/aarch64 逻辑 |
| `deploy/robots/g1_29dof/config/config.yaml` | 无修改（确认与预期一致） |
