from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from langgraph.types import interrupt
from pydantic import BaseModel
from typing_extensions import TypedDict
import json

from services.duckduckgo import make_text_request
from services.google import google_search
from services.youtube import search_youtube
from models import StreamingUpdate
from core.config import settings
from .agents import *


TRAVERSAL_NODE = "traversal"
RESEARCH_NODE = "research"
TOPIC_NODE = "topic"
CREATIVE_NODE = "creative"


class ResearchContext(BaseModel):
    source: str
    content: str


class TopicAgentState(TypedDict):
    traversal: TraversalState
    research_data: list[ResearchContext]
    user_preferences: str
    proposed_topics: list[Topic]
    creative_topics: list[Topic]
    selected_topic: Topic

    perform_creative: bool


async def traversal_selection_stage(state: TopicAgentState) -> TopicAgentState:
    writer = get_stream_writer()
    existing_traversal = state.get("traversal", None)
    if existing_traversal is not None:
        existing_traversal = existing_traversal.model_dump_json()
    else:
        existing_traversal = "Not defined"

    writer(StreamingUpdate(node=TRAVERSAL_NODE,
           update="Started traversal selection with configuration - " + existing_traversal))

    response = None
    while not response:
        try:
            response = await traversal_chain.ainvoke({"existing_nodes": existing_traversal})
        except Exception as e:
            writer(StreamingUpdate(node=TRAVERSAL_NODE,
                   update="Error - " + str(e) + "\nRetrying."))

    return {"traversal": response}


async def research_stage(state: TopicAgentState) -> TopicAgentState:
    writer = get_stream_writer()
    traversal = state['traversal'].model_dump()

    search_query = ", ".join([v for _, v in traversal.items()])
    writer(StreamingUpdate(node=RESEARCH_NODE,
           update=f"Started research with query - {search_query}"))

    research_context = []
    writer(StreamingUpdate(node=RESEARCH_NODE,
           update=f"Performing DDG Search with query - {search_query}"))
    ddg_response = make_text_request(search_query, settings.DDG_SEARCH_RESULTS)
    research_context.append(
        ResearchContext(source="Search Engine 1",
                        content=json.dumps(ddg_response))
    )

    writer(StreamingUpdate(node=RESEARCH_NODE,
           update=f"Performing GOOGLE Search with query - {search_query}"))
    google_response = google_search(
        search_query, max=settings.GOOGLE_SEARCH_RESULTS)
    research_context.append(
        ResearchContext(source="Search Engine 2",
                        content=json.dumps(google_response))
    )

    writer(StreamingUpdate(node=RESEARCH_NODE,
           update=f"Performing YOUTUBE Search with query - {search_query}"))
    yt_response = search_youtube(search_query, settings.YOUTUBE_SEARCH_RESULTS)
    research_context.append(
        ResearchContext(source="YOUTUBE",
                        content=json.dumps(yt_response))
    )

    return {
        "research_data": research_context
    }


async def topics_generation_stage(state: TopicAgentState) -> TopicAgentState:
    writer = get_stream_writer()
    user_preferences = state.get('user_preferences', "")
    traversal = state['traversal'].model_dump_json()
    research_context = state['research_data']
    research_context = "\n".join(
        [context.model_dump_json() for context in research_context])

    writer(StreamingUpdate(node=TOPIC_NODE,
           update=f"Started topics generation, with user preferences - {user_preferences}"))

    response = None
    while not response:
        try:
            response: ResearchTopics = await topics_chain.ainvoke({
                'research_context': research_context,
                'traversal': traversal,
                'preferences': user_preferences
            })
        except Exception as e:
            writer(StreamingUpdate(node=TOPIC_NODE,
                   update="Error - " + str(e) + "\nRetrying."))

    return {
        "proposed_topics": response.topics
    }


async def creativity_stage(state: TopicAgentState) -> TopicAgentState:
    writer = get_stream_writer()
    user_preferences = state.get("user_preferences", "")
    traversal = state['traversal'].model_dump_json()
    existing_topics = state['proposed_topics']
    existing_topics = json.dumps(existing_topics)

    writer(StreamingUpdate(node=CREATIVE_NODE,
           update=f"Started Creative Topics generation, with user preferences - {user_preferences}"))

    response = None
    while not response:
        try:
            response: ResearchTopics = await creative_chain.ainvoke({
                'existing_topics': existing_topics,
                'traversal': traversal,
                'preferences': user_preferences
            })
        except Exception as e:
            writer(StreamingUpdate(node=CREATIVE_NODE,
                   update="Error - " + str(e) + "\nRetrying."))

    return {
        "creative_topics": response.topics
    }


async def topic_selection_stage(state: TopicAgentState) -> TopicAgentState:
    if state['perform_creative']:
        topics = state["creative_topics"]
    else:
        topics = state['proposed_topics']

    writer = get_stream_writer()
    writer(StreamingUpdate(node="selection",
                           update="Initialized manual topic selection."))

    response: Topic = interrupt({
        "source": "topic_selection",
        "topics": topics
    })

    return {
        'selected_topic': response
    }


workflow = StateGraph(TopicAgentState)
workflow.add_node("traversal_stage", traversal_selection_stage)
workflow.add_node("research_stage", research_stage)
workflow.add_node("topics_stage", topics_generation_stage)
workflow.add_node("creative_stage", creativity_stage)
workflow.add_node("selection_stage", topic_selection_stage)

workflow.add_edge(START, "traversal_stage")
workflow.add_edge("traversal_stage", "research_stage")
workflow.add_edge("research_stage", "topics_stage")
workflow.add_conditional_edges(
    "topics_stage",
    lambda state: state['perform_creative'],
    {True: "creative_stage", False: "selection_stage"}
)
workflow.add_edge("creative_stage", "selection_stage")
workflow.add_edge("selection_stage", END)
