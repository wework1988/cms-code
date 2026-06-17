<?php

declare(strict_types=1);

namespace Drupal\story_pipeline;

use Drupal\Core\Url;

/**
 * Top navigation for Story planner only (not the pipeline runner).
 */
final class StoryPlannerNav {

  /**
   * Builds Planning / In progress / Completed tabs.
   */
  public static function buildTopNav(): array {
    $route = \Drupal::routeMatch()->getRouteName();

    $primary = [
      [
        'title' => (string) t('Planning'),
        'url' => Url::fromRoute('story_pipeline.tracker')->toString(),
        'active' => $route === 'story_pipeline.tracker',
      ],
      [
        'title' => (string) t('In progress'),
        'url' => Url::fromRoute('story_pipeline.tracker_in_progress')->toString(),
        'active' => $route === 'story_pipeline.tracker_in_progress',
      ],
      [
        'title' => (string) t('Completed'),
        'url' => Url::fromRoute('story_pipeline.tracker_completed')->toString(),
        'active' => $route === 'story_pipeline.tracker_completed',
      ],
    ];

    return [
      '#type' => 'container',
      '#attributes' => ['class' => ['story-planner-nav-wrap']],
      'nav' => [
        '#theme' => 'story_pipeline_workspace_nav',
        '#primary' => $primary,
        '#secondary' => [],
      ],
      '#attached' => [
        'library' => ['story_pipeline/story-planner-nav'],
      ],
      '#weight' => -1000,
    ];
  }

}
