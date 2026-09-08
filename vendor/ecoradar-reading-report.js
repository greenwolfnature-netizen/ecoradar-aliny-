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
  const labeled = (items, className = 'err-diagnostic-grid') => cards(items || [], className, item =>
    `<article class="err-diagnostic-card">${item.level ? badge(item.level) : ''}<strong>${esc(item.title || item.label)}</strong>${paragraph(item.text || item.reasoning)}${item.evidence ? `<small>${esc(item.evidence)}</small>` : ''}</article>`
  );

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
    const agreements = labeled(report.concordances || [], 'err-diagnostic-grid');
    const contradictions = labeled(report.contradictions || [], 'err-diagnostic-grid');
    const causalFrame = labeled(report.causalFramework || [], 'err-diagnostic-grid');
    const ecologicalPathways = labeled(report.ecologicalPathways || [], 'err-diagnostic-grid');
    const fireDimensions = labeled(report.fireDimensions || [], 'err-diagnostic-grid');
    const scenarios = cards(report.evolutionScenarios || [], 'err-scenario-grid', item => `<article class="err-scenario">${item.level ? badge(item.level) : ''}<strong>${esc(item.title)}</strong>${paragraph(item.conditions)}${paragraph(item.interpretation)}${item.management ? `<small><b>Implicació:</b> ${esc(item.management)}</small>` : ''}</article>`);
    const monitoring = cards(report.monitoringPlan || [], 'err-management-grid', item => `<article class="err-management"><strong>${esc(item.step || item.priority)}</strong><p>${esc(item.action)}</p>${item.indicator ? `<small><b>Indicador de resposta:</b> ${esc(item.indicator)}</small>` : ''}${item.validation ? `<small><b>Validació:</b> ${esc(item.validation)}</small>` : ''}</article>`);
    if (report.reportKind === 'fire-current') {
      const link = item => /^https:\/\//.test(item.url || '') ? `<a href="${esc(item.url)}">${esc(item.label || item.source)}</a>` : esc(item.label || item.source);
      const rows = report.sources.map(item => `<tr><td>${esc(item.label)}<br><small>${item.url ? link({url:item.url,label:item.source}) : esc(item.source)}</small></td><td>${esc(item.value)}</td><td>${esc(item.date)}<br>${esc(item.state)}</td><td>${esc(item.weight)}</td></tr>`).join('');
      const territoryFacts = report.top.map(item=>`<article class="err-diagnostic-card"><strong>${esc(item.label)} · ${esc(item.value)}</strong><small>${esc(item.note)}</small></article>`).join('');
      return `<article class="err-document" data-report-kind="fire-current">
        <header class="err-cover"><div><span>ECORADAR · MUNTANYA D’ALINYÀ</span><h1>${esc(report.name)}</h1><p>Lectura operativa per a la gestió de l’espai</p></div><div class="err-date">Generat ${esc(report.generatedAt)}</div></header>
        <section><h2>1. Situació actual</h2><div class="err-facts">${facts}</div>
          <div class="err-diagnostic-grid"><article class="err-diagnostic-card"><strong>Factors que afavoreixen el foc</strong>${paragraph(report.favour)}</article><article class="err-diagnostic-card"><strong>Factors que limiten la propagació</strong>${paragraph(report.limit)}</article></div>
          <p><strong>Principal incertesa.</strong> ${esc(report.uncertainty)}</p><p>${esc(report.compatibility)}</p>
        </section>
        <section class="err-map-section"><h2>2. Distribució territorial</h2>${paragraph(report.territory)}<p><strong>Màxim territorial:</strong> ${esc(report.maximum)}.</p>
          ${mapSvg ? `<div class="err-map-frame"><div class="err-map">${mapSvg}</div></div>` : ''}
          ${territoryFacts ? `<div class="err-sector-summary"><p>Cel·les amb els valors més elevats de la malla disponible:</p><div class="err-diagnostic-grid">${territoryFacts}</div></div>` : '<p>No hi ha cel·les de la mateixa comprovació disponibles per localitzar els màxims.</p>'}
        </section>
        <section><h2>3. Factors explicatius</h2>${paragraph(report.explanation)}${report.ecologicalContext ? paragraph([...new Set([report.ecologicalContext.meaning, ...report.ecologicalContext.processes, ...report.ecologicalContext.combinations])]) : ''}</section>
        <section><h2>4. Què podria passar si es produís una ignició ara?</h2>${paragraph(report.scenario)}</section>
        <section><h2>5. Elements potencialment exposats</h2>${paragraph(report.exposure)}</section>
        <section><h2>6. Implicacions per a la gestió avui</h2>${paragraph(report.management)}${report.ecologicalContext ? paragraph(report.ecologicalContext.management) : ''}</section>
        <section class="err-limits"><h2>7. Fonts, dades i limitacions</h2>
          <p>Comprovació del càlcul: ${esc(report.dataDate)}. Les dates següents corresponen a cada font.</p>
          <table class="eu-data-table"><thead><tr><th>Font / variable</th><th>Lectura</th><th>Data i vigència</th><th>Pes guardat</th></tr></thead><tbody>${rows}</tbody></table>
          ${paragraph(report.limits)}<p>${report.references.map(link).join(' · ')}</p>
        </section><footer>EcoRadar · Muntanya d’Alinyà</footer>
      </article>`;
    }
    if (report.ecologicalContext) {
      const c=report.ecologicalContext;
      const relationshipCards=c.relations.filter(r=>r.compatible).map(r=>({title:r.label,level:'observat',text:`${r.scope==='historical'?'Contrast històric':'Contrast del període indicat'}. ${r.evidence} ${r.purpose}`}));
      const extra=report.biodiversityChapters?.length?`<section><details><summary>Consultar la diagnosi específica de biodiversitat i hàbitats</summary>${report.biodiversityChapters.map(ch=>`<h3>${esc(ch.title)}</h3>${paragraph(ch.body)}`).join('')}</details></section>`:'';
      return `<article class="err-document" data-report-kind="ecological-context">
        <header class="err-cover"><div><span>ECORADAR · MUNTANYA D’ALINYÀ</span><h1>${esc(report.name)}</h1><p>Diagnosi ecològica contextual i suport a la gestió</p></div><div class="err-date">Generat ${esc(report.generatedAt)}</div></header>
        <section><h2>1. Valor disponible i significat ecològic</h2><div class="err-facts">${facts}</div>${paragraph(c.observation)}${paragraph(c.meaning)}</section>
        <section><h2>2. Distribució territorial i processos ecològics</h2>${mapSvg?`<div class="err-map-frame"><div class="err-map">${mapSvg}</div></div>`:''}${paragraph(c.processes)}${paragraph(report.territorial)}</section>
        <section><h2>3. Relacions amb altres lectures</h2>${labeled(relationshipCards)}${!relationshipCards.length?'<p>No hi ha un creuament específic verificat per a aquesta lectura.</p>':''}</section>
        <section><h2>4. Diagnosi conjunta i interpretacions alternatives</h2>${paragraph(c.combinations)}</section>
        <section><h2>5. Possibles trajectòries ecològiques</h2>${labeled(c.scenarios.map(s=>({title:s.label,text:s.text,level:'potencial'})))}</section>
        <section><h2>6. Implicacions per a la gestió</h2>${paragraph(c.management)}</section>
        <section class="err-limits"><h2>7. Fonts, dades i limitacions</h2><p>Data de la lectura representada: ${esc(report.dataDate)}.</p><ul>${sources}</ul>${c.relations.filter(r=>r.compatible).map(r=>`<p style="overflow-wrap:anywhere"><strong>${esc(r.label)}:</strong> ${esc(r.provenance)}</p>`).join('')}${paragraph(c.limitations)}${paragraph(c.relations.filter(r=>!r.compatible).map(r=>r.excluded))}${c.relations.some(r=>!r.compatible)?paragraph('Pendents de compatibilitat: '+[...new Set(c.relations.filter(r=>!r.compatible).flatMap(r=>r.reasons))].join('; ')+'.'):''}${paragraph([...new Set(report.limits || [])].filter(text=>!text.startsWith('La lectura identifica patrons')))}<p>${c.references.map(r=>`<a href="${esc(r.url)}">${esc(r.label)}</a>`).join(' · ')}</p></section>
        ${extra}<footer>EcoRadar · Muntanya d’Alinyà · diagnosi vinculada a la lectura activa</footer>
      </article>`;
    }
    if (report.reportKind === 'biodiversity-habitats' && report.biodiversityChapters?.length) {
      const chapters = report.biodiversityChapters.map((chapter, index) => {
        const map = index === 1 && mapSvg ? `<div class="err-map-frame"><div class="err-map">${mapSvg}</div></div>` : '';
        return `<section class="${index === 11 ? 'err-limits' : ''}"><h2>${index + 1}. ${esc(chapter.title)}</h2>${map}${paragraph(chapter.body)}</section>`;
      }).join('');
      return `<article class="err-document">
        <header class="err-cover"><div><span>ECORADAR · MUNTANYA D’ALINYÀ</span><h1>${esc(report.name)}</h1><p>Diagnosi ecològica i suport a la gestió</p></div><div class="err-date">Generat ${esc(report.generatedAt)}</div></header>
        <section class="err-metadata"><div><b>Espai</b><span>Muntanya d’Alinyà</span></div><div><b>Data de les dades</b><span>${esc(report.dataDate)}</span></div><div><b>Lectura</b><span>${esc(report.name)}</span></div></section>
        ${facts ? `<section><h2>Síntesi d’evidències disponibles</h2><div class="err-facts">${facts}</div></section>` : ''}
        ${chapters}
        <footer>EcoRadar · diagnosi basada exclusivament en dades disponibles. Les coincidències orienten seguiment i validació; no demostren causalitat, estat de conservació ni absència d’espècies.</footer>
      </article>`;
    }
    return `<article class="err-document">
      <header class="err-cover"><div><span>ECORADAR · MUNTANYA D’ALINYÀ</span><h1>${esc(report.name)}</h1><p>Informe específic de la lectura activa</p></div><div class="err-date">Generat ${esc(report.generatedAt)}</div></header>
      <section class="err-metadata"><div><b>Espai</b><span>Muntanya d’Alinyà</span></div><div><b>Data de les dades</b><span>${esc(report.dataDate)}</span></div><div><b>Lectura</b><span>${esc(report.name)}</span></div></section>
      ${facts ? `<section><h2>Resultats principals</h2><div class="err-facts">${facts}</div></section>` : ''}
      <section><h2>1. Què mesura aquesta lectura i per què és útil?</h2>${paragraph(report.variableExplanation || [report.what, report.contribution])}</section>
      ${mapSvg ? `<section class="err-map-section"><div class="err-map-frame"><h2>2. Lectura territorial real d’Alinyà</h2><div class="err-map">${mapSvg}</div></div>${paragraph(report.territorialDiagnosis || [report.context, report.territorial, report.spatialAssessment].filter(Boolean))}</section>` : ''}
      ${report.technicalSynthesis || report.jointDiagnosis ? `<section class="err-synthesis"><h2>3. Diagnosi conjunta amb altres lectures EcoRadar</h2>${paragraph(report.jointDiagnosis || report.technicalSynthesis)}</section>` : ''}
      ${report.temporal && String(report.temporal).split(/\s+/).length > 35 ? `<section><h2>Comparació temporal</h2>${paragraph(report.temporal)}</section>` : ''}
      ${relations ? `<section><h2>4. Evidències complementàries seleccionades</h2><div class="err-relations">${relations}</div></section>` : ''}
      ${agreements || contradictions ? `<section><h2>5. Coincidències, matisos i contradiccions</h2>${agreements}${contradictions}</section>` : ''}
      ${causalFrame || causes ? `<section><h2>6. Possible causa · condicions associades · conseqüències</h2>${causalFrame || causes}</section>` : ''}
      ${ecologicalPathways ? `<section><h2>7. Vies d’afectació ecològica</h2>${ecologicalPathways}</section>` : `<section><h2>7. Conseqüències ecològiques</h2>${paragraph(report.consequences)}${report.ecologicalConsequences ? paragraph(report.ecologicalConsequences) : ''}</section>`}
      ${report.fireAssessment || fireDimensions ? `<section class="err-fire-assessment"><h2>8. Foc: perill conjuntural, vulnerabilitat estructural i exposició</h2>${fireDimensions || paragraph(report.fireAssessment)}</section>` : ''}
      <section><h2>9. Què passaria si la lectura augmentés o disminuís?</h2>${scenarios || `<div class="err-evolution"><article><strong>Si augmenta</strong>${paragraph(report.evolution?.increase || report.changes)}</article><article><strong>Si disminueix</strong>${paragraph(report.evolution?.decrease || report.changes)}</article></div>`}</section>
      ${chains ? `<section><h2>10. Possibles efectes en cadena</h2>${chains}<p class="err-chain-note">Les cadenes descriuen evolucions ecològicament plausibles; no converteixen una associació en una causa demostrada. Cada pas s’ha de contrastar amb la lectura indicada i amb dates compatibles.</p></section>` : ''}
      ${sectors || report.priorityAssessment ? `<section><h2>11. Priorització territorial justificada</h2>${report.priorityAssessment ? `<div class="err-priority-summary"><strong>${esc(report.priorityAssessment.category)}</strong>${paragraph(report.priorityAssessment.rationale)}${report.priorityAssessment.rule ? `<small>${esc(report.priorityAssessment.rule)}</small>` : ''}</div>` : ''}${sectors}</section>` : ''}
      ${management || monitoring ? `<section><h2>12. Implicacions de gestió i seguiment</h2>${management}${monitoring}</section>` : `<section><h2>12. Implicacions de gestió i seguiment</h2>${paragraph(report.improve)}</section>`}
      ${report.unverified?.length ? `<section class="err-unverified"><h2>Factors rellevants no verificats amb aquesta lectura</h2>${paragraph(report.unverified)}</section>` : ''}
      <section class="err-conclusion"><h2>13. Conclusions i decisions que es poden defensar</h2>${paragraph(report.integratedConclusion || report.conclusions)}</section>
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
    const buttons = [...root.querySelectorAll('[data-generate-reading-report]')];
    const modal = root.querySelector('[data-reading-report-modal]');
    const preview = modal && modal.querySelector('[data-reading-report-preview]');
    if (!buttons.length || !modal || !preview) return;
    let lastReport = null;
    let lastBody = '';
    let activeButton = buttons[0];

    function close() { modal.hidden = true; document.body.classList.remove('err-modal-open'); activeButton.focus(); }
    buttons.forEach(button => button.addEventListener('click', () => {
        activeButton = button;
        const selection = options.getSelection();
        lastReport = options.buildReport(selection);
        const svg = options.getMapSvg && options.getMapSvg();
        const mapClone = svg ? svg.cloneNode(true) : null;
        if (svg && (lastReport.reportKind === 'fire-current' || lastReport.ecologicalContext)) {
          // Preserve the selected layers when the SVG leaves the active map.
          const original = svg.querySelectorAll('*');
          mapClone.querySelectorAll('*').forEach((node, index) => {
            const style = global.getComputedStyle(original[index]);
            node.style.display = style.display;
            node.style.visibility = style.visibility;
            node.style.opacity = style.opacity;
          });
        }
        const mapSvg = mapClone ? mapClone.outerHTML : '';
        lastBody = reportHtml(lastReport, mapSvg);
        preview.innerHTML = lastBody;
        modal.querySelector('[data-reading-report-title]').textContent = lastReport.name;
        modal.hidden = false;
        document.body.classList.add('err-modal-open');
        modal.querySelector('[data-reading-report-close]').focus();
    }));
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
      if (lastReport.reportKind === 'fire-current' || lastReport.ecologicalContext) {
        // Keep inherited EcoRadar styling when html2pdf clones outside the viewer.
        const computed = global.getComputedStyle(documentNode);
        exportDocument.style.fontFamily = computed.fontFamily;
        for (const token of ['--green','--blue','--line','--orange']) {
          exportDocument.style.setProperty(token, computed.getPropertyValue(token));
        }
        exportDocument.querySelectorAll('.err-map svg').forEach(svg => {
          svg.setAttribute('width', '634');
          svg.setAttribute('height', '340');
          svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        });
        if (lastReport.reportKind === 'fire-current') exportDocument.querySelector('.err-limits').style.breakBefore = 'page';
        exportDocument.querySelectorAll('.eu-data-table th, .eu-data-table td').forEach(cell => { cell.style.padding = '4px 10px'; });
      }
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
          avoid: ['[data-report-kind="ecological-context"] > section', '[data-report-kind="ecological-context"] .err-diagnostic-grid', '[data-report-kind="ecological-context"] .err-diagnostic-card', '[data-report-kind="fire-current"] tr', '[data-report-kind="fire-current"] .err-sector-summary', '[data-report-kind="fire-current"] .err-diagnostic-grid', '.err-map-frame', '.err-map', '.err-fact', '.err-diagnostic-card', '.err-relation', '.err-chain-step', '.err-sector', '.err-management', '.err-evolution article', '.err-scenario', '.err-priority-summary']
        }
      };
      global.html2pdf().set(options).from(exportMarkup, 'string').save()
        .then(() => { global.scrollTo(scrollPosition.x, scrollPosition.y); status.textContent = 'PDF preparat. Revisa la carpeta de descàrregues o la ubicació de desament triada.'; })
        .catch(() => { global.scrollTo(scrollPosition.x, scrollPosition.y); status.textContent = 'No s’ha pogut desar el PDF. Torna-ho a provar.'; });
    });
    global.EcoRadarReadingReportTest = { reportHtml, pdfFilename };
  }

  global.EcoRadarReadingReport = { mount, reportHtml };
})(window);
