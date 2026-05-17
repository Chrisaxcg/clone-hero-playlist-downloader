(() => {
  // --- State ---
  let allResults = [];
  let totalTracks = 0;
  let searchedCount = 0;

  // --- DOM refs ---
  const urlInput        = document.getElementById('playlist-url');
  const btnLoad         = document.getElementById('btn-load');
  const sourceBadge     = document.getElementById('source-badge');
  const inputError      = document.getElementById('input-error');
  const phaseResults    = document.getElementById('phase-results');
  const phaseDownload   = document.getElementById('phase-download');
  const playlistName    = document.getElementById('playlist-name');
  const resultsSummary  = document.getElementById('results-summary');
  const resultsBody     = document.getElementById('results-body');
  const btnSelectAll    = document.getElementById('btn-select-all');
  const btnDeselectAll  = document.getElementById('btn-deselect-all');
  const btnDownload     = document.getElementById('btn-download');
  const selectedCount   = document.getElementById('selected-count');
  const chkAll          = document.getElementById('chk-all');
  const searchFill      = document.getElementById('search-progress-fill');
  const searchStatusTxt = document.getElementById('search-status-text');
  const zipPreparing    = document.getElementById('zip-preparing');
  const zipDone         = document.getElementById('zip-done');
  const zipError        = document.getElementById('zip-error');
  const zipStatusText   = document.getElementById('zip-status-text');
  const zipProgressFill = document.getElementById('zip-progress-fill');
  const btnRestart      = document.getElementById('btn-restart');

  // --- URL detection ---
  urlInput.addEventListener('input', () => {
    const v = urlInput.value.trim();
    sourceBadge.className = 'source-badge';
    if (v.includes('spotify.com')) {
      sourceBadge.textContent = 'Spotify';
      sourceBadge.classList.add('spotify');
      sourceBadge.classList.remove('hidden');
    } else if (v.includes('music.apple.com')) {
      sourceBadge.textContent = 'Apple Music';
      sourceBadge.classList.add('apple');
      sourceBadge.classList.remove('hidden');
    } else {
      sourceBadge.classList.add('hidden');
    }
  });

  // --- Load playlist ---
  btnLoad.addEventListener('click', loadPlaylist);
  urlInput.addEventListener('keydown', e => { if (e.key === 'Enter') loadPlaylist(); });

  async function loadPlaylist() {
    const url = urlInput.value.trim();
    if (!url) { showError('Pega un link de Spotify o Apple Music.'); return; }

    setError('');
    btnLoad.disabled = true;
    btnLoad.textContent = 'Cargando…';

    try {
      const resp = await fetch('/api/playlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await resp.json();
      if (!resp.ok) { showError(data.detail || 'Error al cargar la playlist.'); return; }

      phaseResults.classList.remove('hidden');
      playlistName.textContent = data.playlist_name;
      totalTracks = data.total;
      resultsSummary.textContent = `${data.total} canciones`;
      resultsBody.innerHTML = '';
      allResults = [];
      searchedCount = 0;
      updateSearchBar(0, data.total);

      await searchTracks(data.tracks);
    } catch (e) {
      showError('Error de red: ' + e.message);
    } finally {
      btnLoad.disabled = false;
      btnLoad.textContent = 'Cargar playlist';
    }
  }

  // --- Search tracks (NDJSON streaming) ---
  async function searchTracks(tracks) {
    searchStatusTxt.textContent = 'Buscando canciones…';
    btnDownload.disabled = true;

    const resp = await fetch('/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tracks }),
    });

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const result = JSON.parse(line);
          allResults.push(result);
          appendResultRow(result);
          searchedCount++;
          updateSearchBar(searchedCount, totalTracks);
        } catch (_) {}
      }
    }

    searchStatusTxt.textContent =
      `Busqueda completa — ${allResults.filter(r => r.found).length} encontradas de ${allResults.length}`;
    autoSelectFound();
    updateDownloadButton();
  }

  function updateSearchBar(done, total) {
    const pct = total ? Math.round(done / total * 100) : 0;
    searchFill.style.width = pct + '%';
    searchStatusTxt.textContent = `Buscando… ${done}/${total}`;
  }

  // --- Append row to results table ---
  function appendResultRow(result) {
    const tr = document.createElement('tr');
    tr.dataset.idx = allResults.length - 1;

    if (!result.found) tr.classList.add('row-not-found');

    const canDownload = result.found && result.download_url && !result.youtube_only;

    tr.innerHTML = `
      <td><input type="checkbox" class="row-chk" ${canDownload ? '' : 'disabled'} /></td>
      <td>${esc(result.track.name)}</td>
      <td>${esc(result.track.artist)}</td>
      <td>${result.chart_name
            ? esc(result.chart_name)
            : '<span class="badge-nf">No encontrada</span>'}</td>
      <td>${esc(result.charter || '—')}</td>
      <td>${sourceTag(result)}</td>
      <td class="instruments">${(result.instruments || []).join(', ') || '—'}</td>
      <td>${matchBadge(result)}</td>
      <td>${canDownload
            ? `<a class="btn btn-sm btn-dl" href="${esc(result.download_url)}" target="_blank" rel="noopener">SNG</a>`
            : ''}</td>
    `;

    tr.querySelector('.row-chk')?.addEventListener('change', updateDownloadButton);
    resultsBody.appendChild(tr);
  }

  function sourceTag(r) {
    if (!r.found) return '';
    if (r.youtube_only) return '<span class="badge-yt">Solo YouTube</span>';
    if (r.source === 'enchor') return '<span class="source-tag source-enchor">enchor.us</span>';
    if (r.source === 'rhythmverse') return '<span class="source-tag source-rv">RhythmVerse</span>';
    return '';
  }

  function matchBadge(r) {
    if (!r.found) return '';
    const score = r.match_score;
    const cls = score >= 90 ? 'match-high' : score >= 75 ? 'match-medium' : 'match-low';
    return `<span class="match-badge ${cls}">${score}</span>`;
  }

  function esc(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // --- Selection ---
  btnSelectAll.addEventListener('click', () => {
    resultsBody.querySelectorAll('.row-chk:not(:disabled)').forEach(c => c.checked = true);
    updateDownloadButton();
  });

  btnDeselectAll.addEventListener('click', () => {
    resultsBody.querySelectorAll('.row-chk').forEach(c => c.checked = false);
    updateDownloadButton();
  });

  chkAll.addEventListener('change', () => {
    resultsBody.querySelectorAll('.row-chk:not(:disabled)')
      .forEach(c => c.checked = chkAll.checked);
    updateDownloadButton();
  });

  function autoSelectFound() {
    resultsBody.querySelectorAll('.row-chk:not(:disabled)').forEach(c => c.checked = true);
    updateDownloadButton();
  }

  function updateDownloadButton() {
    const checked = resultsBody.querySelectorAll('.row-chk:checked').length;
    selectedCount.textContent = checked;
    btnDownload.disabled = checked === 0;
  }

  // --- Bulk download as ZIP ---
  btnDownload.addEventListener('click', startDownload);

  async function startDownload() {
    const checkedRows = [...resultsBody.querySelectorAll('.row-chk:checked')];
    const selected = checkedRows.map(chk => {
      const idx = parseInt(chk.closest('tr').dataset.idx);
      return allResults[idx];
    });
    if (!selected.length) return;

    // Show download phase
    phaseDownload.classList.remove('hidden');
    phaseDownload.scrollIntoView({ behavior: 'smooth' });
    btnDownload.disabled = true;

    zipPreparing.classList.remove('hidden');
    zipDone.classList.add('hidden');
    zipError.classList.add('hidden');
    zipProgressFill.style.width = '0%';
    zipStatusText.textContent = 'Preparando descarga…';

    // Animate indeterminate progress while waiting
    let fakeProgress = 0;
    const fakeTimer = setInterval(() => {
      fakeProgress = Math.min(fakeProgress + 2, 85);
      zipProgressFill.style.width = fakeProgress + '%';
    }, 400);

    try {
      const resp = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results: selected }),
      });

      clearInterval(fakeTimer);

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `Error ${resp.status}`);
      }

      zipProgressFill.style.width = '100%';
      zipStatusText.textContent = 'Descargando ZIP…';

      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'clone_hero_songs.zip';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);

      zipPreparing.classList.add('hidden');
      zipDone.classList.remove('hidden');
    } catch (err) {
      clearInterval(fakeTimer);
      zipPreparing.classList.add('hidden');
      zipError.textContent = 'Error: ' + err.message;
      zipError.classList.remove('hidden');
      btnDownload.disabled = false;
    }
  }

  // --- Restart ---
  btnRestart.addEventListener('click', () => {
    phaseResults.classList.add('hidden');
    phaseDownload.classList.add('hidden');
    resultsBody.innerHTML = '';
    allResults = [];
    urlInput.value = '';
    sourceBadge.classList.add('hidden');
    btnDownload.disabled = true;
    selectedCount.textContent = '0';
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });

  function showError(msg) {
    inputError.textContent = msg;
    inputError.classList.remove('hidden');
  }
  function setError(msg) {
    if (msg) { showError(msg); }
    else { inputError.textContent = ''; inputError.classList.add('hidden'); }
  }
})();
