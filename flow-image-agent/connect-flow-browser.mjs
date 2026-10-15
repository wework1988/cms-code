export async function connectFlowBrowser(chromium, endpoint, downloadsPath) {
  // Existing Chrome profiles can reject context-scoped download management.
  // Preserve the default context and configure downloads without a context id.
  const browser = await chromium.connectOverCDP(endpoint, {
    noDefaults: true,
    artifactsDir: downloadsPath,
  });
  const context = browser.contexts()[0];
  if (!context) throw new Error('Chrome has no existing signed-in browser context. Restart the Flow profile.');
  const cdp = await browser.newBrowserCDPSession();
  try {
    await cdp.send('Browser.setDownloadBehavior', {
      behavior: 'allowAndName', downloadPath: downloadsPath, eventsEnabled: true,
    });
  } catch (error) {
    await cdp.detach().catch(() => {});
    throw new Error(`Chrome download setup failed before submission: ${error.message}`);
  }
  // Keep this CDP session attached for the browser lifetime. Detaching can
  // revert session-owned download settings and stop progress events.
  return { browser, context, downloadSession: cdp };
}
