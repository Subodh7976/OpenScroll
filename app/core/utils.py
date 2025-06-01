from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import OpenAI
from groq import Groq
import google.genai as genai
from markdownify import markdownify as md
from playwright.async_api import async_playwright


openai_models = [model.id for model in OpenAI().models.list()]
groq_models = [model.id for model in Groq().models.list().data]
google_models = [m.name.replace("models/", "")
                 for m in genai.Client().models.list()]


def create_llm(model_name: str, **kwargs):
    if model_name in openai_models:
        return ChatOpenAI(model_name=model_name, **kwargs)
    elif model_name in groq_models:
        return ChatGroq(model=model_name, **kwargs)
    elif model_name in google_models:
        return ChatGoogleGenerativeAI(model=model_name, **kwargs)


def convert_markdown(content: str) -> str:
    return md(content)


async def get_page_content(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            response = await page.goto(url, timeout=60000)
            await page.wait_for_load_state('networkidle', timeout=15000)

            # Try to extract <pre>, <article>, or <body> content
            content = await page.content()

            # Try to extract the innerText of main markdown-rich elements
            candidates = ['article', 'main', 'pre', 'body']
            markdown = ""
            for tag in candidates:
                el = await page.query_selector(tag)
                if el:
                    text = await el.inner_text()
                    if text and len(text.strip()) > 200:
                        markdown = text.strip()
                        break

            return markdown or content

        finally:
            await browser.close()
