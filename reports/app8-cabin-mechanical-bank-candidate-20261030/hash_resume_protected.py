from pathlib import Path
import hashlib, json, os, subprocess, sys, time
root = Path(r'E:\Tesla_speed\worktrees\hellcat-state-contract-20261027')
out = root / 'reports' / 'app8-cabin-mechanical-bank-candidate-20261030'
mode = sys.argv[1]
if mode not in ('resume-initial','resume-final'): raise SystemExit('expected initial or final')
status = subprocess.run(['git','status','--porcelain=v1','--untracked-files=all'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
diff = subprocess.run(['git','diff','--binary','HEAD','--'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
(out / f'{mode}-status.txt').write_bytes(status.stdout)
(out / f'{mode}-diff.patch').write_bytes(diff.stdout)
records=[]; errors=[]; links=[]; total=0
for base, dirs, files in os.walk(root, followlinks=False):
    base=Path(base)
    kept=[]
    for name in dirs:
        p=base/name
        if p==out or (base==root and name=='.git'): continue
        if p.is_symlink(): links.append({'path':str(p.relative_to(root)).replace('\\','/'),'target':os.readlink(p)}); continue
        kept.append(name)
    dirs[:]=sorted(kept)
    for name in sorted(files):
        p=base/name
        if p==root/'.git': continue
        rel=str(p.relative_to(root)).replace('\\','/')
        try:
            if p.is_symlink(): links.append({'path':rel,'target':os.readlink(p)}); continue
            before=p.stat(); h=hashlib.sha256()
            with p.open('rb') as f:
                for chunk in iter(lambda:f.read(4*1024*1024),b''): h.update(chunk)
            after=p.stat()
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns): raise RuntimeError('file changed while hashing')
            records.append({'path':rel,'bytes':after.st_size,'sha256':h.hexdigest()}); total+=after.st_size
        except Exception as e: errors.append({'path':rel,'error':str(e)})
        if (len(records)+len(errors))%500==0: print(f'[{mode}] {len(records)+len(errors)} files, {total/1e9:.2f} GB hashed, {len(errors)} errors',flush=True)
result={'root':str(root),'mode':mode,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'excluded':[str(out),str(root/'.git')],'files':records,'symlinks':links,'errors':errors,'bytes':total,'count':len(records)}
(out/f'{mode}-protected-sha256.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(f'{mode.upper()} FILES={len(records)} BYTES={total} LINKS={len(links)} ERRORS={len(errors)}',flush=True)
if errors: raise SystemExit(1)
