<script>
  // Before/after with a divider driven by `split` (0 to 1): the parent ties it to scroll progress.
  let { before, after, labels, split = 0.5 } = $props();
</script>
<div class="cmp">
  <img class="bot" src={after} alt={`After: ${labels[1]}`}>
  <img class="top" src={before} alt={`Before: ${labels[0]}`} style:clip-path={`inset(0 ${(1 - split) * 100}% 0 0)`}>
  <div class="bar" style:left={`${split * 100}%`}></div>
  <div class="lab b">Before · {labels[0]}</div><div class="lab a">After · {labels[1]}</div>
</div>
<style>
  .cmp { position:absolute; inset:0; } img { position:absolute; inset:0; width:100%; height:100%; object-fit:cover; }
  .bar { position:absolute; top:0; bottom:0; width:4px; margin-left:-2px; background:#fff; box-shadow:0 0 12px rgba(0,0,0,.5); }
  .lab { position:absolute; top:16px; font:800 15px system-ui, sans-serif; padding:6px 12px; border-radius:7px; color:#fff; }
  .b { left:16px; background:rgba(10,13,16,.85); } .a { right:16px; background:var(--mark); }
</style>
