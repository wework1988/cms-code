(function (Drupal, drupalSettings, once) {
  'use strict';
  const label = value => String(value || 'unknown').replaceAll('_', ' ');
  const time = value => value ? new Date(typeof value === 'number' ? value * 1000 : value).toLocaleTimeString() : 'Not reported';
  function el(tag, text, cls) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }
  function link(text, url) { const node = el('a', text); node.href = url; return node; }
  function runner(data) {
    if (!data.heartbeat_at) return 'Not reporting';
    if (['completed', 'failed', 'stopped', 'exited'].includes(data.state)) return label(data.state);
    return data.stale ? 'Status stale — runner not reporting' : label(data.state);
  }
  Drupal.behaviors.storyMonitor = {
    attach(context) {
      once('story-monitor', '#story-monitor', context).forEach(root => {
        root.replaceChildren();
        const header = el('div', undefined, 'sm-toolbar');
        const updated = el('span', 'Waiting for first refresh');
        const countdown = el('span', '');
        const refresh = el('button', 'Refresh now'); refresh.type = 'button';
        const search = el('input'); search.type = 'search'; search.placeholder = 'Find a story by title or ID'; search.setAttribute('aria-label', 'Find a story');
        header.append(updated, countdown, refresh, search);
        const notice = el('p'); notice.setAttribute('role', 'status');
        const health = el('p', '', 'sm-health');
        const cards = el('div');
        root.append(header, notice, health, el('p', 'Counts show files saved on disk. Expand a story for stage validation and individual scenes.'), cards);
        let snapshot = null, due = Date.now(), busy = false;
        function render() {
          if (!snapshot) return;
          const open = new Set([...cards.querySelectorAll('details[open]')].map(n => n.dataset.id));
          cards.replaceChildren();
          const query = search.value.toLowerCase();
          const stories = snapshot.stories.filter(s => `${s.id} ${s.title}`.toLowerCase().includes(query));
          stories.sort((a,b) => Number(['running','queued'].includes(b.status)) - Number(['running','queued'].includes(a.status)));
          for (const story of stories) {
            const card = el('details', undefined, 'sm-story'); card.dataset.id = String(story.id); card.open = open.has(String(story.id));
            const summary = el('summary'); summary.append(el('strong', `#${story.id} · ${story.title}`), el('span', story.status === 'unmanaged' ? `${label(story.cms_status)} · no tracked job` : label(story.status), 'sm-badge'));
            const counts = el('p', `Images ${story.images}/${story.expected || '?'} · Videos ${story.videos}/${story.expected || '?'} · Last worker update ${time(story.updated_at)}`);
            const components = el('div', undefined, 'sm-components');
            for (const [name, status, stamp] of [
              ['CMS', label(story.cms_status), snapshot.fetched_at],
              ['Python worker', runner(story.python), story.python.heartbeat_at],
              ['Flow images', `${runner(story.flow)}${story.flow_scene ? ` · Scene ${story.flow_scene}` : ''} · Browser: ${label(story.flow.browser)}`, story.flow.heartbeat_at],
              ['Digen videos', `${runner(story.digen)}${story.digen.scene ? ` · Scene ${story.digen.scene}` : ''} · Browser: ${label(story.digen.browser)}`, story.digen.heartbeat_at],
            ]) {
              const box = el('div'); box.append(el('strong', name), el('p', status), el('small', `Last report ${time(stamp)}`)); components.append(box);
            }
            const stages = el('table');
            const headings = el('tr'); ['Stage', 'Status', 'Retries used', 'Last progress', 'Next retry / validation'].forEach(t => headings.append(el('th', t))); stages.append(headings);
            for (const [name, stage] of Object.entries(story.stages)) {
              const row = el('tr');
              const details = stage.error || (stage.next_retry_at && stage.status === 'retry_wait' ? time(stage.next_retry_at) : (stage.validation ? JSON.stringify(stage.validation) : 'Not checked yet'));
              [label(name), label(stage.status), `${Math.max(0,(stage.attempts || 0)-1)} / 2`, time(stage.last_progress_at || stage.completed_at), details].forEach(t => row.append(el('td', t))); stages.append(row);
            }
            if (!Object.keys(story.stages).length) stages.append(el('caption', 'No managed job record. Legacy or manually started jobs may report only browser/file status.'));
            const sceneTable = el('table');
            const sceneHead = el('tr'); ['Scene', 'Image', 'Video'].forEach(t => sceneHead.append(el('th', t))); sceneTable.append(sceneHead);
            for (const scene of story.scenes) {
              const row = el('tr'); row.append(el('td', String(scene.id).padStart(3,'0')));
              for (const kind of ['image','video']) {
                const cell = el('td'); cell.append(scene[`${kind}_url`] ? link('Open saved file', scene[`${kind}_url`]) : el('span', label(scene[kind]))); row.append(cell);
              }
              sceneTable.append(row);
            }
            const body = el('div', undefined, 'sm-body'); body.append(link('Open story in CMS', story.url), counts, components, el('h3', 'Stages and retry status'), stages, el('h3', 'Scenes'), sceneTable);
            card.append(summary,body); cards.append(card);
          }
          if (!stories.length) cards.append(el('p', 'No matching stories.'));
          const check = snapshot.watchdog.checked_at;
          health.textContent = `Recovery monitor: ${!check ? 'No check recorded' : snapshot.fetched_at-check > 660 ? 'Check overdue' : 'Recently checked'} · Last check ${time(check)} · Recovery interval 5 minutes`;
        }
        async function load() {
          if (busy) return;
          busy = true; refresh.disabled = true; countdown.textContent = 'Refreshing…';
          const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 20000);
          try {
            const response = await fetch(drupalSettings.storyMonitor.endpoint, {cache:'no-store', credentials:'same-origin', signal:controller.signal});
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json(); if (!Array.isArray(data.stories)) throw new Error('Invalid status response');
            snapshot = data; render(); updated.textContent = `Last refreshed: ${time(data.fetched_at)}`;
            notice.textContent = ''; root.classList.remove('sm-offline');
          } catch (error) {
            notice.textContent = `Status unavailable. ${snapshot ? 'Showing the last successful snapshot.' : 'No status loaded yet.'} Retrying in one minute.`;
            root.classList.add('sm-offline');
          } finally { clearTimeout(timeout); busy = false; refresh.disabled = false; due = Date.now()+60000; }
        }
        refresh.addEventListener('click', load); search.addEventListener('input', render);
        setInterval(() => {
          if (!root.isConnected || busy) return;
          const remaining = Math.max(0,Math.ceil((due-Date.now())/1000));
          countdown.textContent = `Refreshing in ${remaining} seconds`;
          if (!remaining) load();
        }, 1000);
        load();
      });
    }
  };
})(Drupal, drupalSettings, once);
