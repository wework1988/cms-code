const FLOW_HOSTS = new Set(['flow.google.com', 'labs.google']);

function isFlowTab(tab) {
  try {
    const host = new URL(tab.url).hostname;
    return FLOW_HOSTS.has(host);
  } catch {
    return false;
  }
}

function flowDownloadRelevant(item) {
  try {
    const host = new URL(item.finalUrl || item.url).hostname;
    if (host.includes('flow') || host.includes('google')) return true;
  } catch {
    /* ignore */
  }
  return /flow\.google\.com|labs\.google/.test(item.referrer || '');
}

// Pending download correlation: downloadId -> meta
const pendingDownloads = new Map();

chrome.runtime.onMessage.addListener((message, sender, reply) => {
  if (message.type === 'nativeClick') {
    if (!sender.tab || !isFlowTab(sender.tab)) {
      reply({ error: 'Native click only allowed from a Flow tab.' });
      return;
    }
    const x = Number(message.x);
    const y = Number(message.y);
    if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || y < 0) {
      reply({ error: 'Invalid click position' });
      return;
    }
    const target = { tabId: sender.tab.id };
    (async () => {
      let attached = false;
      try {
        await chrome.debugger.attach(target, '1.3');
        attached = true;
        await chrome.debugger.sendCommand(target, 'Input.dispatchMouseEvent', {
          type: 'mouseMoved', x, y,
        });
        await chrome.debugger.sendCommand(target, 'Input.dispatchMouseEvent', {
          type: 'mousePressed', x, y, button: 'left', clickCount: 1,
        });
        await chrome.debugger.sendCommand(target, 'Input.dispatchMouseEvent', {
          type: 'mouseReleased', x, y, button: 'left', clickCount: 1,
        });
        reply({ ok: true });
      } catch (e) {
        reply({
          error: `Native Flow click failed: ${e.message}. Close DevTools or other browser automation and try again.`,
        });
      } finally {
        if (attached) {
          try { await chrome.debugger.detach(target); } catch { /* ignore */ }
        }
      }
    })();
    return true;
  }

  if (message.type === 'watchDownload') {
    if (!sender.tab || !isFlowTab(sender.tab)) {
      reply({ error: 'Download watch only from Flow tab.' });
      return;
    }
    const watch = {
      tabId: sender.tab.id,
      scene: message.scene,
      jobId: message.jobId,
      since: message.since || new Date().toISOString(),
      resultId: message.resultId || null,
      resolved: null,
    };
    pendingDownloads.set(`watch:${sender.tab.id}:${message.scene}:${watch.since}`, watch);
    reply({ ok: true });
    return;
  }

  if (message.type === 'downloadStatus') {
    if (!sender.tab || !isFlowTab(sender.tab)) {
      reply({ error: 'downloadStatus only from Flow tab.' });
      return;
    }
    const since = message.since;
    chrome.downloads.search({ startedAfter: since, orderBy: ['-startTime'] }, (items) => {
      const error = chrome.runtime.lastError;
      if (error) {
        reply({ error: error.message });
        return;
      }
      const relevant = (items || []).filter((item) => {
        if (item.tabId != null && item.tabId !== sender.tab.id) return false;
        return flowDownloadRelevant(item);
      });
      const complete = relevant.find((item) => item.state === 'complete' && item.exists !== false);
      const interrupted = relevant.some((item) => item.state === 'interrupted');
      const inProgress = relevant.some((item) => item.state === 'in_progress');
      reply({
        complete: Boolean(complete),
        interrupted,
        inProgress,
        download: complete
          ? {
              id: complete.id,
              filename: complete.filename,
              mime: complete.mime,
              fileSize: complete.fileSize,
              url: complete.finalUrl || complete.url,
            }
          : null,
      });
    });
    return true;
  }

  if (message.type === 'helperFetch') {
    // Proxy helper calls so the service worker holds the token out of page context.
    (async () => {
      try {
        const stored = await chrome.storage.local.get(['helperUrl', 'token']);
        const base = (message.helperUrl || stored.helperUrl || 'http://127.0.0.1:8765').replace(/\/$/, '');
        const token = message.token || stored.token;
        if (!token) throw new Error('Pairing token missing. Paste it in the extension popup.');
        const res = await fetch(base + message.path, {
          method: message.method || 'GET',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
            'X-Flow-Agent-Token': token,
          },
          body: message.body ? JSON.stringify(message.body) : undefined,
        });
        const data = await res.json().catch(() => ({}));
        reply({ ok: res.ok, status: res.status, data });
      } catch (e) {
        reply({ ok: false, error: e.message });
      }
    })();
    return true;
  }
});
