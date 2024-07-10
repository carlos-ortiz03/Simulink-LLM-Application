import json
from sim_embeddings import get_embed_fn_and_db

def simulink_documentation_lookup(search_query):
    embed_fn, db = get_embed_fn_and_db()

    # Extract block name from search query
    block_name = search_query.split(": ")[1].split("\n")[0]
    block_name.strip()

    # Exact match search using metadata
    def exact_match_search(query):
        results = db._collection.get(where={"block_name": query})
        if results and 'documents' in results and 'metadatas' in results:
            return [meta for meta in results['metadatas']]
        return []

    # Attempt exact match search
    result = exact_match_search(block_name)

    # If no exact match is found, attempt closest match search
    if not result:
        docs = db.similarity_search(search_query)
        if docs:
            matched_metadata = docs[0].metadata
            return matched_metadata

    # If still no result, return a message
    return "No relevant documents found."

if __name__ == "__main__":
    # Example search
    search_query = "The block_name: Sine Wave\nThe block description: The Sine Wave block generates a sinusoidal waveform."

    result = simulink_documentation_lookup(search_query)
    print(result)
