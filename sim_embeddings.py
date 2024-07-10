import os
import json
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.schema import Document
from langchain.vectorstores import Chroma

EMBEDDING_DIR = "data/sim_embeddings"

def get_embed_fn_and_db():
    # Create embedding function
    embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Check if the directory exists
    if not os.path.exists(EMBEDDING_DIR):
        os.makedirs(EMBEDDING_DIR)
        # Load JSON data
        with open('data/simulink_data.json', 'r') as file:
            data = json.load(file)
        
        # Prepare documents
        delimiter = "|||"
        documents = []
        for record in data:
            content = f"{record.get('block_name', '')} {record.get('description', '')}"
            metadata = {
                "block_name": record.get("block_name"),
                "libraries": delimiter.join(record.get("libraries", [])),  # Convert list to delimited string
                "parameters": delimiter.join(["|||".join(param) for param in record.get("parameters", [])])  # Convert nested list to delimited string
            }
            documents.append(Document(page_content=content, metadata=metadata))

        # Initialize Chroma DB with a specific directory for automatic persistence
        db = Chroma.from_documents(documents, embedding_function, persist_directory=EMBEDDING_DIR)
    else:
        # Load the database from the specified directory
        db = Chroma(persist_directory=EMBEDDING_DIR, embedding_function=embedding_function)

    return embedding_function, db

if __name__ == "__main__":
    get_embed_fn_and_db()
