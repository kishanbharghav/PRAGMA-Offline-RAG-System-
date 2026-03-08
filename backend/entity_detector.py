import re

EMAIL_REGEX = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
PHONE_REGEX = r"\b\d{10}\b"
URL_REGEX = r"https?://[^\s]+"

def detect_entities(text):
    emails = re.findall(EMAIL_REGEX, text)
    phones = re.findall(PHONE_REGEX, text)
    urls = re.findall(URL_REGEX, text)

    return {
        "emails": emails,
        "phones": phones,
        "urls": urls
    }
