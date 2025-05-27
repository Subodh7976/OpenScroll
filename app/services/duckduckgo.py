from duckduckgo_search import DDGS

search_client = DDGS()


def make_text_request(query: str, results: int = 10) -> list[dict]:
    """
    makes a text search request to duckduckgo search engine and retrieves specified results

    Args:
        query (str): search query
        results (int, optional): number of results. Defaults to 10.

    Returns:
        list[dict]: list of dict (can be empty list) with fields - title, href and body.
    """
    try:
        results = search_client.text(query, max_results=results)
    except Exception as e:
        print("Error while searching duckduckgo client - ", e)
        results = []

    return results
