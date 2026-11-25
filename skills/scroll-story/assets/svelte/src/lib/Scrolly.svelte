<script>
  // Which step is in the middle of the screen, and how far the reader is through it (0 to 1).
  // Same idea as The Pudding's Scrolly component; IntersectionObserver plus a scroll listener, no library.
  let { value = $bindable(0), progress = $bindable(0), children } = $props();
  let root;
  $effect(() => {
    const steps = [...root.children];
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) value = steps.indexOf(e.target); }), { rootMargin: "-50% 0px -50% 0px" });
    steps.forEach(s => io.observe(s));
    const onScroll = () => { const r = steps[value]?.getBoundingClientRect(); if (r) progress = Math.max(0, Math.min(1, (innerHeight / 2 - r.top) / r.height)); };
    addEventListener("scroll", onScroll, { passive: true }); onScroll();
    return () => { io.disconnect(); removeEventListener("scroll", onScroll); };
  });
</script>
<div bind:this={root}>{@render children()}</div>
