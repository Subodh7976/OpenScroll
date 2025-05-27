from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from openai import OpenAI
from groq import Groq
import google.genai as genai

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
