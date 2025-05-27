from googleapiclient.discovery import build
from typing import List
import ssl

from core.config import settings

ssl._create_default_https_context = ssl._create_unverified_context


def google_search(query: str, search_type: str = "text", max: int = 5) -> List[dict]:
    """
    function for performing google search and fetch the result for a query in a defined domain

    Args:
        query (str): the query to be searched
        search_type (str, optional): type of search (image or text). Defaults to "text".
        max (int, optional): number of results to retrieve. Defaults to 5.

    Returns:
        List[dict]: list of dict (can be empty list) with fields - title, href and body.
    """
    try:
        service = build(
            "customsearch", "v1", developerKey=settings.GOOGLE_DEVELOPER_KEY
        )
        res = (
            service.cse()
            .list(
                q=query,
                cx=settings.SEARCH_ENGINE_IDENTIFIER,
                searchType=search_type if search_type == "image" else None,
                num=max
            )
            .execute()
        )

        return [{"title": item['title'], 'href': item['link'], 'body': item['snippet']} for item in res['items']]
    except:
        return []
