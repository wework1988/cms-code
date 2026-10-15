const EDITOR = 'textarea:visible,[contenteditable="true"]:visible,[role="textbox"]:visible';
const GENERATE = /^(?:Start generation|Generate|Create|Run|Submit)$/i;

async function dismissPromptOverlay(page) {
  const backdrop = page.locator('.cdk-overlay-backdrop.cdk-overlay-backdrop-showing:visible');
  // Download submenus can leave multiple menu levels open after saving.
  for (let attempt = 0; attempt < 3; attempt++) {
    if (await backdrop.count() === 0) return;
    await page.keyboard.press('Escape');
    try {
      await backdrop.first().waitFor({ state: 'hidden', timeout: 1000 });
    } catch (error) {
      if (error.name !== 'TimeoutError') throw error;
    }
  }
  if (await backdrop.count() > 0) {
    const error = new Error('Flow menu backdrop still blocks the prompt after Escape; close the open menu and restart the job.');
    error.category = 'ui_blocked';
    throw error;
  }
}

async function promptEditor(page) {
  const editor = page.locator(EDITOR);
  await editor.first().waitFor({ state: 'visible', timeout: 15000 });
  if (await editor.count() !== 1) throw new Error('Could not identify the Flow prompt box unambiguously');
  return editor;
}

async function verifyText(editor, expected) {
  const current = await editor.evaluate(el => el.value ?? el.innerText ?? el.textContent ?? '');
  const normalize = text => String(text).replace(/\r\n/g, '\n').trim();
  if (normalize(current) !== normalize(expected)) {
    throw new Error('Could not verify the complete prompt text in the editor; generation was not submitted');
  }
}

export async function enterPrompt(page, text) {
  if (!String(text).trim()) throw new Error('Cannot submit an empty Flow prompt');
  // Background tabs can throttle the animation frames used by click's stability
  // checks. Restore the Flow tab before interacting with the composer.
  await page.bringToFront();
  await dismissPromptOverlay(page);
  const editor = await promptEditor(page);
  // Playwright fill uses standard editable input handling for textareas and
  // contenteditable editors, without value setters or synthetic DOM events.
  await editor.fill(text, { timeout: 15000 });
  await verifyText(editor, text);
}

export async function submitPrompt(page, expectedText) {
  await page.bringToFront();
  await dismissPromptOverlay(page);
  const button = page.getByRole('button', { name: GENERATE });
  await button.waitFor({ state: 'visible', timeout: 15000 });
  const handle = await button.elementHandle();
  try {
    await page.waitForFunction(el => el?.isConnected && !el.disabled
      && el.getAttribute('aria-disabled') !== 'true', handle, { timeout: 15000 });
  } finally {
    await handle?.dispose();
  }
  await verifyText(await promptEditor(page), expectedText);
  // Native button keyboard activation avoids pointer stability checks on Flow's
  // animated composer. Clear overlays first; never retry an activation whose
  // result is uncertain, since it may already have submitted a generation.
  await button.focus({ timeout: 15000 });
  if (!await button.isVisible() || !await button.isEnabled()
      || await button.getAttribute('aria-disabled') === 'true') {
    throw new Error('Generate became unavailable before submission');
  }
  await verifyText(await promptEditor(page), expectedText);
  await button.press('Space', { timeout: 15000 });
}
