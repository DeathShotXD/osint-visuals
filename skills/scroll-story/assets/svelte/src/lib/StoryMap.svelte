<script>
  // A MapLibre map that flies to each map step. Tiles: OpenFreeMap (keyless, OpenStreetMap data).
  import { Map as MapLibreMap, Marker } from "maplibre-gl";   // MapLibre 6 has named exports only
  let { step, theme = "dark", first } = $props();
  let el, map, markers = [];
  const reduce = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
  $effect(() => {
    map = new MapLibreMap({ container: el, style: `https://tiles.openfreemap.org/styles/${theme === "light" ? "positron" : "dark"}`,
      center: first.center, zoom: first.zoom, pitch: first.pitch, bearing: first.bearing, interactive: false,
      attributionControl: { compact: true, customAttribution: "OpenFreeMap" } });
    return () => map.remove();
  });
  $effect(() => {
    if (!map || !step || step.kind !== "map") return;
    const view = { center: step.center, zoom: step.zoom, pitch: step.pitch, bearing: step.bearing };
    reduce ? map.jumpTo(view) : map.flyTo({ ...view, duration: 2400, essential: true });
    markers.forEach(m => m.remove());
    markers = [step.marker, ...(step.markers || [])].filter(Boolean).map(mk => {
      const pin = document.createElement("div"); pin.className = "pin"; pin.innerHTML = "<i></i><span></span>"; pin.querySelector("span").textContent = mk.label;
      return new Marker({ element: pin, anchor: "left" }).setLngLat(mk.lnglat).addTo(map); });
  });
</script>
<div class="map" bind:this={el}></div>
<style>
  .map { position:absolute; inset:0; }
  :global(.pin) { display:flex; align-items:center; gap:8px; transform:translateY(-50%); }
  :global(.pin i) { width:16px; height:16px; border-radius:50%; background:var(--mark); border:3px solid #fff; box-shadow:0 0 0 6px rgba(255,90,74,.25); flex:none; }
  :global(.pin span) { font:800 14px system-ui, sans-serif; color:#fff; background:var(--mark); padding:4px 9px; border-radius:6px; white-space:nowrap; }
</style>
