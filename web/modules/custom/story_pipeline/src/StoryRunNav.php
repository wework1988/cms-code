<?php

declare(strict_types=1);

namespace Drupal\story_pipeline;

use Drupal\Core\Url;

/**
 * Top navigation for Run story jobs (active, completed, live).
 */
final class StoryRunNav {

  /**
   * Builds Ready & in progress / Completed / Live tabs.
   */
  public static function buildTopNav(): array {
    $route = \Drupal::routeMatch()->getRouteName();

    $primary = [
      [
        'title' => (string) t('Ready & in progress'),
        'url' => Url::fromRoute('story_pipeline.run')->toString(),
        'active' => $route === 'story_pipeline.run',
      ],
      [
        'title' => (string) t('Completed'),
        'url' => Url::fromRoute('story_pipeline.run_completed')->toString(),
        'active' => $route === 'story_pipeline.run_completed',
      ],
      [
        'title' => (string) t('Live'),
        'url' => Url::fromRoute('story_pipeline.run_live')->toString(),
        'active' => $route === 'story_pipeline.run_live',
      ],
    ];

    return [
      '#type' => 'container',
      '#attributes' => ['class' => ['story-run-nav-wrap']],
      'nav' => [
        '#theme' => 'story_pipeline_workspace_nav',
        '#primary' => $primary,
        '#secondary' => [],
      ],
      '#attached' => [
        'library' => ['story_pipeline/story-run-nav'],
      ],
      '#weight' => -1000,
    ];
  }

}
