type YoucomSearchResult = {
  url: string;
  title?: string;
  description?: string;
  snippets?: string[];
};

type YoucomSearchResponse = {
  results?: {
    web?: YoucomSearchResult[];
    news?: YoucomSearchResult[];
  };
};

function getYoucomApiKey(): string | null {
  return process.env.YDC_API_KEY ?? null;
}

function formatResults(results: YoucomSearchResult[]): string {
  if (results.length === 0) {
    return 'No results found.';
  }

  return results
    .slice(0, 5)
    .map((result, index) => {
      const snippets = result.snippets?.length ? `\n  Snippets: ${result.snippets.join(' | ')}` : '';
      const description = result.description ? `\n  Summary: ${result.description}` : '';
      return `${index + 1}. ${result.title ?? 'Untitled result'}\n  URL: ${result.url}${description}${snippets}`;
    })
    .join('\n\n');
}

export async function searchWeb(
  query: string,
  count = 5,
): Promise<{ query: string; result: string }> {
  const apiKey = getYoucomApiKey();
  if (!apiKey) {
    return {
      query,
      result: 'You.com search is not enabled. Set YDC_API_KEY to use the optional external web search tool.',
    };
  }

  const url = new URL('https://ydc-index.io/v1/search');
  url.searchParams.set('query', query);
  url.searchParams.set('count', String(count));
  url.searchParams.set('safesearch', 'moderate');

  try {
    const resp = await fetch(url, {
      headers: {
        'X-API-Key': apiKey,
      },
    });

    if (!resp.ok) {
      const body = await resp.text();
      return {
        query,
        result: `You.com search failed with HTTP ${resp.status}: ${body}`,
      };
    }

    const data = (await resp.json()) as YoucomSearchResponse;
    const webResults = data.results?.web ?? [];
    const newsResults = data.results?.news ?? [];

    return {
      query,
      result: [
        `Query: ${query}`,
        webResults.length > 0 ? `Web results:\n${formatResults(webResults)}` : 'Web results: none',
        newsResults.length > 0 ? `News results:\n${formatResults(newsResults)}` : 'News results: none',
      ].join('\n\n'),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      query,
      result: `You.com search failed: ${message}`,
    };
  }
}
