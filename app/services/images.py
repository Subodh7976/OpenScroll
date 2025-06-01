from google import genai
from google.genai import types
from uuid import uuid4
from groq import Groq
import mimetypes
import os

from core.config import settings


os.makedirs(settings.BASE_IMAGE_PATH, exist_ok=True)

groq_client = Groq(api_key=settings.GROQ_API_KEY)
genai_client = genai.Client(
    api_key=settings.GOOGLE_API_KEY
)
def validate_image(query: str, image_url: str) -> bool:
    completion = groq_client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Does this image accurately follows the query - {query}. Your response strictly should only be - YES or NO"
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }
        ],
        temperature=0,
        max_completion_tokens=10,
        top_p=1,
        stream=False,
        stop=None,
    )

    response = completion.choices[0].message.content
    if "YES" in response:
        return True
    return False

def save_binary_file(file_name, data):
    f = open(file_name, "wb")
    f.write(data)
    f.close()
    print(f"File saved to to: {file_name}")


def generate_image(query: str):
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=f"""Generate an accurate image described as - {query}"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        response_modalities=[
            "IMAGE",
            "TEXT"
        ],
        response_mime_type="text/plain",
    )

    files = []
    response = ""
    for chunk in genai_client.models.generate_content_stream(
        model=settings.IMAGE_MODEL,
        contents=contents,
        config=generate_content_config,
    ):
        if (
            chunk.candidates is None
            or chunk.candidates[0].content is None
            or chunk.candidates[0].content.parts is None
        ):
            continue
        if chunk.candidates[0].content.parts[0].inline_data and chunk.candidates[0].content.parts[0].inline_data.data:
            file_name = str(uuid4())
            inline_data = chunk.candidates[0].content.parts[0].inline_data
            data_buffer = inline_data.data
            file_extension = mimetypes.guess_extension(inline_data.mime_type)
            save_binary_file(f"{file_name}{file_extension}", data_buffer)
            files.append(file_name)
        else:
            response += chunk.text
    return files, response