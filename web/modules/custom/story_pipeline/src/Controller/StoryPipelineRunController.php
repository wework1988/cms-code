<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Controller;

use Drupal\Core\Controller\ControllerBase;
use Drupal\Core\Url;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\Service\WorkerLauncher;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\RequestStack;
use Symfony\Component\HttpFoundation\RedirectResponse;
use Symfony\Component\HttpKernel\Exception\AccessDeniedHttpException;

/**
 * Launch or stop pipeline jobs from the Run jobs UI (link actions).
 */
class StoryPipelineRunController extends ControllerBase {

  private const ALLOWED_JOBS = [
    'full_pipeline',
    'generate',
    'storyboard',
    'storyboard_elevenlabs',
    'elevenlabs',
  ];

  public function __construct(
    private readonly WorkerLauncher $launcher,
    private readonly RequestStack $requestStack,
  ) {}

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container): static {
    return new static(
      $container->get('story_pipeline.worker_launcher'),
      $container->get('request_stack'),
    );
  }

  /**
   * Start a background job for one story.
   */
  public function launchJob(NodeInterface $node, string $job): RedirectResponse {
    if ($node->bundle() !== 'story') {
      throw new AccessDeniedHttpException();
    }
    if (!in_array($job, self::ALLOWED_JOBS, TRUE)) {
      throw new AccessDeniedHttpException();
    }

    try {
      $request = $this->requestStack->getCurrentRequest();
      $audio = (string) ($request?->query->get('audio') ?? '');
      if ($audio === '' && in_array($job, ['elevenlabs', 'storyboard_elevenlabs', 'full_pipeline'], TRUE)) {
        $audio = $this->launcher->defaultAudioLanguage($node);
      }
      if ($audio === '') {
        $audio = 'hindi';
      }
      $options = [];
      if (in_array($job, ['elevenlabs', 'storyboard_elevenlabs', 'full_pipeline'], TRUE)) {
        $options['audio_languages'] = $this->launcher->normalizeAudioLanguages([$audio]);
      }
      $this->launcher->launch($node, $job, $options);
      $label = WorkerLauncher::jobLabels()[$job] ?? $job;
      $this->messenger()->addStatus($this->t(
        'Started “@job” for “@title”. It runs in the background — refresh this page in 10–15 minutes.',
        ['@job' => $label, '@title' => $node->getTitle()]
      ));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($this->t('Could not start job: @msg', ['@msg' => $e->getMessage()]));
    }

    return $this->redirectToRunPage();
  }

  /**
   * Stop the background job for one story.
   */
  public function stopJob(NodeInterface $node): RedirectResponse {
    if ($node->bundle() !== 'story') {
      throw new AccessDeniedHttpException();
    }

    if (!$this->launcher->canStopJob($node)) {
      $this->messenger()->addWarning($this->t(
        'No running job for “@title”. Stop is only available while a job is actively executing.',
        ['@title' => $node->getTitle()]
      ));
      return $this->redirectToRunPage();
    }

    try {
      $killed = $this->launcher->stopJob($node);
      if ($killed > 0) {
        $this->messenger()->addStatus($this->t(
          'Stopped job for “@title” (@count background process(es) ended).',
          ['@title' => $node->getTitle(), '@count' => $killed]
        ));
      }
      elseif (($node->get('field_status')->value ?? '') === 'stopped') {
        $this->messenger()->addStatus($this->t(
          'Marked “@title” as Stopped (no background process was found).',
          ['@title' => $node->getTitle()]
        ));
      }
      else {
        $this->messenger()->addWarning($this->t(
          'No running job found for “@title”.',
          ['@title' => $node->getTitle()]
        ));
      }
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($this->t('Could not stop job: @msg', ['@msg' => $e->getMessage()]));
    }

    return $this->redirectToRunPage();
  }

  /**
   * Mark a completed story as live.
   */
  public function moveToLive(NodeInterface $node): RedirectResponse {
    if ($node->bundle() !== 'story') {
      throw new AccessDeniedHttpException();
    }

    try {
      $this->launcher->markLive($node);
      $this->messenger()->addStatus($this->t(
        'Moved “@title” to Live.',
        ['@title' => $node->getTitle()]
      ));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($this->t('Could not move to Live: @msg', ['@msg' => $e->getMessage()]));
      return $this->redirectToRunPage('completed');
    }

    return $this->redirectToRunPage('live');
  }

  /**
   * Redirect back to the Run jobs form.
   */
  private function redirectToRunPage(?string $tab = NULL): RedirectResponse {
    if ($tab === NULL) {
      $tab = (string) ($this->requestStack->getCurrentRequest()?->query->get('tab') ?? 'active');
    }
    $route = match ($tab) {
      'completed' => 'story_pipeline.run_completed',
      'live' => 'story_pipeline.run_live',
      default => 'story_pipeline.run',
    };
    return new RedirectResponse(Url::fromRoute($route)->toString());
  }

}
