from k8s_agent_sandbox.sandbox_env import SandboxEnv, SparseTaskReward, StepPenaltyReward
# from .agent import Agent

# agent = Agent(system_prompt="You are a senior engineer that can code anything.")

env = SandboxEnv(
    reward_fn=StepPenaltyReward(
        base=SparseTaskReward(
            success_fn=lambda obs, info: "manage.py" in obs and info["exit_code"] == 0
        ),
        penalty=0.02,
    ),
    warmpool="simple-sandbox-warmpool",
    connection_mode="tunnel",   # swap to "gateway" for GKE
    connection_cfg={
        "router_namespace": "default",
    },
    max_episode_steps=15,
)

agent_tasks = [
    "create a django poll project",
]

trajectory = []

for task in agent_tasks:
    obs, info = env.reset(options={"task": task})
    terminated, truncated = False, False

    while not terminated and not truncated:
        action = "ls -la" #agent.act(obs, task)
        obs, reward, terminated, truncated, info = env.step(action)
        print(f"""
obs={obs}
reward={reward}
terminated={terminated}
truncated={truncated}
info={info}
""")
        trajectory.append((obs, action, reward, info))

# agent.learn(trajectory)
env.close()
