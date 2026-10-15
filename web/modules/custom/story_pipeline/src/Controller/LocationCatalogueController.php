<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Controller;

use Drupal\story_pipeline\Service\WorkerLauncher;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Drupal\Core\Controller\ControllerBase;

/**
 * Read-only catalogue search and one-place geometry preview.
 */
class LocationCatalogueController extends ControllerBase {

  public function __construct(
    private readonly WorkerLauncher $launcher,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static($container->get('story_pipeline.worker_launcher'));
  }

  public function search(Request $request): JsonResponse {
    $query = trim((string) $request->query->get('q', ''));
    $limit = (int) $request->query->get('limit', 8);
    $offset = (int) $request->query->get('offset', 0);
    $args = ['search', '--query', $query, '--limit', (string) max(1, min($limit, 20)), '--offset', (string) max(0, $offset)];
    foreach (['level', 'country', 'state'] as $name) {
      $value = trim((string) $request->query->get($name, ''));
      if ($value !== '') {
        $args[] = '--' . $name;
        $args[] = $value;
      }
    }
    try {
      $payload = $this->launcher->runCatalogue($args);
    }
    catch (\Throwable $error) {
      return new JsonResponse(['results' => [], 'error' => $error->getMessage()], 400);
    }
    $results = [];
    foreach ($payload['results'] ?? [] as $row) {
      if (!is_array($row) || empty($row['id'])) {
        continue;
      }
      $results[] = [
        'id' => $row['id'],
        'name' => $row['name'] ?? '',
        'alternate_name' => $row['alternate_name'] ?? '',
        'level' => $row['level'] ?? '',
        'feature_type' => $row['feature_type'] ?? '',
        'country_code' => $row['country_code'] ?? '',
        'country_name' => $row['country_name'] ?? '',
        'admin_label' => $row['admin_label'] ?? '',
        'level_label' => $row['level_label'] ?? '',
        'state_name' => $row['state_name'] ?? '',
        'district_name' => $row['district_name'] ?? '',
        'representation' => $row['representation'] ?? '',
        'source_namespace' => $row['source_namespace'] ?? '',
      ];
    }
    return new JsonResponse([
      'results' => $results,
      'limit' => $payload['limit'] ?? $limit,
      'offset' => $payload['offset'] ?? $offset,
    ]);
  }

  public function preview(Request $request): JsonResponse {
    $id = trim((string) $request->query->get('id', ''));
    if (!preg_match('/^[A-Za-z0-9_.:-]{1,80}$/', $id)) {
      return new JsonResponse(['error' => 'Choose a catalogue place.'], 400);
    }
    try {
      $payload = $this->launcher->runCatalogue(['preview', '--id', $id]);
    }
    catch (\Throwable $error) {
      return new JsonResponse(['error' => $error->getMessage()], 404);
    }
    unset($payload['ok']);
    return new JsonResponse($payload);
  }

}
