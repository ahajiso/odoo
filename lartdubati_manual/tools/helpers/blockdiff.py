import json,sys,re
def chunks(md):
    return [c for c in re.split(r"\n\s*\n", md.strip()) if c.strip()]
old=chunks(open(sys.argv[1],encoding='utf-8').read()); new=chunks(open(sys.argv[2],encoding='utf-8').read())
ids=sys.argv[3].split(','); pre=sys.argv[4]; rev=int(sys.argv[5])
ids=[pre+i if i.startswith('.') else i for i in ids]
# merge "   *(...)*" indented continuation chunks into previous list chunk (list continuation)
def merge(cs):
    out=[]
    for c in cs:
        if out and (c.startswith('   ') or re.match(r'^\d+\. ',c) and re.match(r'^(\d+\. |   )',out[-1].split('\n')[-1]) and not out[-1].startswith('#')) and re.match(r'^(\d+\.|-|\s)',out[-1]):
            out[-1]+= '\n\n'+c
        else: out.append(c)
    return out
old=merge(old); new=merge(new)
print(len(old),len(new),len(ids),file=sys.stderr)
assert len(old)==len(new)==len(ids), (len(old),len(new),len(ids))
ops=[]
for i,(o,n) in enumerate(zip(old,new)):
    if o!=n: ops.append({"op":"replace","target":{"kind":"blocks","ids":[ids[i]]},"ifRev":rev,"with":{"as":"markdown","from":{"kind":"inline","content":n}}})
print(json.dumps({"ops":ops},ensure_ascii=False))
