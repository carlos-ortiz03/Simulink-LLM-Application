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

    # Attempt exact match search
    results = exact_match_search(search_query)

    if not results:
        print("No relevant documents found.")
        return "No relevant documents found."

    # Return the HTML content directly
    return '\n\n'.join([doc.page_content for doc in results])



    

    
    # return '\n\n'.join([
    #     format(doc)
    #     for doc in retriever.invoke(search_query)
    # ])