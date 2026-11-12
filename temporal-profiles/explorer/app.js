(function (global) {
  'use strict';
  function compareProfiles(a, b) {
    // Match reference selection: cost first, then stored profile order
    // (loss ascending / W2 descending, then W3 ascending); IDs break exact ties.
    return a.total_cost - b.total_cost || b.w2 - a.w2 || a.w3 - b.w3 || JSON.stringify(a.deleted_ids.slice().sort()).localeCompare(JSON.stringify(b.deleted_ids.slice().sort()));
  }
  function selectTarget(table, request) {
    const result = {status:'invalid', profile:null, candidates:[], minimumCost:null};
    if (!table || !request || !['exact','upper'].includes(request.mode) || !Number.isSafeInteger(request.target) || request.target < 0 || (request.budget !== null && (!Number.isSafeInteger(request.budget) || request.budget < 0))) return result;
    if (table.status === 'infeasible') return Object.assign(result, {status:'quota_infeasible'});
    const matches = table.profiles.filter(p => request.mode === 'exact' ? p.w3 === request.target : p.w3 <= request.target).slice().sort(compareProfiles);
    if (!matches.length) return Object.assign(result, {status:'unattainable'});
    return {status:request.budget !== null && matches[0].total_cost > request.budget ? 'over_budget':'success', profile:matches[0], candidates:matches, minimumCost:matches[0].total_cost};
  }
  function countWalks(events, root) {
    let w2 = 0, w3 = 0;
    events.forEach(c => { if (c.target !== root) return; events.forEach(b => { if (b.target !== c.source || b.time >= c.time) return; w2++; events.forEach(a => { if (a.target === b.source && a.time < b.time) w3++; }); }); });
    return {w2,w3};
  }
  global.TemporalExplorer = {selectTarget, compareProfiles, countWalks};
  if (typeof document === 'undefined') return;

  const $ = id => document.getElementById(id);
  const ns = 'http://www.w3.org/2000/svg';
  const state = {caseIndex:0, inspected:null, graphMode:'witness', request:null, selection:null, table:null};
  const data = global.TEMPORAL_EXPLORER_DATA;
  let resizeTimer;
  function text(id, value) { $(id).textContent = value; }
  function clear(el) { while(el.firstChild) el.removeChild(el.firstChild); }
  function node(tag, attrs, content) { const n = document.createElement(tag); if (attrs) Object.keys(attrs).forEach(k => n.setAttribute(k, attrs[k])); if (content !== undefined) n.textContent = content; return n; }
  function svgNode(tag, attrs, content) { const n = document.createElementNS(ns, tag); Object.keys(attrs || {}).forEach(k => n.setAttribute(k, attrs[k])); if (content !== undefined) n.textContent = content; return n; }
  function currentCase() { return data.cases[state.caseIndex]; }
  function viewedProfile() { return state.inspected || (state.selection && state.selection.profile); }
  function sameProfile(a,b) { return !!a && !!b && a.w2 === b.w2 && a.w3 === b.w3; }
  function eventAlias(event,index) { return event.id.length <= 9 ? event.id : 'E' + (index + 1); }
  function goalText() { return 'W3 ' + (state.request.mode === 'exact' ? '= ' : '≤ ') + state.request.target; }
  function meetsTarget(p) { return state.request.mode === 'exact' ? p.w3 === state.request.target : p.w3 <= state.request.target; }
  function withinBudget(p) { return state.request.budget === null || p.total_cost <= state.request.budget; }
  function readRequest() { return {mode:document.querySelector('input[name="target-mode"]:checked').value, target:$('target-w3').valueAsNumber, budget:$('budget-enabled').checked ? $('cost-budget').valueAsNumber : null}; }

  function setExample(index) {
    state.caseIndex = index; state.inspected = null; state.graphMode = 'witness';
    const c = currentCase(); $('example-select').value = c.id; $('min-w2').max = c.original.w2; $('min-w2').value = c.default_quota; $('target-w3').value = c.default_target;
    document.querySelector('input[name="target-mode"][value="' + c.default_mode + '"]').checked = true;
    $('budget-enabled').checked = c.default_budget !== null; $('cost-budget').disabled = c.default_budget === null; $('cost-budget').value = c.default_budget === null ? 3 : c.default_budget;
    text('example-description',c.description); text('example-lesson',c.lesson);
    refresh();
  }
  function refresh() {
    const c = currentCase(), quota = $('min-w2').valueAsNumber;
    state.request = readRequest(); state.table = c.quotas.find(q => q.min_w2 === quota) || null;
    state.selection = selectTarget(state.table, state.request);
    text('quota-help', 'Original history: W2 = ' + c.original.w2 + '. Choose 0–' + c.original.w2 + '.');
    renderStatus(); renderProfileTable(); renderView();
  }
  function renderStatus() {
    const s = state.selection, t = state.table, c = currentCase();
    const descriptions = {
      success:['Target attained at minimum cost', goalText() + ' is attainable while keeping W2 ≥ ' + t?.min_w2 + '. Minimum total deletion cost: ' + s.minimumCost + '.'],
      quota_infeasible:['Preservation quota is infeasible', 'Mandatory deletions leave W2 = ' + t?.baseline.w2 + ', below the requested minimum ' + t?.min_w2 + '. No legal deletion choice can restore those walks.'],
      unattainable:['This target is unattainable', goalText() + ' cannot be attained at any deletion cost under the current preservation and keep/delete constraints. ' + (state.request.mode === 'exact' ? 'Try “At most” or inspect the attainable table.' : 'Inspect the table or relax the target or preservation requirement.')],
      over_budget:['The target is attainable, but over budget', 'Its minimum total cost is ' + s.minimumCost + '; your limit is ' + state.request.budget + '. That lowest-cost candidate is available to inspect, but exceeds the limit.'],
      invalid:['Check the requested values', 'Use whole numbers: preservation from 0 to ' + c.original.w2 + ', and a nonnegative target and optional cost limit.']
    };
    const desc = descriptions[s.status]; text('status-title',desc[0]); text('status-description',desc[1]);
    $('result-status').className = 'result-status' + (['unattainable','quota_infeasible','invalid'].includes(s.status) ? ' error' : s.status === 'over_budget' ? ' warning' : '');
    document.querySelector('.result-icon').textContent = s.status === 'success' ? '✓' : s.status === 'over_budget' ? '!' : '×';
  }
  function renderProfileTable() {
    const body = $('profiles-body'); clear(body);
    const profiles = state.table ? state.table.profiles.slice().sort((a,b) => a.w3-b.w3 || a.w2-b.w2 || a.total_cost-b.total_cost) : [];
    text('profile-count',profiles.length); $('profiles-empty').hidden = profiles.length > 0;
    text('profiles-empty', state.selection.status === 'invalid' ? 'Enter valid requirements to inspect the table.' : 'No attainable count pairs satisfy this preservation quota.');
    profiles.forEach(p => {
      const row=node('tr'); if(sameProfile(p,state.inspected)) row.className='inspected'; else if(!state.inspected && sameProfile(p,state.selection.profile)) row.className='active';
      [p.w2,p.w3,p.total_cost].forEach(v=>row.appendChild(node('td',null,v)));
      const targetCell=node('td'), budgetCell=node('td');
      const validTarget=Number.isSafeInteger(state.request.target)&&state.request.target>=0;
      const validBudget=state.request.budget===null||(Number.isSafeInteger(state.request.budget)&&state.request.budget>=0);
      targetCell.appendChild(node('span',{class:'badge '+(!validTarget?'neutral':meetsTarget(p)?'pass':'no')},!validTarget?'Invalid':meetsTarget(p)?'Meets':'Outside'));
      budgetCell.appendChild(node('span',{class:'badge '+(!validBudget||state.request.budget===null?'neutral':withinBudget(p)?'pass':'no')},!validBudget?'Invalid':state.request.budget===null?'No limit':withinBudget(p)?'Within':'Over'));
      row.appendChild(targetCell); row.appendChild(budgetCell);
      const cell=node('td'), isActive=sameProfile(p,viewedProfile()), button=node('button',{type:'button',class:'profile-view','aria-label':'Inspect W2 '+p.w2+', W3 '+p.w3+', cost '+p.total_cost,'aria-pressed':String(isActive)},isActive?'Viewing':'Inspect');
      button.addEventListener('click',()=>{state.inspected=p;state.graphMode='witness';renderProfileTable();renderView();});cell.appendChild(button);row.appendChild(cell);body.appendChild(row);
    });
  }
  function renderView() {
    const c=currentCase(), p=viewedProfile(), original=state.graphMode==='original'||!p, removed=new Set(original?[]:p.deleted_ids), counts=original?c.original:{w2:p.w2,w3:p.w3};
    text('metric-w2',counts.w2);text('metric-w3',counts.w3);text('metric-cost',original?'—':p.total_cost);
    text('original-w2','Original: '+c.original.w2+' · minimum: '+(state.table?state.table.min_w2:'—'));text('original-w3','Original: '+c.original.w3+' · target: '+(Number.isFinite(state.request.target)?(state.request.mode==='exact'?'= ':'≤ ')+state.request.target:'—'));
    text('cost-breakdown',original?'Original history, before deletions':p.optional_cost+' optional + '+state.table.forced_cost+' mandatory');
    text('view-label',original?'ORIGINAL EVENT HISTORY':state.inspected?'INSPECTED PROFILE':state.selection.status==='over_budget'?'LOWEST-COST CANDIDATE · OVER BUDGET':'MINIMUM-COST TARGET PROFILE');
    $('view-original').setAttribute('aria-pressed',String(original));$('view-witness').setAttribute('aria-pressed',String(!original));$('view-witness').disabled=!p;
    $('baseline-note').hidden=!c.events.some(e=>e.status==='delete');
    const baseline=state.table?state.table.baseline:c.quotas[0].baseline, forced=state.table?state.table.forced_cost:c.quotas[0].forced_cost;
    text('baseline-note','Before mandatory deletions: (W2, W3) = ('+c.original.w2+', '+c.original.w3+'). After mandatory deletions: ('+baseline.w2+', '+baseline.w3+'), already costing '+forced+'.');
    $('inspection-note').hidden=!state.inspected;
    if(state.inspected)text('inspection-copy','Inspecting W2 = '+p.w2+', W3 = '+p.w3+'. '+(state.selection.status==='invalid'?'Enter a valid target and cost limit to assess this profile.':(meetsTarget(p)?'Meets':'Does not meet')+' your count target; '+(withinBudget(p)?'within your cost limit.':'over your cost limit.'))+' Your request is unchanged.');
    $('download-result').disabled=!p||state.selection.status==='invalid';
    text('graph-caption',original?'The original history is shown before mandatory or optional deletions. Each arrow is one event; the root is the filled account.':p.deleted_ids.length?'Dashed arrows are deleted events. All arrows retain their original identities. The root is the filled account.':'This profile keeps every original event. The root is the filled account.');
    renderGraph(c,removed,original);renderEvents(c,removed,original);
  }
  function renderEvents(c,removed,original) {
    const body=$('events-body');clear(body);text('event-count',c.events.length+' events');
    c.events.forEach((e,i)=>{const row=node('tr'), deleted=removed.has(e.id);if(deleted)row.className=e.status==='delete'?'forced-row':'removed';const id=node('td');id.appendChild(node('span',{class:'event-alias'},eventAlias(e,i)));if(eventAlias(e,i)!==e.id)id.appendChild(node('span',{class:'event-id'},e.id));row.appendChild(id);[e.source+' → '+e.target,e.time,e.cost].forEach(x=>row.appendChild(node('td',null,x)));const end=node('td');end.appendChild(node('span',{class:'badge '+(e.status==='delete'?'no':e.status==='keep'?'pass':'neutral')},e.status==='delete'?'Must delete':e.status==='keep'?'Protected':'Optional'));end.appendChild(node('span',{class:'state-text'},original?'Original event':deleted?'Deleted':'Retained'));row.appendChild(end);body.appendChild(row);});
  }
  function renderGraph(c,removed,original) {
    const svg=$('transaction-graph');clear(svg);svg.appendChild(svgNode('title',{id:'graph-title'},c.title+' — '+(original?'original history':'deletion witness')));svg.appendChild(svgNode('desc',{id:'graph-desc'},'Events point toward root '+c.root+'. '+(original?'All original events are shown.':removed.size+' events are deleted; the inventory below lists their original IDs.')));
    const containerWidth=$('graph-container').clientWidth, vertical=containerWidth<540, width=vertical?Math.max(containerWidth,280):800, nodes=new Set([c.root]), parent=new Map(), children=new Map(), depth=new Map([[c.root,0]]);
    c.events.forEach(e=>{nodes.add(e.source);nodes.add(e.target);parent.set(e.source,e.target);if(!children.has(e.target))children.set(e.target,new Set());children.get(e.target).add(e.source);});
    function getDepth(v){if(!depth.has(v))depth.set(v,1+getDepth(parent.get(v)));return depth.get(v);}nodes.forEach(getDepth);
    const leaves=[];function leafOrder(v){const ch=Array.from(children.get(v)||[]).sort();if(!ch.length)leaves.push(v);else ch.forEach(leafOrder);}leafOrder(c.root);
    const slots=new Map(leaves.map((v,i)=>[v,i]));function getSlot(v){if(slots.has(v))return slots.get(v);const a=Array.from(children.get(v)||[]).map(getSlot);const s=(Math.min(...a)+Math.max(...a))/2;slots.set(v,s);return s;}getSlot(c.root);
    const maxDepth=Math.max(...Array.from(depth.values())), height=vertical?maxDepth*142+124:Math.max(280,leaves.length*80+80), positions=new Map();
    nodes.forEach(v=>{const along=vertical?60+(maxDepth-depth.get(v))*142:68+(maxDepth-depth.get(v))*((width-136)/Math.max(maxDepth,1));const across=vertical?(leaves.length===1?width/2:30+(slots.get(v)+.5)*(width-60)/leaves.length):(leaves.length===1?height/2:60+slots.get(v)*80);positions.set(v,vertical?{x:across,y:along}:{x:along,y:across});});
    svg.setAttribute('viewBox','0 0 '+width+' '+height);svg.setAttribute('width',width);svg.setAttribute('height',height);
    const defs=svgNode('defs');[['retained','#128477'],['protected','#315b78'],['deleted','#ba4c25'],['forced','#9e3b64']].forEach(([id,color])=>{const marker=svgNode('marker',{id:'arrow-'+id,viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:5,markerHeight:5,orient:'auto-start-reverse'});marker.appendChild(svgNode('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:color}));defs.appendChild(marker);});svg.appendChild(defs);
    if(!vertical)for(let d=maxDepth;d>=0;d--){const x=68+(maxDepth-d)*((width-136)/Math.max(maxDepth,1));svg.appendChild(svgNode('text',{x,y:22,class:'node-level-label'},d===0?'ROOT':'DEPTH '+d));}
    const groups=new Map();c.events.forEach((e,i)=>{const key=e.source+'\u0000'+e.target;if(!groups.has(key))groups.set(key,[]);groups.get(key).push({e,i});});
    const edges=svgNode('g'),labels=svgNode('g');
    groups.forEach(group=>group.forEach(({e,i},j)=>{
      const from=positions.get(e.source),to=positions.get(e.target),deleted=removed.has(e.id),kind=deleted?(e.status==='delete'?'forced':'deleted'):(e.status==='keep'?'protected':'retained'),color={retained:'#128477',protected:'#315b78',deleted:'#ba4c25',forced:'#9e3b64'}[kind];
      const offset=(j-(group.length-1)/2)*(vertical?82:53),dx=to.x-from.x,dy=to.y-from.y,len=Math.hypot(dx,dy)||1,ux=dx/len,uy=dy/len,r=24;
      const p0=vertical?{x:from.x,y:from.y+r}:{x:from.x+ux*r,y:from.y+uy*r};
      const p3=vertical?{x:to.x,y:to.y-r-4}:{x:to.x-ux*(r+4),y:to.y-uy*(r+4)};
      const p1=vertical?{x:p0.x+offset,y:p0.y+(p3.y-p0.y)*.8}:{x:p0.x+(p3.x-p0.x)*.35,y:p0.y+(p3.y-p0.y)*.35+offset};
      const p2=vertical?{x:p3.x+offset,y:p3.y-(p3.y-p0.y)*.1}:{x:p0.x+(p3.x-p0.x)*.65,y:p0.y+(p3.y-p0.y)*.65+offset};
      const path=svgNode('path',{d:'M '+p0.x+' '+p0.y+' C '+p1.x+' '+p1.y+', '+p2.x+' '+p2.y+', '+p3.x+' '+p3.y,fill:'none',stroke:color,'stroke-width':e.status==='keep'&&!deleted?2.7:2,'stroke-dasharray':deleted?'6 4':'none','marker-end':'url(#arrow-'+kind+')',opacity:deleted?.8:1});path.appendChild(svgNode('title',{},e.id+': '+e.source+' → '+e.target+', time '+e.time+', deletion cost '+e.cost+', '+e.status+(deleted?', deleted':'')));edges.appendChild(path);
      const labelT=(vertical&&(children.get(e.target)||new Set()).size>2) ? .25 : .5,one=1-labelT;
      const mx=one**3*p0.x+3*one**2*labelT*p1.x+3*one*labelT**2*p2.x+labelT**3*p3.x;
      const my=one**3*p0.y+3*one**2*labelT*p1.y+3*one*labelT**2*p2.y+labelT**3*p3.y;
      const label=svgNode('g',{class:'edge-label'}),w=eventAlias(e,i).length>6?94:vertical?58:79;
      label.appendChild(svgNode('rect',{x:mx-w/2,y:my-17,width:w,height:34,rx:5,fill:'#fffefa',stroke:deleted?'#edc7b4':'#dce1d8','stroke-width':.8}));
      label.appendChild(svgNode('text',{x:mx,y:my-3,'text-anchor':'middle','font-size':10,'font-weight':650,fill:color},eventAlias(e,i)+' · t '+e.time));label.appendChild(svgNode('text',{x:mx,y:my+10,'text-anchor':'middle','font-size':8,fill:deleted?color:'#68776c'},e.status==='keep'?'protected':(e.status==='delete'?'required · ':'cost ')+e.cost));
      label.appendChild(svgNode('title',{},e.id+' | time '+e.time+' | cost '+e.cost+' | '+e.status));labels.appendChild(label);
    }));svg.appendChild(edges);svg.appendChild(labels);
    const nodeGroup=svgNode('g');nodes.forEach(v=>{const p=positions.get(v),root=v===c.root,g=svgNode('g',{class:'graph-node'});g.appendChild(svgNode('circle',{cx:p.x,cy:p.y,r:23,fill:root?'#193b42':'#fffefa',stroke:root?'#193b42':'#93ada0','stroke-width':root?2:1.7}));g.appendChild(svgNode('text',{x:p.x,y:p.y+4,'text-anchor':'middle','font-size':v.length>5?10:12,'font-weight':650,fill:root?'#fffefa':'#294b42'},v));if(root&&vertical)g.appendChild(svgNode('text',{x:p.x,y:p.y+39,'text-anchor':'middle','font-size':9,'letter-spacing':1.2,fill:'#68776c'},'ROOT ACCOUNT'));nodeGroup.appendChild(g);});svg.appendChild(nodeGroup);
  }
  function downloadResult() {
    const p=viewedProfile();if(!p)return;const c=currentCase();const result={example:c.id,example_title:c.title,source_solver_sha256:data.source.solver_sha256,mode:state.inspected?'inspected_profile':'target_candidate',request:{min_w2:state.table.min_w2,...state.request},target_selection_status:state.selection.status,viewed_profile_meets_target:meetsTarget(p),viewed_profile_within_budget:withinBudget(p),original:c.original,after_mandatory_deletions:state.table.baseline,profile:p,note:'Precomputed exact solver output for a bundled mathematical example. An inspected profile is not necessarily an accepted target result.'};
    const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)+'\n'],{type:'application/json'})),a=node('a',{href:url,download:'temporal-profile-'+c.id+'.json'});document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  function init() {
    if(!data||!Array.isArray(data.cases)||!data.cases.length){$('load-error').hidden=false;text('load-error','The example data could not be loaded. Keep index.html, styles.css, app.js and data.js together, or open the standalone HTML version.');$('explorer').hidden=true;return;}
    data.cases.forEach((c,i)=>$('example-select').appendChild(node('option',{value:c.id},String(i+1).padStart(2,'0')+' · '+c.title)));
    $('example-select').addEventListener('change',e=>setExample(data.cases.findIndex(c=>c.id===e.target.value)));
    ['min-w2','target-w3','cost-budget'].forEach(id=>$(id).addEventListener('input',()=>{state.inspected=null;refresh();}));
    document.querySelectorAll('input[name="target-mode"]').forEach(input=>input.addEventListener('change',()=>{state.inspected=null;refresh();}));
    $('budget-enabled').addEventListener('change',()=>{$('cost-budget').disabled=!$('budget-enabled').checked;state.inspected=null;refresh();});
    $('reset-example').addEventListener('click',()=>setExample(state.caseIndex));$('view-original').addEventListener('click',()=>{state.graphMode='original';renderView();});$('view-witness').addEventListener('click',()=>{state.graphMode='witness';renderView();});
    $('return-selection').addEventListener('click',()=>{state.inspected=null;renderProfileTable();renderView();});$('download-result').addEventListener('click',downloadResult);
    const v=data.verification;text('verification-summary',v.case_count+' examples · '+v.quota_tables+' quota tables checked by exhaustive enumeration · '+v.profile_witnesses+' witness checks across those tables.');
    global.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>renderView(),120);});setExample(0);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})(typeof window==='undefined'?globalThis:window);
