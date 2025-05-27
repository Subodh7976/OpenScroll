from googleapiclient.discovery import build
import os

from core.config import settings


SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def youtube_authenticate():
    """
    Authenticate and return YouTube service object
    """
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    api_service_name = "youtube"
    api_version = "v3"

    youtube = build(api_service_name, api_version,
                    developerKey=settings.YOUTUBE_API_KEY)
    return youtube


youtube = youtube_authenticate()


def search_youtube(query: str, max_results: int = 10) -> list[dict]:
    """
    Search YouTube videos using the API

    Args:
        query: str - Search query string
        max_results: int - Maximum number of results to return (default: 10, max: 50)

    Returns:
        list[dict]: including title, channel, publishTime and body of the youtube result
    """
    try:
        request = youtube.search().list(
            part="snippet",
            q=query,
            maxResults=max_results,
            order='relevance',
            type="vide"
        )

        response = request.execute()
        items = response.get("items", [])
        return [
            {
                'title': item['snippet']['title'],
                "channel": item['snippet']['channelTitle'],
                "publishTime": item['snippet']['publishTime'],
                'body': item['snippet']['description']
            }
            for item in items]
    except:
        return []
