import re

emoji_re = re.compile(
    '['
    '\U0001F000-\U0001FFFF'
    '\U00002600-\U000027FF'
    '\U00002B00-\U00002BFF'
    ']+',
    flags=re.UNICODE
)

files = ['index.html', 'web.html', 'api/send_email.js', 'api/assistant.js',
         'api/predict_file.js', 'api/n8n_webhook.js', 'api/data.js', 'api/run.js']

for fn in files:
    try:
        with open(fn, 'r', encoding='utf-8', errors='replace') as f:
            c = f.read()
        found = emoji_re.findall(c)
        cleaned = emoji_re.sub('', c)
        # Clean up spaces left behind in spans
        cleaned = re.sub(r'<span>\s+', '<span>', cleaned)
        cleaned = re.sub(r'\s+</span>', '</span>', cleaned)
        with open(fn, 'w', encoding='utf-8', errors='replace') as f:
            f.write(cleaned)
        if found:
            print(f'{fn}: removed {len(found)} emoji group(s): {set(found[:10])}')
        else:
            print(f'{fn}: already clean')
    except Exception as e:
        print(f'{fn}: ERROR - {e}')

print('\nAll files processed.')
