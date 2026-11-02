import hashlib,os,sys
d=sys.argv[1];files=[]
def walk(path,rel):
    with os.scandir(path) as it:
        for e in it:
            r=f"{rel}/{e.name}"
            if e.is_dir(follow_symlinks=False): walk(e.path,r)
            elif e.is_file(follow_symlinks=False): files.append((os.fsencode(r),e.path))
walk(d,".")
out=hashlib.sha256()
for rel,full in sorted(files):
    out.update(hashlib.sha256(open(full,'rb').read()).hexdigest().encode()+b"  "+rel+b"\n")
print(out.hexdigest()[:12])
