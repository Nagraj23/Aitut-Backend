import chromadb

# Point to your persistent directory
client = chromadb.PersistentClient(path="./chroma_data")

# List all indexed collections
collections = client.list_collections()
print("Available Collections:")
for col in collections:
    print(f"- {col.name}")
    
# Get the specific collection
collection = client.get_collection(name="solapur_cse_1_chemistry")

# Peek at the first 5 items
data = collection.peek(limit=5)
print(f"Total items in collection: {collection.count()}")
print("Sample Data:", data['documents'])