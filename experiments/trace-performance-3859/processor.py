import os,csv,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent; bins=Path(os.environ.get('OTEL_BENCH_BIN_DIR','/tmp/otel-perf-investigation'))
with (p/'processor.csv').open('x',newline='') as f:
 out=csv.writer(f, lineterminator='\n');out.writerow(('phase','round','order','variant','workload','workers','operations','recording','elapsed_seconds','rate_per_second'));f.flush()
 for phase,rounds,duration in [('warmup',1,300),('measurement',9,1000)]:
  for r in range(rounds):
   for j,workers in enumerate((4,8)):
    order='ABC'[(r+j)%3:]+'ABC'[:(r+j)%3]
    for k,v in enumerate(order):
     result=subprocess.check_output([str(bins/(v+'-bench')),'simple',str(workers),str(duration)],text=True).strip().split(',')
     out.writerow((phase,r+1,k+1,v,*result));f.flush()
   print(phase,r+1,flush=True)
