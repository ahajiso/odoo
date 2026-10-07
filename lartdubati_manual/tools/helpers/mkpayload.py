import json,re,sys
outline=open(sys.argv[1],encoding='utf-8').read(); md=open(sys.argv[2],encoding='utf-8').read(); rev=int(sys.argv[3])
body=outline.split("outline='true'>",1)[1]
# top-level elements: depth-0 tags
ids=[];depth=0;prefix=None
for m in re.finditer(r"<(/?)(\w+)([^>]*?)(/?)>",body):
    close,tag,attrs,selfc=m.groups()
    if tag=='doc': continue
    if close: depth-=1; continue
    if depth==0:
        i=re.search(r"id='([^']+)'",attrs).group(1)
        if not i.startswith('.'): prefix=i.split('.')[0]
        ids.append(i if not i.startswith('.') else prefix+i)
    if not selfc and tag not in ('gap',): depth+=1
    elif tag=='gap' and not selfc: depth+=1
print(json.dumps({"ops":[{"op":"replace","target":{"kind":"blocks","ids":ids},"ifRev":rev,"with":{"from":{"kind":"inline","content":md},"as":"markdown"}}]},ensure_ascii=False))
