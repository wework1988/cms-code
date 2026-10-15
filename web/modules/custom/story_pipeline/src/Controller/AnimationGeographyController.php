<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Controller;

use Drupal\Core\Controller\ControllerBase;
use Drupal\story_pipeline\Service\AnimationManager;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Read-only geographic catalogue status. Import stays a command-line action.
 */
class AnimationGeographyController extends ControllerBase {

  public function __construct(
    private readonly AnimationManager $animations,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static($container->get('story_pipeline.animations'));
  }

  public function view(): array {
    $status = $this->animations->catalogStatus();
    $lines = [];
    $lines[] = !empty($status['installed']) ? 'Catalogue installed.' : 'Catalogue not installed.';
    if (!empty($status['built_at'])) {
      $lines[] = 'Last successful import: ' . $status['built_at'];
    }
    $counts = $status['counts'] ?? [];
    if (is_array($counts) && $counts) {
      $bits = [];
      foreach ($counts as $level => $count) {
        $bits[] = $level . ' ' . $count;
      }
      $lines[] = 'Records: ' . implode(', ', $bits);
    }
    $levels = $status['levels'] ?? [];
    if (is_array($levels) && $levels) {
      $lines[] = 'Administrative levels: ' . implode(', ', $levels);
    }
    foreach ($status['datasets'] ?? [] as $dataset) {
      if (!is_array($dataset)) {
        continue;
      }
      $lines[] = trim(implode(' · ', array_filter([
        $dataset['namespace'] ?? '',
        $dataset['version'] ?? '',
        $dataset['boundary_year'] ?? '',
        $dataset['licence'] ?? '',
      ])));
    }
    foreach ($status['limitations'] ?? [] as $limitation) {
      $lines[] = (string) $limitation;
    }
    $safe = array_map(static fn ($line) => htmlspecialchars((string) $line, ENT_QUOTES, 'UTF-8'), $lines);
    return [
      '#markup' => '<p>Story planning still calls DeepSeek. This page does not download data or run an import.</p><ul><li>'
        . implode('</li><li>', $safe) . '</li></ul>',
    ];
  }

}
