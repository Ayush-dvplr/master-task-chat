import ast,sys,re
pat=re.compile(r'\b(tomllib|StrEnum|ExceptionGroup|TaskGroup|datetime\.UTC|from datetime import .*\bUTC\b|typing\.Self|import Self|\bSelf\b|batched|\.walk\(|NotRequired|Required\[|LiteralString|assert_never|reveal_type|override|zoneinfo|asyncio\.timeout|tomli|fromisoformat)\b')
for f in sys.argv[1:]:
    src=open(f).read(); t=ast.parse(src)
    for n in ast.walk(t):
        if type(n).__name__=='Match': print(f, n.lineno, 'match statement (3.10+)')
        if type(n).__name__=='TryStar': print(f, n.lineno, 'except* (3.11+)')
        if type(n).__name__ in ('TypeAlias','TypeVar') : print(f, n.lineno, 'PEP 695 (3.12+)')
    for i,l in enumerate(src.splitlines(),1):
        m=pat.search(l)
        if m and not l.lstrip().startswith('#'): print(f,i,'feature:',m.group(0),'|',l.strip()[:110])
