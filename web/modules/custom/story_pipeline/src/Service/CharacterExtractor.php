<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

/**
 * Extracts structured character roster from a raw story file.
 */
class CharacterExtractor {

  /**
   * Extract characters from full story text.
   *
   * @return list<array{
   *   name: string,
   *   story_importance: string,
   *   visual_identity: string,
   *   clothing: string,
   *   emotional_arc: string,
   *   continuity_note: string,
   *   raw_block: string
   * }>
   */
  public function extract(string $full_story): array {
    $text = $this->normalizePlainText($full_story);
    if ($text === '') {
      return [];
    }

    $section = $this->extractCharactersSection($text);
    if ($section === '') {
      return $this->fallbackNameScan($text);
    }

    return $this->parseCharacterBlocks($section);
  }

  /**
   * Convert Drupal rich-text / HTML story plan into plain text for parsing.
   */
  public function normalizePlainText(string $text): string {
    $text = html_entity_decode($text, ENT_QUOTES | ENT_HTML5, 'UTF-8');
    $text = str_replace(["\xc2\xa0", '&nbsp;'], ' ', $text);
    $text = preg_replace('/<br\s*\/?>/i', "\n", $text) ?? $text;
    $text = preg_replace('/<\/p>\s*<p[^>]*>/i', "\n\n", $text) ?? $text;
    $text = preg_replace('/<\/?p[^>]*>/i', "\n", $text) ?? $text;
    $text = strip_tags($text);
    $text = preg_replace("/\r\n|\r/", "\n", $text) ?? $text;
    $text = preg_replace("/\n{3,}/", "\n\n", $text) ?? $text;
    return trim($text);
  }

  /**
   * Pull the TOP N CHARACTERS block from the story.
   */
  private function extractCharactersSection(string $text): string {
    if (preg_match(
      '/TOP\s+\d+\s+CHARACTERS[^\n]*\r?\n=+\s*\r?\n(.*?)(?:\r?\n=+\s*\r?\nFULL SCRIPT|\r?\n=+\s*\r?\n(?:FULL\s+)?SCRIPT|\z)/si',
      $text,
      $matches
    )) {
      return trim($matches[1]);
    }

    if (preg_match(
      '/CHARACTERS\s+IN\s+THE\s+STORY[^\n]*\r?\n=+\s*\r?\n(.*?)(?:\r?\n=+\s*\r?\nFULL|\z)/si',
      $text,
      $matches
    )) {
      return trim($matches[1]);
    }

    // Some planned stories omit separator lines after the TOP CHARACTERS header.
    if (preg_match(
      '/TOP\s+\d+\s+CHARACTERS[^\n]*\r?\n+(.*?)(?:\r?\n=+\s*\r?\nFULL SCRIPT|\r?\n=+\s*\r?\n(?:FULL\s+)?SCRIPT|\r?\nFULL SCRIPT|\z)/si',
      $text,
      $matches
    )) {
      return $this->stripCharactersSectionWrapper(trim($matches[1]));
    }

    return '';
  }

  /**
   * Remove header/footer wrapper lines from a captured characters section.
   */
  private function stripCharactersSectionWrapper(string $section): string {
    $section = preg_replace('/^=+\s*\r?\n*/', '', $section) ?? $section;
    $section = preg_replace('/\r?\n=+\s*$/', '', $section) ?? $section;
    $section = preg_replace('/^TOP\s+\d+\s+CHARACTERS[^\n]*\r?\n*/i', '', $section) ?? $section;
    return trim($section);
  }

  /**
   * Parse character entries from the characters section.
   *
   * @return list<array<string, string>>
   */
  private function parseCharacterBlocks(string $section): array {
    if (preg_match('/^\d+\.\s+/m', $section)) {
      return $this->parseNumberedCharacterBlocks($section);
    }

    return $this->parseUnnumberedCharacterBlocks($section);
  }

  /**
   * Parse numbered "1. Name" character entries.
   *
   * @return list<array<string, string>>
   */
  private function parseNumberedCharacterBlocks(string $section): array {
    $parts = preg_split('/^\d+\.\s+/m', $section, -1, PREG_SPLIT_NO_EMPTY);
    if ($parts === FALSE) {
      return [];
    }

    $characters = [];
    foreach ($parts as $part) {
      $parsed = $this->parseSingleCharacterPart(trim($part));
      if ($parsed !== NULL) {
        $characters[] = $parsed;
      }
    }

    return $characters;
  }

  /**
   * Parse unnumbered "Name / Role" character entries.
   *
   * @return list<array<string, string>>
   */
  private function parseUnnumberedCharacterBlocks(string $section): array {
    // Some exports merge the end of one continuity note with the next name.
    $section = preg_replace('/\.([A-Z])/', ".\n$1", $section) ?? $section;

    $lines = preg_split('/\r?\n/', $section) ?: [];
    $blocks = [];
    $current = [];

    foreach ($lines as $line) {
      $trimmed = trim($line);
      if ($trimmed === '' || preg_match('/^=+$/', $trimmed)) {
        continue;
      }

      if ($this->isCharacterNameLine($trimmed)) {
        if ($current !== []) {
          $blocks[] = implode("\n", $current);
        }
        $current = [$trimmed];
        continue;
      }

      $current[] = $trimmed;
    }

    if ($current !== []) {
      $blocks[] = implode("\n", $current);
    }

    $characters = [];
    foreach ($blocks as $block) {
      $parsed = $this->parseSingleCharacterPart($block);
      if ($parsed !== NULL) {
        $characters[] = $parsed;
      }
    }

    return $characters;
  }

  /**
   * Parse one character block (first line = name, rest = labeled fields).
   *
   * @return array<string, string>|null
   */
  private function parseSingleCharacterPart(string $part): ?array {
    $part = trim($part);
    if ($part === '') {
      return NULL;
    }

    $lines = preg_split('/\r?\n/', $part);
    if ($lines === FALSE || $lines === []) {
      return NULL;
    }

    $name = trim((string) array_shift($lines));
    if ($name === '') {
      return NULL;
    }

    $fields = [
      'name' => $name,
      'story_importance' => '',
      'visual_identity' => '',
      'clothing' => '',
      'emotional_arc' => '',
      'continuity_note' => '',
      'raw_block' => $part,
    ];

    foreach ($lines as $line) {
      $line = trim($line);
      if (preg_match('/^([^:]+):\s*(.*)$/', $line, $field_match)) {
        $key = strtolower(trim($field_match[1]));
        $value = trim($field_match[2]);
        $mapped = match (TRUE) {
          str_contains($key, 'story importance') => 'story_importance',
          str_contains($key, 'visual identity') => 'visual_identity',
          str_contains($key, 'clothing') => 'clothing',
          str_contains($key, 'emotional arc') => 'emotional_arc',
          str_contains($key, 'continuity') => 'continuity_note',
          default => NULL,
        };
        if ($mapped !== NULL) {
          $fields[$mapped] = $fields[$mapped] === '' ? $value : $fields[$mapped] . ' ' . $value;
        }
      }
    }

    return $fields;
  }

  /**
   * Whether a line starts a new character (as opposed to a labeled field).
   */
  private function isCharacterNameLine(string $line): bool {
    return !preg_match('/^(Story importance|Visual identity|Clothing\s*\/?\s*era look|Emotional arc|Continuity note)\s*:/i', $line);
  }

  /**
   * Fallback when no TOP CHARACTERS section exists.
   *
   * @return list<array<string, string>>
   */
  private function fallbackNameScan(string $text): array {
    $characters = [];
    if (preg_match_all('/^\d+\.\s+(.+)$/m', $text, $matches)) {
      foreach ($matches[1] as $name) {
        $name = trim($name);
        if ($name !== '') {
          $characters[] = [
            'name' => $name,
            'story_importance' => '',
            'visual_identity' => '',
            'clothing' => '',
            'emotional_arc' => '',
            'continuity_note' => '',
            'raw_block' => $name,
          ];
        }
      }
    }
    return $characters;
  }

}
