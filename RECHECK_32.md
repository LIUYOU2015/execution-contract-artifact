# Completed primary-source audit: 32 assertions

Completed November 18, 2026 by the coordinating model. **32/32 checked; 0 pending; 28 supported and 4 supported with precision notes.** This pass adds no human checks or native trials.

| Assertion | Source-grounded result |
|---|---|
|A0|Separate task/evaluator conditions from execution settings; correlation metadata does not guarantee deterministic trajectories.|
|A1|The opening says 100 sandboxes and the later section says over 100. Preserve both descriptions instead of claiming a reconciled exact count.|
|A2|Preserve the conditional task selection, five repeats and the distinction between default and resource-experiment model settings.|
|A7|Idle-time fractions refer to the controlled second-level samples and source-defined idle wording, not memory utilization or reclaimability.|
|A8|The 65%, 4.9-fold and idealized threefold results come from analytical pricing replay, not native policy measurements.|
|AF-C1|Typed pools, same-ID reuse, asynchronous capacity waits and rollout/global lifetimes match the described design.|
|AF-C2|The reported 66.95-to-1.86-minute change measures training-step time while pool capacity grows from 1 to 64.|
|AF-C3|The six WebShop values match, while scaffolds/settings differ. Error bars describe variation across steps, not independent trials.|
|AF-C4|The four R2E values match. The appendix calls the rollout-only denominator generation time; preserve this wording and the configuration differences.|
|AF-C6|The inspected throughput section/tables do not separately tabulate fault/timeout/cancellation/missing denominators; this is a bounded reporting claim.|
|AF-C7|The pinned artifact defines close and real-enroot owner-death tests. They were not executed here and postdate the reviewed paper.|
|AW-N1|Section 2 describes recovery architecture; Section 3 does not quantify the selected lifecycle postconditions. Do not infer absent functionality.|
|AW-Q1|Preserve the distributed/sequential comparator and distinguish the reported 14.6 ratio from the printed-time ratio of 14.66.|
|AW-Q2|Training is 144 seconds in both arms; the complete-cycle ratio is 11.72, rather than a convergence-normalized learning-cost result.|
|D1|Production instance counts describe one scale unit, rather than useful-command concurrency or successful task throughput.|
|D12|The quantitative evaluation explicitly excludes training-framework integration.|
|D16|The dedicated ten-node evaluation cluster is separate from production; preserve the reported hardware and kernel configurations.|
|D5|Peak memory, integrated memory and transient CPU utilization are distinct outcomes under separate mechanism comparisons.|
|E01|The original tables agree. Zero GB denotes the modified-state amount; all cells time snapshot plus restore, with different state coverage.|
|E02|Memory-only row values match. Preserve GB/GiB ambiguity and undefined missing markers; do not invent component timings.|
|E03|Disk-only row values match. Joint memory/disk variation and snapshot/restore splits are not supplied.|
|E05|Replay, snapshot/restore, compensation and minimum state domains are conceptual arguments, rather than universal correctness measurements.|
|E06|The described checkpoint-lite prototype is measured; semantic native forks and remote/multi-agent effects remain research directions.|
|E07|The reviewed four-page source supplies no identified prototype-code/raw-trial link or executed lifecycle-fault study; availability elsewhere was not assessed.|
|GKE-Q1|The report supplies average and maximum TTFC, not P99. Preserve the printed ranges and the strict under-ten-second maximum.|
|GKE-RESOURCE|Warm-replica and phase counters are not CPU/memory allocation integrals or a census of held-plus-warm capacity.|
|GKE-TIMER|The inspected generic probe sleeps and returns a pod name. Its phase summaries do not independently establish the headline first-command endpoint.|
|GKE-WARM|The reported critical-path gain relies on preparation before requests; CPU and background cluster time remain part of the trade-off.|
|RT-02|Figure 2 confirms the four T0 medians and units; 17.9/0.162=110.49. Retain the source authors tested configuration.|
|RT-03|All eight T1/T2 medians match. The displayed T2 ratio is 1.8833; identify the python/attrs workload and preserve preparation/configuration scope.|
|RT-05|The worker-hours are projections. Printed latency rounding is compatible with the reported hours, but does not reconstruct them exactly.|
|S6|The 2.46 result is a mean of paired reserved-vCPU-hour ratios, including idle capacity. The steady-step interval remains inconclusive.|

The full JSON preserves each checked statement, version, locator, observation, evidence class, source hash and disposition. Precision notes concern RT-05, A1, AF-C4 and E01. Original dated model records and the 251-entry ledger remain intact. Human confirmations are recorded separately; neither inter-rater agreement nor independent system replication is claimed.
