import os
from dotenv import load_dotenv
from langchain.docstore.document import Document

load_dotenv()

def simulink_documentation_lookup(search_query):
    from sim_embeddings import get_embed_fn_and_db
    embed_fn, db = get_embed_fn_and_db()

    # Exact match search using metadata
    def exact_match_search(query):
        results = db._collection.get(where={"block_name": query.strip()})
        if results and 'documents' in results and 'metadatas' in results:
            return [Document(
                page_content=doc,
                metadata=meta
            ) for doc, meta in zip(results['documents'], results['metadatas'])]
        return []

    # Closest match search using embedding similarity
    def closest_match_search(query):
        query_embedding = embed_fn.embed_query(query)  # Use embed_query method to get embeddings
        search_results = db.similarity_search_by_vector(query_embedding)
        if search_results and 'documents' in search_results and 'metadatas' in search_results:
            return [Document(
                page_content=doc,
                metadata=meta
            ) for doc, meta in zip(search_results['documents'], search_results['metadatas'])]
        return []

    # Attempt exact match search
    results = exact_match_search(search_query)

    # If no exact match is found, attempt closest match search
    if not results:
        results = closest_match_search(search_query)

    # If still no results, return a message
    if not results:
        print("No relevant documents found.")
        return "No relevant documents found."

    # Return the HTML content directly
    return '\n\n'.join([doc.page_content for doc in results])
