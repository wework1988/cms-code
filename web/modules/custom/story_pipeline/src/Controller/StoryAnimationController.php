<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Controller;

use Drupal\Core\Controller\ControllerBase;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\Service\AnimationManager;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Exception\AccessDeniedHttpException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

/**
 * Authenticated download/preview of animation outputs.
 */
class StoryAnimationController extends ControllerBase {

  public function __construct(
    private readonly AnimationManager $animations,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static($container->get('story_pipeline.animations'));
  }

  public function file(NodeInterface $node, string $job_id, Request $request): BinaryFileResponse {
    if ($node->bundle() !== 'story') {
      throw new AccessDeniedHttpException();
    }
    $relative = (string) $request->query->get('file', '');
    if ($relative === '' || str_contains($relative, '..')) {
      throw new NotFoundHttpException();
    }
    try {
      $job = $this->animations->loadJob($job_id, (int) $node->id());
      $path = $this->animations->resolveJobFile($job, $relative);
    }
    catch (\InvalidArgumentException $e) {
      throw new NotFoundHttpException();
    }
    $ext = strtolower(pathinfo($path, PATHINFO_EXTENSION));
    if (!in_array($ext, ['mp4', 'png', 'json'], TRUE)) {
      throw new NotFoundHttpException();
    }
    $response = new BinaryFileResponse($path);
    $response->headers->set('Content-Type', match ($ext) {
      'mp4' => 'video/mp4',
      'png' => 'image/png',
      default => 'application/json',
    });
    return $response;
  }

}
