use opentelemetry::trace::{Span as _, Tracer, TracerProvider};
use opentelemetry::Context;
use opentelemetry_sdk::error::OTelSdkResult;
use opentelemetry_sdk::trace::{FinishedSpan, Sampler, SdkTracerProvider, SimpleSpanProcessor, Span, SpanData, SpanExporter, SpanProcessor};
use std::future::Future;
use std::sync::{atomic::{AtomicBool, Ordering}, Barrier};
use std::time::{Duration, Instant, SystemTime};
#[derive(Debug)] struct VoidExporter;
impl SpanExporter for VoidExporter { fn export(&self, _: Vec<SpanData>) -> impl Future<Output=OTelSdkResult> + Send { std::future::ready(Ok(())) } }
#[derive(Debug)] struct Noop;
impl SpanProcessor for Noop {
 fn on_start(&self, _: &mut Span, _: &Context) {}
 fn on_end(&self, _: FinishedSpan<'_>) {}
 fn force_flush(&self) -> OTelSdkResult { Ok(()) }
 fn shutdown_with_timeout(&self, _: Duration) -> OTelSdkResult { Ok(()) }
}
fn main() {
 let args: Vec<String> = std::env::args().collect();
 let workload = &args[1]; let workers: usize = args[2].parse().unwrap(); let millis: u64 = args[3].parse().unwrap();
 let sampler = match workload.as_str() { "mixed" | "validate" => Sampler::TraceIdRatioBased(0.5), "off" => Sampler::AlwaysOff, _ => Sampler::AlwaysOn };
 let mut builder = SdkTracerProvider::builder().with_sampler(sampler);
 if workload == "simple" { builder = builder.with_span_processor(SimpleSpanProcessor::new(VoidExporter)); }
 if workload == "noop" { builder = builder.with_span_processor(Noop); }
 let provider = builder.build(); let tracer = provider.tracer("trace-scaling");
 let barrier = Barrier::new(workers + 1); let stop = AtomicBool::new(false);
 let (total, recording, elapsed) = std::thread::scope(|s| {
  let handles: Vec<_> = (0..workers).map(|_| s.spawn(|| { let (mut n,mut rec)=(0_u64,0_u64); barrier.wait(); while !stop.load(Ordering::Relaxed) {
   let mut span = tracer.span_builder("trace-scaling").with_start_time(SystemTime::UNIX_EPOCH).start(&tracer);
   if workload == "validate" { rec += u64::from(span.is_recording()); }
   span.end_with_timestamp(SystemTime::UNIX_EPOCH); std::hint::black_box(span); n+=1;
  } (n,rec) })).collect();
  let started = Instant::now(); barrier.wait(); std::thread::sleep(Duration::from_millis(millis)); stop.store(true,Ordering::Relaxed); let elapsed=started.elapsed();
  let (mut n,mut rec)=(0,0); for h in handles { let (a,b)=h.join().unwrap(); n+=a;rec+=b; } (n,rec,elapsed)
 });
 println!("{workload},{workers},{total},{recording},{:.9},{:.3}", elapsed.as_secs_f64(),total as f64 / elapsed.as_secs_f64());
}
