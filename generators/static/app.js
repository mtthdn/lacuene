const VIZDATA = {{ vizdata_json }};
const GENE_ROWS = {{ gene_rows_json }};
const CRITICAL_GAPS = {{ critical_gaps_json }};
const SNAPSHOTS = {{ snapshots_json }};
const WEIGHTED_GAPS = {{ weighted_gaps_json }};
const ANOMALIES = {{ anomalies_json }};
const SOURCE_COUNT = {{ source_count }};
let currentFilteredRows = GENE_ROWS;

// Populate gap list (Card 1) — sorted by weighted priority score
const gapList = document.getElementById('gap-list');
const sortedGaps = [...CRITICAL_GAPS].sort((a, b) => {
  const sa = (WEIGHTED_GAPS[a.symbol] || {}).priority_score || 0;
  const sb = (WEIGHTED_GAPS[b.symbol] || {}).priority_score || 0;
  return sb - sa;
});
sortedGaps.slice(0, 20).forEach(g => {
  const div = document.createElement('div');
  div.className = 'gap-item';
  div.onclick = () => focusGene(g.symbol);
  const syns = (g.syndromes || []).join(', ') || 'Disease association (see OMIM)';
  const pubLabel = g.pub_count > 0 ? g.pub_count + ' pubs' : 'No pubs';
  const severity = g.pub_count === 0 ? 'var(--red)' : g.pub_count < 20 ? 'var(--orange)' : 'var(--green)';
  const score = (WEIGHTED_GAPS[g.symbol] || {}).priority_score || 0;
  const scoreBadge = score > 0 ? `<span class="priority-badge">P:${score}</span>` : '';
  div.innerHTML = `
    <div>
      <div class="gap-gene"><span class="gap-severity" style="background:${severity}"></span>${g.symbol}${scoreBadge}</div>
      <div class="gap-syndrome">${syns}</div>
    </div>
    <div class="gap-pubs">${pubLabel}</div>
  `;
  gapList.appendChild(div);
});

// Populate understudied list (Card 3)
const understudiedList = document.getElementById('understudied-list');
const diseaseGenes = GENE_ROWS.filter(g => g.omim).sort((a, b) => a.pub_total - b.pub_total);
diseaseGenes.slice(0, 20).forEach(g => {
  const div = document.createElement('div');
  div.className = 'gap-item';
  div.onclick = () => focusGene(g.symbol);
  const score = (WEIGHTED_GAPS[g.symbol] || {}).priority_score || 0;
  const scoreBadge = score > 0 ? `<span class="priority-badge">P:${score}</span>` : '';
  div.innerHTML = `
    <div>
      <div class="gap-gene">${g.symbol}${scoreBadge}</div>
      <div class="gap-syndrome">${g.syndrome || 'See OMIM'}</div>
    </div>
    <div class="gap-pubs">${g.pub_total} pubs<br><span style="color:var(--text-sec)">${g.phenotype_count} phenotypes</span></div>
  `;
  understudiedList.appendChild(div);
});

// Gene table
const tbody = document.getElementById('gene-tbody');
let sortState = { col: null, asc: true };
function trendArrow(pub_total, pub_recent) {
  if (!pub_total || pub_total === 0) return '';
  const ratio = pub_recent / pub_total;
  if (ratio > 0.5) return '<span class="trend-arrow rising" title="Rising">&#9650;</span>';
  if (ratio > 0.2) return '<span class="trend-arrow stable" title="Stable">&#9644;</span>';
  return '<span class="trend-arrow declining" title="Declining">&#9660;</span>';
}

function renderTable(rows) {
  tbody.innerHTML = '';
  rows.forEach(g => {
    const mark = v => v ? '<span class="check">Y</span>' : '<span class="miss">&mdash;</span>';
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.onclick = () => focusGene(g.symbol);
    tr.innerHTML = `
      <td><span class="gene-link">${g.symbol}</span></td>
      <td>${mark(g.go)}</td>
      <td>${mark(g.omim)}</td>
      <td>${mark(g.hpo)}</td>
      <td>${mark(g.uniprot)}</td>
      <td>${mark(g.facebase)}</td>
      <td>${mark(g.clinvar)}</td>
      <td>${mark(g.pubmed)}</td>
      <td>${mark(g.gnomad)}</td>
      <td>${mark(g.nih_reporter)}</td>
      <td>${mark(g.gtex)}</td>
      <td>${mark(g.clinicaltrials)}</td>
      <td>${mark(g.string)}</td>
      <td>${g.count}/${SOURCE_COUNT}</td>
      <td>${g.pub_total || '&mdash;'}${trendArrow(g.pub_total, g.pub_recent)}</td>
      <td>${g.pub_recent || '&mdash;'}</td>
      <td>${g.pathogenic || '&mdash;'}</td>
      <td style="font-size:0.75rem;color:var(--text-sec)">${g.syndrome}</td>
    `;
    tbody.appendChild(tr);
  });
}
renderTable(GENE_ROWS);
document.querySelectorAll('th[data-sort]').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.sort;
    const type = th.dataset.type;
    if (sortState.col === col) sortState.asc = !sortState.asc;
    else { sortState.col = col; sortState.asc = true; }

    document.querySelectorAll('th .sort-arrow').forEach(a => a.remove());
    const arrow = document.createElement('span');
    arrow.className = 'sort-arrow';
    arrow.textContent = sortState.asc ? ' \u25B2' : ' \u25BC';
    th.appendChild(arrow);

    const sorted = [...currentFilteredRows].sort((a, b) => {
      let va = a[col], vb = b[col];
      if (type === 'bool') { va = va ? 1 : 0; vb = vb ? 1 : 0; }
      if (type === 'num') { va = va || 0; vb = vb || 0; }
      if (type === 'str') { va = (va || '').toLowerCase(); vb = (vb || '').toLowerCase(); }
      if (va < vb) return sortState.asc ? -1 : 1;
      if (va > vb) return sortState.asc ? 1 : -1;
      return 0;
    });
    renderTable(sorted);
  });
});

// Cytoscape graph
const cy = cytoscape({
  container: document.getElementById('cy'),
  elements: [...VIZDATA.nodes, ...VIZDATA.edges],
  style: [
    {
      selector: 'node',
      style: {
        'background-color': 'data(color)',
        'label': 'data(label)',
        'color': '#e6edf3',
        'font-size': '12px',
        'font-family': "'Atkinson Hyperlegible Next', system-ui, sans-serif",
        'font-weight': 600,
        'text-valign': 'bottom',
        'text-margin-y': 6,
        'text-outline-width': 2.5,
        'text-outline-color': '#0d1117',
        'text-outline-opacity': 1,
        'width': 'data(size)',
        'height': 'data(size)',
        'border-width': 2,
        'border-color': '#0d1117',
        'min-zoomed-font-size': 8,
        'transition-property': 'opacity, border-color, border-width',
        'transition-duration': '0.2s',
      }
    },
    {
      selector: 'edge',
      style: {
        'width': 0.5,
        'line-color': '#21262d',
        'curve-style': 'bezier',
        'opacity': 0.12,
        'transition-property': 'opacity, line-color, width',
        'transition-duration': '0.2s',
      }
    },
    {
      selector: 'edge[type="shared_syndrome"]',
      style: {
        'line-color': '#db61a2',
        'width': 1.5,
        'opacity': 0.55,
      }
    },
    {
      selector: 'edge[type="ppi"]',
      style: {
        'line-color': '#3fb950',
        'width': 1.2,
        'opacity': 0.45,
        'line-style': 'dashed',
      }
    },
    {
      selector: 'edge[type="shared_pathway"]',
      style: {
        'line-color': '#a371f7',
        'width': 0.8,
        'opacity': 0.25,
      }
    },
    {
      selector: 'edge[type="shared_phenotype"]',
      style: {
        'line-color': '#30363d',
        'width': 0.5,
        'opacity': 0.08,
      }
    },
    {
      selector: 'node:selected',
      style: {
        'border-color': '#e6edf3',
        'border-width': 3,
      }
    },
    {
      selector: '.highlighted',
      style: {
        'opacity': 1,
      }
    },
    {
      selector: 'edge.highlighted',
      style: {
        'opacity': 0.8,
        'width': 2,
      }
    },
    {
      selector: '.faded',
      style: {
        'opacity': 0.04,
      }
    },
  ],
  layout: {
    name: 'cose',
    idealEdgeLength: 180,
    nodeOverlap: 40,
    refresh: 20,
    fit: true,
    padding: 60,
    randomize: false,
    componentSpacing: 160,
    nodeRepulsion: 80000,
    edgeElasticity: 200,
    nestingFactor: 5,
    gravity: 25,
    numIter: 1500,
    initialTemp: 300,
    coolingFactor: 0.95,
    minTemp: 1.0,
    animate: false,
  },
  wheelSensitivity: 0.3,
  maxZoom: 5,
  minZoom: 0.1,
});

function setLayout(name, btn) {
  document.querySelectorAll('.layout-btn:not(.edge-filter)').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  const opts = { name: name, animate: true, animationDuration: 600 };
  if (name === 'cose') {
    Object.assign(opts, {
      nodeOverlap: 40, idealEdgeLength: 180, nodeRepulsion: 80000,
      edgeElasticity: 200, componentSpacing: 160,
      gravity: 25, numIter: 1500, initialTemp: 300,
      padding: 60, animate: false,
    });
  } else if (name === 'circle') {
    Object.assign(opts, { avoidOverlap: true, spacingFactor: 1.75, padding: 60 });
  } else if (name === 'concentric') {
    Object.assign(opts, {
      avoidOverlap: true, spacingFactor: 1.75, padding: 60,
      minNodeSpacing: 40,
      concentric: n => n.data('pub_count') || 0,
      levelWidth: () => 2,
    });
  }
  cy.layout(opts).run();
}

function filterEdges(type, btn) {
  document.querySelectorAll('.edge-filter').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (type === 'all') {
    cy.edges().style('display', 'element');
  } else if (type === 'key') {
    // Show only syndrome + PPI edges (the most informative ones)
    cy.edges().style('display', 'none');
    cy.edges('[type="shared_syndrome"]').style('display', 'element');
    cy.edges('[type="ppi"]').style('display', 'element');
  } else {
    cy.edges().style('display', 'none');
    cy.edges(`[type="${type}"]`).style('display', 'element');
  }
}

// Default to showing key edges only (syndrome + PPI) to avoid visual overload
(function() {
  cy.edges().style('display', 'none');
  cy.edges('[type="shared_syndrome"]').style('display', 'element');
  cy.edges('[type="ppi"]').style('display', 'element');
  document.querySelectorAll('.edge-filter').forEach(b => b.classList.remove('active'));
  const keyBtn = document.querySelector('.edge-filter[data-edge="key"]');
  if (keyBtn) keyBtn.classList.add('active');
})();

cy.on('tap', 'node', function(evt) {
  const node = evt.target;
  const neighborhood = node.closedNeighborhood();
  cy.elements().addClass('faded');
  neighborhood.removeClass('faded').addClass('highlighted');
  cy.animate({ center: { eles: node }, zoom: 2 }, { duration: 400 });
  showGeneDetail(node.data('id'));
});

cy.on('tap', function(evt) {
  if (evt.target === cy) {
    cy.elements().removeClass('faded').removeClass('highlighted');
    cy.animate({ fit: { eles: cy.elements(), padding: 40 } }, { duration: 400 });
    closeDetail();
  }
});

// Edge hover tooltip
const edgeTooltip = document.getElementById('edge-tooltip');
cy.on('mouseover', 'edge', function(evt) {
  const edge = evt.target;
  const label = edge.data('label') || '';
  if (!label) return;
  const edgeType = edge.data('type');
  const prefix = edgeType === 'shared_syndrome' ? 'Syndrome' : edgeType === 'shared_pathway' ? 'Pathway' : edgeType === 'ppi' ? 'PPI' : 'Phenotype';
  edgeTooltip.textContent = prefix + ': ' + label;
  edgeTooltip.style.display = 'block';
  const pos = evt.renderedPosition || evt.position;
  const container = document.getElementById('cy').getBoundingClientRect();
  edgeTooltip.style.left = (container.left + pos.x + 12) + 'px';
  edgeTooltip.style.top = (container.top + pos.y - 10) + 'px';
});
cy.on('mouseout', 'edge', function() {
  edgeTooltip.style.display = 'none';
});
cy.on('viewport', function() {
  edgeTooltip.style.display = 'none';
});

function focusGene(symbol) {
  const graphEl = document.getElementById('cy');
  graphEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  const node = cy.getElementById(symbol);
  if (node.length) {
    const neighborhood = node.closedNeighborhood();
    cy.elements().addClass('faded');
    neighborhood.removeClass('faded').addClass('highlighted');
    cy.animate({ center: { eles: node }, zoom: 2 }, { duration: 400 });
  }
  showGeneDetail(symbol);
}

function showGeneDetail(symbol) {
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');
  const row = GENE_ROWS.find(g => g.symbol === symbol);
  if (!row) return;

  const node = VIZDATA.nodes.find(n => n.data.id === symbol);
  const roleLabel = node ? node.data.role_label : '';

  const edges = VIZDATA.edges.filter(e =>
    e.data.source === symbol || e.data.target === symbol
  );
  const connected = new Set();
  edges.forEach(e => {
    connected.add(e.data.source === symbol ? e.data.target : e.data.source);
  });

  // Funding case blurb
  let fundingCase = '';
  if (row.omim) {
    const synCount = (row.syndromes || []).length;
    const pubDesc = row.pub_total > 0 ? `has ${row.pub_total} craniofacial publications` : 'has zero craniofacial publications';
    const fbDesc = row.facebase ? 'has FaceBase experimental data' : 'has zero FaceBase datasets';
    const gap = !row.facebase ? ' This represents a research gap for NIDCR.' : '';
    fundingCase = `<div class="funding-case">${row.symbol} is associated with ${synCount} Mendelian phenotype${synCount !== 1 ? 's' : ''}, ${pubDesc}, and ${fbDesc}.${gap}</div>`;
  }

  // Publication list
  let papersHtml = '';
  if (row.papers && row.papers.length > 0) {
    papersHtml = '<div class="detail-field"><div class="detail-label">Recent Publications</div>';
    row.papers.forEach(p => {
      papersHtml += `<div class="paper-item">
        <div class="paper-title">${p.title}</div>
        <div class="paper-meta"><a href="https://pubmed.ncbi.nlm.nih.gov/${p.pmid}/" target="_blank">PMID:${p.pmid}</a> (${p.year})</div>
      </div>`;
    });
    papersHtml += '</div>';
  }

  // Source coverage line
  const srcLabels = [];
  if (row.go) srcLabels.push('GO');
  if (row.omim) srcLabels.push('OMIM');
  if (row.hpo) srcLabels.push('HPO');
  if (row.uniprot) srcLabels.push('UniProt');
  if (row.facebase) srcLabels.push('FaceBase');
  if (row.clinvar) srcLabels.push('ClinVar');
  if (row.pubmed) srcLabels.push('PubMed');
  if (row.gnomad) srcLabels.push('gnomAD');
  if (row.nih_reporter) srcLabels.push('NIH Reporter');
  if (row.gtex) srcLabels.push('GTEx');
  if (row.clinicaltrials) srcLabels.push('ClinicalTrials');
  if (row.string) srcLabels.push('STRING');

  // Publication trend
  const trend = trendArrow(row.pub_total, row.pub_recent);

  // Tissue expression (GTEx)
  let tissueHtml = '';
  if (row.craniofacial_expression != null || (row.top_tissues && row.top_tissues.length > 0)) {
    tissueHtml = '<div class="detail-field"><div class="detail-label">Tissue Expression (GTEx)</div>';
    if (row.craniofacial_expression != null) {
      tissueHtml += `<div class="detail-value" style="margin-bottom:6px">Craniofacial: <strong>${row.craniofacial_expression} TPM</strong></div>`;
    }
    if (row.top_tissues && row.top_tissues.length > 0) {
      const maxTpm = Math.max(...row.top_tissues.map(t => t.tpm || t.median_tpm || 0));
      row.top_tissues.slice(0, 5).forEach(t => {
        const tpm = t.tpm || t.median_tpm || 0;
        const pct = maxTpm > 0 ? Math.round(tpm / maxTpm * 100) : 0;
        const tissueName = t.tissue || t.name || 'Unknown';
        tissueHtml += `<div class="tissue-bar-row">
          <span class="tissue-bar-label" title="${tissueName}">${tissueName}</span>
          <div class="tissue-bar-bg"><div class="tissue-bar-fill" style="width:${pct}%"></div></div>
          <span class="tissue-bar-value">${tpm.toFixed(1)}</span>
        </div>`;
      });
    }
    tissueHtml += '</div>';
  }

  // NIH Reporter grants
  let grantsHtml = '';
  if (row.grant_count > 0 || (row.nih_projects && row.nih_projects.length > 0)) {
    const projectCount = row.nih_projects ? row.nih_projects.length : row.grant_count;
    grantsHtml = `<div class="detail-field"><div class="detail-label">Active Grants (${projectCount})</div>`;
    if (row.nih_projects && row.nih_projects.length > 0) {
      row.nih_projects.forEach(p => {
        const projNum = p.project_num || p.project_number || '';
        const pi = p.pi_name || p.contact_pi_name || 'N/A';
        const org = p.org_name || p.organization || '';
        const url = projNum ? `https://reporter.nih.gov/project-details/${projNum}` : '#';
        grantsHtml += `<div style="padding:0.3rem 0;border-bottom:1px solid var(--elevated);font-size:0.8rem">
          <a href="${url}" target="_blank" class="gene-link">${projNum || 'Project'}</a>
          <div style="font-size:0.75rem;color:var(--text-sec)">${pi}${org ? ' &middot; ' + org : ''}</div>
        </div>`;
      });
    } else {
      grantsHtml += `<div class="detail-value">${row.grant_count} active grant(s)</div>`;
    }
    grantsHtml += '</div>';
  }

  // Genetic constraint (pLI / LOEUF)
  let constraintHtml = '';
  {
    let pliText = 'N/A';
    let pliClass = 'constraint-low';
    if (row.pli_score != null) {
      if (row.pli_score > 0.9) { pliText = `${row.pli_score.toFixed(3)} &mdash; Highly constrained (essential gene)`; pliClass = 'constraint-high'; }
      else if (row.pli_score > 0.5) { pliText = `${row.pli_score.toFixed(3)} &mdash; Moderately constrained`; pliClass = 'constraint-moderate'; }
      else { pliText = `${row.pli_score.toFixed(3)} &mdash; Not constrained`; pliClass = 'constraint-low'; }
    }
    let loeufText = '';
    if (row.loeuf_score != null) {
      loeufText = ` &middot; LOEUF: ${row.loeuf_score.toFixed(3)}`;
    }
    constraintHtml = `<div class="detail-field">
      <div class="detail-label">Genetic Constraint</div>
      <div class="detail-value"><span class="${pliClass}">pLI: ${pliText}</span>${loeufText}</div>
    </div>`;
  }

  // STRING interaction partners
  let stringHtml = '';
  if (row.string_partners && row.string_partners.length > 0) {
    const partnerSymbols = row.string_partners.map(p => typeof p === 'string' ? p : (p.symbol || '')).filter(s => s);
    stringHtml = `<div class="detail-field">
      <div class="detail-label">Protein Interactions (${partnerSymbols.length})</div>
      <div class="detail-value">
        ${partnerSymbols.sort().map(g => `<span class="detail-tag" onclick="focusGene('${g}')">${g}</span>`).join('')}
      </div>
    </div>`;
  }

  content.innerHTML = `
    <h2>${symbol}</h2>
    ${fundingCase}
    <div class="detail-field">
      <div class="detail-label">Role</div>
      <div class="detail-value">${roleLabel}</div>
    </div>
    <div class="detail-field">
      <div class="detail-label">Protein</div>
      <div class="detail-value">${row.protein || 'N/A'}</div>
    </div>
    <div class="detail-field">
      <div class="detail-label">Key Syndrome</div>
      <div class="detail-value">${(row.syndromes || []).join(', ') || 'None listed'}</div>
    </div>
    <div class="detail-field">
      <div class="detail-label">Publication Data</div>
      <div class="detail-value">${row.pub_total} total ${trend} &middot; ${row.pub_recent} recent (5yr) &middot; ${row.pathogenic} pathogenic variants</div>
    </div>
    ${tissueHtml}
    <div class="detail-field">
      <div class="detail-label">Source Coverage (${row.count}/${SOURCE_COUNT})</div>
      <div class="detail-value">${srcLabels.join(' ')}</div>
    </div>
    ${grantsHtml}
    ${constraintHtml}
    ${stringHtml}
    ${papersHtml}
    <div class="detail-field">
      <div class="detail-label">Connected Genes (${connected.size})</div>
      <div class="detail-value">
        ${[...connected].sort().map(g => `<span class="detail-tag" onclick="focusGene('${g}')">${g}</span>`).join('')}
      </div>
    </div>
    <div class="detail-field">
      <div class="detail-label">External Links</div>
      <div class="detail-value">
        <a href="https://www.genenames.org/tools/search/#!/?query=${symbol}" target="_blank" class="gene-link">HGNC</a> &middot;
        <a href="https://www.uniprot.org/uniprotkb?query=${symbol}+AND+organism_id:9606" target="_blank" class="gene-link">UniProt</a> &middot;
        <a href="https://www.ebi.ac.uk/QuickGO/search/${symbol}" target="_blank" class="gene-link">QuickGO</a> &middot;
        <a href="https://pubmed.ncbi.nlm.nih.gov/?term=${symbol}+AND+(craniofacial+OR+neural+crest)" target="_blank" class="gene-link">PubMed</a> &middot;
        <a href="https://www.omim.org/search?search=${symbol}" target="_blank" class="gene-link">OMIM</a> &middot;
        <a href="https://www.ncbi.nlm.nih.gov/clinvar/?term=${symbol}[gene]" target="_blank" class="gene-link">ClinVar</a> &middot;
        <a href="https://www.facebase.org/chaise/recordset/#1/isa:dataset/*::cfacets::N4IghgDg9lBcBOBnALhANjAcwCZ0A" target="_blank" class="gene-link">FaceBase</a> &middot;
        <a href="https://string-db.org/network/9606.${symbol}" target="_blank" class="gene-link">STRING</a>
      </div>
    </div>
  `;
  panel.classList.add('open');
}

function closeDetail() {
  document.getElementById('detail-panel').classList.remove('open');
}

// Keyboard navigation: Escape closes panels
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    closeDetail();
    closeBriefing();
  }
});

function toggleExportMenu() {
  const menu = document.getElementById('export-menu');
  menu.classList.toggle('open');
}

// Close export menu on click outside
document.addEventListener('click', function(e) {
  const dropdown = document.querySelector('.export-dropdown');
  const menu = document.getElementById('export-menu');
  if (dropdown && menu && !dropdown.contains(e.target)) {
    menu.classList.remove('open');
  }
});

function downloadCSV(template) {
  const headers = ['Gene','GO','OMIM','HPO','UniProt','FaceBase','ClinVar','PubMed','gnomAD','NIH Reporter','GTEx','ClinicalTrials','STRING','Sources','PubTotal','PubRecent','Pathogenic','Phenotypes','Key Syndrome'];
  let exportRows;
  const gapSymbols = new Set(CRITICAL_GAPS.map(g => g.symbol));

  if (template === 'gaps') {
    exportRows = GENE_ROWS.filter(g => gapSymbols.has(g.symbol));
  } else if (template === 'priority') {
    exportRows = GENE_ROWS.filter(g => {
      const w = WEIGHTED_GAPS[g.symbol];
      return w && w.priority_score >= 15;
    });
  } else if (template === 'understudied') {
    exportRows = GENE_ROWS.filter(g => g.pub_total < 20);
  } else {
    exportRows = currentFilteredRows.length < GENE_ROWS.length ? currentFilteredRows : GENE_ROWS;
  }

  const rows = exportRows.map(g => [
    g.symbol,
    g.go ? 'Y' : '',
    g.omim ? 'Y' : '',
    g.hpo ? 'Y' : '',
    g.uniprot ? 'Y' : '',
    g.facebase ? 'Y' : '',
    g.clinvar ? 'Y' : '',
    g.pubmed ? 'Y' : '',
    g.gnomad ? 'Y' : '',
    g.nih_reporter ? 'Y' : '',
    g.gtex ? 'Y' : '',
    g.clinicaltrials ? 'Y' : '',
    g.string ? 'Y' : '',
    g.count,
    g.pub_total,
    g.pub_recent,
    g.pathogenic,
    g.phenotype_count,
    '"' + (g.syndrome || '').replace(/"/g, '""') + '"',
  ]);
  const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
  const blob = new Blob([csv], {type: 'text/csv'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  const suffix = template ? `-${template}` : '';
  a.download = `lacuene-grant-gap-finder${suffix}.csv`;
  a.click();

  // Close dropdown
  const menu = document.getElementById('export-menu');
  if (menu) menu.classList.remove('open');
}

function showBriefing() {
  const isFiltered = currentFilteredRows.length < GENE_ROWS.length;
  const filteredSymbols = isFiltered ? new Set(currentFilteredRows.map(g => g.symbol)) : null;
  const relevantGaps = isFiltered
    ? CRITICAL_GAPS.filter(g => filteredSymbols.has(g.symbol))
    : CRITICAL_GAPS;
  const topGaps = [...relevantGaps].sort((a, b) => a.pub_count - b.pub_count).slice(0, 5);
  const geneCount = isFiltered ? currentFilteredRows.length : GENE_ROWS.length;

  let text = 'NIDCR Grant Gap Analysis: Neural Crest Genes\n';
  text += '='.repeat(50) + '\n\n';
  if (isFiltered) {
    text += `[Filtered view: ${geneCount} of ${GENE_ROWS.length} genes matching current filter]\n\n`;
  }
  text += `This analysis cross-references ${GENE_ROWS.length} neural crest genes across ${SOURCE_COUNT} biomedical databases `;
  text += `(Gene Ontology, OMIM, HPO, UniProt, FaceBase, ClinVar, PubMed, gnomAD, NIH Reporter, GTEx, ClinicalTrials, STRING) `;
  text += `to identify clinically important but scientifically understudied genes.\n\n`;
  text += `Of ${geneCount} genes${isFiltered ? ' in this filtered set' : ''}, ${relevantGaps.length} have Mendelian disease associations `;
  text += `but lack FaceBase experimental data, representing potential funding gaps.\n\n`;
  if (topGaps.length > 0) {
    text += `Top ${Math.min(5, topGaps.length)} Priority Targets:\n\n`;
    topGaps.forEach((g, i) => {
      const syns = (g.syndromes || []).join(', ') || 'disease association';
      text += `${i + 1}. ${g.symbol} - ${syns} (${g.pub_count} craniofacial publications)\n`;
    });
    text += '\n';
    text += 'These genes have confirmed disease relevance through OMIM but minimal ';
    text += 'experimental coverage in the NIDCR-funded FaceBase repository. ';
    text += 'Directing funding toward these targets could yield high-impact results ';
    text += 'in understanding craniofacial and dental development.\n';
  } else {
    text += 'No critical gaps in the current filtered set.\n';
  }
  text += '\nGenerated by lacuene - CUE lattice unification for biomedical data';

  document.getElementById('briefing-text').textContent = text;
  document.getElementById('briefing-modal').classList.add('open');
}

function copyBriefing() {
  const text = document.getElementById('briefing-text').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.modal-actions .action-btn');
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = 'Copy to Clipboard'; }, 2000);
  });
}

function closeBriefing() {
  document.getElementById('briefing-modal').classList.remove('open');
}

// === Syndrome-Centric View ===
function buildSyndromeIndex() {
  const index = {};
  GENE_ROWS.forEach(g => {
    (g.syndromes || []).forEach(syn => {
      const name = syn.replace(/,\s*\d{6}\s*$/, '').trim();
      if (!name) return;
      if (!index[name]) index[name] = { name, genes: [] };
      index[name].genes.push(g);
    });
  });
  return Object.values(index);
}

const SYNDROME_INDEX = buildSyndromeIndex();

function renderSyndromeTable(syndromes, showSingle) {
  const multi = syndromes.filter(s => s.genes.length >= 2);
  const single = syndromes.filter(s => s.genes.length < 2);

  const sortFn = (a, b) => {
    const aFb = a.genes.filter(g => g.facebase).length / a.genes.length;
    const bFb = b.genes.filter(g => g.facebase).length / b.genes.length;
    return aFb - bFb;
  };
  if (!synSortState.col) {
    multi.sort(sortFn);
    single.sort(sortFn);
  }

  const multiTbody = document.getElementById('syndrome-tbody');
  const singleTbody = document.getElementById('syndrome-tbody-single');
  multiTbody.innerHTML = '';
  singleTbody.innerHTML = '';

  function renderRows(tbody, items) {
    items.forEach(s => {
      const geneCount = s.genes.length;
      const fbCount = s.genes.filter(g => g.facebase).length;
      const fbPct = Math.round(fbCount * 100 / geneCount);
      const avgPubs = Math.round(s.genes.reduce((sum, g) => sum + (g.pub_total || 0), 0) / geneCount);
      const totalPath = s.genes.reduce((sum, g) => sum + (g.pathogenic || 0), 0);

      const tr = document.createElement('tr');
      tr.className = 'syndrome-row';
      tr.onclick = () => highlightSyndromeGenes(s.genes.map(g => g.symbol));

      const barColor = fbPct >= 80 ? 'var(--green)' : fbPct >= 40 ? 'var(--orange)' : 'var(--red)';
      tr.innerHTML = `
        <td>
          <div style="font-weight:500;color:var(--text)">${s.name}</div>
          <div class="syndrome-genes">
            ${s.genes.map(g => `<span class="syndrome-gene-tag" onclick="event.stopPropagation();focusGene('${g.symbol}')">${g.symbol}</span>`).join('')}
          </div>
        </td>
        <td>${geneCount}</td>
        <td>
          <div style="display:flex;align-items:center;gap:0.5rem">
            <div class="source-bar-bg" style="width:60px"><div class="source-bar" style="width:${fbPct}%;background:${barColor}"></div></div>
            <span style="font-size:0.75rem;color:var(--text-sec)">${fbCount}/${geneCount}</span>
          </div>
        </td>
        <td>${avgPubs}</td>
        <td>${totalPath || '&mdash;'}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  renderRows(multiTbody, multi);
  renderRows(singleTbody, single);

  const info = document.getElementById('syndrome-filter-info');
  info.textContent = `Showing ${multi.length} multi-gene syndromes` +
    (single.length > 0 ? ` (${single.length} single-gene syndromes ${showSingle ? 'shown' : 'hidden'})` : '');
}

let showingSingleSyndromes = false;

function toggleSingleGeneSyndromes() {
  showingSingleSyndromes = !showingSingleSyndromes;
  const tbody = document.getElementById('syndrome-tbody-single');
  const btn = document.getElementById('syndrome-toggle-btn');
  if (showingSingleSyndromes) {
    tbody.classList.add('open');
    btn.textContent = 'Hide Single-Gene';
  } else {
    tbody.classList.remove('open');
    btn.textContent = 'Show All';
  }
  renderSyndromeTable(SYNDROME_INDEX, showingSingleSyndromes);
}

function highlightSyndromeGenes(symbols) {
  const graphEl = document.getElementById('cy');
  graphEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  cy.elements().addClass('faded');
  symbols.forEach(sym => {
    const node = cy.getElementById(sym);
    if (node.length) {
      node.closedNeighborhood().removeClass('faded').addClass('highlighted');
    }
  });
  const highlighted = cy.elements('.highlighted');
  if (highlighted.length) {
    cy.animate({ fit: { eles: highlighted, padding: 60 } }, { duration: 400 });
  }
}

// Syndrome table sorting
let synSortState = { col: null, asc: true };
document.querySelectorAll('th[data-sort-syn]').forEach(th => {
  th.addEventListener('click', () => {
    const col = th.dataset.sortSyn;
    const type = th.dataset.type;
    if (synSortState.col === col) synSortState.asc = !synSortState.asc;
    else { synSortState.col = col; synSortState.asc = true; }

    document.querySelectorAll('#syndrome-table th .sort-arrow').forEach(a => a.remove());
    const arrow = document.createElement('span');
    arrow.className = 'sort-arrow';
    arrow.textContent = synSortState.asc ? ' \u25B2' : ' \u25BC';
    th.appendChild(arrow);

    const getValue = (s) => {
      if (col === 'name') return s.name.toLowerCase();
      if (col === 'gene_count') return s.genes.length;
      if (col === 'fb_pct') return s.genes.filter(g => g.facebase).length / s.genes.length;
      if (col === 'avg_pubs') return s.genes.reduce((sum, g) => sum + (g.pub_total || 0), 0) / s.genes.length;
      if (col === 'pathogenic') return s.genes.reduce((sum, g) => sum + (g.pathogenic || 0), 0);
      return 0;
    };

    SYNDROME_INDEX.sort((a, b) => {
      const va = getValue(a), vb = getValue(b);
      if (va < vb) return synSortState.asc ? -1 : 1;
      if (va > vb) return synSortState.asc ? 1 : -1;
      return 0;
    });
    renderSyndromeTable(SYNDROME_INDEX, showingSingleSyndromes);
  });
});

renderSyndromeTable(SYNDROME_INDEX, false);

// === Portfolio Overlay ===
function analyzePortfolio() {
  const input = document.getElementById('portfolio-input').value.trim();
  if (!input) return;

  const symbols = input
    .split(/[,\s\n\r]+/)
    .map(s => s.trim().toUpperCase())
    .filter(s => s.length > 0);

  const uniqueSymbols = [...new Set(symbols)];

  const gapSymbols = new Set(CRITICAL_GAPS.map(g => g.symbol));
  const allGeneSymbols = new Set(GENE_ROWS.map(g => g.symbol));

  const coveredGaps = uniqueSymbols.filter(s => gapSymbols.has(s));
  const uncoveredGaps = CRITICAL_GAPS.filter(g => !uniqueSymbols.includes(g.symbol));
  const nonGapGenes = uniqueSymbols.filter(s => allGeneSymbols.has(s) && !gapSymbols.has(s));
  const unknownGenes = uniqueSymbols.filter(s => !allGeneSymbols.has(s));

  const results = document.getElementById('portfolio-results');

  let html = `<div class="portfolio-summary">
    Your portfolio covers <strong style="color:var(--green)">${coveredGaps.length}</strong> of
    <strong>${CRITICAL_GAPS.length}</strong> gap genes.
    <strong style="color:var(--red)">${uncoveredGaps.length}</strong> remain unfunded.
  </div>`;

  html += '<div class="portfolio-columns">';

  html += '<div class="portfolio-col portfolio-col-covered">';
  html += `<h4>Covered Gaps (${coveredGaps.length})</h4>`;
  html += '<div class="portfolio-gene-list">';
  if (coveredGaps.length > 0) {
    coveredGaps.forEach(sym => {
      html += `<span class="portfolio-gene-tag covered" onclick="focusGene('${sym}')">${sym}</span>`;
    });
  } else {
    html += '<span style="font-size:0.8rem;color:var(--text-sec)">None of your genes are gap genes</span>';
  }
  html += '</div></div>';

  html += '<div class="portfolio-col portfolio-col-uncovered">';
  html += `<h4>Unfunded Gaps (${uncoveredGaps.length})</h4>`;
  html += '<div class="portfolio-gene-list">';
  uncoveredGaps.forEach(g => {
    html += `<span class="portfolio-gene-tag uncovered" onclick="focusGene('${g.symbol}')">${g.symbol}</span>`;
  });
  html += '</div></div>';

  html += '</div>';

  if (nonGapGenes.length > 0) {
    html += `<div class="portfolio-info">${nonGapGenes.length} gene${nonGapGenes.length !== 1 ? 's' : ''} in your portfolio are not gap genes (already well-covered).</div>`;
  }
  if (unknownGenes.length > 0) {
    html += `<div class="portfolio-info">${unknownGenes.length} symbol${unknownGenes.length !== 1 ? 's' : ''} not recognized: ${unknownGenes.join(', ')}</div>`;
  }

  results.innerHTML = html;
}

// === Change History ===
(function() {
  const container = document.getElementById('history-content');
  if (SNAPSHOTS.length === 0) {
    container.innerHTML = '<div style="font-size:0.85rem;color:var(--text-sec)">No snapshot data yet. Run the pipeline again to capture a baseline.</div>';
    return;
  }
  if (SNAPSHOTS.length === 1) {
    const s = SNAPSHOTS[0];
    container.innerHTML = '<div style="font-size:0.85rem;color:var(--text-sec)">Baseline captured on <strong style="color:var(--text)">' + s.date + '</strong>: ' + s.critical_count + ' critical gaps, ' + s.facebase_symbols.length + ' FaceBase genes, ' + s.total_genes + ' total genes. Run the pipeline again to see changes.</div>';
    return;
  }
  // 2+ snapshots: compute diffs
  let html = '<div style="font-size:0.85rem;color:var(--text-sec);margin-bottom:1rem">' + SNAPSHOTS.length + ' snapshots from ' + SNAPSHOTS[0].date + ' to ' + SNAPSHOTS[SNAPSHOTS.length - 1].date + '</div>';
  for (let i = SNAPSHOTS.length - 1; i >= 1; i--) {
    const curr = SNAPSHOTS[i];
    const prev = SNAPSHOTS[i - 1];
    const prevGaps = new Set(prev.gap_symbols);
    const currGaps = new Set(curr.gap_symbols);
    const prevFb = new Set(prev.facebase_symbols);
    const currFb = new Set(curr.facebase_symbols);
    const newGaps = [...currGaps].filter(s => !prevGaps.has(s));
    const closedGaps = [...prevGaps].filter(s => !currGaps.has(s));
    const newFb = [...currFb].filter(s => !prevFb.has(s));
    const tag = (sym, color) => '<span class="detail-tag" onclick="focusGene(\'' + sym + '\')" style="border:1px solid ' + color + ';color:' + color + '">' + sym + '</span>';
    html += '<div style="margin-bottom:1rem;padding:1rem;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius)">';
    html += '<div style="font-weight:600;color:var(--text);margin-bottom:0.5rem">' + prev.date + ' &rarr; ' + curr.date + '</div>';
    if (newGaps.length === 0 && closedGaps.length === 0 && newFb.length === 0) {
      html += '<div style="font-size:0.85rem;color:var(--text-sec)">No changes.</div>';
    } else {
      if (closedGaps.length > 0) {
        html += '<div style="font-size:0.8rem;margin-bottom:0.4rem"><span style="color:var(--green)">Gaps closed (' + closedGaps.length + '):</span> ' + closedGaps.map(s => tag(s, 'var(--green)')).join(' ') + '</div>';
      }
      if (newGaps.length > 0) {
        html += '<div style="font-size:0.8rem;margin-bottom:0.4rem"><span style="color:var(--red)">New gaps (' + newGaps.length + '):</span> ' + newGaps.map(s => tag(s, 'var(--red)')).join(' ') + '</div>';
      }
      if (newFb.length > 0) {
        html += '<div style="font-size:0.8rem"><span style="color:var(--accent)">New FaceBase (' + newFb.length + '):</span> ' + newFb.map(s => tag(s, 'var(--accent)')).join(' ') + '</div>';
      }
    }
    html += '</div>';
  }
  container.innerHTML = html;
})();

// === Cross-Source Anomalies ===
const ANOMALY_TYPE_META = {
  omim_no_clinvar:       { label: 'OMIM Disease / No ClinVar',   color: 'var(--orange)',  icon: 'W' },
  high_pli_no_trials:    { label: 'High pLI / No Trials',        color: 'var(--accent)',  icon: 'I' },
  high_pubs_no_facebase: { label: 'High Pubs / No FaceBase',     color: 'var(--orange)',  icon: 'W' },
  clinvar_no_hpo:        { label: 'ClinVar / No HPO Phenotypes',  color: 'var(--red)',     icon: 'E' },
};

let anomaliesExpanded = false;

function toggleAnomalies() {
  anomaliesExpanded = !anomaliesExpanded;
  const body = document.getElementById('anomalies-body');
  const btn = document.getElementById('anomaly-toggle-btn');
  if (anomaliesExpanded) {
    body.classList.add('open');
    btn.textContent = 'Collapse';
  } else {
    body.classList.remove('open');
    btn.textContent = 'Expand';
  }
}

(function renderAnomalies() {
  const items = ANOMALIES.genes_with_anomalies || [];
  const summary = ANOMALIES.summary || {};

  // Badge
  const badge = document.getElementById('anomaly-count-badge');
  badge.textContent = summary.total_anomalies + ' flagged';
  if (summary.clinvar_no_hpo_count > 0) {
    badge.style.borderColor = 'rgba(248,81,73,0.5)';
    badge.style.color = 'var(--red)';
  }

  // Type bar: one button per anomaly type showing count
  const typeBar = document.getElementById('anomalies-type-bar');
  let typeBarHtml = '';
  for (const [key, meta] of Object.entries(ANOMALY_TYPE_META)) {
    const count = summary[key + '_count'] || 0;
    typeBarHtml += '<button class="anomaly-type-pill" data-anomaly-type="' + key + '" onclick="filterAnomalyType(this)" style="--pill-color:' + meta.color + '">';
    typeBarHtml += '<span class="anomaly-type-icon" style="background:' + meta.color + '">' + meta.icon + '</span>';
    typeBarHtml += meta.label + ' <strong>' + count + '</strong>';
    typeBarHtml += '</button>';
  }
  typeBar.innerHTML = typeBarHtml;

  // Render all items
  renderAnomalyList(items);
})();

let activeAnomalyFilter = null;

function filterAnomalyType(btn) {
  const type = btn.dataset.anomalyType;
  const pills = document.querySelectorAll('.anomaly-type-pill');
  if (activeAnomalyFilter === type) {
    activeAnomalyFilter = null;
    pills.forEach(p => p.classList.remove('active'));
    renderAnomalyList(ANOMALIES.genes_with_anomalies);
  } else {
    activeAnomalyFilter = type;
    pills.forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    const filtered = ANOMALIES.genes_with_anomalies.filter(a => a.anomaly_type === type);
    renderAnomalyList(filtered);
  }
}

function renderAnomalyList(items) {
  const container = document.getElementById('anomalies-list');
  let html = '';
  items.forEach(a => {
    const meta = ANOMALY_TYPE_META[a.anomaly_type] || { label: a.anomaly_type, color: 'var(--text-sec)', icon: '?' };
    let detail = '';
    if (a.syndromes && a.syndromes.length > 0) detail = a.syndromes[0].split(',')[0];
    else if (a.pli_score != null) detail = 'pLI: ' + a.pli_score.toFixed(3);
    else if (a.pub_count != null) detail = a.pub_count + ' publications';
    else if (a.pathogenic_count != null) detail = a.pathogenic_count + ' pathogenic variants';

    html += '<div class="anomaly-item" onclick="focusGene(\'' + a.symbol + '\')">';
    html += '<div class="anomaly-item-left">';
    html += '<span class="anomaly-severity-tag" style="background:' + meta.color + '">' + meta.icon + '</span>';
    html += '<div>';
    html += '<div class="anomaly-item-gene">' + a.symbol + '</div>';
    html += '<div class="anomaly-item-desc">' + a.description + '</div>';
    html += '</div>';
    html += '</div>';
    html += '<div class="anomaly-item-right">';
    if (detail) html += '<span class="anomaly-item-detail">' + detail + '</span>';
    html += '<span class="anomaly-item-type">' + meta.label + '</span>';
    html += '</div>';
    html += '</div>';
  });
  if (items.length === 0) {
    html = '<div style="padding:1.5rem;color:var(--text-sec);font-size:0.85rem">No anomalies detected for this filter.</div>';
  }
  container.innerHTML = html;
}

// === Cross-Source Filter ===
function cycleFilter(btn) {
  const states = ['any', 'required', 'excluded'];
  const current = btn.dataset.state;
  const next = states[(states.indexOf(current) + 1) % 3];
  btn.dataset.state = next;
  btn.className = 'filter-toggle' + (next !== 'any' ? ' ' + next : '');
  btn.setAttribute('aria-checked', next === 'required' ? 'true' : 'false');
  btn.setAttribute('aria-label', 'Filter: ' + btn.textContent + ' — ' + next);
}

function buildFilterPredicate() {
  const toggles = document.querySelectorAll('.filter-toggle');
  const boolFilters = [];
  toggles.forEach(btn => {
    if (btn.dataset.state !== 'any') {
      boolFilters.push({ field: btn.dataset.filter, required: btn.dataset.state === 'required' });
    }
  });

  const pubMin = parseInt(document.getElementById('filter-pub-min').value) || 0;
  const pubMax = document.getElementById('filter-pub-max').value ? parseInt(document.getElementById('filter-pub-max').value) : Infinity;
  const pathMin = parseInt(document.getElementById('filter-path-min').value) || 0;
  const pathMax = document.getElementById('filter-path-max').value ? parseInt(document.getElementById('filter-path-max').value) : Infinity;

  return (g) => {
    for (const f of boolFilters) {
      if (f.required && !g[f.field]) return false;
      if (!f.required && g[f.field]) return false;
    }
    const pubs = g.pub_total || 0;
    if (pubs < pubMin || pubs > pubMax) return false;
    const path = g.pathogenic || 0;
    if (path < pathMin || path > pathMax) return false;
    return true;
  };
}

function applyFilter() {
  const pred = buildFilterPredicate();
  currentFilteredRows = GENE_ROWS.filter(pred);
  document.getElementById('gene-search').value = '';
  sortState.col = null;
  renderTable(currentFilteredRows);
  document.getElementById('filter-count').textContent = currentFilteredRows.length + ' of ' + GENE_ROWS.length + ' genes';
  document.getElementById('gene-table-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
  saveHashState();
}

function resetFilter() {
  document.querySelectorAll('.filter-toggle').forEach(btn => {
    btn.dataset.state = 'any';
    btn.className = 'filter-toggle';
  });
  document.getElementById('filter-pub-min').value = '';
  document.getElementById('filter-pub-max').value = '';
  document.getElementById('filter-path-min').value = '';
  document.getElementById('filter-path-max').value = '';
  document.getElementById('gene-search').value = '';
  currentFilteredRows = GENE_ROWS;
  sortState.col = null;
  renderTable(currentFilteredRows);
  document.getElementById('filter-count').textContent = '';
  saveHashState();
}

// Filter: Enter key on range inputs triggers apply
document.querySelectorAll('#filter-section input[type="number"]').forEach(inp => {
  inp.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') applyFilter();
  });
});

// === Gene Table Search ===
let searchTimeout = null;
document.getElementById('gene-search').addEventListener('input', function() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => searchGenes(this.value), 200);
});

function searchGenes(query) {
  const q = query.trim().toLowerCase();
  if (!q) {
    currentFilteredRows = GENE_ROWS;
  } else {
    currentFilteredRows = GENE_ROWS.filter(g =>
      g.symbol.toLowerCase().includes(q) ||
      (g.syndrome || '').toLowerCase().includes(q) ||
      (g.protein || '').toLowerCase().includes(q)
    );
  }
  sortState.col = null;
  renderTable(currentFilteredRows);
  saveHashState();
}

// === URL Hash State ===
function saveHashState() {
  const parts = [];
  const toggles = document.querySelectorAll('.filter-toggle');
  const filterParts = [];
  toggles.forEach(btn => {
    if (btn.dataset.state !== 'any') {
      filterParts.push(btn.dataset.filter + ':' + (btn.dataset.state === 'required' ? 'req' : 'exc'));
    }
  });
  if (filterParts.length > 0) parts.push('filter=' + filterParts.join(','));

  const pubMin = document.getElementById('filter-pub-min').value;
  const pubMax = document.getElementById('filter-pub-max').value;
  const pathMin = document.getElementById('filter-path-min').value;
  const pathMax = document.getElementById('filter-path-max').value;
  if (pubMin) parts.push('pub_min=' + pubMin);
  if (pubMax) parts.push('pub_max=' + pubMax);
  if (pathMin) parts.push('path_min=' + pathMin);
  if (pathMax) parts.push('path_max=' + pathMax);

  const search = document.getElementById('gene-search').value.trim();
  if (search) parts.push('search=' + encodeURIComponent(search));

  if (parts.length > 0) {
    history.replaceState(null, '', '#' + parts.join('&'));
  } else {
    history.replaceState(null, '', window.location.pathname);
  }
}

function restoreHashState() {
  const hash = window.location.hash.slice(1);
  if (!hash) return;

  const params = {};
  hash.split('&').forEach(part => {
    const [k, v] = part.split('=');
    if (k && v) params[k] = decodeURIComponent(v);
  });

  // Restore filter toggles
  if (params.filter) {
    params.filter.split(',').forEach(item => {
      const [field, state] = item.split(':');
      const btn = document.querySelector(`.filter-toggle[data-filter="${field}"]`);
      if (btn) {
        const fullState = state === 'req' ? 'required' : 'excluded';
        btn.dataset.state = fullState;
        btn.className = 'filter-toggle ' + fullState;
      }
    });
  }

  // Restore range inputs
  if (params.pub_min) document.getElementById('filter-pub-min').value = params.pub_min;
  if (params.pub_max) document.getElementById('filter-pub-max').value = params.pub_max;
  if (params.path_min) document.getElementById('filter-path-min').value = params.path_min;
  if (params.path_max) document.getElementById('filter-path-max').value = params.path_max;

  // Restore search
  if (params.search) {
    document.getElementById('gene-search').value = params.search;
    searchGenes(params.search);
    return; // search already renders the table
  }

  // Apply filter if any toggles or ranges were set
  if (params.filter || params.pub_min || params.pub_max || params.path_min || params.path_max) {
    applyFilter();
  }
}

restoreHashState();

// === Community Detection (Label Propagation) ===
function detectCommunities() {
  const nodes = cy.nodes();
  // Initialize: each node gets its own label
  nodes.forEach((n, i) => n.data('community', i));

  for (let iter = 0; iter < 30; iter++) {
    let changed = false;
    // Shuffle traversal order for better convergence
    const order = [...Array(nodes.length).keys()];
    for (let i = order.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [order[i], order[j]] = [order[j], order[i]];
    }
    for (const idx of order) {
      const node = nodes[idx];
      const neighbors = node.neighborhood().nodes();
      if (neighbors.length === 0) continue;
      // Count neighbor labels, weighted by edge count between them
      const counts = {};
      neighbors.forEach(nb => {
        const lbl = nb.data('community');
        counts[lbl] = (counts[lbl] || 0) + 1;
      });
      // Pick the most frequent label (tie-break: smallest label for stability)
      let bestLabel = node.data('community'), bestCount = 0;
      for (const [lbl, cnt] of Object.entries(counts)) {
        if (cnt > bestCount || (cnt === bestCount && Number(lbl) < Number(bestLabel))) {
          bestLabel = Number(lbl);
          bestCount = cnt;
        }
      }
      if (bestLabel !== node.data('community')) {
        node.data('community', bestLabel);
        changed = true;
      }
    }
    if (!changed) break;
  }

  // Collect communities and assign sequential IDs
  const labelMap = {};
  let nextId = 0;
  nodes.forEach(n => {
    const raw = n.data('community');
    if (!(raw in labelMap)) labelMap[raw] = nextId++;
    n.data('community', labelMap[raw]);
  });
  return nextId;
}

const communityCount = detectCommunities();

// Build community metadata
function getCommunityInfo() {
  const communities = {};
  cy.nodes().forEach(n => {
    const cid = n.data('community');
    if (!communities[cid]) communities[cid] = { id: cid, members: [], roles: {} };
    communities[cid].members.push(n.data('id'));
    const role = n.data('role_label') || 'Unknown';
    communities[cid].roles[role] = (communities[cid].roles[role] || 0) + 1;
  });
  // Determine dominant role per community
  for (const c of Object.values(communities)) {
    let bestRole = '', bestCount = 0;
    for (const [role, cnt] of Object.entries(c.roles)) {
      if (cnt > bestCount) { bestRole = role; bestCount = cnt; }
    }
    c.dominantRole = bestRole;
  }
  return Object.values(communities).sort((a, b) => b.members.length - a.members.length);
}

const COMMUNITY_INFO = getCommunityInfo();

// Community color palette (muted, for hull overlays)
const COMMUNITY_COLORS = [
  'rgba(88,166,255,0.12)', 'rgba(163,113,247,0.12)', 'rgba(63,185,80,0.12)',
  'rgba(210,153,34,0.12)', 'rgba(248,81,73,0.12)', 'rgba(219,97,162,0.12)',
  'rgba(121,192,255,0.12)', 'rgba(240,136,62,0.12)', 'rgba(130,200,180,0.12)',
  'rgba(200,200,100,0.12)', 'rgba(180,130,220,0.12)', 'rgba(100,180,230,0.12)',
];
const COMMUNITY_BORDER_COLORS = [
  'rgba(88,166,255,0.45)', 'rgba(163,113,247,0.45)', 'rgba(63,185,80,0.45)',
  'rgba(210,153,34,0.45)', 'rgba(248,81,73,0.45)', 'rgba(219,97,162,0.45)',
  'rgba(121,192,255,0.45)', 'rgba(240,136,62,0.45)', 'rgba(130,200,180,0.45)',
  'rgba(200,200,100,0.45)', 'rgba(180,130,220,0.45)', 'rgba(100,180,230,0.45)',
];

// Draw community hulls on a canvas overlay
let hullCanvas = null;
let hullCtx = null;
let showingClusters = false;

function initHullCanvas() {
  if (hullCanvas) return;
  const container = document.getElementById('cy');
  hullCanvas = document.createElement('canvas');
  hullCanvas.className = 'community-hull-canvas';
  hullCanvas.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;';
  container.style.position = 'relative';
  container.appendChild(hullCanvas);
}

function drawCommunityHulls() {
  if (!hullCanvas || !showingClusters) return;
  const rect = hullCanvas.parentElement.getBoundingClientRect();
  hullCanvas.width = rect.width;
  hullCanvas.height = rect.height;
  hullCtx = hullCanvas.getContext('2d');
  hullCtx.clearRect(0, 0, hullCanvas.width, hullCanvas.height);

  COMMUNITY_INFO.forEach((comm, i) => {
    if (comm.members.length < 2) return;
    const points = [];
    comm.members.forEach(sym => {
      const n = cy.getElementById(sym);
      if (n.length) {
        const pos = n.renderedPosition();
        points.push([pos.x, pos.y]);
      }
    });
    if (points.length < 2) return;

    // Compute convex hull
    const hull = convexHull(points);
    if (hull.length < 3) return;

    const ci = i % COMMUNITY_COLORS.length;
    hullCtx.beginPath();
    // Expand hull outward by 25px for padding
    const cx = hull.reduce((s, p) => s + p[0], 0) / hull.length;
    const cy2 = hull.reduce((s, p) => s + p[1], 0) / hull.length;
    const expanded = hull.map(p => {
      const dx = p[0] - cx, dy = p[1] - cy2;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      return [p[0] + dx / dist * 25, p[1] + dy / dist * 25];
    });
    hullCtx.moveTo(expanded[0][0], expanded[0][1]);
    for (let j = 1; j < expanded.length; j++) hullCtx.lineTo(expanded[j][0], expanded[j][1]);
    hullCtx.closePath();
    hullCtx.fillStyle = COMMUNITY_COLORS[ci];
    hullCtx.fill();
    hullCtx.strokeStyle = COMMUNITY_BORDER_COLORS[ci];
    hullCtx.lineWidth = 1.5;
    hullCtx.stroke();
  });
}

function convexHull(points) {
  if (points.length < 3) return points.slice();
  const pts = points.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (O, A, B) => (A[0] - O[0]) * (B[1] - O[1]) - (A[1] - O[1]) * (B[0] - O[0]);
  const lower = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pts[i]) <= 0) upper.pop();
    upper.push(pts[i]);
  }
  upper.pop();
  lower.pop();
  return lower.concat(upper);
}

function clearHulls() {
  if (hullCanvas && hullCtx) {
    hullCtx.clearRect(0, 0, hullCanvas.width, hullCanvas.height);
  }
}

// Redraw hulls on viewport changes when in cluster view
cy.on('viewport', function() {
  if (showingClusters) drawCommunityHulls();
});

// Cluster layout: position communities in a circle, members around center
function setClusterLayout(btn) {
  document.querySelectorAll('.layout-btn:not(.edge-filter)').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  showingClusters = true;
  initHullCanvas();

  const R = 220; // radius for community centers
  const centerX = cy.width() / 2;
  const centerY = cy.height() / 2;

  const positions = {};
  COMMUNITY_INFO.forEach((comm, i) => {
    const angle = (2 * Math.PI * i) / COMMUNITY_INFO.length;
    const commCx = centerX + R * Math.cos(angle);
    const commCy = centerY + R * Math.sin(angle);
    const memberR = Math.max(30, Math.sqrt(comm.members.length) * 28);
    comm.members.forEach((sym, j) => {
      const mAngle = (2 * Math.PI * j) / comm.members.length;
      positions[sym] = {
        x: commCx + memberR * Math.cos(mAngle),
        y: commCy + memberR * Math.sin(mAngle),
      };
    });
  });

  cy.layout({
    name: 'preset',
    positions: node => positions[node.data('id')] || { x: centerX, y: centerY },
    animate: true,
    animationDuration: 600,
    fit: true,
    padding: 50,
  }).run();

  setTimeout(drawCommunityHulls, 650);
}

// Override setLayout to clear hulls when switching away from cluster view
const _origSetLayout = setLayout;
setLayout = function(name, btn) {
  showingClusters = false;
  clearHulls();
  _origSetLayout(name, btn);
};

// Render community info panel
function renderCommunityPanel() {
  const panel = document.getElementById('community-info');
  if (!panel) return;
  let html = '<div class="community-header">';
  html += '<span class="community-count">' + COMMUNITY_INFO.length + '</span> communities detected';
  html += '</div>';

  COMMUNITY_INFO.forEach((comm, i) => {
    const ci = i % COMMUNITY_COLORS.length;
    const borderColor = COMMUNITY_BORDER_COLORS[ci].replace('0.45', '0.8');
    html += '<div class="community-item">';
    html += '<div class="community-item-header">';
    html += '<span class="community-dot" style="background:' + borderColor + '"></span>';
    html += '<span class="community-label">' + comm.dominantRole + '</span>';
    html += '<span class="community-size">' + comm.members.length + ' genes</span>';
    html += '</div>';
    html += '<div class="community-members">';
    comm.members.sort().forEach(sym => {
      html += '<span class="community-gene-tag" onclick="focusGene(\'' + sym + '\')">' + sym + '</span>';
    });
    html += '</div></div>';
  });

  panel.innerHTML = html;
}
renderCommunityPanel();