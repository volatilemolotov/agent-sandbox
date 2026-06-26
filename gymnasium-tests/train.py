import torch
from transformers import AutoTokenizer
from trl import AutoModelForCausalLMWithValueHead, PPOConfig, PPOTrainer
from peft import LoraConfig

from k8s_agent_sandbox.sandbox_env import SandboxEnv, SparseTaskReward

# ── 1. Configuration & Setup ─────────────────────────────────────────────────

model_name = "Qwen/Qwen2.5-Coder-1.5B"  # Good starting point for code/bash
ppo_config = PPOConfig(
    learning_rate=1.41e-5,
    batch_size=1,           # Keep small for local testing
    mini_batch_size=1,
)

# Apply LoRA to make training memory-efficient
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    bias="none",
    task_type="CAUSAL_LM",
)

# ── 2. Load Model and Tokenizer ──────────────────────────────────────────────

# TRL uses a special wrapper that adds a "Value Head" to the LLM for PPO
model = AutoModelForCausalLMWithValueHead.from_pretrained(
    model_name,
    peft_config=lora_config,
    device_map="auto",
)
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token

# Initialize the PPO Trainer
ppo_trainer = PPOTrainer(
    config=ppo_config,
    model=model,
    ref_model=None, # TRL handles the reference model internally with PEFT
    tokenizer=tokenizer,
)

# ── 3. Initialize Your Custom Environment ────────────────────────────────────

# Let's use a task where the agent must create a specific file
env = SandboxEnv(
    reward_fn=SparseTaskReward(
        success_fn=lambda obs, info: "hello_world.sh" in obs and info["exit_code"] == 0
    ),
    warmpool="simple-sandbox-warmpool",
    connection_mode="tunnel",
    max_episode_steps=5,
)

# ── 4. The Training Loop ─────────────────────────────────────────────────────

epochs = 50
task = "Create a bash script named hello_world.sh that prints 'Hello World'."

for epoch in range(epochs):
    obs, info = env.reset(options={"task": task})
    terminated, truncated = False, False

    # We will collect the step data to update the model at the end of the episode
    episode_queries = []
    episode_responses = []
    episode_rewards = []

    while not terminated and not truncated:
        # A. Format the Prompt for the LLM
        prompt = f"System: You are an expert bash programmer.\nTask: {task}\nTerminal Output: {obs}\nCommand to run:"
        query_tensor = tokenizer(prompt, return_tensors="pt").input_ids.squeeze().to(ppo_trainer.accelerator.device)

        # B. Generate the Action (Shell Command)
        # We generate a short sequence representing the next bash command
        generation_kwargs = {"max_new_tokens": 32, "do_sample": True, "top_k": 0.0, "top_p": 1.0}
        response_tensor = ppo_trainer.generate(query_tensor, **generation_kwargs).squeeze()

        # C. Decode the Action and Step the Environment
        # Extract *only* the newly generated text
        action = tokenizer.decode(response_tensor[len(query_tensor):], skip_special_tokens=True).strip()
        print(f"Agent executed: {action}")

        next_obs, reward, terminated, truncated, info = env.step(action)
        print(f"Reward: {reward} | Exit Code: {info['exit_code']}")

        # D. Store tensors for PPO Update
        episode_queries.append(query_tensor)
        episode_responses.append(response_tensor[len(query_tensor):])
        episode_rewards.append(torch.tensor(reward, dtype=torch.float32))

        obs = next_obs

        # End episode early if successful
        if reward > 0:
            break

    # E. Perform the PPO Optimization Step
    # TRL expects lists of tensors for a batch update
    stats = ppo_trainer.step(episode_queries, episode_responses, episode_rewards)
    print(f"Epoch {epoch} finished. Loss: {stats['ppo/loss/total']}")

env.close()

# Save your fine-tuned model adapters!
model.save_pretrained("./sandbox-agent-lora")
