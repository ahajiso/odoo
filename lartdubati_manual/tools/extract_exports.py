"""Extract latest Claude Docs markdown exports (bytes_b64) from the session transcript."""
import base64, glob, json, os, re, sys
src = sys.argv[1] if len(sys.argv) > 1 else max(glob.glob('/root/.claude/projects/-home-claude/*.jsonl'), key=os.path.getmtime)
out = sys.argv[2] if len(sys.argv) > 2 else 'src'
pat = re.compile(r'\{\\?"verdict\\?":\\?"allow\\?",\\?"rev\\?":\d+,\\?"data\\?":\{\\?"name\\?":\\?"(.*?)\\?",.*?\\?"bytes_b64\\?":\\?"([A-Za-z0-9+/=]+)\\?"')
found = {}
with open(src, encoding='utf-8') as f:
    for line in f:
        if 'bytes_b64' not in line: continue
        for m in pat.finditer(line):
            name = json.loads('"%s"' % m.group(1).replace('\\\\', '\\'))
            found[name] = m.group(2)
os.makedirs(out, exist_ok=True)
for name, b in found.items():
    data = base64.b64decode(b)
    open(os.path.join(out, name), 'wb').write(data)
    print(name, len(data))
