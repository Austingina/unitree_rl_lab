# G1 velocity turnB trained checkpoint

This branch contains the locally trained left/right-turn-capable G1 velocity policy uploaded on 2026-07-24.

## Main artifact
- `model_49999.pt`

## Training run
- Log dir: `logs/rsl_rl/unitree_g1_29dof_velocity/2026-07-23_09-02-04/`
- Watch log: `logs/manual_watch/g1_velocity_turnB_train_stdout.log`

## Final monitored metrics
- iteration: `49999/50000`
- mean reward: `60.51`
- yaw tracking reward: `0.8809`
- xy tracking reward: `0.9248`
- yaw error: `0.2967`
- xy error: `0.2292`
- mean episode length: `995.56`
- bad_orientation termination rate: `0.0052`
- curriculum: `lin=1.0000, ang=0.7000, terrain=1.6930`
- elapsed: `14:16:27`

## Related deployment/config files included in this branch
- `deploy/robots/g1_29dof/config/policy/velocity/v0/exported/policy.onnx`
- `deploy/robots/g1_29dof/config/policy/velocity/v0/params/deploy.yaml`
- `deploy/robots/g1_29dof/config/policy/velocity/v0/params/agent.yaml`
- `deploy/robots/g1_29dof/config/policy/velocity/v0/params/velocity_env_cfg.py`
- `scripts/rsl_rl/eval_turning_checkpoint.py`

## Notes
- This upload was pushed to the existing `Austingina/unitree_rl_lab` fork because that repository already existed under the account.
- The branch name used for this upload is `velocity-turnB-trained-20260724`.
