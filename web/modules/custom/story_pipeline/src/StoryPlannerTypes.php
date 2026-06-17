<?php

declare(strict_types=1);

namespace Drupal\story_pipeline;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\taxonomy\TermInterface;

/**
 * Story Type taxonomy helpers for the planner (General, Crime, English, God Story).
 */
final class StoryPlannerTypes {

  /** @var list<string> */
  public const ORDER = ['general', 'crime', 'english', 'god_story'];

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
  ) {}

  /**
   * Story type terms in display order (general → crime → english → god_story).
   *
   * @return array<string, \Drupal\taxonomy\TermInterface>
   */
  public function loadOrderedTerms(): array {
    $storage = $this->entityTypeManager->getStorage('taxonomy_term');
    $ordered = [];
    foreach (self::ORDER as $machine) {
      $label = $this->machineToLabel($machine);
      $terms = $storage->loadByProperties(['vid' => 'story_type', 'name' => $label]);
      $term = $terms ? reset($terms) : NULL;
      if ($term instanceof TermInterface) {
        $ordered[$machine] = $term;
      }
    }
    return $ordered;
  }

  /**
   * Select options: term ID => label.
   *
   * @return array<int|string, string>
   */
  public function selectOptions(): array {
    $options = [];
    foreach ($this->loadOrderedTerms() as $term) {
      $options[(int) $term->id()] = $term->label();
    }
    return $options;
  }

  /**
   * Default story type term ID (General).
   */
  public function defaultTermId(): ?int {
    $terms = $this->loadOrderedTerms();
    $general = $terms['general'] ?? reset($terms);
    return $general instanceof TermInterface ? (int) $general->id() : NULL;
  }

  /**
   * Groups tracker rows by story type machine name.
   *
   * @param object[] $stories
   *
   * @return array<string, object[]>
   */
  public function groupStories(array $stories): array {
    $terms = $this->loadOrderedTerms();
    $tid_to_machine = [];
    foreach ($terms as $machine => $term) {
      $tid_to_machine[(int) $term->id()] = $machine;
    }

    $grouped = array_fill_keys(self::ORDER, []);
    foreach ($stories as $story) {
      $tid = isset($story->story_type_tid) ? (int) $story->story_type_tid : 0;
      $machine = $tid_to_machine[$tid] ?? 'general';
      $grouped[$machine][] = $story;
    }

    foreach ($grouped as $machine => $rows) {
      usort($rows, static fn (object $a, object $b): int => ((int) ($a->weight ?? 0)) <=> ((int) ($b->weight ?? 0)));
      $grouped[$machine] = $rows;
    }

    return $grouped;
  }

  /**
   * Human label for a stored term ID.
   */
  public function labelForTid(?int $tid): string {
    if (!$tid) {
      return (string) t('General');
    }
    $term = $this->entityTypeManager->getStorage('taxonomy_term')->load($tid);
    return $term instanceof TermInterface ? $term->label() : (string) t('General');
  }

  /**
   * Machine name for a stored term ID.
   */
  public function machineForTid(?int $tid): string {
    if (!$tid) {
      return 'general';
    }
    foreach ($this->loadOrderedTerms() as $machine => $term) {
      if ((int) $term->id() === $tid) {
        return $machine;
      }
    }
    return 'general';
  }

  private function machineToLabel(string $machine): string {
    return match ($machine) {
      'crime' => 'Crime',
      'english' => 'English',
      'god_story' => 'God Story',
      default => 'General',
    };
  }

}
