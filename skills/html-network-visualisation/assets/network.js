"use strict";
(() => {
  const G = JSON.parse(document.getElementById("network-data").textContent);
  const $ = id => document.getElementById(id);
  const el = (tag, text, parent, cls) => {
    const n = document.createElement(tag);
    n.dir = "auto";
    if (text !== undefined && text !== null) n.textContent = String(text);
    if (cls) n.className = cls;
    if (parent) parent.append(n);
    return n;
  };
  const link = (text, href, parent) => {
    if (!href) return;
    const a = el("a", text, parent); a.href = href; a.target = "_blank"; a.rel = "noopener noreferrer";
    return a;
  };
  const fmt = x => Number(x).toLocaleString("en-GB");
  const nodeMap = new Map(G.nodes.map(n => [n.id, n]));
  const edgeMap = new Map(G.edges.map(e => [e.id, e]));
  const kinds = Object.fromEntries(Object.entries(G.types).map(([k,v])=>[k,v.label]));
  const shapes = Object.fromEntries(Object.entries(G.types).map(([k,v])=>[k,v.shape||"dot"]));
  const primary = G.primary_type || Object.keys(G.types)[0];
  const state = {selected:null,selectedEdge:null,physics:true,pinned:new Set(),positions:{},visibleNodes:[],visibleEdges:[],tablePage:0,table:false};
  const dataNodes = new vis.DataSet(), dataEdges = new vis.DataSet();
  const relationChecks = Object.create(null);
  const graphemes=text=>typeof Intl.Segmenter==="function"?[...new Intl.Segmenter(undefined,{granularity:"grapheme"}).segment(text)].map(s=>s.segment):[...text];
  const shortLabel=text=>{const letters=graphemes(text);return letters.length>62?letters.slice(0,59).join("")+"…":text;};
  Object.entries(G.relations).forEach(([key, value]) => {
    const label = el("label", undefined, $("relationFilters"));
    const input = el("input", undefined, label); input.type = "checkbox"; input.checked = value.default;
    input.dataset.relation = key; input.id = "relation-" + key;
    relationChecks[key] = input; label.append(document.createTextNode(value.label));
    input.addEventListener("change", () => applyFilters());
  });
  document.title = G.title;
  $("networkTitle").textContent = G.title;
  $("subtitle").textContent = G.subtitle || "";
  $("handling").textContent = G.handling;
  $("scopeNote").textContent = G.scope_note;
  $("footerNote").textContent = G.footer_note || "Positions reflect graph layout, not geography or influence.";
  (G.links||[]).forEach(item=>link(item.label,item.href,$("headerLinks")));
  Object.entries(G.types).forEach(([key,item])=>el("span",`${item.shape||"dot"} · ${item.label}`,$("typeLegend")));
  $("summaryStats").textContent = `${fmt(G.counts.nodes)} nodes · ${fmt(G.counts.edges)} links · ${fmt(G.counts.records)} records. Needs review: ${fmt(G.counts.review_records)}.`;
  if (window.matchMedia("(max-width:600px)").matches) $("controlDetails").open = false;

  function fitGraph(){network.fit({animation:false});network.moveTo({scale:network.getScale()*.85,animation:false});}
  function physicsOptions() {
    return {enabled:state.physics,solver:"barnesHut",barnesHut:{theta:.65,gravitationalConstant:-Number($("repulsion").value),centralGravity:.12,springLength:Number($("spring").value),springConstant:.035,damping:Number($("damping").value),avoidOverlap:.25},maxVelocity:35,minVelocity:.5,stabilization:{enabled:true,iterations:180,updateInterval:25,fit:true}};
  }
  const network = new vis.Network($("graph"),{nodes:dataNodes,edges:dataEdges},{
    autoResize:true,layout:{randomSeed:37,improvedLayout:false},physics:physicsOptions(),
    nodes:{shape:"dot",borderWidth:1.5,font:{face:"system-ui",size:13,color:"#eef2f0",strokeWidth:3,strokeColor:"#0b0e11"},scaling:{min:6,max:22,label:{enabled:true,min:10,max:16,drawThreshold:6}},chosen:true},
    edges:{smooth:false,color:{color:"#7a9380",highlight:"#5bbf4b",opacity:.55},width:1,selectionWidth:2,hoverWidth:1.2,arrows:{to:{enabled:true,scaleFactor:.35}}},
    interaction:{hover:true,dragNodes:true,dragView:true,zoomView:true,hideEdgesOnDrag:true,hideEdgesOnZoom:true,keyboard:{enabled:true,bindToWindow:false,autoFocus:false},selectConnectedEdges:true}
  });
  network.on("stabilizationProgress", p => { $("physicsStatus").textContent = `Settling layout · ${Math.round(100*p.iterations/p.total)}%`; });
  network.on("stabilizationIterationsDone", () => { $("physicsStatus").textContent = state.physics ? "Physics on · drag to move" : "Physics paused"; });
  network.on("stabilized", () => { $("physicsStatus").textContent = state.physics ? "Layout settled · physics ready" : "Physics paused"; });
  network.on("dragEnd", () => { Object.assign(state.positions,network.getPositions()); });
  network.on("click", p => {
    if (p.nodes.length) selectNode(p.nodes[0],false);
    else if (p.edges.length) selectEdge(p.edges[0]);
  });

  function activeIds(ids) { return ids.filter(id => $("includeReview").checked || G.records[id].status !== "review"); }
  function evidenceState(ids) {
    const review = ids.filter(id => G.records[id].status === "review").length;
    return {review,checked:ids.length-review};
  }
  function filters() {
    return {relations:Object.fromEntries(Object.entries(relationChecks).map(([k,v])=>[k,v.checked])),includeReview:$("includeReview").checked,includeIsolates:$("includeIsolates").checked,focusDepth:Number($("focusDepth").value),labels:$("showLabels").checked};
  }
  function computeVisible() {
    const f = filters();
    let edges = G.edges.filter(e => f.relations[e.relation]).map(e => ({...e,active:activeIds(e.mentions)})).filter(e => e.active.length);
    const nodeIds = new Set(edges.flatMap(e => [e.from,e.to]));
    if (f.includeIsolates) G.nodes.forEach(n => { if(activeIds(n.mentions).length) nodeIds.add(n.id); });
    if (state.selected && f.focusDepth) {
      const neighbourhood = new Set([state.selected]);
      let frontier = new Set([state.selected]);
      for(let i=0;i<f.focusDepth;i++) {
        const next = new Set();
        edges.forEach(e => {
          if(frontier.has(e.from)) next.add(e.to);
          if(frontier.has(e.to)) next.add(e.from);
        });
        next.forEach(n=>neighbourhood.add(n)); frontier=next;
      }
      edges = edges.filter(e=>neighbourhood.has(e.from)&&neighbourhood.has(e.to));
      nodeIds.forEach(n=>{if(!neighbourhood.has(n))nodeIds.delete(n);});
      if(activeIds(nodeMap.get(state.selected).mentions).length)nodeIds.add(state.selected);
    }
    return {nodes:[...nodeIds].map(id=>nodeMap.get(id)),edges};
  }
  function applyFilters(fit=true,compact=false) {
    Object.assign(state.positions,network.getPositions());
    const view = computeVisible(); state.visibleNodes=view.nodes;state.visibleEdges=view.edges;state.tablePage=0;
    if(compact && Number($("focusDepth").value)>0 && state.selected) {
      const centre=state.positions[state.selected]||{x:0,y:0};
      view.nodes.forEach((n,i)=>{if(n.id===state.selected||state.pinned.has(n.id))return;const angle=i*2.399963, radius=100+35*Math.sqrt(i);state.positions[n.id]={x:centre.x+radius*Math.cos(angle),y:centre.y+radius*Math.sin(angle)};});
    }
    const degrees = new Map(); view.edges.forEach(e=>{degrees.set(e.from,(degrees.get(e.from)||0)+1);degrees.set(e.to,(degrees.get(e.to)||0)+1);});
    dataEdges.clear();dataNodes.clear();
    dataNodes.add(view.nodes.map(n=>{
      const ids=activeIds(n.mentions),s=evidenceState(ids),degree=degrees.get(n.id)||0;
      const style={background:n.kind===primary?"#254425":"#252e32",border:s.review?"#c7d0da":n.kind===primary?"#5bbf4b":"#7e91a4",highlight:{background:"#254425",border:"#5bbf4b"},hover:{background:"#263e52",border:"#5bbf4b"}};
      return {id:n.id,label:$("showLabels").checked?shortLabel(n.label):"",shape:shapes[n.kind]||"dot",value:Math.min(35,1+degree),mass:1+Math.min(8,Math.log2(1+degree)),color:style,shapeProperties:{borderDashes:s.review?[5,4]:false},fixed:state.pinned.has(n.id)?{x:true,y:true}:false,...(state.positions[n.id]||{})};
    }));
    dataEdges.add(view.edges.map(e=>{const s=evidenceState(e.active);return{id:e.id,from:e.from,to:e.to,width:1+Math.min(5,Math.log2(e.active.length+1))*.6,dashes:s.review?[6,4]:false,arrows:{to:{enabled:e.directed!==false,scaleFactor:.35}},color:{color:s.review?"#8996a5":"#5bbf4b",highlight:"#5bbf4b",opacity:s.review?.5:.42}};}));
    network.setOptions({physics:physicsOptions()});
    $("liveStats").textContent=`${fmt(view.nodes.length)} / ${fmt(G.counts.nodes)} nodes · ${fmt(view.edges.length)} / ${fmt(G.counts.edges)} links`;
    $("pinSelected").disabled=!state.selected || !dataNodes.get(state.selected);
    if(state.selected && dataNodes.get(state.selected))network.selectNodes([state.selected]);
    if(fit && view.nodes.length)requestAnimationFrame(()=>{network.redraw();fitGraph();});
    if(!view.nodes.length)$("physicsStatus").textContent="No nodes match these filters";
    else if(!state.physics)network.stopSimulation();
    renderTable();
    if(state.selectedEdge)inspectEdgeAfterFilter();
    else if(state.selected)inspectNode(state.selected);
  }
  function tag(text,parent,cls="") { return el("span",text,parent,"tag "+cls); }
  function renderRecord(record,parent,relation) {
    const details=el("details",undefined,parent);
    const summary=el("summary",`${record.label} · ${record.status==="review"?"needs review":"recorded support"}`,details);
    details.addEventListener("toggle",()=>{
      if(!details.open||details.dataset.ready)return;
      details.dataset.ready="1";
      if(record.details)el("p",record.details,details);
      const dl=el("dl",undefined,details);
      Object.entries(record.fields||{}).forEach(([key,value])=>{el("dt",key,dl);el("dd",typeof value==="string"?value:JSON.stringify(value),dl);});
      (record.uncertainty||[]).forEach(text=>el("p",text,details,"small"));
      (record.sources||[]).forEach(source=>{
        const section=el("div",undefined,details);
        if(source.label)el("h3",source.label,section);
        if(source.locator)el("p",source.locator,section,"small");
        if(source.quote)el("blockquote",source.quote,section);
        if(source.href)link("Open source",source.href,section);
      });
    });
    return summary;
  }
  function recordList(ids,parent,field) {
    const active=activeIds(ids),box=el("div",undefined,parent);let shown=0;
    const more=el("button","Show more records",parent);
    const add=()=>{active.slice(shown,shown+15).forEach(id=>renderRecord(G.records[id],box,field));shown+=15;more.hidden=shown>=active.length;};
    more.addEventListener("click",add);add();
  }
  function inspectNode(id) {
    const n=nodeMap.get(id),parent=$("inspector");parent.replaceChildren();
    el("p",kinds[n.kind],parent,"meta");el("h2",n.label,parent,"name");
    const ids=activeIds(n.own_mentions.length?n.own_mentions:n.mentions),s=evidenceState(ids);
    if(n.details)el("p",n.details,parent);
    if(G.identity_note)el("p",G.identity_note,parent,"small");
    if(s.checked)tag(`Recorded support: ${fmt(s.checked)}`,parent,"checked");
    if(s.review)tag(`Needs review: ${fmt(s.review)}`,parent,"review");
    const nearby=state.visibleEdges.filter(e=>e.from===id||e.to===id).sort((a,b)=>b.active.length-a.active.length);
    el("h3",`Visible connections: ${fmt(nearby.length)}`,parent);
    const connections=el("div",undefined,parent);
    nearby.slice(0,40).forEach(e=>{const other=nodeMap.get(e.from===id?e.to:e.from),arrow=e.directed===false?"↔":e.from===id?"→":"←";const button=el("button",`${G.relations[e.relation].label} ${arrow} ${other.label} (${e.active.length})`,connections,"node-link");button.addEventListener("click",()=>selectEdge(e.id));});
    if(nearby.length>40)el("p","More connections are available in the connection table or after narrowing the graph.",parent,"small");
    el("h3","Source records",parent);recordList(ids,parent);
  }
  function selectNode(id,focus=true) {
    const n=nodeMap.get(id);if(!n)return;
    state.selected=id;state.selectedEdge=null;
    if(!activeIds(n.mentions).length)$("includeReview").checked=true;
    if(!dataNodes.get(id))$("includeIsolates").checked=true;
    if(Number($("focusDepth").value)||!dataNodes.get(id))applyFilters(false);
    if(dataNodes.get(id)){
      network.selectNodes([id]);
      if(focus)network.focus(id,{scale:Math.max(.55,network.getScale()),animation:false});
    }
    $("pinSelected").disabled=false;$("pinSelected").textContent=state.pinned.has(id)?"Unpin selected node":"Pin selected node";
    inspectNode(id);$("searchResults").replaceChildren();
  }
  function inspectEdgeAfterFilter() {
    const id=state.selectedEdge;
    if(state.visibleEdges.some(e=>e.id===id))selectEdge(id);
    else {state.selectedEdge=null;$("inspector").replaceChildren();el("p","This connection has no visible support under the current filters.",$("inspector"));}
  }
  function selectEdge(id) {
    const e=edgeMap.get(id);if(!e)return;
    state.selectedEdge=id;const parent=$("inspector");parent.replaceChildren();
    el("p","Connection",parent,"meta");el("h2",G.relations[e.relation].label,parent);
    [e.from,e.to].forEach(nid=>{const button=el("button",nodeMap.get(nid).label,parent,"node-link");button.addEventListener("click",()=>selectNode(nid));});
    const ids=activeIds(e.mentions),s=evidenceState(ids);
    if(s.checked)tag(`Recorded support: ${fmt(s.checked)}`,parent,"checked");if(s.review)tag(`Needs review: ${fmt(s.review)}`,parent,"review");
    el("p",G.relations[e.relation].description || "Inspect the supporting records to assess this connection.",parent,"small");
    el("p",e.directed===false?"Undirected connection":"Direction: from the first node to the second",parent,"small");
    if(dataEdges.get(id))network.selectEdges([id]);
    recordList(ids,parent,e.relation);
  }
  function renderTable(printAll=false) {
    if(!state.table&&!printAll)return;
    const edges=state.visibleEdges,start=printAll?0:state.tablePage*100,body=$("edgeRows");body.replaceChildren();
    edges.slice(start,printAll?edges.length:start+100).forEach(e=>{
      const row=el("tr",undefined,body);
      [e.from,null,e.to].forEach((id,i)=>{const td=el("td",undefined,row);if(id){const button=el("button",nodeMap.get(id).label,td);button.addEventListener("click",()=>selectNode(id));}else{const button=el("button",G.relations[e.relation].label+(e.directed===false?" ↔":" →"),td);button.addEventListener("click",()=>selectEdge(e.id));}});
      el("td",e.active.length,row);const s=evidenceState(e.active);el("td",s.review?`${s.review} review; ${s.checked} recorded`:"Recorded support",row);
    });
    $("tableCaption").textContent="The table follows the graph filters. Select a connection to inspect its source excerpts.";
    $("tablePage").textContent=`${edges.length?start+1:0}–${Math.min(start+100,edges.length)} of ${fmt(edges.length)}`;
    $("previousRows").disabled=state.tablePage===0;$("nextRows").disabled=start+100>=edges.length;
  }
  function setTable(on) {state.table=on;$("graph").hidden=on;$("tablePanel").hidden=!on;$("graphTab").setAttribute("aria-pressed",String(!on));$("tableTab").setAttribute("aria-pressed",String(on));renderTable();if(!on)network.redraw();}
  function updatePhysics() {
    state.physics=$("physics").checked;
    $("repulsionValue").textContent=fmt($("repulsion").value);$("springValue").textContent=$("spring").value;$("dampingValue").textContent=Number($("damping").value).toFixed(2);
    network.setOptions({physics:physicsOptions()});
    if(state.physics)network.startSimulation();else network.stopSimulation();
    $("physicsStatus").textContent=state.physics?"Physics on · settling":"Physics paused";
  }

  function exportPNG() {
    const source=network.canvas.frame.canvas, width=1600, pad=48;
    const canvas=document.createElement("canvas"),ctx=canvas.getContext("2d");
    const wrap=(text,size)=>{
      ctx.font=`${size}px system-ui`;const lines=[];let line="";
      const segmenter=typeof Intl.Segmenter==="function"?new Intl.Segmenter(undefined,{granularity:"grapheme"}):null;
      for(const word of String(text).split(/\s+/)){
        const next=line?line+" "+word:word;
        if(ctx.measureText(next).width<=width-2*pad){line=next;continue;}
        if(line){lines.push({text:line,size});line="";}
        const letters=segmenter?[...segmenter.segment(word)].map(s=>s.segment):[...word];
        for(const letter of letters){if(line&&ctx.measureText(line+letter).width>width-2*pad){lines.push({text:line,size});line="";}line+=letter;}
      }
      if(line)lines.push({text:line,size});return lines;
    };
    const activeRecords=[...new Set(state.visibleNodes.flatMap(n=>activeIds(n.mentions)))];
    const sources=[...new Set(activeRecords.flatMap(id=>(G.records[id].sources||[]).map(s=>s.label||"Unlabelled source")))];
    const heading=[...wrap(G.handling,16),...wrap(G.title,32),...wrap(G.scope_note,19)];
    const foot=[...wrap(`${state.visibleNodes.length}/${G.counts.nodes} nodes; ${state.visibleEdges.length}/${G.counts.edges} links. Review support ${$("includeReview").checked?"included":"excluded"}.`,18),...wrap("Sources: "+(sources.join("; ")||"Not stated"),18),...wrap(G.footer_note||"Line weight counts records; layout is not geography or influence.",18)];
    const graphHeight=Math.max(400,Math.round((width-2*pad)*source.height/source.width));
    canvas.width=width;canvas.height=pad*2+heading.reduce((n,l)=>n+l.size+10,0)+graphHeight+foot.reduce((n,l)=>n+l.size+10,0)+24;
    ctx.fillStyle="#0b0e11";ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle="#eef2f0";
    let y=pad;
    const probe=document.createElement("span");probe.dir="auto";probe.style.cssText="position:fixed;visibility:hidden";document.body.append(probe);
    const draw=line=>{probe.textContent=line.text;const rtl=getComputedStyle(probe).direction==="rtl";ctx.direction=rtl?"rtl":"ltr";ctx.textAlign=rtl?"right":"left";ctx.textBaseline="top";ctx.font=`${line.size}px system-ui`;ctx.fillText(line.text,rtl?width-pad:pad,y);y+=line.size+10;};
    heading.forEach(draw);
    network.redraw();ctx.drawImage(source,pad,y,width-2*pad,graphHeight);y+=graphHeight+24;
    foot.forEach(draw);probe.remove();
    canvas.toBlob(blob=>{if(blob)downloadBlob(blob,"network.png");},"image/png");
  }
  function downloadBlob(blob,name){const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  $("exportPNG").addEventListener("click",exportPNG);

  function exportView() {
    Object.assign(state.positions,network.getPositions());
    return {schema_version:1,title:G.title,handling:G.handling,exported_utc:new Date().toISOString(),filters:filters(),physics:{enabled:state.physics,repulsion:Number($("repulsion").value),springLength:Number($("spring").value),damping:Number($("damping").value)},selected_node:state.selected,selected_edge:state.selectedEdge,pinned_nodes:[...state.pinned],positions:state.positions,visible_node_ids:state.visibleNodes.map(n=>n.id),visible_edge_ids:state.visibleEdges.map(e=>e.id)};
  }
  const foldSearch=value=>String(value).normalize("NFKC").toLowerCase().normalize("NFD").replace(/\p{M}/gu,"").replace(/ß/g,"ss");
  $("search").addEventListener("input",()=>{
    const query=foldSearch($("search").value.trim()),box=$("searchResults");box.replaceChildren();if(!query)return;
    G.nodes.filter(n=>foldSearch(n.label).includes(query)).sort((a,b)=>b.mentions.length-a.mentions.length).slice(0,35).forEach(n=>{const button=el("button",n.label,box);el("span",kinds[n.kind],button,"meta");button.addEventListener("click",()=>selectNode(n.id));});
    if(!box.children.length)el("p","No exact-text matches.",box,"small");
  });
  $("search").addEventListener("keydown",e=>{if(e.key==="Enter"){const button=$("searchResults").querySelector("button");if(button){e.preventDefault();button.click();}}});
  ["includeReview","includeIsolates","focusDepth","showLabels"].forEach(id=>$(id).addEventListener("change",()=>applyFilters(true,id==="focusDepth")));
  ["physics","repulsion","spring","damping"].forEach(id=>$(id).addEventListener("input",updatePhysics));
  $("reheat").addEventListener("click",()=>{$("physics").checked=true;updatePhysics();});
  $("fit").addEventListener("click",()=>fitGraph());
  $("pinSelected").addEventListener("click",()=>{const id=state.selected;if(!id)return;if(state.pinned.has(id))state.pinned.delete(id);else state.pinned.add(id);dataNodes.update({id,fixed:state.pinned.has(id)?{x:true,y:true}:false});$("pinSelected").textContent=state.pinned.has(id)?"Unpin selected node":"Pin selected node";});
  $("allConnections").addEventListener("click",()=>{Object.values(relationChecks).forEach(n=>n.checked=true);$("includeIsolates").checked=true;$("includeReview").checked=true;$("focusDepth").value="0";applyFilters();});
  $("resetFilters").addEventListener("click",()=>{Object.entries(relationChecks).forEach(([key,n])=>n.checked=G.relations[key].default);$("includeIsolates").checked=false;$("includeReview").checked=true;$("focusDepth").value="0";applyFilters();});
  $("graphTab").addEventListener("click",()=>setTable(false));$("tableTab").addEventListener("click",()=>setTable(true));
  $("previousRows").addEventListener("click",()=>{state.tablePage=Math.max(0,state.tablePage-1);renderTable();});$("nextRows").addEventListener("click",()=>{state.tablePage++;renderTable();});
  $("downloadView").addEventListener("click",()=>{const blob=new Blob([JSON.stringify(exportView(),null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=el("a",undefined,document.body);a.href=url;a.download="network_view.json";a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);$("exportStatus").textContent="Current view downloaded as JSON. Repository files are unchanged.";});
  $("copyView").addEventListener("click",async()=>{const text=JSON.stringify(exportView(),null,2);try{if(!navigator.clipboard)throw new Error("Clipboard unavailable");await navigator.clipboard.writeText(text);$("exportStatus").textContent="Current view copied as JSON.";}catch{ $("exportPanel").hidden=false;$("exportText").value=text;$("exportText").focus();$("exportText").select();$("exportStatus").textContent="Use the selectable JSON fallback or Download view.";}});
  $("closeExport").addEventListener("click",()=>$("exportPanel").hidden=true);
  let printDetails=[];
  window.addEventListener("beforeprint",()=>{
    renderTable(true);printDetails=[...$("inspector").querySelectorAll("details")].map(d=>[d,d.open]);
    printDetails.forEach(([d])=>{d.open=true;d.dispatchEvent(new Event("toggle"));});
  });
  window.addEventListener("afterprint",()=>{printDetails.forEach(([d,open])=>d.open=open);if(state.table)renderTable();});
  window.networkViewer={data:G,network,state,computeVisible,applyFilters,selectNode,selectEdge,exportView};
  applyFilters();
})();
