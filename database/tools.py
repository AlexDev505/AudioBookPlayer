import re


def replace_quotes(text: str):
    """
    Заменяет кавычки в тексте.
    Обеспечивает правильность имён для файлов.
    """
    while '"' in text:
        text = re.sub(r'"(.*)"', r"«\g<1>»", text)
    return text
