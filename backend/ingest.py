# ingest.py
import os
import pandas as pd
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions

# Load environment variables
load_dotenv("keys.env")

EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

def get_collection():
    client = chromadb.PersistentClient(path="chroma_db")
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return client.get_or_create_collection(name="hr_policies", embedding_function=ef)

def ingest_from_txt(path="data/hr_policies.txt"):
    """Ingest policies from a TXT file (format: PolicyName: Description)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found.")
    
    coll = get_collection()
    docs, metas, ids = [], [], []
    
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    
    # Split by double newlines to separate policies, or by single newlines if no double newlines
    if '\n\n' in content:
        sections = content.split('\n\n')
    else:
        sections = content.split('\n')
    
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
            
        if ":" in section:
            # Split only on the first colon to handle policy descriptions with colons
            parts = section.split(":", 1)
            if len(parts) == 2:
                policy_name = parts[0].strip()
                policy_content = parts[1].strip()
                
                # If policy content is very short, it might just be a title - use the whole section
                if len(policy_content) < 20:
                    policy_content = section
            else:
                policy_name = f"Policy_{i+1}"
                policy_content = section
        else:
            policy_name = f"Policy_{i+1}"
            policy_content = section
        
        docs.append(policy_content)
        metas.append({"policy": policy_name})
        ids.append(f"txt_{i}")
    
    if not docs:
        print("No valid policy content found in TXT file.")
        return
    
    # Clear existing collection and add new data
    try:
        existing = coll.get()
        if existing["ids"]:
            coll.delete(ids=existing["ids"])
            print(f"Cleared {len(existing['ids'])} existing documents.")
    except:
        pass
    
    # Add new documents
    coll.add(documents=docs, metadatas=metas, ids=ids)
    print(f"Successfully ingested {len(docs)} policies into Chroma collection 'hr_policies' from TXT.")
    
    # Debug: Print first few entries to verify content
    print("\nFirst few policies ingested:")
    for i, (doc, meta) in enumerate(zip(docs[:3], metas[:3])):
        print(f"{i+1}. {meta['policy']}: {doc[:100]}...")

def ingest_from_csv(path="data/hr_policies.csv"):
    """Ingest policies from a CSV with columns: Policy, Description."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found.")
    
    df = pd.read_csv(path)
    
    # Handle different possible column names
    policy_col = None
    desc_col = None
    
    for col in df.columns:
        if col.lower() in ['policy', 'policy_name', 'name', 'title']:
            policy_col = col
        elif col.lower() in ['description', 'content', 'details', 'text']:
            desc_col = col
    
    if not policy_col or not desc_col:
        available_cols = list(df.columns)
        raise ValueError(f"CSV must have policy and description columns. Available columns: {available_cols}")
    
    coll = get_collection()
    docs = df[desc_col].astype(str).tolist()
    metas = [{"policy": str(p)} for p in df[policy_col].astype(str).tolist()]
    ids = [f"csv_{i}" for i in range(len(docs))]
    
    # Remove empty or invalid entries
    valid_docs, valid_metas, valid_ids = [], [], []
    for doc, meta, id_val in zip(docs, metas, ids):
        if doc and doc.strip() and doc != 'nan':
            valid_docs.append(doc.strip())
            valid_metas.append(meta)
            valid_ids.append(id_val)
    
    if not valid_docs:
        print("No valid policy content found in CSV file.")
        return
    
    # Clear existing collection and add new data
    try:
        existing = coll.get()
        if existing["ids"]:
            coll.delete(ids=existing["ids"])
            print(f"Cleared {len(existing['ids'])} existing documents.")
    except:
        pass
    
    # Add new documents
    coll.add(documents=valid_docs, metadatas=valid_metas, ids=valid_ids)
    print(f"Successfully ingested {len(valid_docs)} policies into Chroma collection 'hr_policies' from CSV.")
    
    # Debug: Print first few entries to verify content
    print("\nFirst few policies ingested:")
    for i, (doc, meta) in enumerate(zip(valid_docs[:3], valid_metas[:3])):
        print(f"{i+1}. {meta['policy']}: {doc[:100]}...")

def clear_collection():
    """Clear all documents from the collection."""
    coll = get_collection()
    try:
        existing = coll.get()
        if existing["ids"]:
            coll.delete(ids=existing["ids"])
            print(f"Cleared {len(existing['ids'])} documents from collection.")
        else:
            print("Collection is already empty.")
    except Exception as e:
        print(f"Error clearing collection: {e}")

def verify_collection():
    """Verify what's in the collection."""
    coll = get_collection()
    try:
        data = coll.get()
        print(f"Collection has {len(data['ids'])} documents")
        
        if data['documents']:
            print("\nSample documents:")
            for i, (doc, meta) in enumerate(zip(data['documents'][:3], data['metadatas'][:3])):
                policy_name = meta.get('policy', 'Unknown')
                print(f"{i+1}. {policy_name}:")
                print(f"   Content: {doc[:150]}...")
                print()
    except Exception as e:
        print(f"Error verifying collection: {e}")

if __name__ == "__main__":
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    print("HR Policy Ingestion Tool")
    print("========================")
    
    if os.path.exists("data/hr_policies.txt"):
        print("Found TXT file, ingesting...")
        ingest_from_txt("data/hr_policies.txt")
    elif os.path.exists("data/hr_policies.csv"):
        print("Found CSV file, ingesting...")
        ingest_from_csv("data/hr_policies.csv")
    else:
        print("No policy file found in data/.")
        print("Please add either:")
        print("- data/hr_policies.txt (format: PolicyName: Description)")
        print("- data/hr_policies.csv (with Policy and Description columns)")
    
    print("\nVerifying collection...")
    verify_collection()
