(function (global) {
  'use strict';

  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
  const paragraph = value => Array.isArray(value)
    ? `<ul>${value.map(item => `<li>${esc(item)}</li>`).join('')}</ul>`
    : String(value ?? '').split(/\n\s*\n/).filter(Boolean).map(item => `<p>${esc(item)}</p>`).join('');
  const badge = level => `<span class="err-evidence err-evidence-${esc(level || 'potencial')}">${esc(level || 'potencial')}</span>`;
  const cards = (items, className, renderer) => items?.length ? `<div class="${className}">${items.map(renderer).join('')}</div>` : '';

  function reportHtml(report, mapSvg) {
    const facts = (report.facts || []).map(fact =>
      `<div class="err-fact"><span>${esc(fact.label)}</span><strong>${esc(fact.value)}</strong>${fact.note ? `<small>${esc(fact.note)}</small>` : ''}</div>`
    ).join('');
    const sources = (report.sources || []).map(source => `<li>${esc(source)}</li>`).join('');
    const relations = (report.crossRelations || []).map(item => `<article class="err-relation">
      <div><strong>${esc(item.factor)}</strong><span>${esc(item.reading || '')}</span>${badge(item.level)}</div>
      <p>${esc(item.reasoning)}</p><small>${esc(item.evidence)}</small>
    </article>`).join('');
    const causes = cards(report.causes || [], 'err-diagnostic-grid', item => `<article class="err-diagnostic-card">${badge(item.level)}<strong>${esc(item.factor)}</strong><p>${esc(item.reasoning)}</p><small>${esc(item.evidence || '')}</small></article>`);
    const chains = cards(report.chainEffects || [], 'err-chain', item => `<article class="err-chain-step">${badge(item.level)}<strong>${esc(item.title)}</strong><p>${esc(item.reasoning)}</p></article>`);
    const sectors = cards(report.prioritySectors || [], 'err-sector-grid', item => `<article class="err-sector"><div><strong>${esc(item.category)}</strong>${badge(item.level)}</div><p>${esc(item.description)}</p><small><b>Base:</b> ${esc(item.basis)}</small>${item.validation ? `<small><b>Cal comprovar:</b> ${esc(item.validation)}</small>` : ''}</article>`);
    const management = cards(report.managementImplications || [], 'err-management-grid', item => `<article class="err-management"><strong>${esc(item.priority)}</strong><p>${esc(item.action)}</p><small>${esc(item.rationale)}</small>${item.validation ? `<small><b>Abans d’actuar:</b> ${esc(item.validation)}</small>` : ''}</article>`);
    return `<article class="err-document">
      <header class="err-cover"><div><span>ECORADAR · MUNTANYA D’ALINYÀ</span><h1>${esc(report.name)}</h1><p>Informe específic de la lectura activa</p></div><div class="err-date">Generat ${esc(report.generatedAt)}</div></header>
      <section class="err-metadata"><div><b>Espai</b><span>Muntanya d’Alinyà</span></div><div><b>Data de les dades</b><span>${esc(report.dataDate)}</span></div><div><b>Lectura</b><span>${esc(report.name)}</span></div></section>
      ${facts ? `<section><h2>Resultats principals</h2><div class="err-facts">${facts}</div></section>` : ''}
      ${report.technicalSynthesis ? `<section class="err-synthesis"><h2>Diagnosi tècnica integrada</h2>${paragraph(report.technicalSynthesis)}</section>` : ''}
      <section><h2>Què estem mesurant?</h2>${paragraph(report.what)}</section>
      <section><h2>Què ens aporta aquesta informació?</h2>${paragraph(report.contribution)}</section>
      ${mapSvg ? `<section><h2>Què ens diu la lectura d’Alinyà?</h2><div class="err-map">${mapSvg}</div>${paragraph(report.context)}${paragraph(report.territorial)}${report.spatialAssessment ? paragraph(report.spatialAssessment) : ''}</section>` : ''}
      ${report.temporal ? `<section><h2>Comparació temporal</h2>${paragraph(report.temporal)}</section>` : ''}
      ${causes ? `<section><h2>Possibles causes i factors condicionants</h2>${causes}</section>` : ''}
      ${relations ? `<section><h2>Creuament amb altres lectures EcoRadar</h2><p>${esc(report.relationships)}</p><div class="err-relations">${relations}</div></section>` : ''}
      ${chains ? `<section><h2>Efectes en cadena</h2>${chains}</section>` : ''}
      <section><h2>Com pot evolucionar aquesta lectura?</h2><div class="err-evolution"><article><strong>Si augmenta</strong>${paragraph(report.evolution?.increase || report.changes)}</article><article><strong>Si disminueix</strong>${paragraph(report.evolution?.decrease || report.changes)}</article></div></section>
      <section><h2>Conseqüències ecològiques</h2>${paragraph(report.consequences)}${report.ecologicalConsequences ? paragraph(report.ecologicalConsequences) : ''}</section>
      ${report.fireAssessment ? `<section class="err-fire-assessment"><h2>Relació amb els incendis</h2>${paragraph(report.fireAssessment)}</section>` : ''}
      ${sectors ? `<section><h2>Sectors prioritaris</h2>${sectors}</section>` : ''}
      ${management ? `<section><h2>Implicacions per a la gestió</h2>${management}${paragraph(report.improve)}</section>` : `<section><h2>Implicacions per a la gestió</h2>${paragraph(report.improve)}</section>`}
      ${report.unverified?.length ? `<section class="err-unverified"><h2>Factors rellevants no verificats amb aquesta lectura</h2>${paragraph(report.unverified)}</section>` : ''}
      <section class="err-conclusion"><h2>Conclusió integrada</h2>${paragraph(report.integratedConclusion || report.conclusions)}</section>
      <section class="err-limits"><h2>Límits de la interpretació</h2>${paragraph(report.limits)}</section>
      <section><h2>Fonts i traçabilitat</h2><ul>${sources}</ul></section>
      <footer>EcoRadar · diagnosi ambiental basada exclusivament en les dades disponibles al visor. Les decisions finals requereixen contrast tècnic i, quan correspon, validació de camp.</footer>
    </article>`;
  }

  const pdfFilename = report => `EcoRadar_Alinya_${String(report.name || 'lectura')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_|_$/g, '')}.pdf`;

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
      const status = modal.querySelector('[data-reading-report-status]');
      const documentNode = preview.querySelector('.err-document');
      if (typeof global.html2pdf !== 'function' || !documentNode) {
        status.textContent = 'No s’ha pogut preparar el PDF. Torna a carregar la pàgina i prova-ho de nou.';
        return;
      }
      status.textContent = 'Preparant el PDF per desar…';
      const exportDocument = documentNode.cloneNode(true);
      exportDocument.classList.add('err-pdf-source');
      exportDocument.style.maxWidth = '690px';
      exportDocument.style.width = '690px';
      exportDocument.style.margin = '0';
      exportDocument.style.boxShadow = 'none';
      exportDocument.style.position = 'relative';
      const exportStyle = document.createElement('style');
      exportStyle.textContent = Array.from(document.styleSheets).flatMap(sheet => {
        try { return Array.from(sheet.cssRules).map(rule => rule.cssText.replaceAll('#ecoradar-alinya ', '')); }
        catch (_) { return []; }
      }).join('\n');
      exportDocument.prepend(exportStyle);
      const exportMarkup = exportDocument.outerHTML;
      const scrollPosition = { x: global.scrollX, y: global.scrollY };
      global.scrollTo(0, 0);
      const options = {
        margin: [9, 9, 9, 9],
        filename: pdfFilename(lastReport),
        image: { type: 'jpeg', quality: 0.97 },
        html2canvas: { scale: 2, useCORS: true, backgroundColor: '#ffffff', logging: false },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
        pagebreak: {
          mode: ['css', 'legacy'],
          avoid: ['.err-fact', '.err-diagnostic-card', '.err-relation', '.err-chain-step', '.err-sector', '.err-management', '.err-evolution article']
        }
      };
      global.html2pdf().set(options).from(exportMarkup, 'string').save()
        .then(() => { global.scrollTo(scrollPosition.x, scrollPosition.y); status.textContent = 'PDF preparat. Revisa la carpeta de descàrregues o la ubicació de desament triada.'; })
        .catch(() => { global.scrollTo(scrollPosition.x, scrollPosition.y); status.textContent = 'No s’ha pogut desar el PDF. Torna-ho a provar.'; });
    });
    global.EcoRadarReadingReportTest = { reportHtml, pdfFilename };
  }

  global.EcoRadarReadingReport = { mount };
})(window);
