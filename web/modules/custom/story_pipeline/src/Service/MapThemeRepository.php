<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\Session\AccountInterface;
use Drupal\Core\State\StateInterface;
use Drupal\story_pipeline\MapThemes;

/**
 * Custom map-appearance templates. Built-in templates stay in the lab export.
 */
final class MapThemeRepository {

  public function __construct(
    private readonly Connection $database,
    private readonly StateInterface $state,
  ) {}

  public function defaultId(): string {
    $stored = (string) $this->state->get('story_pipeline.map_theme_default', MapThemes::DEFAULT_ID);
    return $stored !== '' ? $stored : MapThemes::DEFAULT_ID;
  }

  public function setDefault(string $theme_id): void {
    $this->state->set('story_pipeline.map_theme_default', $theme_id);
  }

  /**
   * @return list<array<string, mixed>>
   */
  public function customThemes(bool $include_archived = FALSE): array {
    if (!$this->database->schema()->tableExists('story_pipeline_map_theme')) {
      return [];
    }
    $query = $this->database->select('story_pipeline_map_theme', 't')
      ->fields('t')
      ->orderBy('name');
    if (!$include_archived) {
      $query->condition('status', 'active');
    }
    $rows = [];
    foreach ($query->execute() as $row) {
      $document = json_decode((string) $row->document, TRUE);
      $rows[] = [
        'theme_id' => $row->theme_id,
        'name' => $row->name,
        'description' => $row->description,
        'revision' => (int) $row->revision,
        'status' => $row->status,
        'document' => is_array($document) ? $document : [],
      ];
    }
    return $rows;
  }

  public function saveCustom(array $theme, AccountInterface $account, bool $update = FALSE): void {
    if (!$this->database->schema()->tableExists('story_pipeline_map_theme')) {
      throw new \RuntimeException('Map theme storage is not installed. Run the database update.');
    }
    $theme_id = (string) ($theme['id'] ?? '');
    if (!preg_match('/^custom_[a-z0-9_]+$/', $theme_id)) {
      throw new \InvalidArgumentException('Custom theme ids must start with custom_.');
    }
    $now = \Drupal::time()->getRequestTime();
    $existing = $this->database->select('story_pipeline_map_theme', 't')
      ->fields('t', ['id', 'revision', 'document'])
      ->condition('theme_id', $theme_id)
      ->execute()
      ->fetchAssoc();
    $revision = $existing ? ((int) $existing['revision'] + 1) : 1;
    $theme['revision'] = $revision;
    $fields = [
      'theme_id' => $theme_id,
      'name' => substr((string) ($theme['name'] ?? $theme_id), 0, 128),
      'description' => (string) ($theme['description'] ?? ''),
      'revision' => $revision,
      'status' => 'active',
      'document' => json_encode($theme, JSON_UNESCAPED_UNICODE),
      'uid' => (int) $account->id(),
      'updated' => $now,
    ];
    if ($existing && $update) {
      if ($this->database->schema()->tableExists('story_pipeline_map_theme_revision')) {
        $this->database->insert('story_pipeline_map_theme_revision')->fields([
          'theme_id' => $theme_id,
          'revision' => (int) $existing['revision'],
          'document' => (string) $existing['document'],
          'uid' => (int) $account->id(),
          'created' => $now,
        ])->execute();
      }
      $this->database->update('story_pipeline_map_theme')
        ->fields($fields)
        ->condition('id', $existing['id'])
        ->execute();
      return;
    }
    if ($existing) {
      throw new \InvalidArgumentException('That template id already exists.');
    }
    $fields['created'] = $now;
    $this->database->insert('story_pipeline_map_theme')->fields($fields)->execute();
  }

  public function setStatus(string $theme_id, string $status): void {
    if (!in_array($status, ['active', 'archived'], TRUE)) {
      throw new \InvalidArgumentException('Unknown template status.');
    }
    $this->database->update('story_pipeline_map_theme')
      ->fields(['status' => $status, 'updated' => \Drupal::time()->getRequestTime()])
      ->condition('theme_id', $theme_id)
      ->execute();
  }

}
