import pytest

from langchain.agents import create_agent
from langchain_google_genai import ChatGoogleGenerativeAI

from agentic_sandbox.integrations.langchain.tools.python_sandbox import create_python_sandbox_tool

def test_langchain(python_sandbox_settings):
    
    python_sandbox_tool = create_python_sandbox_tool(python_sandbox_settings)
    
    model = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
    )
    
    agent = create_agent(model, tools=[python_sandbox_tool])

    result = agent.invoke(
       {"messages": [{"role": "user", "content": "Write a Python code that requests an IP from a web service like ipify and print current IP. Execute that in a sandbox. Do not use third party libraries."}]}
    )   

    for message in result["messages"]:
        message.pretty_print()
