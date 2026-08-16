import re, shutil

with open('index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove emojis using a broad unicode range
def remove_emojis(text):
    # Match emoji/symbol unicode blocks
    emoji_re = re.compile(
        "["
        "\U0001F300-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\U00002600-\U000027BF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U00002500-\U00002BEF"
        "]+",
        flags=re.UNICODE
    )
    return emoji_re.sub('', text)

cleaned = remove_emojis(content)

# Clean up stray spaces around tags left by emoji removal
cleaned = re.sub(r'> +', '> ', cleaned)
cleaned = re.sub(r' +<', ' <', cleaned)
# Clean leading/trailing spaces in button text spans
cleaned = re.sub(r'<span> +', '<span>', cleaned)
cleaned = re.sub(r' +</span>', '</span>', cleaned)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(cleaned)

shutil.copy('index.html', 'web.html')
print('Done. Emojis removed from index.html and web.html.')
