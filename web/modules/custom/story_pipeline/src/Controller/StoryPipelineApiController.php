<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Controller;

use Drupal\Core\Access\AccessResult;
use Drupal\Core\Controller\ControllerBase;
use Drupal\Core\Session\AccountInterface;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\Service\StoryPipelineManager;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Exception\BadRequestHttpException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

/**
 * REST API for Story Pipeline.
 */
class StoryPipelineApiController extends ControllerBase {

  public function __construct(
    private readonly StoryPipelineManager $manager,
  ) {}

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container): static {
    return new static(
      $container->get('story_pipeline.manager'),
    );
  }

  /**
   * Custom access: permission OR valid X-Story-Pipeline-Key header.
   */
  public static function apiAccess(AccountInterface $account): AccessResult {
    if ($account->hasPermission('use story pipeline api')) {
      return AccessResult::allowed()->cachePerPermissions();
    }
    $request = \Drupal::request();
    $key = $request->headers->get('X-Story-Pipeline-Key', '');
    $expected = \Drupal::config('story_pipeline.settings')->get('api_key') ?? '';
    if ($expected && hash_equals($expected, $key)) {
      return AccessResult::allowed()->setCacheMaxAge(0);
    }
    return AccessResult::forbidden()->cachePerPermissions();
  }

  /**
   * POST /api/story-pipeline/stories
   */
  public function createStory(Request $request): JsonResponse {
    $data = json_decode($request->getContent(), TRUE);
    if (!is_array($data)) {
      throw new BadRequestHttpException('Invalid JSON body.');
    }
    try {
      $node = $this->manager->createStory($data);
      return new JsonResponse($this->manager->serializeStory($node), 201);
    }
    catch (\InvalidArgumentException $e) {
      throw new BadRequestHttpException($e->getMessage());
    }
  }

  /**
   * GET /api/story-pipeline/stories/{story_id}
   */
  public function getStory(int $story_id): JsonResponse {
    $node = $this->loadStoryById($story_id);
    return new JsonResponse($this->manager->serializeStory($node));
  }

  /**
   * GET /api/story-pipeline/stories/{story_id}/bundle
   */
  public function getBundle(int $story_id, Request $request): JsonResponse {
    $node = $this->loadStoryById($story_id);
    $pipeline = $request->query->get('pipeline', 'storyboard');
    return new JsonResponse($this->manager->buildBundle($node, $pipeline));
  }

  /**
   * POST /api/story-pipeline/generate-story
   */
  public function generateStory(Request $request): JsonResponse {
    $data = json_decode($request->getContent(), TRUE) ?: [];
    $node = $this->loadStoryById($data['story_id'] ?? NULL);
    $type = $this->storyTypeMachine($node);
    $missing = $this->manager->hasRequiredKeys($type, 'generate-story');
    if ($missing) {
      throw new BadRequestHttpException('Missing API keys for story type "' . $type . '": ' . implode(', ', $missing) . '. Set them at /admin/config/content/story-pipeline');
    }
    try {
      $this->manager->queueGenerateStory($node);
      return new JsonResponse([
        'message' => 'Queued for story generation. Worker should GET bundle and POST update when done.',
        'story' => $this->manager->serializeStory($node),
        'bundle_url' => '/api/story-pipeline/stories/' . $node->id() . '/bundle?pipeline=generate',
      ]);
    }
    catch (\InvalidArgumentException $e) {
      throw new BadRequestHttpException($e->getMessage());
    }
  }

  /**
   * POST /api/story-pipeline/run-storyboard
   */
  public function runStoryboard(Request $request): JsonResponse {
    $data = json_decode($request->getContent(), TRUE) ?: [];
    $node = $this->loadStoryById($data['story_id'] ?? NULL);
    $type = $this->storyTypeMachine($node);
    $missing = $this->manager->hasRequiredKeys($type, 'storyboard');
    if ($missing) {
      throw new BadRequestHttpException('Missing API keys for story type "' . $type . '": ' . implode(', ', $missing) . '. Set them at /admin/config/content/story-pipeline');
    }
    $max_step = (int) ($data['max_step'] ?? 4);
    try {
      $this->manager->queueStoryboard($node, $max_step);
      return new JsonResponse([
        'message' => 'Queued for storyboard. Worker should GET bundle and POST update when done.',
        'story' => $this->manager->serializeStory($node),
        'bundle_url' => '/api/story-pipeline/stories/' . $node->id() . '/bundle?pipeline=storyboard',
      ]);
    }
    catch (\InvalidArgumentException $e) {
      throw new BadRequestHttpException($e->getMessage());
    }
  }

  /**
   * POST/PATCH /api/story-pipeline/stories/{story_id}/update — worker writes outputs.
   */
  public function updateStory(int $story_id, Request $request): JsonResponse {
    $node = $this->loadStoryById($story_id);
    $data = json_decode($request->getContent(), TRUE);
    if (!is_array($data)) {
      throw new BadRequestHttpException('Invalid JSON body.');
    }
    $node = $this->manager->updateStoryFromWorker($node, $data);
    return new JsonResponse($this->manager->serializeStory($node));
  }

  /**
   * Story type machine name from node.
   */
  private function storyTypeMachine(NodeInterface $node): string {
    $term = $node->get('field_story_type')->entity;
    if (!$term) {
      throw new BadRequestHttpException('Story has no story type.');
    }
    return $this->manager->getTypeMachine($term);
  }

  /**
   * Load story node by ID.
   */
  private function loadStoryById(int|string|null $story_id): NodeInterface {
    if (!$story_id) {
      throw new BadRequestHttpException('story_id is required.');
    }
    $node = $this->entityTypeManager()->getStorage('node')->load((int) $story_id);
    if (!$node instanceof NodeInterface || $node->bundle() !== 'story') {
      throw new NotFoundHttpException('Story not found.');
    }
    return $node;
  }

}
