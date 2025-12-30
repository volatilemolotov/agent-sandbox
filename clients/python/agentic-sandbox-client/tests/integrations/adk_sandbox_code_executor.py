import asyncio

from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types


from agentic_sandbox.integrations.adk.code_executors.python_sandbox import PythonSandboxCodeExecutor

def test_adk_code_executor(python_sandbox_settings):

    python_sandbox_code_executor = PythonSandboxCodeExecutor(python_sandbox_settings)



    agent = LlmAgent(
        model="gemini-3-flash-preview",
        name="agent_engine_code_execution_agent",
        instruction="You are a helpful agent that can write and execute code in a sandbox environment to answer questions and solve problems.",
        code_executor=python_sandbox_code_executor,
    )
    runner = InMemoryRunner(
        agent=agent,
        app_name='my_app',
    )
    
    session = asyncio.run(runner.session_service.create_session(
        app_name='my_app', user_id='user'
    ))

    message = "Write and execute a Python code that requests an IP from a web service like ipify and print current IP. Also tell the IP from the code output. Do not use third party libraries."
    # message = "Get weather in belgrade in celcius"
    
    content = types.Content(role='user', parts=[types.Part(text=message)])
    events = runner.run(user_id="user", session_id=session.id, new_message=content)

    for event in events:
        # print(f"\nDEBUG EVENT: {event}\n")
        if event.is_final_response() and event.content:
            pass
            # final_answer = event.content.parts[0].text.strip()
            final_answer = event.content.parts
            # print("\n🟢 FINAL ANSWER\n", final_answer, "\n")
    print()
