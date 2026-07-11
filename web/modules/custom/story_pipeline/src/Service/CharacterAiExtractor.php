<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\Core\Config\ConfigFactoryInterface;
use Drupal\Core\Logger\LoggerChannelFactoryInterface;
use Drupal\node\NodeInterface;
use GuzzleHttp\ClientInterface;
use GuzzleHttp\Exception\GuzzleException;

/**
 * Extracts story characters via DeepSeek API into pipeline-ready format.
 */
class CharacterAiExtractor {

  private const API_URL = 'https://api.deepseek.com/chat/completions';

  private const DEFAULT_MODEL = 'deepseek-chat';

  private const MAX_SOURCE_CHARS = 90000;

  public function __construct(
    private readonly ClientInterface $httpClient,
    private readonly ConfigFactoryInterface $configFactory,
    private readonly LoggerChannelFactoryInterface $loggerFactory,
    private readonly CharacterExtractor $extractor,
    private readonly StoryPipelineManager $pipelineManager,
  ) {}

  /**
   * Whether DeepSeek API key is configured.
   */
  public function isAvailable(): bool {
    $keys = $this->pipelineManager->getApiKeysForStoryType('crime');
    return ($keys['deepseek_api_key'] ?? '') !== '';
  }

  /**
   * Extract characters from story using DeepSeek, return pipeline character rows.
   *
   * @return list<array<string, mixed>>
   *
   * @throws \RuntimeException
   */
  public function extractCharacters(NodeInterface $story): array {
    $source = $this->getSourceText($story);
    if ($source === '') {
      throw new \RuntimeException('No story text found. Paste your plan or full story on the story edit form first.');
    }

    $keys = $this->pipelineManager->getApiKeysForStoryType('crime');
    $api_key = $keys['deepseek_api_key'] ?? '';
    if ($api_key === '') {
      throw new \RuntimeException('DeepSeek API key is not configured. Set it at Configuration → Story Pipeline settings.');
    }

    $truncated = FALSE;
    if (mb_strlen($source) > self::MAX_SOURCE_CHARS) {
      $source = mb_substr($source, 0, self::MAX_SOURCE_CHARS);
      $truncated = TRUE;
    }

    $system = <<<'PROMPT'
You are a story production assistant. Extract the main characters from the story plan or script.

Return ONLY valid JSON (no markdown fences, no commentary) with this exact shape:
{"characters":[{"name":"Full Name / Role","story_importance":"...","visual_identity":"...","clothing":"...","emotional_arc":"...","continuity_note":"..."}]}

Rules:
- Include up to 10 characters most important for video/image production.
- "name" must include role when known (example: "Ajit Doval / National Security Advisor").
- Use the same language as the source (Hindi, English, or mixed).
- "clothing" means clothing / era look.
- Base every character on the provided text; do not invent people not implied by the story.
- Use empty strings for unknown fields.
PROMPT;

    $user = "Extract characters from this story:\n\n" . $source;
    if ($truncated) {
      $user .= "\n\n[Note: source text was truncated for length.]";
    }

    $raw = $this->callDeepSeek($api_key, $system, $user, $this->getModel($story));
    $parsed = $this->parseCharactersJson($raw);

    if ($parsed === []) {
      throw new \RuntimeException('DeepSeek returned no characters. Try again or check the story text.');
    }

    return $this->normalizeCharacterRows($parsed);
  }

  /**
   * Build canonical TOP N CHARACTERS text block from character rows.
   *
   * @param list<array<string, mixed>> $characters
   */
  public function formatCharactersBlock(array $characters): string {
    $count = max(1, count($characters));
    $lines = [
      'TOP ' . $count . ' CHARACTERS IN THE STORY',
      str_repeat('=', 50),
      '',
    ];

    foreach ($characters as $index => $character) {
      $num = $index + 1;
      $lines[] = $num . '. ' . trim((string) ($character['name'] ?? 'Character ' . $num));
      $this->appendFieldLine($lines, 'Story importance', (string) ($character['story_importance'] ?? ''));
      $this->appendFieldLine($lines, 'Visual identity', (string) ($character['visual_identity'] ?? ''));
      $this->appendFieldLine($lines, 'Clothing / era look', (string) ($character['clothing'] ?? ''));
      $this->appendFieldLine($lines, 'Emotional arc', (string) ($character['emotional_arc'] ?? ''));
      $this->appendFieldLine($lines, 'Continuity note', (string) ($character['continuity_note'] ?? ''));
      $lines[] = '';
    }

    return rtrim(implode("\n", $lines));
  }

  /**
   * Insert or replace the TOP CHARACTERS block in field_story_plan_raw.
   *
   * @param list<array<string, mixed>> $characters
   */
  public function mergeCharactersIntoPlan(NodeInterface $story, array $characters): void {
    if (!$story->hasField('field_story_plan_raw')) {
      return;
    }

    $block = $this->formatCharactersBlock($characters);
    $existing = '';
    if ($story->hasField('field_story_plan_raw') && !$story->get('field_story_plan_raw')->isEmpty()) {
      $existing = $this->extractor->normalizePlainText((string) $story->get('field_story_plan_raw')->value);
    }

    if ($existing === '') {
      $updated = $block;
    }
    elseif (preg_match('/TOP\s+\d+\s+CHARACTERS.*?(\n=+\s*\nFULL SCRIPT|\nFULL SCRIPT)/si', $existing)) {
      $updated = preg_replace(
        '/TOP\s+\d+\s+CHARACTERS.*?(\n=+\s*\nFULL SCRIPT|\nFULL SCRIPT)/si',
        $block . '$1',
        $existing,
        1
      );
    }
    elseif (preg_match('/(\n=+\s*\nFULL SCRIPT|\nFULL SCRIPT)/i', $existing, $matches, PREG_OFFSET_CAPTURE)) {
      $pos = $matches[0][1];
      $updated = rtrim(substr($existing, 0, $pos)) . "\n\n" . $block . "\n\n" . ltrim(substr($existing, $pos));
    }
    else {
      $updated = $block . "\n\n" . ltrim($existing);
    }

    $story->set('field_story_plan_raw', ['value' => $updated]);
    $story->save();
  }

  /**
   * Plain text from story plan, falling back to full story.
   */
  public function getSourceText(NodeInterface $story): string {
    $parts = [];
    if ($story->hasField('field_story_plan_raw') && !$story->get('field_story_plan_raw')->isEmpty()) {
      $parts[] = (string) $story->get('field_story_plan_raw')->value;
    }
    if ($story->hasField('field_full_story') && !$story->get('field_full_story')->isEmpty()) {
      $parts[] = (string) $story->get('field_full_story')->value;
    }

    $combined = trim(implode("\n\n", array_filter(array_map('trim', $parts))));
    if ($combined === '') {
      return '';
    }

    return $this->extractor->normalizePlainText($combined);
  }

  /**
   * Call DeepSeek chat completions API.
   */
  private function callDeepSeek(string $api_key, string $system, string $user, string $model): string {
    $payload = [
      'model' => $model,
      'messages' => [
        ['role' => 'system', 'content' => $system],
        ['role' => 'user', 'content' => $user],
      ],
      'max_tokens' => 8192,
      'temperature' => 0.2,
    ];

    try {
      $response = $this->httpClient->request('POST', self::API_URL, [
        'headers' => [
          'Authorization' => 'Bearer ' . $api_key,
          'Content-Type' => 'application/json',
        ],
        'json' => $payload,
        'timeout' => 180,
      ]);
    }
    catch (GuzzleException $e) {
      $this->loggerFactory->get('story_pipeline')->error('DeepSeek character extract failed: @msg', [
        '@msg' => $e->getMessage(),
      ]);
      throw new \RuntimeException('DeepSeek API request failed: ' . $e->getMessage(), 0, $e);
    }

    $body = (string) $response->getBody();
    $data = json_decode($body, TRUE);
    if (!is_array($data)) {
      throw new \RuntimeException('DeepSeek returned invalid JSON.');
    }

    $content = $data['choices'][0]['message']['content'] ?? '';
    if (!is_string($content) || trim($content) === '') {
      throw new \RuntimeException('DeepSeek returned an empty response.');
    }

    return trim($content);
  }

  /**
   * Parse character list from model JSON output.
   *
   * @return list<array<string, string>>
   */
  private function parseCharactersJson(string $raw): array {
    $raw = trim($raw);
    if (preg_match('/```(?:json)?\s*(.*?)```/si', $raw, $matches)) {
      $raw = trim($matches[1]);
    }

    $data = json_decode($raw, TRUE);
    if (!is_array($data)) {
      $start = strpos($raw, '{');
      $end = strrpos($raw, '}');
      if ($start !== FALSE && $end !== FALSE && $end > $start) {
        $data = json_decode(substr($raw, $start, $end - $start + 1), TRUE);
      }
    }

    if (!is_array($data) || !isset($data['characters']) || !is_array($data['characters'])) {
      throw new \RuntimeException('DeepSeek response was not valid character JSON.');
    }

    $out = [];
    foreach ($data['characters'] as $row) {
      if (!is_array($row)) {
        continue;
      }
      $name = trim((string) ($row['name'] ?? ''));
      if ($name === '') {
        continue;
      }
      $out[] = [
        'name' => $name,
        'story_importance' => trim((string) ($row['story_importance'] ?? '')),
        'visual_identity' => trim((string) ($row['visual_identity'] ?? '')),
        'clothing' => trim((string) ($row['clothing'] ?? $row['clothing_era_look'] ?? '')),
        'emotional_arc' => trim((string) ($row['emotional_arc'] ?? '')),
        'continuity_note' => trim((string) ($row['continuity_note'] ?? '')),
      ];
    }

    return $out;
  }

  /**
   * Map parsed rows to CharacterExtractor shape.
   *
   * @param list<array<string, string>> $parsed
   *
   * @return list<array<string, string>>
   */
  private function normalizeCharacterRows(array $parsed): array {
    $characters = [];
    foreach ($parsed as $row) {
      $block = $this->formatCharactersBlock([$row]);
      $characters[] = [
        'name' => $row['name'],
        'story_importance' => $row['story_importance'],
        'visual_identity' => $row['visual_identity'],
        'clothing' => $row['clothing'],
        'emotional_arc' => $row['emotional_arc'],
        'continuity_note' => $row['continuity_note'],
        'raw_block' => trim($block),
      ];
    }
    return $characters;
  }

  /**
   * Resolve DeepSeek model from story type settings or config default.
   */
  private function getModel(NodeInterface $story): string {
    $term = $story->get('field_story_type')->entity;
    if ($term && $term->hasField('field_pipeline_settings') && !$term->get('field_pipeline_settings')->isEmpty()) {
      $settings = json_decode((string) $term->get('field_pipeline_settings')->value, TRUE);
      if (is_array($settings) && !empty($settings['model'])) {
        return (string) $settings['model'];
      }
    }

    $config = $this->configFactory->get('story_pipeline.settings');
    return (string) ($config->get('character_extract_model') ?: self::DEFAULT_MODEL);
  }

  /**
   * Append one labeled field line when value is non-empty.
   *
   * @param list<string> $lines
   */
  private function appendFieldLine(array &$lines, string $label, string $value): void {
    $value = trim($value);
    if ($value === '') {
      return;
    }
    $lines[] = '  ' . $label . ': ' . $value;
  }

}
