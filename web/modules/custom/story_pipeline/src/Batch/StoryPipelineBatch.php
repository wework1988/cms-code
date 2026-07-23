<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Batch;

/**
 * Batch launcher for bulk story jobs from the Run jobs UI.
 */
final class StoryPipelineBatch {

  /**
   * Start bulk jobs for all selected IDs (parallel launch).
   *
   * @param int[] $nids
   * @param array{audio_languages?: string[]} $options
   */
  public static function launchSequentialQueue(array $nids, string $job, array $options, array &$context): void {
    $context['results']['requested'] = count($nids);

    $storage = \Drupal::entityTypeManager()->getStorage('node');
    $nodes = $storage->loadMultiple($nids);
    $ordered = [];
    foreach ($nids as $nid) {
      if (isset($nodes[$nid])) {
        $ordered[] = $nodes[$nid];
      }
    }

    try {
      $result = \Drupal::service('story_pipeline.worker_launcher')->launchBulk($ordered, $job, 0, $options);
      $context['results']['started'] = $result['started'];
      $context['results']['errors'] = $result['errors'];
    }
    catch (\Throwable $e) {
      $context['results']['errors']['queue'] = $e->getMessage();
    }
  }

  /**
   * Batch finished callback.
   */
  public static function finished(bool $success, array $results, array $operations): void {
    $messenger = \Drupal::messenger();
    $started = $results['started'] ?? [];
    $errors = $results['errors'] ?? [];
    $requested = (int) ($results['requested'] ?? 0);

    if ($started !== []) {
      $messenger->addStatus(t(
        'Started @count story job(s) (@ids). They run in parallel in the background. Safe to close the browser.',
        [
          '@count' => count($started),
          '@ids' => implode(', ', array_map(static fn($id) => '#' . $id, $started)),
        ]
      ));
    }
    foreach ($errors as $nid => $msg) {
      if ($nid === 'queue') {
        $messenger->addError(t('Could not start bulk jobs: @msg', ['@msg' => $msg]));
      }
      else {
        $messenger->addError(t('Story @id: @msg', ['@id' => $nid, '@msg' => $msg]));
      }
    }
    if ($started === [] && $errors === []) {
      $messenger->addWarning(t('No jobs were started.'));
    }
  }

}
