<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Controller;

use Drupal\Core\Controller\ControllerBase;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\Service\JobProgressParser;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;

/**
 * JSON progress for Run jobs page (auto-refresh).
 */
class StoryPipelineProgressController extends ControllerBase {

  public function __construct(
    private readonly JobProgressParser $progressParser,
  ) {}

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container): static {
    return new static(
      $container->get('story_pipeline.progress_parser'),
    );
  }

  /**
   * GET progress for all story nodes.
   */
  public function allProgress(): JsonResponse {
    $ids = $this->entityTypeManager()->getStorage('node')->getQuery()
      ->accessCheck(TRUE)
      ->condition('type', 'story')
      ->sort('changed', 'DESC')
      ->execute();

    $storage = $this->entityTypeManager()->getStorage('node');
    $progress = [];
    foreach ($ids as $nid) {
      $node = $storage->load($nid);
      if ($node instanceof NodeInterface && $node->bundle() === 'story') {
        $progress[(string) $nid] = $this->progressParser->getProgress($node);
      }
      $storage->resetCache([$nid]);
    }
    return new JsonResponse($progress);
  }

  /**
   * GET progress for one story.
   */
  public function storyProgress(int $story_id): JsonResponse {
    $node = $this->entityTypeManager()->getStorage('node')->load($story_id);
    if (!$node instanceof NodeInterface || $node->bundle() !== 'story') {
      return new JsonResponse(['error' => 'Story not found'], 404);
    }
    return new JsonResponse($this->progressParser->getProgress($node));
  }

  /**
   * GET live console tail for running / recent jobs.
   */
  public function console(Request $request): JsonResponse {
    $raw_offsets = $request->query->all('offsets');
    $offsets = [];
    if (is_array($raw_offsets)) {
      foreach ($raw_offsets as $nid => $offset) {
        $offsets[(string) $nid] = (int) $offset;
      }
    }

    $ids = $this->entityTypeManager()->getStorage('node')->getQuery()
      ->accessCheck(TRUE)
      ->condition('type', 'story')
      ->sort('changed', 'DESC')
      ->execute();

    $storage = $this->entityTypeManager()->getStorage('node');
    $nodes = [];
    foreach ($ids as $nid) {
      $node = $storage->load($nid);
      if ($node instanceof NodeInterface && $node->bundle() === 'story') {
        $nodes[] = $node;
      }
      $storage->resetCache([$nid]);
    }
    return new JsonResponse($this->progressParser->getConsoleData($nodes, $offsets));
  }

}
