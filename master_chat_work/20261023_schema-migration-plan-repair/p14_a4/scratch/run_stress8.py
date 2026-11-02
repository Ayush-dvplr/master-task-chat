import subprocess,sys,time
O=sys.argv[1]
for cfg in sys.argv[2:]:
    for who in ("oracle","agent"):
        t0=time.time()
        try:
            r=subprocess.run([sys.executable,"-u","stress8_local.py",f"{O}/{who}/repo/src",cfg,f"{O}/g8_{who[0]}"],capture_output=True,text=True,timeout=400)
            print(who,cfg,"rc",r.returncode,r.stdout.strip(),r.stderr[-300:],f"wall={time.time()-t0:.1f}",flush=True)
        except subprocess.TimeoutExpired:
            print(who,cfg,"TIMEOUT 400s",flush=True)
