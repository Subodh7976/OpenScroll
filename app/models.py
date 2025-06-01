from pydantic import BaseModel

class StreamingUpdate(BaseModel):
    node: str
    update: str