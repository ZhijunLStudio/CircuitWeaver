import os
from configs import settings

def load_corpus_content():
    """
    Loads the original, full markdown document content for context if needed.
    This is now primarily for reference, as RAG is the main retrieval method.
    """
    # This function can be expanded later if we need to load the full text.
    # For now, RAG doesn't require loading the whole file into context.
    print("RAG is used for documentation retrieval. Full corpus loading skipped.")
    return "Documentation is accessed via RAG."