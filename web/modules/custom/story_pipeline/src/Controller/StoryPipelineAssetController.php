<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Controller;

use Drupal\Core\Controller\ControllerBase;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\Service\StoryPipelineAssetStorage;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\BinaryFileResponse;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpKernel\Exception\AccessDeniedHttpException;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

/**
 * Download story asset files from story_asset_path.
 */
class StoryPipelineAssetController extends ControllerBase {

  public function __construct(
    private readonly StoryPipelineAssetStorage $assetStorage,
  ) {}

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container): static {
    return new static(
      $container->get('story_pipeline.asset_storage'),
    );
  }

  /**
   * Serve one file from the story asset folder (?f=prompts/prompt.txt).
   */
  public function download(NodeInterface $node, Request $request): BinaryFileResponse {
    if ($node->bundle() !== 'story') {
      throw new AccessDeniedHttpException();
    }

    $relative = (string) $request->query->get('f', '');
    $path = $this->assetStorage->resolveRelativePath($node, $relative);
    if ($path === NULL) {
      throw new NotFoundHttpException('Asset file not found.');
    }

    $response = new BinaryFileResponse($path);
    $response->setContentDisposition('inline', basename($path));
    return $response;
  }

}
