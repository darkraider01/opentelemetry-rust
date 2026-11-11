import io, json, os, shutil, subprocess, tarfile
from pathlib import Path
here=Path(__file__).resolve().parent
repo=Path(os.environ['OTEL_REPO']) if 'OTEL_REPO' in os.environ else Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip())
root=Path('/tmp/otel-perf-reproduce')
root.mkdir(exist_ok=False)
revs={'A':'1e29b1fe1d03bde8e48eb564a3dee8ec9efed6a7','B':'28e4bc4d13a642c3f889105399db1dc241e3d9ab','C':'02826b01125941891aed8de2f3b6b8c987de2495','D':'02826b01125941891aed8de2f3b6b8c987de2495'}
for name,rev in revs.items():
 dest=root/name; dest.mkdir(); data=subprocess.check_output(['git','archive',rev],cwd=repo)
 with tarfile.open(fileobj=io.BytesIO(data)) as t: t.extractall(dest,filter='data')
 shutil.copy2(here/'harness.rs',dest/'opentelemetry-sdk/benches/trace_scaling.rs')
 shutil.copy2(here/'Cargo.lock',dest/'Cargo.lock')
 if name=='D':
  tracer=dest/'opentelemetry-sdk/src/trace/tracer.rs'
  source=tracer.read_text(); assert source.count('struct SdkTracerInner {') == 1
  tracer.write_text(source.replace('struct SdkTracerInner {', '#[repr(align(64))]\nstruct SdkTracerInner {'))
 if name=='A':
  with (dest/'opentelemetry-sdk/Cargo.toml').open('a') as f: f.write('\n[[bench]]\nname = "trace_scaling"\nharness = false\nrequired-features = ["trace"]\n')
 output=subprocess.check_output(['cargo','bench','--locked','--offline','-p','opentelemetry_sdk','--bench','trace_scaling','--no-run','--message-format=json'],cwd=dest,text=True)
 for line in output.splitlines():
  msg=json.loads(line)
  if msg.get('executable') and msg.get('target',{}).get('name')=='trace_scaling': shutil.copy2(msg['executable'],root/(name+'-bench'))
print('Binaries:',root,'Set OTEL_BENCH_BIN_DIR to this directory before running.')
