import os, csv, subprocess, time
from pathlib import Path
p=Path(__file__).resolve().parent
bins=Path(os.environ.get('OTEL_BENCH_BIN_DIR','/tmp/otel-perf-investigation'))
configs=[('mixed',i) for i in (1,2,4,6,8,12)]+[(w,i) for w in ('simple','noop','recording') for i in (1,4,8)]+[('off',1)]
with (p/'raw.csv').open('x',newline='') as f:
 out=csv.writer(f, lineterminator='\n'); out.writerow(('phase','round','order','variant','workload','workers','operations','recording','elapsed_seconds','rate_per_second')); f.flush()
 for phase,rounds,duration in [('warmup',1,150),('measurement',9,300),('validate',1,300)]:
  for r in range(rounds):
   for j,(workload,workers) in enumerate(configs if phase!='validate' else [('validate',i) for i in (1,2,4,6,8,12)]):
    order='ABC'[(r+j)%3:]+'ABC'[:(r+j)%3]
    for k,v in enumerate(order):
     output=subprocess.check_output([str(bins/(v+'-bench')),workload,str(workers),str(duration)],text=True).strip().split(',')
     out.writerow((phase,r+1,k+1,v,*output)); f.flush()
   print(phase,r+1,flush=True)
