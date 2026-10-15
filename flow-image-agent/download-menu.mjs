// Per-image resolution submenu. Gallery "Download batch" is a button, not a menuitem.
export const MENU_OVERLAY = '.cdk-overlay-container';
export const DOWNLOAD_LABEL = /^\s*Download\s*$/i;
export const TWO_K_LABEL = /^\s*2K(?:\s+Upscaled)?\s*$/i;
export const MENU_BACKDROP = '.cdk-overlay-backdrop.cdk-overlay-backdrop-showing';

export function downloadItem(page) {
  return page.getByRole('menuitem', { name: DOWNLOAD_LABEL }).first();
}

export function resolutionItem(page) {
  return page.getByRole('menuitem', { name: TWO_K_LABEL }).first();
}

export function boxInViewport(box, height, pad = 8) {
  if (!box || !height) return false;
  const mid = box.y + box.height / 2;
  return mid >= pad && mid <= height - pad;
}

export async function viewportHeight(page) {
  const size = page.viewportSize?.();
  if (size?.height) return size.height;
  return page.evaluate(() => window.innerHeight);
}

export async function dismissFlowMenus(page, pause) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const backdrops = page.locator(MENU_BACKDROP);
    const menus = page.getByRole('menu');
    const open = (await backdrops.count()) + (await menus.count());
    if (open === 0) return;
    await page.keyboard.press('Escape');
    if (pause) await pause(150);
  }
  const leftover = page.locator(MENU_BACKDROP);
  if (await leftover.count()) {
    await leftover.first().click({ force: true }).catch(() => {});
    if (pause) await pause(150);
  }
}

export async function select2KMenu(page, openMenu, click, pause) {
  let lastError;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      await dismissFlowMenus(page, pause);
      await openMenu();
      const download = downloadItem(page);
      await download.waitFor({ state: 'visible', timeout: 8000 });
      const height = await viewportHeight(page);
      const box = await download.boundingBox();
      // Hovering an off-screen item (or one under the full-page backdrop) never
      // opens the 2K submenu. Click the menuitem instead; Material accepts it.
      if (boxInViewport(box, height)) {
        await download.hover({ timeout: 2000, force: true }).catch(() => {});
      }
      const twoK = resolutionItem(page);
      try {
        await twoK.waitFor({ state: 'visible', timeout: 2000 });
      } catch {
        await click(download);
        await twoK.waitFor({ state: 'visible', timeout: 8000 });
      }
      return twoK;
    } catch (error) {
      lastError = error;
      if (page.isClosed()) throw error;
      if (attempt < 3) await pause(750);
    }
  }
  throw new Error(`Could not open Flow's per-image Download → 2K menu after 3 attempts: ${lastError.message}`);
}
