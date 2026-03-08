import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from intent_processor import extract_file_filter

queries = [
    "What is the total revenue?",
    "Compare the margins in the Q3 report and the Q4 report.",
    "Who is the CEO according to the 2024 financial statement?"
]

for q in queries:
    print(f"Query: {q}")
    print(f"Filter: {extract_file_filter(q)}\n")
