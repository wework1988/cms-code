<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\StoryPlannerTypes;

/**
 * Keeps story planner rows in sync with Story content nodes.
 */
class StoryPlannerNodeSync {

  /** Minimum titleMatchScore() to auto-link an existing node. */
  private const MATCH_THRESHOLD = 70;

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly Connection $database,
    private readonly StoryPlannerTypes $plannerTypes,
  ) {}

  /**
   * Creates a draft Story node for a planner row.
   */
  public function createNode(string $title, ?int $story_type_tid = NULL): NodeInterface {
    $values = [
      'type' => 'story',
      'title' => trim($title),
      'field_status' => ['value' => 'draft'],
    ];
    $tid = $story_type_tid ?: $this->plannerTypes->defaultTermId();
    if ($tid) {
      $values['field_story_type'] = ['target_id' => $tid];
    }
    /** @var \Drupal\node\NodeInterface $node */
    $node = $this->entityTypeManager->getStorage('node')->create($values);
    $node->save();
    return $node;
  }

  /**
   * Attempts to link planner rows that have no story_nid yet.
   *
   * @return array{linked: int, draft: int}
   */
  public function linkUnlinkedPlans(): array {
    $stats = ['linked' => 0, 'draft' => 0];
    $used_nids = $this->linkedNodeIds();

    $rows = $this->database->select('story_pipeline_tracker', 't')
      ->fields('t', ['id', 'title', 'story_type_tid'])
      ->isNull('story_nid')
      ->execute()
      ->fetchAll();

    foreach ($rows as $row) {
      $type_tid = !empty($row->story_type_tid) ? (int) $row->story_type_tid : NULL;
      $match = $this->findMatchingNodeId((string) $row->title, $type_tid, $used_nids);
      if ($match) {
        $this->setPlanNodeId((int) $row->id, $match);
        $used_nids[] = $match;
        $stats['linked']++;
      }
      else {
        $stats['draft']++;
      }
    }

    return $stats;
  }

  /**
   * Finds a story node whose title matches a planner title.
   *
   * @param list<int> $exclude_nids
   */
  public function findMatchingNodeId(string $planner_title, ?int $story_type_tid = NULL, array $exclude_nids = []): ?int {
    $needle = $this->normalizeTitle($planner_title);
    if ($needle === '') {
      return NULL;
    }

    $query = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'story');
    if ($exclude_nids !== []) {
      $query->condition('nid', $exclude_nids, 'NOT IN');
    }
    $nids = $query->execute();
    if ($nids === []) {
      return NULL;
    }

    $nodes = $this->entityTypeManager->getStorage('node')->loadMultiple($nids);
    $best_nid = NULL;
    $best_score = 0;
    foreach ($nodes as $node) {
      if (!$node instanceof NodeInterface) {
        continue;
      }
      $score = $this->titleMatchScore($needle, $this->normalizeTitle($node->getTitle()));
      if ($story_type_tid && $node->hasField('field_story_type')) {
        $node_tid = (int) ($node->get('field_story_type')->target_id ?? 0);
        if ($node_tid === $story_type_tid) {
          $score += 5;
        }
      }
      if ($score > $best_score) {
        $best_score = $score;
        $best_nid = (int) $node->id();
      }
    }

    return ($best_score >= self::MATCH_THRESHOLD) ? $best_nid : NULL;
  }

  /**
   * Persists story_nid on a planner row.
   */
  public function setPlanNodeId(int $tracker_id, int $story_nid): void {
    $this->database->update('story_pipeline_tracker')
      ->fields([
        'story_nid' => $story_nid,
        'changed' => \Drupal::time()->getRequestTime(),
      ])
      ->condition('id', $tracker_id)
      ->execute();
  }

  /**
   * @return list<int>
   */
  private function linkedNodeIds(): array {
    $nids = $this->database->select('story_pipeline_tracker', 't')
      ->fields('t', ['story_nid'])
      ->isNotNull('story_nid')
      ->execute()
      ->fetchCol();
    return array_values(array_map('intval', array_filter($nids)));
  }

  private function normalizeTitle(string $title): string {
    $title = html_entity_decode(strip_tags($title), ENT_QUOTES | ENT_HTML5, 'UTF-8');
    $title = mb_strtolower(trim($title));
    $title = preg_replace('/[^\p{L}\p{N}\s]+/u', ' ', $title) ?? $title;
    $title = preg_replace('/\s+/u', ' ', $title) ?? $title;
    return trim($title);
  }

  /**
   * Scores how well two normalized titles match (0–100).
   */
  private function titleMatchScore(string $a, string $b): int {
    if ($a === '' || $b === '') {
      return 0;
    }
    if ($a === $b) {
      return 100;
    }
    if (str_contains($b, $a) || str_contains($a, $b)) {
      $shorter = min(mb_strlen($a), mb_strlen($b));
      if ($shorter >= 4) {
        return 90;
      }
    }

    $words_a = array_values(array_filter(explode(' ', $a), static fn (string $w): bool => mb_strlen($w) >= 3));
    $words_b = array_values(array_filter(explode(' ', $b), static fn (string $w): bool => mb_strlen($w) >= 3));
    if ($words_a === [] || $words_b === []) {
      return 0;
    }

    $short = count($words_a) <= count($words_b) ? $words_a : $words_b;
    $long = array_flip(count($words_a) > count($words_b) ? $words_a : $words_b);
    $hits = 0;
    foreach ($short as $word) {
      if (isset($long[$word])) {
        $hits++;
      }
    }
    if ($hits === 0) {
      return 0;
    }

    return (int) round(75 * ($hits / count($short)));
  }

}
