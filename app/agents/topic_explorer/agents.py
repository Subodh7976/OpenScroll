from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from core.utils import create_llm
from .prompts import *

TRAVERSAL_MODEL = "gemini-2.0-flash"
TOPICS_GENERATOR_MODEL = 'gemini-2.0-flash'
CREATIVE_TOPICS_MODEL = "gemini-2.0-flash"


class TraversalState(BaseModel):
    domain: str = Field(
        "", description="Broad umbrella (K-12, Skill Development, Higher Ed, etc.)")
    group: str = Field(
        "", description="Grade level or experience band (Grade 8, Beginner, Intermediate)")
    track: str = Field(
        "", description="Academic subject or skill category (Biology, Soft Skills, Programming)")
    concept: str = Field(
        "", description="Granular focus area (Cell Division, Business Writing, Color Perception)")


class Topic(BaseModel):
    topic: str = Field(
        "", description="The proposed well researched topic name for the article.")
    format: str = Field(
        "", description="Format to be followed by the content in the article.")
    topic_breakdown: list[str] = Field(
        ..., description="Breakdown of the topic, which described the content to be included in the topic.")
    rationale: str = Field(
        "", description="Rationale or logical reasoning behind the topic selection and breakdown.")


class ResearchTopics(BaseModel):
    topics: list[Topic] = Field(
        ..., description="List of research topics with associated attributes for Article.")


parser = PydanticOutputParser(pydantic_object=TraversalState)
prompt = PromptTemplate(
    template=TRAVERSAL_PROMPT,
    input_variables=['existing_nodes'],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)
llm = create_llm(TRAVERSAL_MODEL, temperature=0.8)
traversal_chain = prompt | llm | parser

parser = PydanticOutputParser(pydantic_object=ResearchTopics)
prompt = PromptTemplate(
    template=TOPICS_GENERATION_PROMPT,
    input_variables=['research_context', 'traversal', 'preferences'],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)
llm = create_llm(TOPICS_GENERATOR_MODEL, temperature=0.7)
topics_chain = prompt | llm | parser

parser = PydanticOutputParser(pydantic_object=ResearchTopics)
prompt = PromptTemplate(
    template=CREATIVE_TOPICS_PROMPT,
    input_variables=['traversal', 'existing_topics', 'preferences'],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)
llm = create_llm(CREATIVE_TOPICS_MODEL, temperature=0.7)
creative_chain = prompt | llm | parser
