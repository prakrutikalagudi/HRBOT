# utils.py
import os
import textwrap
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
import google.generativeai as genai
from typing import Tuple, List
from employee_db import format_emp, get_employee

load_dotenv("keys.env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
TOP_K = int(os.getenv("TOP_K", "7"))  # Increased for better retrieval

if not GEMINI_API_KEY:
    raise ValueError("Set GEMINI_API_KEY in keys.env file")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Chroma client and collection handle
_chroma = chromadb.PersistentClient(path="chroma_db")
_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
_collection = _chroma.get_or_create_collection(name="hr_policies", embedding_function=_ef)

SYSTEM_INSTRUCTION = textwrap.dedent("""
You are a helpful HR assistant. Answer questions using the provided policy information and employee data.
Provide detailed, specific answers based on the context given.
If you cannot find the answer in the provided information, say you don't know and suggest contacting HR.
Be professional and helpful in your responses.
Never mention sources, citations, policy names, or document references.
""").strip()

def retrieve_context(query: str, k: int = TOP_K) -> str:
    """Retrieve relevant policy context from the vector database."""
    try:
        # Try multiple search variations to improve retrieval
        search_queries = [query]
        
        # Add variations for common HR terms
        if "leave" in query.lower():
            search_queries.append(query.replace("leave", "time off"))
            search_queries.append(query + " vacation sick")
        
        if "remote" in query.lower() or "work from home" in query.lower():
            search_queries.extend(["remote work policy", "telecommute policy", "work from home guidelines"])
        
        if "half day" in query.lower():
            search_queries.extend(["partial day leave", "half day policy", "short leave"])
        
        all_docs = []
        seen_docs = set()
        
        for search_query in search_queries:
            try:
                res = _collection.query(query_texts=[search_query], n_results=k)
                docs = res.get("documents", [[]])[0]
                
                for doc in docs:
                    if doc and doc not in seen_docs:
                        all_docs.append(doc)
                        seen_docs.add(doc)
            except:
                continue
        
        if not all_docs:
            return ""
        
        # Return combined context
        return "\n\n".join(all_docs[:5])  # Limit to top 5 most relevant
        
    except Exception as e:
        print(f"Error retrieving context: {e}")
        return ""

def call_gemini(prompt: str, max_output_tokens: int = 512) -> str:
    """Call Gemini API with improved error handling."""
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_output_tokens,
            temperature=0.2,  # Slightly higher for more natural responses
        )
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content.parts:
                return candidate.content.parts[0].text.strip()
        
        return "I apologize, but I couldn't generate a proper response. Please try again or contact HR."
    
    except Exception as e:
        print(f"Gemini API error: {e}")
        return "I'm experiencing technical difficulties. Please contact HR for assistance."

def build_prompt(query: str, context: str, employee_snippet: str = "") -> str:
    """Build a comprehensive prompt for the Gemini model."""
    prompt = SYSTEM_INSTRUCTION + "\n\n"
    
    if employee_snippet:
        prompt += f"Employee Information:\n{employee_snippet}\n\n"
    
    if context:
        prompt += f"HR Policy Information:\n{context}\n\n"
    else:
        prompt += "No specific policy information found for this query.\n\n"
    
    prompt += f"Employee Question: {query}\n\n"
    prompt += "Provide a helpful response based on the information above. Do not mention document names, sources, or policy references."
    
    return prompt

def clean_response(response: str) -> str:
    """Clean any remaining citations or source references from response."""
    # List of patterns to remove
    patterns_to_remove = [
        "(Source: Employee Database)",
        "(Source:",
        "(source:",
        "Source:",
        "source:",
        "(Policy_",
        "(policy_",
        "Policy_",
        "policy_",
        "(General HR Knowledge",
        "(Employee Database)",
        "Employee Database",
        "- Please verify with HR for specific policies",
        "Please verify with HR for specific policies"
    ]
    
    for pattern in patterns_to_remove:
        if pattern in response:
            # Split at the pattern and take only the first part
            response = response.split(pattern)[0].strip()
    
    # Clean up any trailing punctuation from removed citations
    response = response.rstrip(" -.,;:()")
    
    return response

def answer_query(query: str, emp_id: str = None, top_k: int = TOP_K) -> str:
    """Main function to answer HR queries - returns only clean answer text."""
    if not query.strip():
        return "Please ask a specific question about HR policies or your employment details."
    
    ql = query.lower().strip()
    personal_keywords = [
        "my", "me", "remaining", "left", "balance", 
        "my leave", "my insurance", "my manager", "my salary",
        "my profile", "my details", "my information"
    ]

    # Handle personal queries with employee DB - NO CITATIONS
    if emp_id and any(k in ql for k in personal_keywords):
        rec = get_employee(emp_id)
        if not rec:
            return f"Sorry, I couldn't find employee record for ID {emp_id}. Please contact HR to verify your employee ID."

        name = rec.get("Name", "Employee")

        # Direct employee DB queries - COMPLETELY CLEAN
        if any(word in ql for word in ["sick", "sick leave"]) and any(word in ql for word in ["remaining", "left", "balance", "have"]):
            remaining_sl = rec.get('Remaining_SL', 'N/A')
            return f"{name}, you have {remaining_sl} sick leave(s) remaining."
        
        if any(word in ql for word in ["casual", "paid", "paid leave"]) and any(word in ql for word in ["remaining", "left", "balance", "have"]):
            remaining_pl = rec.get('Remaining_PL', 'N/A')
            return f"{name}, you have {remaining_pl} paid/casual leave(s) remaining."
        
        if "salary" in ql and any(word in ql for word in ["my", "what", "how much"]):
            salary = rec.get('Salary', 'N/A')
            return f"{name}, your salary information: {salary}. For detailed salary breakdown, please contact HR."
        
        if any(word in ql for word in ["profile", "details", "information", "show me"]):
            snippet = format_emp(emp_id)
            return f"Here's your profile information:\n\n{snippet}"

    # For all other queries, use RAG + Gemini
    try:
        context = retrieve_context(query, k=top_k)
        emp_snippet = format_emp(emp_id) if emp_id else ""
        
        # Build prompt and get response
        prompt = build_prompt(query=query, context=context, employee_snippet=emp_snippet)
        response = call_gemini(prompt, max_output_tokens=512)
        
        # Clean any remaining citations
        response = clean_response(response)
        
        # If response is too generic and we have context, try to be more specific
        if not context and ("don't know" in response.lower() or "contact hr" in response.lower()):
            return "I don't have specific information about that topic in my knowledge base. Please contact HR for detailed information."
        
        return response.strip()
    
    except Exception as e:
        print(f"Error in answer_query: {e}")
        return "I'm sorry, I encountered an error while processing your request. Please contact HR directly for assistance."

def validate_employee_credentials(emp_id, emp_name, password):
    """
    Validate employee ID, name and password.
    """

    try:

        employee_data = get_employee(emp_id)

        if not employee_data:
            return (
                False,
                None,
                "Employee ID not found in the system."
            )

        stored_name = employee_data.get("Name", "")
        stored_password = employee_data.get("Password", "")

        stored_name_normalized = (
            ' '.join(stored_name.lower().split())
        )

        input_name_normalized = (
            ' '.join(emp_name.lower().split())
        )

        if stored_name_normalized != input_name_normalized:
            return (
                False,
                employee_data,
                "Employee name does not match our records."
            )

        if not stored_password:
            return (
                False,
                employee_data,
                "Password not found for this employee."
            )

        if stored_password != password:
            return (
                False,
                employee_data,
                "Incorrect password."
            )

        emp_status = employee_data.get("Emp_Status", "Active")

        if emp_status.lower() not in ["active", "employed"]:
            return (
                False,
                employee_data,
                "Employee account is not active."
            )

        return (
            True,
            employee_data,
            None
        )

    except Exception as e:

        return (
            False,
            None,
            f"System error during validation: {str(e)}"
        )

def get_employee_display_name(employee_data):
    """Get the proper display name for the employee."""
    return employee_data.get('Name') or employee_data.get('name') or employee_data.get('emp_name') or 'Employee'

def validate_employee_id(emp_id):
    """Legacy function for backward compatibility."""
    employee_data = get_employee(emp_id)
    return employee_data is not None

def get_employee_name(emp_id):
    """Legacy function for backward compatibility."""
    employee_data = get_employee(emp_id)
    if employee_data:
        return get_employee_display_name(employee_data)
    return None

def health_check() -> dict:
    """Check if all components are working properly."""
    status = {
        "gemini_api": False,
        "vector_db": False,
        "employee_db": False,
        "errors": []
    }
    
    try:
        test_response = call_gemini("Hello", max_output_tokens=10)
        if test_response and "error" not in test_response.lower():
            status["gemini_api"] = True
    except Exception as e:
        status["errors"].append(f"Gemini API: {str(e)}")
    
    try:
        context = retrieve_context("test query", k=1)
        status["vector_db"] = True
    except Exception as e:
        status["errors"].append(f"Vector DB: {str(e)}")
    
    try:
        from employee_db import employee_df
        if not employee_df.empty:
            status["employee_db"] = True
        else:
            status["errors"].append("Employee DB: No employee data loaded")
    except Exception as e:
        status["errors"].append(f"Employee DB: {str(e)}")
    
    return status

# Debug function to test your vector database
def debug_query(query: str):
    """Debug function to see what's in your vector database."""
    print(f"Testing query: '{query}'")
    try:
        res = _collection.query(query_texts=[query], n_results=5)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        
        print(f"Found {len(docs)} documents:")
        for i, (doc, meta) in enumerate(zip(docs, metas)):
            print(f"{i+1}. Policy: {meta.get('policy', 'Unknown')}")
            print(f"   Content: {doc[:200]}...")
            print()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test the vector database
    debug_query("half day leave policy")
    debug_query("remote work policy")
    debug_query("sick leave policy")
