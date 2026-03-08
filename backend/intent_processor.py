import ollama
from query_expander import try_expand
from query_rewriter import rewrite_query

def process_query(query):

    expanded = try_expand(query)

    if expanded:
        print("Intent: rule-based expansion")
        return expanded

    print("Intent: AI rewrite")
    return rewrite_query(query)

def extract_file_filter(query: str) -> str:
    """
    Uses a fast LLM call to extract an implied document title or keyword.
    If the user asks 'What was the revenue in the Q3 report?', this returns 'Q3'.
    """
    PROMPT = """
    Extract the specific document name, title, or time period the user is referring to.
    ONLY output the keyword or short phrase. If they are asking a general question without specifying a document, output "NONE".
    
    Examples:
    "What was the revenue in the Q3 report?" -> Q3
    "Compare the features in the 2023 financial doc." -> 2023 financial
    "What is DocuVault?" -> NONE
    "Who is John Doe?" -> NONE
    """
    
    try:
        response = ollama.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": query}
            ]
        )
        result = response["message"]["content"].strip()
        if result.upper() == "NONE" or len(result) > 30:
            return None
            
        return result
    except Exception as e:
        print(f"Skipping metadata filter due to LLM error: {e}")
        return None
