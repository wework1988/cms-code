// Prompt entry for the isolated animation-lab runner only.
export function normalizePrompt(value) {
  return String(value ?? '').normalize('NFC').replace(/[\u200b\ufeff]/gu, '').replace(/\s+/gu, ' ').trim();
}

export async function fillPrompt(page, text) {
  // Flow's rich-text editor can turn newlines into block elements. A single
  // paragraph preserves every word and avoids textContent joining those blocks.
  const expected = normalizePrompt(text);
  if (!expected) throw new Error('Animation prompt is empty');
  const editor = page.locator('textarea:visible,[contenteditable="true"]:visible,[role="textbox"]:visible');
  if (await editor.count() !== 1) throw new Error('Could not identify one visible Flow prompt editor');
  await editor.fill(expected);
  for (let attempt = 0; attempt < 5; attempt++) {
    const actual = await editor.evaluate(el => {
      if ('value' in el) return el.value;
      return el.innerText ?? el.textContent ?? '';
    });
    if (normalizePrompt(actual) === expected) return;
    await new Promise(resolve => setTimeout(resolve, 150));
  }
  throw new Error('Flow prompt text did not match after entry; generation was not submitted');
}
