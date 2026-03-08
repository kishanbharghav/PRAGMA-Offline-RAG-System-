import ollama

SYSTEM_PROMPT = """
You are DocuVault, an Enterprise Document Intelligence Engine.

STRICT RULES:
1. Answer ONLY from the given context.
2. If unsure say: "I cannot find this information in the document."
3. Every piece of context is prefixed with [Source File: filename | Page: X].
4. Base your answers strictly on this source data. If a user asks to compare two documents, explicitly mention how they differ based on the source attributes.
5. Pay rigorous attention to Document Headings and Labels. Do NOT confuse "Projects" with "Certificates", "Experience", or "Education". Categorize explicitly.
6. After every fact, cite the source like [filename, Page X].
7. Be concise, factual, and strictly professional.
"""

def generate_answer(query, contexts, pages):

    context_text = ""

    for text, page in zip(contexts, pages):
        context_text += f"[Page {page}]\n{text}\n\n"

    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context_text}\nQuestion: {query}"}
        ]
    )

    return response["message"]["content"]

def generate_answer_stream(query, contexts, pages):

    context_text = "\n\n".join(contexts)

    response = ollama.chat(
        model="llama3",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context_text}\nQuestion: {query}"}
        ],
        stream=True,
        options={
            "num_ctx": 8192,
            "num_predict": 1024
        }
    )

    for chunk in response:
        if "message" in chunk and "content" in chunk["message"]:
            yield chunk["message"]["content"]
