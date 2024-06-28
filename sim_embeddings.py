import os
import json
import torch
from transformers import AutoTokenizer, AutoModel
from langchain_community.vectorstores import Chroma
from langchain.docstore.document import Document

class SentenceTransformerEmbeddings:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(
            'sentence-transformers/all-mpnet-base-v2',
        )
        self.model = AutoModel.from_pretrained(
            'sentence-transformers/all-mpnet-base-v2',
        )

    def embed_fn(self, sentences: list[str]) -> torch.Tensor:
        encoded_input = self.tokenizer(
            sentences,
            padding=True,
            truncation=True,
            return_tensors='pt',
        )
        # Compute token embeddings
        with torch.no_grad():
            model_output = self.model(**encoded_input)
        # Perform pooling
        pooled_output = self.mean_pooling(
            model_output,
            encoded_input['attention_mask'],
        )
        return pooled_output

    def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return self.embed_fn(documents).tolist()

    def embed_query(self, query: str) -> list[float]:
        return self.embed_fn([query]).tolist()[0]

    # Mean Pooling - Take attention mask into account for correct averaging
    @staticmethod
    def mean_pooling(model_output: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        token_embeddings = model_output[0]
        input_mask_expanded = (attention_mask
                            .unsqueeze(-1)
                            .expand(token_embeddings.size())
                            .float())
        return (
            torch.sum(token_embeddings * input_mask_expanded, 1) /
            torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        )

def format_parameters(parameters):
    formatted_parameters = []
    for param_set in parameters:
        formatted_parameters.append("\n".join(param_set))
    return "\n\n".join(formatted_parameters)

# Ensure the JSON file with data exists by running fetch_web.py first
json_file_path = os.path.join('data', 'simulink_data.json')
if not os.path.exists(json_file_path):
    os.system('python fetch_web.py')

# Load documents from JSON file
with open(json_file_path, 'r') as f:
    documents_json = json.load(f)

# Combine the relevant fields into a single text content
documents = [
    Document(
        page_content=f"Block: {doc['block_name']}\nLibraries: {', '.join(doc['libraries'])}\nParameters:\n" + format_parameters(doc['parameters']),
        metadata={"block_name": doc['block_name'], "source": doc['source']}
    ) for doc in documents_json
]

embed_fn = SentenceTransformerEmbeddings()

persist_directory = './data/om_embeddings'

# Ensure the persist directory exists
os.makedirs(persist_directory, exist_ok=True)

if not os.path.exists(os.path.join(persist_directory, 'chroma.sqlite3')):
    print("Creating new vector store...")
    db = Chroma.from_documents(
        documents,
        embed_fn,
        persist_directory=persist_directory,
    )
else:
    print("Loading existing vector store...")
    db = Chroma(
        embedding_function=embed_fn.embed_documents,
        persist_directory=persist_directory,
    )

# Expose the embedding function and database for use in other modules
def get_embed_fn_and_db():
    return embed_fn, db
