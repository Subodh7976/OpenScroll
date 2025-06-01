from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from langgraph.types import interrupt
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from models import StreamingUpdate
import asyncio

from core.utils import get_page_content
from services.wikipedia import get_wiki_page
from .agents import (
    research_refine_agent,
    summarizer_chain,
    planner_chain,
    writer_agent,
    intro_conclusion_chain,
    concise_content_chain,
    ArticlePlan,
    Section,
    IntroConclusion
)

RESEARCH_REFINE_NODE = "research_refine"
PLANNER_NODE = "planner"
COMPREHENSIVE_CONTENT_NODE = "comprehensive_content"
CONCISE_CONTENT_NODE = "concise_content"


class SectionContent(Section):
    content: str


class Source(BaseModel):
    title: str
    href: str
    summary: str


class ComprehensiveArticle(BaseModel):
    intro: str = Field(default="")
    section: list[SectionContent]
    conclusion: str = Field(default="")
    sources: list[Source]


class ConciseArticle(BaseModel):
    content: str
    sources: list[Source]


class SourceContext(BaseModel):
    title: str
    href: str
    raw_content: str
    summary: str


class ContentGeneratorType(TypedDict):
    topic_title: str
    format: str
    topic_breakdown: list[str]

    context_sources: list[SourceContext]
    article_plan: ArticlePlan
    comprehensive_article: ComprehensiveArticle
    concise_article: ConciseArticle

    human_feedback: bool


def structure_context(raw_context: list[SourceContext]) -> str:
    context = ""
    for i in raw_context:
        context += f"**{i.title}**\n**Source:** {i.href}\n{i.summary}\n---\n"
    return context


async def research_refine_stage(state: ContentGeneratorType) -> ContentGeneratorType:
    writer = get_stream_writer()
    title = state['topic_title']
    topic_breakdown = state['topic_breakdown']

    writer(StreamingUpdate(node=RESEARCH_REFINE_NODE,
                           update='Starting Research and Refinement stage.'))
    response = await research_refine_agent.run(title, "\n".join(topic_breakdown), writer)
    if not response:
        interrupt({
            "source": "research_refine",
            "cause": "Failed to generate a response."
        })
    else:
        writer(StreamingUpdate(node=RESEARCH_REFINE_NODE,
                               update="Starting context building"))

        source_results = response.relevant_results

        async def process_source(source_url: str) -> dict:
            writer(StreamingUpdate(node=RESEARCH_REFINE_NODE,
                                   update=f"Processing page - {source_url}"))
            if "wikipedia" in source_url:
                raw_content = await get_wiki_page(source_url)
            else:
                raw_content = await get_page_content(source_url)

            try:
                summary = await summarizer_chain.ainvoke({"title": title, "content": raw_content})
            except Exception as e:
                writer(StreamingUpdate(node=RESEARCH_REFINE_NODE,
                                       update=f"Found error in summarization - {e}"))
                summary = raw_content[:1000]

            return {"summary": summary, "content": raw_content}

        tasks = []
        for result in source_results:
            tasks.append(process_source(result.href))

        results = await asyncio.gather(*tasks)

        context_sources = []
        for result, source in zip(results, source_results):
            context_sources.append(
                SourceContext(
                    title=source.title,
                    href=source.href,
                    raw_content=result['content'],
                    summary=result['summary']
                )
            )

        return {
            "context_sources": context_sources
        }


async def planner_stage(state: ContentGeneratorType) -> ContentGeneratorType:
    writer = get_stream_writer()
    title = state['topic_title']
    format = state['format']
    topic_breakdown = state['topic_breakdown']
    research_context = state['context_sources']

    writer(StreamingUpdate(node=PLANNER_NODE,
                           update="Started planning article"))
    plan = None
    while plan is None:
        try:
            plan: ArticlePlan = await planner_chain.ainvoke(
                {"title": title, "topic_breakdown": ", ".join(topic_breakdown),
                 "format": format, "research_context": structure_context(research_context)})
        except Exception as e:
            writer(StreamingUpdate(node=PLANNER_NODE,
                                   update=f"Got an error - {str(e)}"))

    return {
        "article_plan": plan
    }


async def comprehensive_content_stage(state: ContentGeneratorType) -> ContentGeneratorType:
    writer = get_stream_writer()
    title = state['topic_title']
    format = state['format']
    topic_breakdown = state['topic_breakdown']
    research_context = state['context_sources']
    research_context_raw = structure_context(research_context)
    article_plan = state['article_plan']

    sections: list[SectionContent] = []
    for section in article_plan.sections:
        writer(StreamingUpdate(node=COMPREHENSIVE_CONTENT_NODE,
                               update=f"Processing section - {section.title}"))
        section_content = await writer_agent.run(
            title,
            section.title,
            section.description,
            research_context_raw,
            writer
        )
        sections.append(SectionContent(
            title=section.title,
            description=section.description,
            content=section_content
        ))

    intro_conclusion_response = None
    while intro_conclusion_response is None:
        writer(StreamingUpdate(node=COMPREHENSIVE_CONTENT_NODE,
                               update="Processing intro-conclusion sections"))
        try:
            intro_conclusion_response: IntroConclusion = await intro_conclusion_chain.ainvoke({
                "title": title,
                "format": format,
                "sections": "\n".join([f"## {i.title}\n{i.content}" for i in sections]),
                "topic_breakdown": ", ".join(topic_breakdown)
            })
        except Exception as e:
            writer(StreamingUpdate(node=COMPREHENSIVE_CONTENT_NODE,
                                   update=f"Got an error - {str(e)}"))

    sources = []
    for source in research_context:
        sources.append(Source(
            title=source.title,
            href=source.href,
            summary=source.summary
        ))

    return {
        "comprehensive_article": ComprehensiveArticle(
            intro=intro_conclusion_response.introduction,
            section=sections,
            conclusion=intro_conclusion_response.conclusion,
            sources=sources
        )
    }


async def concise_content_stage(state: ContentGeneratorType) -> ContentGeneratorType:
    writer = get_stream_writer()
    ['title', 'content', 'format', 'topic_breakdown']
    title = state['topic_title']
    format = state['format']
    topic_breakdown = ", ".join(state['topic_breakdown'])

    article = state['comprehensive_article']
    content = article.intro
    for i in article.section:
        content += f"## {i.title}\n{i.content}\n"
    content += "\n" + article.conclusion

    response = None
    while response is None:
        try:
            response = await concise_content_chain.ainvoke({
                "title": title, "format": format,
                "content": content, "topic_breakdown": topic_breakdown
            })
        except Exception as e:
            writer(StreamingUpdate(node=CONCISE_CONTENT_NODE, 
                                   update=f"Got an error - {str(e)}"))
    
    return {
        "concise_article": ConciseArticle(content=response, 
                                          sources=article.sources)
    }

graph = StateGraph(ContentGeneratorType)
graph.add_node("research_stage", research_refine_stage)
graph.add_node("planner_stage", planner_stage)
graph.add_node("comprehensive_content_stage", comprehensive_content_stage)
graph.add_node("concise_content_stage", concise_content_stage)

graph.add_edge(START, "research_stage")
graph.add_edge("research_stage", "planner_stage")
graph.add_edge("planner_stage", "comprehensive_content_stage")
graph.add_edge("comprehensive_content_stage", "concise_content_stage")
graph.add_edge("concise_content_edge", END)
