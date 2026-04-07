import chromadb
from config import MEMORY_PATH

class Memory:
    def __init__(self, persistent=False):
        if persistent:
            self.client = chromadb.PersistentClient(path=MEMORY_PATH)
        else:
            # OPTION 1: Use ephemeral (in-memory) storage for session-only memory
            self.client = chromadb.EphemeralClient()
            
        self.collection = self.client.get_or_create_collection("memory")

    def clear_session(self):
        """Manually clear the collection to start fresh."""
        print("[Memory] Clearing session memory...")
        self.client.delete_collection("memory")
        self.collection = self.client.get_or_create_collection("memory")

    def store(self, text):
        import uuid
        self.collection.add(
            documents=[text],
            ids=[str(uuid.uuid4())]
        )

    def get_context(self, query_text, n_results=5):
        # Only query if there is actually data in the collection
        if self.collection.count() == 0:
            return "No research yet."
            
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        if results['documents'] and results['documents'][0]:
            return "\n---\n".join(results['documents'][0])
        return "No relevant memory found."