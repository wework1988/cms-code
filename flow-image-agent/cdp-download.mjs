import path from 'node:path';
const trackers = new WeakMap();

function collectFrameIds(tree, into = new Set()) {
  if (tree?.frame?.id) into.add(tree.frame.id);
  for (const child of tree?.childFrames || []) collectFrameIds(child, into);
  return into;
}

function isFlowDownload(event) {
  const url = String(event.url || '');
  const name = String(event.suggestedFilename || '');
  return /(?:^blob:)?https:\/\/flow\.google\.com\//i.test(url) || /_2K_/i.test(name);
}

export async function trackPageDownloads(page, context, session, directory) {
  const pageSession = await context.newCDPSession(page);
  try {
    const { frameTree } = await pageSession.send('Page.getFrameTree');
    const frameIds = collectFrameIds(frameTree);
    trackers.set(page, {
      session,
      directory,
      frameId: frameTree.frame.id,
      frameIds,
    });
  } finally { await pageSession.detach(); }
}

export async function downloadFromPage(page, click, timeoutMs = 180000) {
  const tracker = trackers.get(page);
  if (!tracker) throw new Error('Download tracking is not initialized for this Flow tab');
  return receiveDownload(tracker, click, timeoutMs);
}

export async function receiveDownload({ session, directory, frameId, frameIds }, click, timeoutMs) {
  let guid, timer, resolve, reject;
  const completed = new Promise((yes, no) => { resolve = yes; reject = no; });
  completed.catch(() => {});
  const frames = frameIds instanceof Set ? frameIds : new Set(frameId ? [frameId] : []);
  const begin = event => {
    if (guid) return;
    if (!/^[a-zA-Z0-9-]+$/.test(event.guid)) return;
    const sameTab = frames.has(event.frameId) || event.frameId === frameId;
    if (!sameTab && !isFlowDownload(event)) return;
    guid = event.guid;
  };
  const progress = event => {
    if (!guid || event.guid !== guid) return;
    if (event.state === 'completed') resolve(path.join(directory, guid));
    if (event.state === 'canceled') reject(new Error('Flow download was canceled'));
  };
  session.on('Browser.downloadWillBegin', begin);
  session.on('Browser.downloadProgress', progress);
  timer = setTimeout(() => reject(new Error('Flow download did not complete within timeout')), timeoutMs);
  try {
    await click();
    return await completed;
  } finally {
    clearTimeout(timer);
    session.off('Browser.downloadWillBegin', begin);
    session.off('Browser.downloadProgress', progress);
  }
}
