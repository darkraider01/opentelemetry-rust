import os, csv,subprocess
from pathlib import Path
p=Path(__file__).resolve().parent
bins=Path(os.environ.get('OTEL_BENCH_BIN_DIR','/tmp/otel-perf-investigation'))
configs=[('mixed',8),('recording',8),('noop',8),('simple',4)]
with (p/'layout.csv').open('x',newline='') as f:
 out=csv.writer(f, lineterminator='\n');out.writerow(('phase','round','order','variant','workload','workers','operations','recording','elapsed_seconds','rate_per_second'));f.flush()
 for phase,rounds,duration in [('warmup',1,150),('measurement',9,300)]:
  for r in range(rounds):
   for j,(workload,workers) in enumerate(configs):
    order='BCD'[(r+j)%3:]+'BCD'[:(r+j)%3]
    for k,v in enumerate(order):
     result=subprocess.check_output([str(bins/(v+'-bench')),workload,str(workers),str(duration)],text=True).strip().split(',')
     out.writerow((phase,r+1,k+1,v,*result));f.flush()
   print(phase,r+1,flush=True)
