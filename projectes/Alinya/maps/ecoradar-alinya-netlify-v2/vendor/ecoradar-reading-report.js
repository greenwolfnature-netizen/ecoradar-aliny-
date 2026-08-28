(function (global) {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const paragraph = value => Array.isArray(value)
    ? `<ul>${value.map(item => `<li>${esc(item)}</li>`).join('')}</ul>`
    : String(value ?? '').split(/\n\s*\n/).filter(Boolean).map(item => `<p>${esc(item)}</p>`).join('');

  function reportHtml(report, mapSvg) {
    const facts = (report.facts || []).map(fact =>
      `<div class="err-fact"><span>${esc(fact.label)}</span><strong>${esc(fact.value)}</strong>${fact.note ? `<small>${esc(fact.note)}</small>` : ''}</div>`
    ).join('');
    const sources = (report.sources || []).map(source => `<li>${esc(source)}</li>`).join('');
    const relations = (report.crossRelations || []).map(item => `<article class="err-relation">
      <div><strong>${esc(item.factor)}</strong><span>${esc(item.reading || '')}</span></div>
      <p>${esc(item.reasoning)}</p><small>${esc(item.evidence)}</small>
    </article>`).join('');
    const sections = [
      ['Què estem mesurant?', report.what],
      ['Què ens aporta aquesta informació?', report.contribution],
      ['Què significa aquesta lectura en aquest espai?', report.context],
      ['Com es relaciona amb la resta de lectures EcoRadar?', report.relationships],
      ['Què pot passar si aquest indicador augmenta o disminueix?', report.changes],
      ['Quines conseqüències pot tenir sobre vegetació, fauna, hàbitats i processos ecològics?', report.consequences],
      ['Es pot millorar? Com?', report.improve],
      ['Conclusions i implicacions per a la gestió.', report.conclusions]
    ];
    return `<article class="err-document">
      <header class="err-cover"><div><span>ECORADAR · MUNTANYA D’ALINYÀ</span><h1>${esc(report.name)}</h1><p>Informe específic de la lectura activa</p></div><div class="err-date">Generat ${esc(report.generatedAt)}</div></header>
      <section class="err-metadata"><div><b>Espai</b><span>Muntanya d’Alinyà</span></div><div><b>Data de les dades</b><span>${esc(report.dataDate)}</span></div><div><b>Lectura</b><span>${esc(report.name)}</span></div></section>
      ${facts ? `<section><h2>Resultats principals</h2><div class="err-facts">${facts}</div></section>` : ''}
      ${report.technicalSynthesis ? `<section class="err-synthesis"><h2>Diagnosi tècnica integrada</h2>${paragraph(report.technicalSynthesis)}</section>` : ''}
      ${mapSvg ? `<section><h2>Distribució territorial</h2><div class="err-map">${mapSvg}</div><p>${esc(report.territorial)}</p></section>` : ''}
      ${report.temporal ? `<section><h2>Comparació temporal</h2>${paragraph(report.temporal)}</section>` : ''}
      ${relations ? `<section><h2>Relacions ecològiques que cal contrastar</h2><div class="err-relations">${relations}</div></section>` : ''}
      ${report.unverified?.length ? `<section class="err-unverified"><h2>Factors rellevants no verificats amb aquesta lectura</h2>${paragraph(report.unverified)}</section>` : ''}
      ${sections.map(([title, body]) => `<section><h2>${esc(title)}</h2>${paragraph(body)}</section>`).join('')}
      <section class="err-limits"><h2>Límits de la interpretació</h2>${paragraph(report.limits)}</section>
      <section><h2>Fonts i traçabilitat</h2><ul>${sources}</ul></section>
      <footer>EcoRadar · diagnosi ambiental basada exclusivament en les dades disponibles al visor. Les decisions finals requereixen contrast tècnic i, quan correspon, validació de camp.</footer>
    </article>`;
  }

  function printableHtml(title, body) {
    return `<!doctype html><html lang="ca"><head><meta charset="utf-8"><title>${esc(title)}</title><style>
      @page{size:A4 portrait;margin:14mm}*{box-sizing:border-box}body{margin:0;color:#304958;font:11pt/1.5 Arial,sans-serif}h1,h2{color:#173249}h1{font-size:25pt;line-height:1.05;margin:8mm 0 2mm}h2{font-size:14.5pt;margin:8mm 0 2mm;border-bottom:1px solid #d8d4ca;padding-bottom:2mm}p,li{orphans:3;widows:3}.err-cover{min-height:52mm;padding:10mm;background:#edf4ea;border-top:5mm solid #2f743f;display:flex;justify-content:space-between;gap:10mm}.err-cover span{color:#2f743f;font-weight:800;letter-spacing:.12em}.err-date{font-size:9.5pt}.err-metadata,.err-facts{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm;margin:5mm 0}.err-metadata>div,.err-fact{border:1px solid #d8d4ca;padding:3mm}.err-metadata b,.err-metadata span,.err-fact span,.err-fact strong,.err-fact small{display:block}.err-fact strong{color:#2f743f;font-size:14pt}.err-synthesis{padding:5mm!important;background:#edf4ea;border-left:2mm solid #2f743f}.err-relations{display:grid;gap:3mm}.err-relation{border:1px solid #d8d4ca;padding:3mm;break-inside:avoid}.err-relation div{display:flex;justify-content:space-between;gap:5mm}.err-relation span,.err-relation small{color:#687682;font-size:9pt}.err-unverified{padding:4mm!important;background:#f3f1ed;border-left:2mm solid #7b858c}.err-map{height:92mm;border:1px solid #d8d4ca;overflow:hidden}.err-map svg{width:100%;height:100%}.err-limits{padding:4mm;background:#fff6e8;border-left:2mm solid #c2832d}section{break-inside:auto}h2,.err-fact,.err-map{break-inside:avoid}footer{margin-top:10mm;padding-top:3mm;border-top:1px solid #d8d4ca;color:#687682;font-size:9pt}@media print{button{display:none}}
    </style></head><body>${body}<script>addEventListener('load',()=>setTimeout(()=>print(),250));<\/script></body></html>`;
  }

  function mount(options) {
    const root = options.root;
    const button = root.querySelector('[data-generate-reading-report]');
    const modal = root.querySelector('[data-reading-report-modal]');
    const preview = modal && modal.querySelector('[data-reading-report-preview]');
    if (!button || !modal || !preview) return;
    let lastReport = null;
    let lastBody = '';

    function close() { modal.hidden = true; document.body.classList.remove('err-modal-open'); button.focus(); }
    button.addEventListener('click', () => {
      const selection = options.getSelection();
      lastReport = options.buildReport(selection);
      const svg = options.getMapSvg && options.getMapSvg();
      const mapSvg = svg ? svg.cloneNode(true).outerHTML : '';
      lastBody = reportHtml(lastReport, mapSvg);
      preview.innerHTML = lastBody;
      modal.querySelector('[data-reading-report-title]').textContent = lastReport.name;
      modal.hidden = false;
      document.body.classList.add('err-modal-open');
      modal.querySelector('[data-reading-report-close]').focus();
    });
    modal.querySelectorAll('[data-reading-report-close]').forEach(node => node.addEventListener('click', close));
    modal.addEventListener('click', event => { if (event.target === modal) close(); });
    document.addEventListener('keydown', event => { if (event.key === 'Escape' && !modal.hidden) close(); });
    modal.querySelector('[data-reading-report-pdf]').addEventListener('click', () => {
      if (!lastReport) return;
      const popup = window.open('', '_blank');
      if (!popup) { modal.querySelector('[data-reading-report-status]').textContent = 'El navegador ha bloquejat la finestra d’exportació. Permet les finestres emergents i torna-ho a provar.'; return; }
      popup.opener = null;
      popup.document.open(); popup.document.write(printableHtml(`EcoRadar Alinyà · ${lastReport.name}`, lastBody)); popup.document.close();
    });
    global.EcoRadarReadingReportTest = { reportHtml, printableHtml };
  }

  global.EcoRadarReadingReport = { mount };
})(window);
