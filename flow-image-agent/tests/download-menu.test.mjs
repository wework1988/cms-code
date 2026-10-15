import test from 'node:test';
import assert from 'node:assert/strict';
import {
  select2KMenu, downloadItem, resolutionItem, boxInViewport, dismissFlowMenus,
  DOWNLOAD_LABEL, TWO_K_LABEL, MENU_BACKDROP,
} from '../download-menu.mjs';

test('resolution label accepts split lines; batch is never a Download item', () => {
  assert(TWO_K_LABEL.test('2K\nUpscaled'));
  assert(TWO_K_LABEL.test('2K'));
  assert(!TWO_K_LABEL.test('4K Upscaled'));
  assert(!TWO_K_LABEL.test('2K Upscaled 4K Upscaled Upgrade'));
  assert(!DOWNLOAD_LABEL.test('Download batch'));
  assert(DOWNLOAD_LABEL.test('Download'));
});

test('boxInViewport rejects off-screen Download rows', () => {
  assert(boxInViewport({ x: 640, y: 200, width: 80, height: 20 }, 800));
  assert(!boxInViewport({ x: 640, y: -88, width: 66, height: 20 }, 816));
  assert(!boxInViewport({ x: 640, y: 900, width: 66, height: 20 }, 816));
  assert(!boxInViewport(null, 816));
});

function fixture({
  hoverOpens = true,
  missedMenus = 0,
  backdrops = 0,
  downloadY = 200,
  viewport = 800,
} = {}) {
  let opens = 0;
  let clicks = 0;
  let hovers = 0;
  let resolutionOpen = false;
  let menus = 0;
  const download = {
    async waitFor() { if (opens <= missedMenus) throw new Error('menu missed'); },
    async hover() { hovers++; resolutionOpen = hoverOpens; },
    async boundingBox() { return { x: 640, y: downloadY, width: 80, height: 20 }; },
    async click() { clicks++; resolutionOpen = true; },
  };
  const resolution = {
    async waitFor() { if (!resolutionOpen) throw new Error('submenu closed'); },
  };
  const page = {
    keyboard: { async press() { resolutionOpen = false; menus = 0; if (backdrops) backdrops -= 1; } },
    isClosed: () => false,
    viewportSize: () => ({ width: 1280, height: viewport }),
    locator(selector) {
      assert.equal(selector, MENU_BACKDROP);
      return {
        count: async () => backdrops,
        first() {
          return { click: async () => { backdrops = 0; } };
        },
      };
    },
    getByRole(role, options = {}) {
      if (role === 'menu') return { count: async () => menus };
      assert.equal(role, 'menuitem');
      const target = options.name === DOWNLOAD_LABEL ? download : resolution;
      return { first: () => target };
    },
  };
  return {
    page, resolution, download,
    open: async () => { opens++; menus = 1; },
    click: async (target) => { assert.equal(target, download); clicks++; resolutionOpen = true; },
    pause: async () => {},
    counts: () => ({ opens, clicks, hovers, backdrops }),
  };
}

test('hover opens the submenu without toggling it closed', async () => {
  const f = fixture();
  assert.equal(await select2KMenu(f.page, f.open, f.click, f.pause), f.resolution);
  assert.deepEqual(f.counts(), { opens: 1, clicks: 0, hovers: 1, backdrops: 0 });
});

test('click opens submenu when hover does not', async () => {
  const f = fixture({ hoverOpens: false });
  await select2KMenu(f.page, f.open, f.click, f.pause);
  assert.deepEqual(f.counts(), { opens: 1, clicks: 1, hovers: 1, backdrops: 0 });
});

test('off-screen Download skips hover and clicks the menuitem', async () => {
  const f = fixture({ hoverOpens: false, downloadY: -88, viewport: 816 });
  await select2KMenu(f.page, f.open, f.click, f.pause);
  assert.deepEqual(f.counts(), { opens: 1, clicks: 1, hovers: 0, backdrops: 0 });
});

test('leftover backdrop is dismissed before opening More options', async () => {
  const f = fixture({ backdrops: 2 });
  await select2KMenu(f.page, f.open, f.click, f.pause);
  assert.equal(f.counts().backdrops, 0);
  assert.equal(f.counts().opens, 1);
});

test('missed menu is reopened on the same image', async () => {
  const f = fixture({ missedMenus: 2 });
  await select2KMenu(f.page, f.open, f.click, f.pause);
  assert.equal(f.counts().opens, 3);
});

test('unavailable 2K stops after bounded retries', async () => {
  const f = fixture({ missedMenus: 3 });
  await assert.rejects(select2KMenu(f.page, f.open, f.click, f.pause), /after 3 attempts/);
  assert.equal(f.counts().opens, 3);
});

test('downloadItem and resolutionItem use menuitem roles', () => {
  const f = fixture();
  assert.equal(downloadItem(f.page), f.download);
  assert.equal(resolutionItem(f.page), f.resolution);
});

test('dismissFlowMenus clicks a stuck backdrop', async () => {
  const f = fixture({ backdrops: 1 });
  f.page.keyboard.press = async () => {};
  await dismissFlowMenus(f.page, async () => {});
  assert.equal(f.counts().backdrops, 0);
});
