<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\Core\Database\Connection;

/**
 * CRUD for planned stories (custom table, not content types).
 */
class StoryTracker {

  public const STATUS_PLANNING = 'planning';

  public const STATUS_IN_PROGRESS = 'in_progress';

  public const STATUS_COMPLETED = 'completed';

  public function __construct(
    private readonly Connection $database,
  ) {}

  /**
   * Loads stories for a planner section.
   *
   * @return object[]
   */
  public function loadByStatus(string $status): array {
    $query = $this->database->select('story_pipeline_tracker', 't')
      ->fields('t')
      ->condition('status', $status);

    if ($status === self::STATUS_PLANNING) {
      $query->orderBy('story_type_tid', 'ASC');
      $query->orderBy('weight', 'ASC');
    }
    else {
      $query->orderBy('story_type_tid', 'ASC');
      $query->orderBy('expected_publish', 'ASC');
      $query->orderBy('changed', 'DESC');
    }

    return $query->execute()->fetchAll();
  }

  /**
   * Loads a single tracker row.
   */
  public function load(int $id): ?object {
    $row = $this->database->select('story_pipeline_tracker', 't')
      ->fields('t')
      ->condition('id', $id)
      ->execute()
      ->fetchObject();
    return $row ?: NULL;
  }

  /**
   * Adds multiple stories to Planning in priority order.
   *
   * @param list<array{title: string, expected_publish?: ?string, story_type_tid?: ?int}> $stories
   *   Ordered list — first item = highest priority (weight 0).
   *
   * @return int
   *   Number of stories inserted.
   */
  public function bulkAddPlanning(array $stories, ?int $default_story_type_tid = NULL): int {
    $count = 0;
    foreach ($stories as $weight => $story) {
      $title = trim($story['title'] ?? '');
      if ($title === '') {
        continue;
      }
      $now = \Drupal::time()->getRequestTime();
      $this->database->insert('story_pipeline_tracker')
        ->fields([
          'title' => $title,
          'story_written' => 0,
          'image_prompt_generated' => 0,
          'image_generated' => 0,
          'digen_video_generated' => 0,
          'completed_assigned' => 0,
          'status' => self::STATUS_PLANNING,
          'weight' => (int) $weight,
          'story_type_tid' => !empty($story['story_type_tid']) ? (int) $story['story_type_tid'] : $default_story_type_tid,
          'expected_publish' => !empty($story['expected_publish']) ? $story['expected_publish'] : NULL,
          'created' => $now,
          'changed' => $now,
        ])
        ->execute();
      $count++;
    }
    return $count;
  }

  /**
   * Adds a new story to the Planning queue.
   */
  public function add(string $title, ?string $expected_publish = NULL, ?int $story_type_tid = NULL, ?int $story_nid = NULL): int {
    $now = \Drupal::time()->getRequestTime();
    $max = $this->database->query(
      'SELECT COALESCE(MAX(weight), -1) FROM {story_pipeline_tracker} WHERE status = :status AND story_type_tid <=> :tid',
      [
        ':status' => self::STATUS_PLANNING,
        ':tid' => $story_type_tid,
      ]
    )->fetchField();

    return (int) $this->database->insert('story_pipeline_tracker')
      ->fields([
        'title' => trim($title),
        'story_written' => 0,
        'image_prompt_generated' => 0,
        'image_generated' => 0,
        'digen_video_generated' => 0,
        'completed_assigned' => 0,
        'status' => self::STATUS_PLANNING,
        'weight' => (int) $max + 1,
        'story_type_tid' => $story_type_tid,
        'story_nid' => $story_nid,
        'expected_publish' => $expected_publish ?: NULL,
        'created' => $now,
        'changed' => $now,
      ])
      ->execute();
  }

  /**
   * Moves a story from Planning to In progress.
   */
  public function start(int $id): void {
    $this->database->update('story_pipeline_tracker')
      ->fields([
        'status' => self::STATUS_IN_PROGRESS,
        'changed' => \Drupal::time()->getRequestTime(),
      ])
      ->condition('id', $id)
      ->condition('status', self::STATUS_PLANNING)
      ->execute();
  }

  /**
   * Saves priority order for planning stories.
   *
   * @param array<int, int|float|string> $weights
   *   Story ID => weight value from the form.
   */
  public function savePlanningOrder(array $weights): void {
    $now = \Drupal::time()->getRequestTime();
    foreach ($weights as $id => $weight) {
      if (!is_numeric($id)) {
        continue;
      }
      $this->database->update('story_pipeline_tracker')
        ->fields([
          'weight' => (int) $weight,
          'changed' => $now,
        ])
        ->condition('id', (int) $id)
        ->condition('status', self::STATUS_PLANNING)
        ->execute();
    }
  }

  /**
   * Updates checklist fields for in-progress / completed stories.
   *
   * @param array<string, mixed> $values
   */
  public function update(int $id, array $values): void {
    $completed = !empty($values['completed_assigned']);
    $fields = [
      'story_written' => !empty($values['story_written']) ? 1 : 0,
      'image_prompt_generated' => !empty($values['image_prompt_generated']) ? 1 : 0,
      'image_generated' => !empty($values['image_generated']) ? 1 : 0,
      'digen_video_generated' => !empty($values['digen_video_generated']) ? 1 : 0,
      'completed_assigned' => $completed ? 1 : 0,
      'expected_publish' => !empty($values['expected_publish']) ? $values['expected_publish'] : NULL,
      'changed' => \Drupal::time()->getRequestTime(),
    ];
    if (isset($values['story_type_tid']) && $values['story_type_tid'] !== '') {
      $fields['story_type_tid'] = (int) $values['story_type_tid'];
    }
    if (array_key_exists('story_nid', $values)) {
      $fields['story_nid'] = $values['story_nid'];
    }
    if ($completed) {
      $fields['status'] = self::STATUS_COMPLETED;
    }
    $this->database->update('story_pipeline_tracker')
      ->fields($fields)
      ->condition('id', $id)
      ->execute();
  }

  /**
   * Updates planning metadata (type, publish date, linked story node).
   */
  public function updatePlanningMeta(int $id, ?string $expected_publish, ?int $story_type_tid = NULL, ?int $story_nid = NULL, bool $story_nid_provided = FALSE): void {
    $fields = [
      'expected_publish' => $expected_publish ?: NULL,
      'changed' => \Drupal::time()->getRequestTime(),
    ];
    if ($story_type_tid !== NULL) {
      $fields['story_type_tid'] = $story_type_tid;
    }
    if ($story_nid_provided) {
      $fields['story_nid'] = $story_nid;
    }
    $this->database->update('story_pipeline_tracker')
      ->fields($fields)
      ->condition('id', $id)
      ->condition('status', self::STATUS_PLANNING)
      ->execute();
  }

  /**
   * Deletes a planned story.
   */
  public function delete(int $id): void {
    $this->database->delete('story_pipeline_tracker')
      ->condition('id', $id)
      ->execute();
  }

  /**
   * Deletes every row in the planner table.
   */
  public function deleteAll(): void {
    $this->database->delete('story_pipeline_tracker')->execute();
  }

  /**
   * Normalize entity_autocomplete value to a story node ID or NULL.
   */
  public function normalizeStoryNid(mixed $value): ?int {
    if ($value === NULL || $value === '' || $value === []) {
      return NULL;
    }
    if (is_array($value)) {
      $value = reset($value);
    }
    if (is_object($value) && isset($value->target_id)) {
      $value = $value->target_id;
    }
    if (!is_numeric($value)) {
      return NULL;
    }
    $nid = (int) $value;
    if ($nid <= 0) {
      return NULL;
    }
    $node = \Drupal::entityTypeManager()->getStorage('node')->load($nid);
    return ($node && $node->bundle() === 'story') ? $nid : NULL;
  }

}
