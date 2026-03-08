import ollama

SYSTEM = """
Rewrite the user query into a clear question for searching a document.

Rules:
- Expand short queries into meaningful questions
- Do NOT answer the question
- Only rewrite it
- Keep same meaning

Examples:
name → What is the name mentioned in the document?
email → What email address is mentioned in the document?
linkedin → What LinkedIn profile is mentioned in the document?
projects → What projects are described in the document?
"""

def rewrite_query(query: str) -> str:
    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": query}
        ]
    )
    return response["message"]["content"].strip()
