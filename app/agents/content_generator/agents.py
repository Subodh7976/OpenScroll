from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool, BaseTool
from langgraph.types import StreamWriter
from pydantic import BaseModel, Field
from typing import Dict, Any
import json

from services.duckduckgo import make_text_request, make_image_request
from services.wikipedia import make_wikipedia_query
from services.images import validate_image, generate_image
from core.config import settings
from core.utils import create_llm
from models import StreamingUpdate
from .prompts import *

RESEARCH_REFINE_NODE = "research_refine"
SECTION_NODE = "section"

# Research & Refinement Agent
class Result(BaseModel):
    title: str = Field(description="Title of the Source")
    description: str = Field(
        description="Brief description describing the source")
    href: str = Field(description="hyperlink or URL of the source.")


class SearchResults(BaseModel):
    relevant_results: list[Result] = Field(description="")


@tool
def search_query(query: str) -> list[dict]:
    '''
    performs a web search with given query and returns results in structured format. 
    Returns the search results as a list of dict, with each containing "title", "href" and "body" of the web search result.

    Args:
        query: search query for web search
    '''
    results = make_text_request(query, settings.RESEARCH_WEB_RESULTS)
    return results


@tool
def search_wikipedia(query: str) -> list[dict]:
    '''
    performs a wikipedia keyword search with given query and returns results in structured format. 
    Returns the search results as a list of dict, with each containing "title", "href" and "body" of the wikipedia search result.

    Args:
        query: search query for wikipedia (keyword based search)
    '''
    results = make_wikipedia_query(query, limit=settings.RESEARCH_WIKI_RESULTS)
    return results


class ResearchRefineAgent:
    def __init__(
        self,
        tools: list[BaseTool],
        max_iterations: int = 5
    ):
        llm = create_llm(settings.CONTENT_RESEARCH_MODEL)
        self.tools = {tool.name: tool for tool in tools}
        self.llm_with_tools = llm.bind_tools(tools)
        self.max_iterations = max_iterations
        self.parser = PydanticOutputParser(pydantic_object=SearchResults)
        self.system_message = SystemMessage(
            content=RESEARCH_REFINE_PROMPT.format(
                format_instructions=self.parser.get_format_instructions()
            )
        )

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        if tool_name in self.tools:
            try:
                return json.dumps(self.tools[tool_name].invoke(tool_args))
            except Exception as e:
                print("Error while executing tool - ", e)
                return f"Error while executing tool - {str(e)}"
        else:
            return f"Tool name not found: {tool_name}"

    async def run(self, title: str, topic_breakdown: str, writer: StreamWriter = None) -> SearchResults | None:
        messages = [
            self.system_message,
            HumanMessage(
                content=f"**Article Title:**\n{title}\n**Article Breakdown:**\n{topic_breakdown}\nNow use the necessary tools, gather the context, refine and generate the final structured response.")
        ]

        iterations = 0
        while iterations < self.max_iterations:
            iterations += 1
            writer(StreamingUpdate(node=RESEARCH_REFINE_NODE,
                                   update=f"--- Performing Iteration - {iterations} --- "))

            response: AIMessage = await self.llm_with_tools.ainvoke(messages)
            messages.append(response)

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    tool_id = tool_call['id']

                    writer(StreamingUpdate(node=RESEARCH_REFINE_NODE,
                                           update=f"Executing tool: {tool_name} with args: {tool_args}"))

                    tool_result = self.execute_tool(tool_name, tool_args)
                    messages.append(
                        ToolMessage(
                            content=tool_result,
                            tool_call_id=tool_id
                        )
                    )

                    writer(StreamingUpdate(node=RESEARCH_REFINE_NODE,
                                           update=f"Tool result: {tool_result[:100]}..."))
            else:
                if response.content:
                    try:
                        response = self.parser.parse(response.content)
                        return response
                    except Exception as e:
                        messages.append(HumanMessage(
                            content="Please provide your final analysis in the specified JSON format."))
                else:
                    messages.append(HumanMessage(
                        content="Please provide your final analysis in the specified JSON format."))

        return


tools = [search_query, search_wikipedia]
research_refine_agent = ResearchRefineAgent(tools)

# Summarizer Agent
llm = create_llm(settings.SUMMARIZER_MODEL)
prompt = PromptTemplate(
    template=SUMMARIZER_PROMPT,
    input_variables=['title', 'content']
)
summarizer_chain = prompt | llm

# Planner agent
class Section(BaseModel):
    title: str = Field(description="Title of the section")
    description: str = Field(
        description="Brief description describing what should be included in the section.")


class ArticlePlan(BaseModel):
    sections: list[Section]


parser = PydanticOutputParser(pydantic_object=ArticlePlan)
llm = create_llm(settings.PLANNER_MODEL)
prompt = PromptTemplate(
    template=PLANNER_PROMPT,
    input_variables=['title', 'research_context', 'topic_breakdown', 'format'],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)
planner_chain = prompt | llm | parser


# Writer agents
@tool
async def web_image_search(keywords: str) -> str:
    '''
    search web for relevant images, and validates the image against the keywords

    Args:
        keywords: str - keywords accurately defining the image
    '''
    results = make_image_request(keywords, 5)
    for result in results:
        image_url = result.get("image", None)
        if image_url and validate_image(keywords, image_url):
            source_url = result.get("url", image_url)
            return f'<img src="{image_url}" width=600 height=600><br>\n[Source]({source_url})'

    return "No relevant images found."


@tool
async def generate_ai_image(description: str) -> tuple[str, list[str]]:
    '''
    generates image with the given description using ai. Returns ai generated response, and list of filenames where images are stored.

    Args:
        description: str - accurate definition of image to be generated.
    '''
    response = generate_image(description)
    return response


class WriterAgent:
    def __init__(
        self,
        tools: list[BaseTool],
        max_iterations: int = 5
    ):
        llm = create_llm(settings.WRITER_MODEL)
        self.tools = {tool.name: tool for tool in tools}
        self.llm_with_tools = llm.bind_tools(tools)
        self.max_iterations = max_iterations
        self.system_message = SystemMessage(
            content=RESEARCH_REFINE_PROMPT
        )

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> str:
        if tool_name in self.tools:
            try:
                return json.dumps(self.tools[tool_name].invoke(tool_args))
            except Exception as e:
                print("Error while executing tool - ", e)
                return f"Error while executing tool - {str(e)}"
        else:
            return f"Tool name not found: {tool_name}"

    async def run(
        self,
        article_title: str,
        section_title: str,
        section_description: str,
        context: str,
        writer: StreamWriter = None
    ) -> SearchResults | None:
        messages = [
            self.system_message,
            HumanMessage(
                content=f"**Article Title:** {article_title}\n**Section Title:** {section_title}\n**Section Description:** {section_description}\n**Research Context:**\n```text\n{context}\n```\n**Now, write the content for the specified section, adhering to all instructions.**")
        ]

        iterations = 0
        while iterations < self.max_iterations:
            iterations += 1
            writer(StreamingUpdate(node=SECTION_NODE,
                                   update=f"--- Performing Iteration - {iterations} --- "))

            response: AIMessage = await self.llm_with_tools.ainvoke(messages)
            messages.append(response)

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    tool_id = tool_call['id']

                    writer(StreamingUpdate(node=SECTION_NODE,
                                           update=f"Executing tool: {tool_name} with args: {tool_args}"))

                    tool_result = self.execute_tool(tool_name, tool_args)
                    messages.append(
                        ToolMessage(
                            content=tool_result,
                            tool_call_id=tool_id
                        )
                    )

                    writer(StreamingUpdate(node=RESEARCH_REFINE_NODE,
                                           update=f"Tool result: {tool_result[:100]}..."))
            else:
                if response.content:
                    return response.content
                else:
                    messages.append(HumanMessage(
                        content="Please provide your final response."))

        return


tools = [web_image_search, generate_ai_image]
writer_agent = WriterAgent(tools)

# Intro-Conclusion Agent
class IntroConclusion(BaseModel):
    introduction: str
    conclusion: str


parser = PydanticOutputParser(pydantic_object=IntroConclusion)
llm = create_llm(settings.WRITER_MODEL)
prompt = PromptTemplate(
    template=INTRO_CONCLUSION_PROMPT,
    input_variables=['title', 'sections', 'format', 'topic_breakdown'],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)
intro_conclusion_chain = prompt | llm | parser


# Concise Writer Agent
prompt = PromptTemplate(
    template=CONCISE_CONTENT_PROMPT,
    input_variables=['title', 'content', 'format', 'topic_breakdown']
)
concise_content_chain = prompt | llm
