from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from core.utils import create_llm
from .prompts import *

TRAVERSAL_MODEL = "gemini-2.0-flash"


class TraversalState(BaseModel):
    domain: str = Field(
        "", description="Broad umbrella (K-12, Skill Development, Higher Ed, etc.)")
    group: str = Field(
        "", description="Grade level or experience band (Grade 8, Beginner, Intermediate)")
    track: str = Field(
        "", description="Academic subject or skill category (Biology, Soft Skills, Programming)")
    concept: str = Field(
        "", description="Granular focus area (Cell Division, Business Writing, Color Perception)")


parser = PydanticOutputParser(pydantic_object=TraversalState)
prompt = PromptTemplate(
    template=TRAVERSAL_PROMPT,
    input_variables=['existing_nodes'],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)
llm = create_llm(TRAVERSAL_MODEL, temperature=0.8)
traversal_chain = prompt | llm | parser