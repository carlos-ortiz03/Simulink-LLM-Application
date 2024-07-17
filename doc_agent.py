import json
from sim_embeddings import get_embed_fn_and_db

def simulink_documentation_lookup(search_query):
    embed_fn, db = get_embed_fn_and_db()

    # Extract block type from search query
    block_type = search_query.split(": ")[1].split("\n")[0].strip()

    # Exact match search using metadata
    def exact_match_search(query):
        results = db._collection.get(where={"block_type": query})
        if results and 'metadatas' in results and results['metadatas']:
            metadata = results['metadatas'][0]
            metadata["description"] = metadata["description"][11:]
            # Convert delimited strings back to lists
            metadata['libraries'] = metadata['libraries'].split("|||")
            metadata['parameters'] = [param.split(" || ") for param in metadata['parameters'].split("|||")] if metadata['parameters'] else [[]]
            return [metadata]  # Return the first matching metadata in a list
        return []

    # Attempt exact match search
    result = exact_match_search(block_type)

    # If an exact match is found, return the result
    if result:
        return result

    # If no exact match is found, attempt closest match search
    docs = db.similarity_search(search_query)
    if docs:
        matched_metadata = docs[0].metadata
        matched_metadata["description"] = matched_metadata["description"][11:]
        # Convert delimited strings back to lists
        matched_metadata['libraries'] = matched_metadata['libraries'].split("|||")
        matched_metadata['parameters'] = [param.split(" || ") for param in matched_metadata['parameters'].split("|||")]
        return [matched_metadata]  # Return as a list for consistency

    # If still no result, return a message
    return ["No relevant documents found."]

# Example usage
if __name__ == "__main__":
    query = "block name: ExampleBlock\nblock description: Example description"
    print(simulink_documentation_lookup(query))
