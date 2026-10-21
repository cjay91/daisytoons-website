import re
import unicodedata


def slugify(text: str) -> str:
    """'Valentine's Day Mug!' -> 'valentines-day-mug'"""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    ascii_text = re.sub(r"['’]", "", ascii_text.lower())
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
