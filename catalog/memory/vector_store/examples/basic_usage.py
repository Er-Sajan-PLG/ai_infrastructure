"""Minimal example: add embeddings, search, delete."""

from vector_store import VectorStore

store = VectorStore(max_size=100)

# Add some embeddings (3D for simplicity)
store.add("paris", [1.0, 0.0, 0.0], {"country": "France"})
store.add("london", [0.0, 1.0, 0.0], {"country": "UK"})
store.add("tokyo", [0.0, 0.0, 1.0], {"country": "Japan"})
store.add("berlin", [1.0, 1.0, 0.0], {"country": "Germany"})

# Search for something similar to Paris
results = store.search([1.0, 0.0, 0.0], k=3)
print("Query: [1.0, 0.0, 0.0] (Paris-like)")
for r in results:
    print(f"  {r.id}: score={r.score:.4f} metadata={r.metadata}")

# Delete and verify
store.delete("london")
print(f"\nAfter deleting London: {len(store)} items")

# Search again
results = store.search([0.0, 1.0, 0.0], k=3)
print("\nQuery: [0.0, 1.0, 0.0] (London-like, but London deleted)")
for r in results:
    print(f"  {r.id}: score={r.score:.4f} metadata={r.metadata}")
