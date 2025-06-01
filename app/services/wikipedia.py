import requests
import wikipediaapi

from core.utils import (
    convert_markdown,
    get_page_content
)


def make_wikipedia_query(query: str, language: str = 'en', limit: int = 5) -> list[dict]:
    """Search using Wikimedia REST API"""

    results = []
    try:
        base_url = f'https://api.wikimedia.org/core/v1/wikipedia/{language}'
        endpoint = '/search/page'
        url = base_url + endpoint

        headers = {
            'User-Agent': 'WikipediaSearchApp (your-email@example.com)'
        }

        params = {
            'q': query,
            'limit': limit
        }

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()

            for page in data['pages']:
                title = page['title']
                description = page.get(
                    'description', 'No description available')
                article_url = f'https://{language}.wikipedia.org/wiki/{page["key"]}'
                results.append({
                    'title': title,
                    'body': description,
                    'href': article_url
                })
    except:
        pass

    return results


async def get_wiki_page(page_url: str) -> str:
    wiki_wiki = wikipediaapi.Wikipedia(
        user_agent='MyProjectName (merlin@example.com)',
        language='en',
        extract_format=wikipediaapi.ExtractFormat.HTML
    )
    content = ""
    try:
        page_title = page_url.split("/")[-1]
        page_py = wiki_wiki.page(page_title)
        if page_py.exists():
            content = page_py.text
    except:
        content = await get_page_content(page_url)

    return convert_markdown(content)
