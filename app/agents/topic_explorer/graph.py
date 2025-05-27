from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from pydantic import BaseModel
from typing_extensions import TypedDict

from .agents import *


TRAVERSAL_NODE = "traversal"


class StreamingUpdate(BaseModel):
    node: str
    update: str

class ResearchContext(BaseModel):
    web_search: str
    youtube: str
    

class TopicAgentState(TypedDict):
    traversal: TraversalState


async def traversal_selection_stage(state: TopicAgentState) -> TopicAgentState:
    writer = get_stream_writer()
    existing_traversal = state['traversal']
    existing_traversal = existing_traversal.model_dump_json()

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
    pass
