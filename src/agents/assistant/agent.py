from agents.utils.agent_utils import create_agent
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

llm = ChatOpenAI(model="gpt-4o")

assistant_agent = create_agent(
    name="assistant",
    model=llm,
    tools=[],
)