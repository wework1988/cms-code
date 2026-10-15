<?php

declare(strict_types=1);
namespace Drupal\story_pipeline\Controller;

use Drupal\Core\Controller\ControllerBase;
use Drupal\Core\Url;
use Drupal\node\NodeInterface;
use Symfony\Component\HttpFoundation\JsonResponse;

/** Read-only, uncached view of durable pipeline and runner records. */
final class StoryMonitorController extends ControllerBase {
  public function page(): array {
    return [
      '#type' => 'container', '#attributes' => ['id' => 'story-monitor'],
      'loading' => ['#markup' => '<p>Loading story status…</p>'],
      '#attached' => ['library' => ['story_pipeline/story-monitor'], 'drupalSettings' => [
        'storyMonitor' => ['endpoint' => Url::fromRoute('story_pipeline.monitor_data')->toString()],
      ]], '#cache' => ['max-age' => 0],
    ];
  }

  private function record(string $path): array {
    if (!is_readable($path) || filesize($path) > 8388608) { return []; }
    $data = json_decode((string) file_get_contents($path), TRUE);
    return is_array($data) ? $data : [];
  }

  private function runner(array $data, int $now): array {
    $heartbeat = (float) ($data['heartbeat_at'] ?? 0);
    return [
      'state' => $data['state'] ?? 'not_reporting',
      'heartbeat_at' => $heartbeat ?: NULL,
      'updated_at' => $data['updated_at'] ?? NULL,
      'stale' => !$heartbeat || $now - $heartbeat > 90,
      'browser' => (!$heartbeat || $now - $heartbeat > 90) ? 'unknown' : ($data['browser'] ?? 'unknown'),
      'scene' => $data['scene'] ?? NULL,
      'scenes' => $data['scenes'] ?? [],
    ];
  }

  public function data(): JsonResponse {
    $now = time();
    $storage = $this->entityTypeManager()->getStorage('node');
    $ids = $storage->getQuery()->accessCheck(TRUE)->condition('type', 'story')->sort('changed', 'DESC')->execute();
    $assets = \Drupal::service('story_pipeline.asset_storage');
    $worker = \Drupal::service('story_pipeline.worker_launcher')->workerPath();
    $watchdog = $this->record($worker . '/.pipeline-jobs/watchdog-health.json');
    $stories = [];
    foreach ($ids as $id) {
      $node = $storage->load($id);
      if (!$node instanceof NodeInterface || !$node->access('view')) { continue; }
      $job = $this->record($worker . '/.pipeline-jobs/story-' . (int) $id . '.json');
      $dir = $assets->resolveStoryDir($node);
      $flow = $dir ? $this->record($dir . '/images/generation-manifest.json') : [];
      $digen = $dir ? $this->record($dir . '/videos/runner-status.json') : [];
      $flow_runner = $dir ? $this->record($dir . '/images/runner-status.json') : [];
      $python = $this->record($worker . '/.pipeline-jobs/story-' . (int) $id . '.heartbeat.json');
      $active = (string) ($flow['active_scene'] ?? '');
      if (($flow_runner['state'] ?? '') === 'running' && isset($flow['scenes'][$active]['status'])) {
        $flow_runner['state'] = $flow['scenes'][$active]['status'];
      }
      $scene_ids = [];
      if ($dir && is_readable($dir . '/image-prompts/image-prompts-only.txt')) {
        preg_match_all('/^\s*(?:---\s*)?Scene\s+(\d+)(?:\s*[.\/:]|\s*$)/m', (string) file_get_contents($dir . '/image-prompts/image-prompts-only.txt'), $matches);
        $scene_ids = array_unique(array_map('intval', $matches[1])); sort($scene_ids);
      }
      $scenes = []; $image_count = 0; $video_count = 0;
      $image_files = $dir ? (glob($dir . '/images/*') ?: []) : [];
      foreach ($scene_ids as $scene) {
        $image = NULL;
        foreach ($image_files as $file) {
          if (ctype_digit(pathinfo($file, PATHINFO_FILENAME)) && (int) pathinfo($file, PATHINFO_FILENAME) === $scene && in_array(strtolower(pathinfo($file, PATHINFO_EXTENSION)), ['jpg', 'jpeg', 'png', 'webp'], TRUE) && filesize($file) > 0) { $image = 'images/' . basename($file); break; }
        }
        $video = is_file($dir . '/videos/scene_' . $scene . '.mp4') && filesize($dir . '/videos/scene_' . $scene . '.mp4') > 0 ? 'videos/scene_' . $scene . '.mp4' : NULL;
        $image_count += (int) (bool) $image; $video_count += (int) (bool) $video;
        $link = fn($file) => $file ? Url::fromRoute('story_pipeline.download_asset', ['node' => $id], ['query' => ['f' => $file]])->toString() : NULL;
        $scenes[] = ['id' => $scene, 'image' => $image ? 'saved' : ($flow['scenes'][(string) $scene]['status'] ?? 'pending'), 'video' => $video ? 'saved' : ($digen['scenes'][(string) $scene]['state'] ?? 'pending'), 'image_url' => $link($image), 'video_url' => $link($video)];
      }
      $stages = [];
      foreach ($job['stages'] ?? [] as $name => $stage) {
        $stages[$name] = array_intersect_key($stage, array_flip(['status', 'attempts', 'last_progress_at', 'next_retry_at', 'error', 'validation', 'completed_at']));
      }
      $stories[] = ['id' => (int) $id, 'title' => $node->label(), 'url' => $node->toUrl()->toString(),
        'cms_status' => $node->get('field_status')->value ?? 'draft', 'status' => $job['status'] ?? 'unmanaged',
        'updated_at' => $job['updated_at'] ?? NULL, 'stages' => $stages, 'python' => $this->runner($python, $now),
        'flow' => $this->runner($flow_runner, $now), 'digen' => $this->runner($digen, $now),
        'flow_scene' => $flow['active_scene'] ?? NULL, 'flow_updated_at' => $flow['updated_at'] ?? NULL,
        'expected' => count($scene_ids), 'images' => $image_count, 'videos' => $video_count, 'scenes' => $scenes];
      $storage->resetCache([$id]);
    }
    $response = new JsonResponse(['fetched_at' => $now, 'watchdog' => $watchdog, 'stories' => $stories]);
    $response->headers->set('Cache-Control', 'no-store, private');
    return $response;
  }
}
