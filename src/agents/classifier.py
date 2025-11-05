from enum import Enum
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini")

class ClassifyTypes(Enum):
    IT_SCRUM = "it_scrum"
    GENERAL_SCRUM = "general_scrum"
    GENERAL = "general"

# Pydantic model for structured output
class ClassificationResult(BaseModel):
    classification: Literal["it_scrum", "general_scrum", "general"] = Field(
        description="Classification result must be one of: it_scrum, general_scrum, general"
    )

parser = PydanticOutputParser(pydantic_object=ClassificationResult)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an expert at classifying user inputs.\n\n"
            "Classify the input into one of the following categories:\n"
            "- it_scrum: IT/development related scrum tasks\n"
            "- general_scrum: General scrum tasks\n"
            "- general: General questions or tasks\n\n"
            "{format_instructions}"
        ),
        (
            "human",
            "{message}"
        )
    ]
).partial(format_instructions=parser.get_format_instructions())


classifier = prompt | llm | parser