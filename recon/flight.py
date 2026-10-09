"""Decode Next.js RSC ("flight") payloads from deweloperuch.pl pages.

flight(path)                 -> concatenated flight text from a saved HTML page (self.__next_f.push chunks)
find_json_after(text, prop)  -> every JSON value that follows `"prop":` in flight text (works on raw RSC responses too)

CLI: python3 recon/flight.py <page.html> <propName>
"""
import re,sys,json
def flight(path):
    s=open(path,encoding='utf-8').read()
    chunks=re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>',s,re.S)
    return ''.join(json.loads('"'+c+'"') for c in chunks)
def find_json_after(text,key):
    """yield decoded JSON values appearing right after "key":"""
    out=[]
    for m in re.finditer(re.escape('"'+key+'":'),text):
        dec=json.JSONDecoder()
        try:
            v,_=dec.raw_decode(text,m.end()); out.append(v)
        except Exception as e: pass
    return out
if __name__=='__main__':
    t=flight(sys.argv[1]); key=sys.argv[2]
    for v in find_json_after(t,key):
        if isinstance(v,dict):
            print({k:(f'{type(x).__name__}[{len(x)}]' if isinstance(x,(list,dict)) else x) for k,x in v.items()})
            for k,x in v.items():
                if isinstance(x,list) and x: print('  ',k,'[0]=',json.dumps(x[0],ensure_ascii=False)[:1500])
        else: print(type(v).__name__, str(v)[:300])
