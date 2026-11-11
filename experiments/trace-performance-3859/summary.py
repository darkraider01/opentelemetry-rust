import csv,statistics,collections
from pathlib import Path
p=Path(__file__).resolve().parent
rows=list(csv.DictReader((p/'raw.csv').open()))
groups=collections.defaultdict(list)
for r in rows:
 if r['phase']=='measurement': groups[(r['workload'],int(r['workers']),r['variant'])].append(float(r['rate_per_second'])/1e6)
with (p/'summary.csv').open('x',newline='') as f:
 w=csv.writer(f, lineterminator='\n'); w.writerow(('workload','workers','variant','n','median_M_per_s','min','max','MAD'))
 for (work,workers,v),x in sorted(groups.items()):
  med=statistics.median(x); w.writerow((work,workers,v,len(x),round(med,3),round(min(x),3),round(max(x),3),round(statistics.median(abs(y-med) for y in x),3)))
