<script>
  // The story comes from story.json (written by story.py). Edit the text there or re-run story.py.
  import story from "./story.json";
  import Scrolly from "./lib/Scrolly.svelte";
  import StoryMap from "./lib/StoryMap.svelte";
  import Compare from "./lib/Compare.svelte";
  let index = $state(0), progress = $state(0);
  const steps = story.steps, firstMap = steps.find(s => s.kind === "map");
  const step = $derived(steps[index]);
  // the picture behind the text: the last image/compare step reached, or the map
  const shown = $derived(step.kind === "image" || step.kind === "compare" ? index : step.kind === "map" ? -1 : lastPicture(index));
  function lastPicture(i) { for (let k = i; k >= 0; k--) { if (steps[k].kind === "map") return -1; if (steps[k].kind !== "text") return k; } return -1; }
  const sources = [story.sources, ...story.credits].filter(Boolean).concat(story.map ? ["Maps: OpenFreeMap © OpenMapTiles, data © OpenStreetMap contributors."] : []);
  $effect(() => { document.documentElement.dataset.theme = story.theme; document.title = story.title; });
</script>

<header class="hero"><div>
  <div class="kicker">Story</div><h1 class="serif">{story.title}</h1><p class="dek serif">{story.dek}</p><div class="byline">{story.byline}</div><div class="cue">Scroll ↓</div>
</div></header>

<section class="scrolly">
  <div class="graphic">
    {#if firstMap}<StoryMap step={steps[index].kind === "map" ? steps[index] : null} theme={story.theme} first={firstMap} />{/if}
    {#each steps as s, i}
      {#if s.kind === "image"}
        <div class="layer" class:on={shown === i} class:cover={s.fit === "cover"}><img src={s.src} alt={s.alt}>{#if s.credit}<div class="credit">{s.credit}</div>{/if}</div>
      {:else if s.kind === "compare"}
        <div class="layer" class:on={shown === i}><Compare before={s.before} after={s.after} labels={s.labels} split={index === i ? Math.max(0.02, Math.min(0.98, progress * 1.25)) : 0.5} />{#if s.credit}<div class="credit">{s.credit}</div>{/if}</div>
      {/if}
    {/each}
    <div class="dim" class:on={step.kind === "text"}></div>
  </div>
  <div class="steps">
    <Scrolly bind:value={index} bind:progress>
      {#each steps as s, i}
        <div class="step" class:on={index === i} class:text-only={s.kind === "text"}><div class="card">{@html s.html}</div></div>
      {/each}
    </Scrolly>
  </div>
</section>

<footer><h2>Sources and credits</h2><ul>{#each sources as s}<li>{s}</li>{/each}</ul><p>Made with osint-visuals.</p></footer>

<style>
  .hero { min-height:92vh; display:grid; align-content:center; padding:10vh 7vw 6vh; max-width:980px; }
  .kicker { font:800 14px system-ui, sans-serif; letter-spacing:.2em; color:var(--accent); text-transform:uppercase; }
  h1 { font-size:clamp(38px, 6.2vw, 76px); line-height:1.04; margin:.25em 0 .3em; }
  .dek { font-size:clamp(20px, 2.2vw, 26px); color:var(--dim); max-width:760px; margin:0 0 1.2em; }
  .byline { font-weight:600; color:var(--dim); font-size:16px; } .cue { margin-top:9vh; color:var(--dim); font-size:15px; }
  .scrolly { position:relative; } .graphic { position:sticky; top:0; height:100vh; overflow:hidden; }
  .layer { position:absolute; inset:0; opacity:0; transition:opacity .6s ease; display:grid; place-items:center; background:var(--bg); z-index:3; }
  .layer.on { opacity:1; } .layer img { width:100%; height:100%; object-fit:contain; } .layer.cover img { object-fit:cover; }
  .credit { position:absolute; left:12px; bottom:10px; font-size:12px; color:#fff; background:rgba(0,0,0,.55); padding:3px 8px; border-radius:6px; max-width:60%; }
  .dim { position:absolute; inset:0; background:var(--shade); opacity:0; transition:opacity .5s; pointer-events:none; z-index:4; } .dim.on { opacity:1; }
  .steps { position:relative; z-index:2; margin-top:-100vh; padding:0 5vw 40vh; pointer-events:none; }
  .step { min-height:95vh; display:flex; align-items:center; }
  .card { pointer-events:auto; max-width:440px; background:var(--card); border:1px solid var(--line); border-radius:14px; padding:22px 26px; box-shadow:0 10px 40px rgba(0,0,0,.35); opacity:.35; transform:translateY(10px); transition:opacity .4s, transform .4s; }
  .step.on .card { opacity:1; transform:none; } .text-only { justify-content:center; } .text-only .card { max-width:640px; font-size:21px; }
  .card :global(p) { margin:0 0 .7em; } .card :global(p:last-child) { margin:0; }
  footer { max-width:780px; padding:8vh 7vw 12vh; color:var(--dim); font-size:15px; } footer h2 { color:var(--ink); font-size:20px; }
  @media (prefers-reduced-motion: reduce) { .layer, .dim, .card { transition:none; } }
  @media (max-width:720px) { .steps { padding:0 16px 40vh; } .step { justify-content:center; } .card { max-width:100%; padding:18px 20px; font-size:17px; } }
</style>
