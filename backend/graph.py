# graph.py
from langgraph.graph import StateGraph, END
from typing import Dict, Any, Literal
from utils import answer_query
from employee_db import format_emp

# Define the state schema
class GraphState(Dict[str, Any]):
    """State schema for the HR bot graph"""
    query: str
    emp_id: str = None
    route: str = None
    answer: str = None

def clean_graph_response(response: str) -> str:
    """Clean any citations from graph responses."""
    citation_patterns = [
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
        "Employee Database"
    ]
    
    for pattern in citation_patterns:
        if pattern in response:
            response = response.split(pattern)[0].strip()
    
    return response.rstrip(" -.,;:")

def router_node(state: GraphState) -> Dict[str, str]:
    """Route queries to appropriate handlers based on content."""
    q = state.get("query", "").lower()
    emp_id = state.get("emp_id")
    
    # Personal keywords that indicate employee-specific queries
    personal_keywords = [
        "my", "me", "remaining", "left", "balance", 
        "my leave", "my manager", "my insurance", "my salary",
        "my profile", "my details"
    ]
    
    # If user uses personal keywords and has emp_id, route to employee node
    if emp_id and any(keyword in q for keyword in personal_keywords):
        return {"route": "employee"}
    
    # Otherwise use policy (RAG) for general HR policy questions
    return {"route": "policy"}

def employee_node(state: GraphState) -> Dict[str, str]:
    """Handle employee-specific queries using direct database lookup."""
    query = state.get("query", "")
    emp_id = state.get("emp_id")
    
    if not emp_id:
        return {"answer": "I need your employee ID to access personal information. Please provide your employee ID."}
    
    try:
        answer = answer_query(query, emp_id=emp_id)
        # Clean any potential citations
        answer = clean_graph_response(answer)
        return {"answer": answer}
    except Exception as e:
        return {"answer": "Sorry, I couldn't retrieve your information. Please contact HR for assistance."}

def policy_node(state: GraphState) -> Dict[str, str]:
    """Handle general policy queries using RAG."""
    query = state.get("query", "")
    emp_id = state.get("emp_id")
    
    try:
        answer = answer_query(query, emp_id=emp_id)
        # Clean any potential citations
        answer = clean_graph_response(answer)
        return {"answer": answer}
    except Exception as e:
        return {"answer": "Sorry, I couldn't find information about that policy. Please contact HR for assistance."}

def should_route_to_employee(state: GraphState) -> Literal["employee", "policy"]:
    """Conditional edge function to determine routing."""
    route = state.get("route", "policy")
    return "employee" if route == "employee" else "policy"

def build_graph():
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(GraphState)
    
    # Add nodes
    workflow.add_node("router", router_node)
    workflow.add_node("employee", employee_node)
    workflow.add_node("policy", policy_node)
    
    # Set entry point
    workflow.set_entry_point("router")
    
    # Add conditional edges from router
    workflow.add_conditional_edges(
        "router",
        should_route_to_employee,
        {
            "employee": "employee",
            "policy": "policy"
        }
    )
    
    # Add terminal edges
    workflow.add_edge("employee", END)
    workflow.add_edge("policy", END)
    
    return workflow.compile()

# Create the compiled graph runner
try:
    runner = build_graph()
    print("HR Bot graph compiled successfully!")
except Exception as e:
    print(f"Error building graph: {e}")
    runner = None

def run_hr_bot(query: str, emp_id: str = None) -> str:
    """Convenience function to run the HR bot with a query."""
    if runner is None:
        return "HR Bot is not properly initialized. Please check the configuration."
    
    try:
        initial_state = {
            "query": query,
            "emp_id": emp_id
        }
        
        result = runner.invoke(initial_state)
        answer = result.get("answer", "I couldn't process your request. Please try again.")
        
        # Final cleaning of any remaining citations
        answer = clean_graph_response(answer)
        
        return answer
    
    except Exception as e:
        return "An error occurred. Please contact HR for assistance."

# Example usage function for testing
def test_bot():
    """Test function to verify bot functionality."""
    test_queries = [
        ("What is the sick leave policy?", None),
        ("How many sick leaves do I have remaining?", "EMP001"),
        ("What are the working hours?", None),
        ("Show me my profile", "EMP001"),
        ("What are the guidelines for remote work policy?", None)
    ]
    
    print("Testing HR Bot:")
    print("=" * 50)
    
    for query, emp_id in test_queries:
        print(f"\nQuery: {query}")
        if emp_id:
            print(f"Employee ID: {emp_id}")
        response = run_hr_bot(query, emp_id)
        print(f"Response: {response}")
        print("-" * 30)

if __name__ == "__main__":
    test_bot()
