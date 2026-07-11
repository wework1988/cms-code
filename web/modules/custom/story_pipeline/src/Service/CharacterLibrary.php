<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;
use Drupal\taxonomy\TermInterface;

/**
 * Character library storage, matching, import/export.
 */
class CharacterLibrary {

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly CharacterExtractor $extractor,
  ) {}

  /**
   * Load all published library entries.
   *
   * @return list<array{
   *   nid: int,
   *   title: string,
   *   char_id: string,
   *   context_label: string,
   *   aliases: list<string>,
   *   locked_anchor: string,
   *   negative_firewall: string,
   *   story_type_tid: ?int
   * }>
   */
  public function loadAll(?int $story_type_tid = NULL): array {
    $query = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'character_library')
      ->condition('status', 1)
      ->sort('title');

    if ($story_type_tid) {
      $query->condition('field_story_type', $story_type_tid);
    }

    $nids = $query->execute();
    if (!$nids) {
      return [];
    }

    $nodes = $this->entityTypeManager->getStorage('node')->loadMultiple($nids);
    $out = [];
    foreach ($nodes as $node) {
      if (!$node instanceof NodeInterface) {
        continue;
      }
      $record = $this->nodeToRecord($node);
      if ($record !== NULL) {
        $out[] = $record;
      }
    }
    return $out;
  }

  /**
   * Find a library entry matching a story character name.
   */
  public function matchByName(string $name, ?int $story_type_tid = NULL): ?array {
    $normalized_name = $this->normalizeForMatch($name);
    if ($normalized_name === '') {
      return NULL;
    }

    $best = NULL;
    $best_score = 0;

    foreach ($this->loadAll($story_type_tid) as $entry) {
      $score = $this->scoreMatch($normalized_name, $entry['aliases'], $entry['title'], $entry['char_id']);
      if ($score > $best_score) {
        $best_score = $score;
        $best = $entry;
      }
    }

    // Also search global entries (no story type filter) if scoped search missed.
    if ($best === NULL && $story_type_tid) {
      foreach ($this->loadAll(NULL) as $entry) {
        $score = $this->scoreMatch($normalized_name, $entry['aliases'], $entry['title'], $entry['char_id']);
        if ($score > $best_score) {
          $best_score = $score;
          $best = $entry;
        }
      }
    }

    return $best_score >= 70 ? $best : NULL;
  }

  /**
   * Extract characters from story and attach library matches.
   *
   * @return list<array<string, mixed>>
   */
  public function extractWithMatches(NodeInterface $story): array {
    $plan_text = $this->getStoryPlanText($story);
    $extracted = $this->extractor->extract($plan_text);
    return $this->attachLibraryMatches($story, $extracted);
  }

  /**
   * Plain text from uploaded raw story file (Drupal field or asset folder).
   */
  public function getRawStoryFileText(NodeInterface $story): string {
    return \Drupal::service('story_pipeline.asset_storage')->readRawStoryFileText($story);
  }

  /**
   * Whether the story has an uploaded raw file or on-disk raw-story copy.
   */
  public function hasRawStoryFile(NodeInterface $story): bool {
    return $this->getRawStoryFileText($story) !== '';
  }

  /**
   * Parse a pasted character block and attach library matches.
   *
   * Preserves existing tags when character names match the saved roster.
   *
   * @return list<array<string, mixed>>
   */
  public function parsePastedCharacters(string $raw, NodeInterface $story): array {
    $raw = trim($raw);
    if ($raw === '') {
      throw new \InvalidArgumentException('Paste your character list first.');
    }

    $parsed = $this->extractor->extract($raw);
    if ($parsed === []) {
      $wrapped = "TOP 10 CHARACTERS IN THE STORY\n==================================================\n\n" . $raw;
      $parsed = $this->extractor->extract($wrapped);
    }

    if ($parsed === []) {
      throw new \InvalidArgumentException(
        'Could not parse any characters. Use TOP 10 CHARACTERS with numbered entries (1. Name) and field labels (Story importance, Visual identity, etc.).'
      );
    }

    return $this->attachLibraryMatches($story, $parsed);
  }

  /**
   * Load characters for display: saved roster first, then plan extract, then pipeline.
   *
   * The roster holds the full extracted list (e.g. 10 rows) with tagging state.
   * field_characters_info only contains applied pipeline characters (e.g. 4).
   *
   * @return list<array<string, mixed>>
   */
  public function loadCharactersForStory(NodeInterface $story): array {
    $roster = $this->loadRoster($story);
    if ($roster !== []) {
      return $this->attachLibraryMatches($story, $roster);
    }

    $extracted = $this->extractWithMatches($story);
    if ($extracted !== []) {
      return $extracted;
    }

    return $this->charactersFromPipelineField($story);
  }

  /**
   * Summary counts for tagged and pipeline-applied characters.
   *
   * @return array{total: int, tagged: int, untagged: int, applied: int}
   */
  public function getCharacterStatus(NodeInterface $story): array {
    $characters = $this->loadCharactersForStory($story);
    $tagged = 0;
    foreach ($characters as $character) {
      if (!empty($character['library_nid'])) {
        $tagged++;
      }
    }

    $applied = count($this->parseCharacterTxt($story->get('field_characters_info')->value ?? ''));

    return [
      'total' => count($characters),
      'tagged' => $tagged,
      'untagged' => count($characters) - $tagged,
      'applied' => $applied,
    ];
  }

  /**
   * Build character rows from field_characters_info (after Apply to pipeline).
   *
   * @return list<array<string, mixed>>
   */
  public function charactersFromPipelineField(NodeInterface $story): array {
    if (!$story->hasField('field_characters_info') || $story->get('field_characters_info')->isEmpty()) {
      return [];
    }

    $parsed = $this->parseCharacterTxt($story->get('field_characters_info')->value ?? '');
    if ($parsed === []) {
      return [];
    }

    $rows = [];
    foreach ($parsed as $record) {
      $char_id = (string) ($record['char_id'] ?? '');
      $lib = $char_id !== '' ? $this->findLibraryRecordByCharId($char_id) : NULL;
      $name = (string) ($record['title'] ?? $char_id);

      $rows[] = [
        'name' => $name,
        'story_importance' => '',
        'visual_identity' => '',
        'clothing' => '',
        'emotional_arc' => '',
        'continuity_note' => '',
        'raw_block' => (string) ($record['locked_anchor'] ?? $name),
        'library_nid' => $lib['nid'] ?? NULL,
        'char_id' => $char_id,
        'match_status' => $lib ? 'linked' : 'applied',
        'locked_anchor' => (string) ($record['locked_anchor'] ?? ''),
        'negative_firewall' => (string) ($record['negative_firewall'] ?? ''),
        'context_label' => (string) ($record['context_label'] ?? ''),
        'aliases' => $record['aliases'] ?? $this->defaultAliases($name),
        'applied_to_pipeline' => TRUE,
        'library_label' => $lib ? $this->formatAutocompleteLabel($lib) : '',
      ];
    }

    return $rows;
  }

  /**
   * Find a published library entry by character ID.
   */
  public function findLibraryRecordByCharId(string $char_id): ?array {
    $char_id = strtoupper(trim($char_id));
    if ($char_id === '') {
      return NULL;
    }

    $nids = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'character_library')
      ->condition('status', 1)
      ->condition('field_char_id', $char_id)
      ->range(0, 1)
      ->execute();

    if (!$nids) {
      return NULL;
    }

    $node = $this->entityTypeManager->getStorage('node')->load((int) reset($nids));
    return $node instanceof NodeInterface ? $this->nodeToRecord($node) : NULL;
  }

  /**
   * Attach library matches to pre-parsed character rows (e.g. from DeepSeek).
   *
   * @param list<array<string, mixed>> $extracted
   *
   * @return list<array<string, mixed>>
   */
  public function attachLibraryMatches(NodeInterface $story, array $extracted): array {
    $story_type_tid = $this->storyTypeTid($story);

    $roster = $this->loadRoster($story);
    $roster_by_name = [];
    foreach ($roster as $item) {
      if (!empty($item['name'])) {
        $roster_by_name[strtolower($item['name'])] = $item;
      }
    }

    $out = [];
    foreach ($extracted as $character) {
      $name = $character['name'];
      $key = strtolower($name);
      $saved = $roster_by_name[$key] ?? [];

      $match = NULL;
      if (!empty($saved['library_nid'])) {
        $node = $this->entityTypeManager->getStorage('node')->load((int) $saved['library_nid']);
        if ($node instanceof NodeInterface) {
          $match = $this->nodeToRecord($node);
        }
      }
      if ($match === NULL) {
        $match = $this->matchByName($name, $story_type_tid);
      }

      $out[] = array_merge($character, [
        'library_nid' => $match['nid'] ?? ($saved['library_nid'] ?? NULL),
        'char_id' => $match['char_id'] ?? ($saved['char_id'] ?? ''),
        'match_status' => $match ? 'matched' : (!empty($saved['library_nid']) ? 'linked' : 'new'),
        'locked_anchor' => $match['locked_anchor'] ?? ($saved['locked_anchor'] ?? ''),
        'negative_firewall' => $match['negative_firewall'] ?? ($saved['negative_firewall'] ?? ''),
        'context_label' => $match['context_label'] ?? ($saved['context_label'] ?? ''),
        'aliases' => $match['aliases'] ?? ($saved['aliases'] ?? $this->defaultAliases($name)),
      ]);
    }

    return $out;
  }

  /**
   * Save a new character to the library.
   */
  public function saveCharacter(array $data): NodeInterface {
    $char_id = strtoupper(trim($data['char_id'] ?? ''));
    if ($char_id === '') {
      $char_id = $this->suggestCharId($data['name'] ?? 'CHAR');
    }
    if ($this->charIdExists($char_id)) {
      throw new \InvalidArgumentException("Character ID already exists: $char_id");
    }

    $aliases = $data['aliases'] ?? [];
    if (is_string($aliases)) {
      $aliases = preg_split('/\r?\n/', $aliases) ?: [];
    }
    $aliases = array_values(array_filter(array_map('trim', $aliases)));

    $values = [
      'type' => 'character_library',
      'title' => $data['name'] ?? $char_id,
      'status' => 1,
      'field_char_id' => ['value' => $char_id],
      'field_context_label' => ['value' => $data['context_label'] ?? ''],
      'field_match_aliases' => ['value' => implode("\n", $aliases)],
      'field_locked_anchor' => ['value' => trim($data['locked_anchor'] ?? '')],
      'field_negative_firewall' => ['value' => trim($data['negative_firewall'] ?? '')],
    ];

    if (!empty($data['story_type_tid'])) {
      $values['field_story_type'] = ['target_id' => (int) $data['story_type_tid']];
    }

    $node = $this->entityTypeManager->getStorage('node')->create($values);
    $node->save();
    return $node;
  }

  /**
   * Build character.txt content from library node IDs.
   */
  public function exportCharacterTxt(array $library_nids): string {
    $blocks = [];
    $storage = $this->entityTypeManager->getStorage('node');
    foreach ($library_nids as $nid) {
      $node = $storage->load((int) $nid);
      if ($node instanceof NodeInterface) {
        $record = $this->nodeToRecord($node);
        if ($record !== NULL) {
          $blocks[] = $this->exportBlock($record);
        }
      }
    }
    return implode("\n\n", $blocks);
  }

  /**
   * Export one character block in pipeline format.
   */
  public function exportBlock(array $record): string {
    $context = $record['context_label'] !== '' ? $record['context_label'] : 'general';
    $lines = [
      str_repeat('=', 80),
      $record['char_id'] . ' — Character (' . $context . ')',
      str_repeat('=', 80),
      '',
      'MATCH ALIASES — PIPELINE ONLY, NEVER COPY TO IMAGE PROMPT:',
    ];
    foreach ($record['aliases'] as $alias) {
      $lines[] = $alias;
    }
    $lines[] = '';
    $lines[] = 'LOCKED CHARACTER ANCHOR — COPY VERBATIM EVERY TIME:';
    $lines[] = $record['locked_anchor'];
    if ($record['negative_firewall'] !== '') {
      $lines[] = '';
      $lines[] = 'NEGATIVE IDENTITY FIREWALL:';
      $lines[] = $record['negative_firewall'];
    }
    return implode("\n", $lines);
  }

  /**
   * Parse character.txt into records.
   *
   * @return list<array<string, mixed>>
   */
  public function parseCharacterTxt(string $content): array {
    $content = trim($content);
    if ($content === '' || strtoupper($content) === 'NONE') {
      return [];
    }

    if (!preg_match_all(
      '/={10,}\s*\r?\n([A-Z0-9_]+)\s+—\s+Character\s*\(([^)]*)\)\s*\r?\n={10,}\s*\r?\n(.*?)(?=\r?\n={10,}\s*\r?\n[A-Z0-9_]+\s+—\s+Character|\z)/si',
      $content,
      $matches,
      PREG_SET_ORDER
    )) {
      return [];
    }

    $records = [];
    foreach ($matches as $match) {
      $char_id = trim($match[1]);
      $context = trim($match[2]);
      $body = trim($match[3]);

      $aliases = [];
      if (preg_match('/MATCH ALIASES[^\n]*\r?\n(.*?)(?:\r?\n\r?\n|\r?\nLOCKED CHARACTER ANCHOR)/si', $body, $alias_match)) {
        foreach (preg_split('/\r?\n/', trim($alias_match[1])) as $line) {
          $line = trim($line);
          if ($line !== '') {
            $aliases[] = $line;
          }
        }
      }

      $anchor = '';
      if (preg_match('/LOCKED CHARACTER ANCHOR[^\n]*\r?\n(.*?)(?:\r?\n\r?\n|\r?\nNEGATIVE IDENTITY FIREWALL|\z)/si', $body, $anchor_match)) {
        $anchor = trim($anchor_match[1]);
      }

      $firewall = '';
      if (preg_match('/NEGATIVE IDENTITY FIREWALL:\s*\r?\n(.*)$/si', $body, $fw_match)) {
        $firewall = trim($fw_match[1]);
      }

      $title = $aliases[0] ?? $char_id;
      $records[] = [
        'char_id' => $char_id,
        'context_label' => $context,
        'title' => $title,
        'aliases' => $aliases,
        'locked_anchor' => $anchor,
        'negative_firewall' => $firewall,
      ];
    }

    return $records;
  }

  /**
   * Update existing library node from parsed record.
   */
  public function updateCharacter(NodeInterface $node, array $record): NodeInterface {
    if ($node->bundle() !== 'character_library') {
      throw new \InvalidArgumentException('Not a character library node.');
    }
    $aliases = $record['aliases'] ?? [];
    $node->set('title', $record['title'] ?? $node->getTitle());
    $node->set('field_context_label', ['value' => $record['context_label'] ?? '']);
    $node->set('field_match_aliases', ['value' => implode("\n", $aliases)]);
    $node->set('field_locked_anchor', ['value' => $record['locked_anchor'] ?? '']);
    $node->set('field_negative_firewall', ['value' => $record['negative_firewall'] ?? '']);
    $node->save();
    return $node;
  }

  /**
   * Import character.txt file into library nodes.
   *
   * @return array{imported: int, updated: int, skipped: int, errors: list<string>}
   */
  public function importFromFile(string $path, ?int $story_type_tid = NULL, bool $skip_existing = TRUE): array {
    if (!is_readable($path)) {
      throw new \RuntimeException("Cannot read character file: $path");
    }

    $records = $this->parseCharacterTxt((string) file_get_contents($path));
    $report = ['imported' => 0, 'updated' => 0, 'skipped' => 0, 'errors' => []];

    foreach ($records as $record) {
      try {
        $existing_nid = $this->findNodeIdByCharId($record['char_id']);
        if ($existing_nid) {
          if ($skip_existing) {
            $report['skipped']++;
            continue;
          }
          $node = $this->entityTypeManager->getStorage('node')->load($existing_nid);
          if ($node instanceof NodeInterface) {
            $this->updateCharacter($node, $record);
            $report['updated']++;
          }
          continue;
        }

        $this->saveCharacter([
          'name' => $record['title'],
          'char_id' => $record['char_id'],
          'context_label' => $record['context_label'],
          'aliases' => $record['aliases'],
          'locked_anchor' => $record['locked_anchor'],
          'negative_firewall' => $record['negative_firewall'],
          'story_type_tid' => $story_type_tid,
        ]);
        $report['imported']++;
      }
      catch (\Throwable $e) {
        $report['errors'][] = $record['char_id'] . ': ' . $e->getMessage();
      }
    }

    return $report;
  }

  /**
   * Find library node ID by character ID.
   */
  public function findNodeIdByCharId(string $char_id): ?int {
    $ids = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'character_library')
      ->condition('field_char_id', strtoupper(trim($char_id)))
      ->range(0, 1)
      ->execute();
    if (!$ids) {
      return NULL;
    }
    return (int) reset($ids);
  }

  /**
   * Persist extracted roster on the story node.
   */
  public function saveRoster(NodeInterface $story, array $roster, bool $allow_empty = FALSE): void {
    if (!$story->hasField('field_character_roster')) {
      return;
    }
    if ($roster === [] && !$allow_empty && $this->loadRoster($story) !== []) {
      return;
    }
    $story->set('field_character_roster', ['value' => json_encode($roster, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)]);
    $story->save();
  }

  /**
   * Load saved roster JSON from story.
   */
  public function loadRoster(NodeInterface $story): array {
    if (!$story->hasField('field_character_roster')) {
      return [];
    }
    $raw = $story->get('field_character_roster')->value ?? '';
    if ($raw === '') {
      return [];
    }
    $decoded = json_decode($raw, TRUE);
    return is_array($decoded) ? $decoded : [];
  }

  /**
   * Apply library selections to story field_characters_info.
   */
  public function applyToStory(NodeInterface $story, array $library_nids): void {
    $txt = $this->exportCharacterTxt($library_nids);
    $story->set('field_characters_info', ['value' => $txt]);
    $story->save();
  }

  /**
   * Search library entries for autocomplete (title, char ID, aliases).
   *
   * @return list<array<string, mixed>>
   */
  public function searchForAutocomplete(string $query, ?int $story_type_tid = NULL): array {
    $query = trim($query);
    if ($query === '') {
      return [];
    }

    $needle = mb_strtolower($query);
    $results = [];

    foreach ($this->loadAll($story_type_tid) as $record) {
      if ($this->recordMatchesAutocompleteQuery($record, $needle)) {
        $results[] = $record;
      }
    }

    if ($results === [] && $story_type_tid) {
      foreach ($this->loadAll(NULL) as $record) {
        if ($this->recordMatchesAutocompleteQuery($record, $needle)) {
          $results[] = $record;
        }
      }
    }

    usort($results, static function (array $a, array $b): int {
      return strcasecmp($a['char_id'], $b['char_id']);
    });

    return array_slice($results, 0, 15);
  }

  /**
   * Label shown in autocomplete and tag field.
   */
  public function formatAutocompleteLabel(array $record): string {
    $aliases = array_slice($record['aliases'] ?? [], 0, 2);
    $alias_hint = $aliases !== [] ? ' · ' . implode(', ', $aliases) : '';
    return sprintf(
      '%s — %s%s [%d]',
      $record['char_id'],
      $record['title'],
      $alias_hint,
      $record['nid']
    );
  }

  /**
   * Parse node ID from autocomplete text value.
   */
  public function parseAutocompleteNid(string $value): ?int {
    $value = trim($value);
    if ($value === '') {
      return NULL;
    }
    if (preg_match('/\[(\d+)\]\s*$/', $value, $matches)) {
      return (int) $matches[1];
    }
    if (ctype_digit($value)) {
      return (int) $value;
    }
    return NULL;
  }

  /**
   * Append a story name alias to an existing library character.
   */
  public function appendAlias(int $library_nid, string $alias): NodeInterface {
    $alias = trim($alias);
    if ($alias === '') {
      throw new \InvalidArgumentException('Alias cannot be empty.');
    }

    $node = $this->entityTypeManager->getStorage('node')->load($library_nid);
    if (!$node instanceof NodeInterface || $node->bundle() !== 'character_library') {
      throw new \InvalidArgumentException('Library character not found.');
    }

    $record = $this->nodeToRecord($node);
    if ($record === NULL) {
      throw new \InvalidArgumentException('Invalid library character.');
    }

    $aliases = $record['aliases'];
    $normalized = array_map(static fn(string $a): string => mb_strtolower(trim($a)), $aliases);
    if (!in_array(mb_strtolower($alias), $normalized, TRUE)) {
      $aliases[] = $alias;
      $node->set('field_match_aliases', ['value' => implode("\n", $aliases)]);
      $node->save();
    }

    return $node;
  }

  /**
   * Link a story character row to a library entry; optionally store story name as alias.
   *
   * @return array<string, mixed>
   */
  public function applyLibraryLink(array $character, int $library_nid, bool $add_story_name_as_alias = TRUE): array {
    if ($add_story_name_as_alias && !empty($character['name'])) {
      $this->appendAlias($library_nid, (string) $character['name']);
    }

    $node = $this->entityTypeManager->getStorage('node')->load($library_nid);
    if (!$node instanceof NodeInterface) {
      throw new \InvalidArgumentException('Library character not found.');
    }

    $record = $this->nodeToRecord($node);
    if ($record === NULL) {
      throw new \InvalidArgumentException('Invalid library character.');
    }

    return array_merge($character, [
      'library_nid' => $record['nid'],
      'char_id' => $record['char_id'],
      'match_status' => 'linked',
      'locked_anchor' => $record['locked_anchor'],
      'negative_firewall' => $record['negative_firewall'],
      'context_label' => $record['context_label'],
      'aliases' => $record['aliases'],
      'library_label' => $this->formatAutocompleteLabel($record),
    ]);
  }

  /**
   * Check whether a library record matches an autocomplete query.
   */
  private function recordMatchesAutocompleteQuery(array $record, string $needle): bool {
    $haystacks = array_filter([
      mb_strtolower($record['char_id'] ?? ''),
      mb_strtolower($record['title'] ?? ''),
      mb_strtolower(implode(' ', $record['aliases'] ?? [])),
      mb_strtolower($this->formatAutocompleteLabel($record)),
    ]);

    foreach ($haystacks as $haystack) {
      if ($haystack !== '' && str_contains($haystack, $needle)) {
        return TRUE;
      }
    }

    return FALSE;
  }

  /**
   * Suggest next CHAR_* ID from a name.
   */
  public function suggestCharId(string $name): string {
    $slug = strtoupper(preg_replace('/[^A-Z0-9]+/', '_', $this->normalizeForMatch($name)) ?? 'CHAR');
    $slug = trim($slug, '_');
    if ($slug === '') {
      $slug = 'CHAR';
    }
    if (strlen($slug) > 20) {
      $slug = substr($slug, 0, 20);
    }

    $candidate = 'CHAR_' . $slug;
    if (!$this->charIdExists($candidate)) {
      return $candidate;
    }

    for ($i = 2; $i <= 99; $i++) {
      $candidate = 'CHAR_' . $slug . '_' . $i;
      if (!$this->charIdExists($candidate)) {
        return $candidate;
      }
    }

    return 'CHAR_' . bin2hex(random_bytes(3));
  }

  /**
   * Check if a character ID already exists.
   */
  public function charIdExists(string $char_id): bool {
    $ids = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'character_library')
      ->condition('field_char_id', strtoupper(trim($char_id)))
      ->range(0, 1)
      ->execute();
    return (bool) $ids;
  }

  /**
   * Convert library node to array record.
   */
  public function nodeToRecord(NodeInterface $node): ?array {
    if ($node->bundle() !== 'character_library') {
      return NULL;
    }

    $aliases_raw = $node->get('field_match_aliases')->value ?? '';
    $aliases = array_values(array_filter(array_map('trim', preg_split('/\r?\n/', $aliases_raw) ?: [])));

    $story_type_tid = NULL;
    $term = $node->get('field_story_type')->entity;
    if ($term instanceof TermInterface) {
      $story_type_tid = (int) $term->id();
    }

    return [
      'nid' => (int) $node->id(),
      'title' => $node->getTitle(),
      'char_id' => $node->get('field_char_id')->value ?? '',
      'context_label' => $node->get('field_context_label')->value ?? '',
      'aliases' => $aliases,
      'locked_anchor' => $node->get('field_locked_anchor')->value ?? '',
      'negative_firewall' => $node->get('field_negative_firewall')->value ?? '',
      'story_type_tid' => $story_type_tid,
    ];
  }

  /**
   * Build default alias list from a character name.
   *
   * @return list<string>
   */
  public function defaultAliases(string $name): array {
    $aliases = [trim($name)];
    $parts = preg_split('/\s*\(/', $name, 2);
    if ($parts && trim($parts[0]) !== $name) {
      $aliases[] = trim($parts[0]);
    }
    return array_values(array_unique(array_filter($aliases)));
  }

  /**
   * Build a draft locked anchor from extracted story fields.
   */
  public function draftAnchor(array $character): string {
    $bits = array_filter([
      $character['visual_identity'] ?? '',
      $character['clothing'] ?? '',
      $character['continuity_note'] ?? '',
    ]);
    if ($bits === []) {
      return '';
    }
    return implode(' ', $bits);
  }

  /**
   * Normalize text for alias matching.
   */
  public function normalizeForMatch(string $text): string {
    $text = mb_strtoupper(trim($text));
    $text = preg_replace('/\([^)]*\)/u', '', $text) ?? $text;
    $text = preg_replace('/\b(PM|NSA|GEN|GENERAL|COL|COLONEL|WING COMMANDER|CDS|MRS|MR|DR|SRI|SMT|SHRI)\b\.?/u', '', $text) ?? $text;
    $text = preg_replace('/[^A-Z0-9\s]/u', ' ', $text) ?? $text;
    return trim(preg_replace('/\s+/u', ' ', $text) ?? '');
  }

  /**
   * Score how well a name matches library aliases.
   */
  private function scoreMatch(string $normalized_name, array $aliases, string $title, string $char_id): int {
    $candidates = array_merge($aliases, [$title, $char_id]);
    $best = 0;

    foreach ($candidates as $alias) {
      $alias_norm = $this->normalizeForMatch($alias);
      if ($alias_norm === '') {
        continue;
      }

      if ($normalized_name === $alias_norm) {
        return 100;
      }

      // Ignore very short/generic aliases for fuzzy substring matching.
      $generic_aliases = ['VICTIMS', 'FAMILIES', 'PEOPLE', 'SOLDIERS', 'CIVILIANS', 'CHARACTER', 'OFFICER', 'PILOTS'];
      if (in_array($alias_norm, $generic_aliases, TRUE)) {
        continue;
      }

      if (strlen($alias_norm) >= 5) {
        if (preg_match('/\b' . preg_quote($alias_norm, '/') . '\b/u', $normalized_name)) {
          $best = max($best, min(92, 55 + (int) (strlen($alias_norm) / max(strlen($normalized_name), 1) * 35)));
        }
      }

      $name_tokens = array_filter(explode(' ', $normalized_name));
      $alias_tokens = array_filter(explode(' ', $alias_norm));
      if ($name_tokens && $alias_tokens) {
        $overlap = count(array_intersect($name_tokens, $alias_tokens));
        $stopwords = ['ARMY', 'GENERAL', 'INDIAN', 'PAKISTAN', 'SENIOR', 'CHIEF', 'COLLECTIVE', 'CHARACTER'];
        $meaningful = array_filter(
          array_intersect($name_tokens, $alias_tokens),
          static fn(string $token): bool => strlen($token) >= 5 && !in_array($token, $stopwords, TRUE)
        );
        if ($overlap >= 2) {
          $best = max($best, 80);
        }
        elseif (count($meaningful) >= 1) {
          $best = max($best, 65);
        }
      }
    }

    return $best;
  }

  /**
   * Raw planned story text used for character extraction only.
   */
  public function getStoryPlanText(NodeInterface $story): string {
    if (!$story->hasField('field_story_plan_raw')) {
      return '';
    }
    $raw = trim($story->get('field_story_plan_raw')->value ?? '');
    if ($raw === '') {
      return '';
    }
    return $this->extractor->normalizePlainText($raw);
  }

  /**
   * Story type term ID from story node.
   */
  public function storyTypeTid(NodeInterface $story): ?int {
    $term = $story->get('field_story_type')->entity;
    return $term instanceof TermInterface ? (int) $term->id() : NULL;
  }

}
