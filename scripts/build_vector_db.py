import os
import sys
import torch
from langchain_community.document_loaders import DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from configs import models, settings

def main():
    print("Starting the vector database build process...")
    print(f"Loading documents from: {settings.CORPUS_DIR}")
    loader = DirectoryLoader(settings.CORPUS_DIR, glob="**/*.md", show_progress=True)
    documents = loader.load()
    if not documents:
        print(f"Error: No documents found in {settings.CORPUS_DIR}")
        return
    print(f"Loaded {len(documents)} documents.")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split documents into {len(chunks)} chunks.")

    print(f"Loading embedding model: {models.EMBEDDING_MODEL}")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    
    embedding_model = HuggingFaceEmbeddings(
        model_name=models.EMBEDDING_MODEL,
        model_kwargs={'device': device}, # <-- *** 关键修正 ***
        encode_kwargs={'normalize_embeddings': True}
    )
    print("Embedding model loaded successfully.")

    print("Creating vector store... This may take a while.")
    vector_store = FAISS.from_documents(chunks, embedding_model)
    
    vector_store.save_local(settings.VECTOR_DB_PATH)
    print(f"Vector store built and saved to: {settings.VECTOR_DB_PATH}")

if __name__ == "__main__":
    main()