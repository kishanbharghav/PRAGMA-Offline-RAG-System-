def try_expand(query: str):
    q = query.lower().strip()

    rules = {
        "name": "What is the full name of the person mentioned in the document?",
        "email": "What is the email address mentioned in the document?",
        "phone": "What is the phone number mentioned in the document?",
        "linkedin": "What is the LinkedIn profile URL mentioned in the document?",
        "github": "What is the GitHub profile link mentioned in the document?",
        "college": "Which college or university is mentioned in the document?",
        "languages": "What languages does the person know?",
        "projects": "What projects has the person worked on?"
    }


    return rules.get(q, None)

