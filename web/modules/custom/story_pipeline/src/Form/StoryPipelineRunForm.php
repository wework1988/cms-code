<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Form;

use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\Form\FormBase;
use Drupal\Core\Form\FormStateInterface;
use Drupal\Core\Url;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\Batch\StoryPipelineBatch;
use Drupal\story_pipeline\Service\JobProgressParser;
use Drupal\story_pipeline\Service\StoryPipelineManager;
use Drupal\story_pipeline\Service\WorkerLauncher;
use Drupal\story_pipeline\StoryRunNav;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Simple UI to start pipeline jobs — work runs in the background worker.
 */
class StoryPipelineRunForm extends FormBase {

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly WorkerLauncher $launcher,
    private readonly StoryPipelineManager $manager,
    private readonly JobProgressParser $progressParser,
    private string $tab = 'active',
  ) {}

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container): static {
    $route_match = \Drupal::routeMatch();
    $tab = $route_match->getRouteObject()?->getDefault('tab') ?? 'active';
    return new static(
      $container->get('entity_type.manager'),
      $container->get('story_pipeline.worker_launcher'),
      $container->get('story_pipeline.manager'),
      $container->get('story_pipeline.progress_parser'),
      $tab,
    );
  }

  /**
   * {@inheritdoc}
   */
  public function getFormId(): string {
    return 'story_pipeline_run_form';
  }

  /**
   * {@inheritdoc}
   */
  public function buildForm(array $form, FormStateInterface $form_state, ?string $tab = 'active'): array {
    $this->tab = $tab;
    $is_completed_tab = $this->tab === 'completed';
    $is_live_tab = $this->tab === 'live';
    $is_archive_tab = $is_completed_tab || $is_live_tab;

    $form['#attached']['library'][] = 'story_pipeline/story-pipeline-run';
    $form['#attributes']['class'][] = 'story-pipeline-run-form';
    if ($is_completed_tab) {
      $form['#attributes']['class'][] = 'story-pipeline-run-form--completed';
    }
    if ($is_live_tab) {
      $form['#attributes']['class'][] = 'story-pipeline-run-form--live';
    }
    $form['#attached']['drupalSettings']['storyPipelineRun'] = [
      'progressUrl' => Url::fromRoute('story_pipeline.progress_all')->toString(),
      'consoleUrl' => Url::fromRoute('story_pipeline.console')->toString(),
      'pollIntervalMs' => 8000,
      'consolePollIntervalMs' => 4000,
    ];

    $form['run_nav'] = StoryRunNav::buildTopNav();

    if (!$is_archive_tab) {
      $form['console_panel'] = [
        '#type' => 'details',
        '#title' => $this->t('Backend console'),
        '#open' => TRUE,
        '#attributes' => ['class' => ['story-pipeline-console-wrap']],
        '#weight' => 100,
      ];
      $form['console_panel']['intro'] = [
        '#markup' => '<p class="story-pipeline-console__intro">' . $this->t(
          'Live output from background jobs on your Mac (same as the terminal log). Updates every few seconds while jobs run.'
        ) . '</p>',
      ];
      $form['console_panel']['toolbar'] = [
        '#markup' => '<div class="story-pipeline-console__toolbar">'
          . '<span id="story-pipeline-console-status" class="story-pipeline-console__status">' . $this->t('Waiting for jobs…') . '</span>'
          . '<div id="story-pipeline-console-jobs" class="story-pipeline-console__jobs"></div>'
          . '<button type="button" id="story-pipeline-console-pause" class="button button--small" aria-pressed="false">' . $this->t('Pause') . '</button>'
          . '<button type="button" id="story-pipeline-console-clear" class="button button--small">' . $this->t('Clear') . '</button>'
          . '</div>',
      ];
      $form['console_panel']['body'] = [
        '#markup' => '<div id="story-pipeline-console-body" class="story-pipeline-console__body" tabindex="0">'
          . '<div class="story-pipeline-console__placeholder">' . $this->t('Log output will appear here when you start a job.') . '</div>'
          . '</div>',
      ];
    }

    $form['intro'] = [
      '#type' => 'markup',
      '#markup' => '<p>' . match ($this->tab) {
        'completed' => $this->t('Stories whose pipeline job finished successfully. Download outputs below, move them to <strong>Live</strong> when published, or start a new job if you need to re-run.'),
        'live' => $this->t('Stories marked as live (published or handed off). They no longer appear in Completed.'),
        default => $this->t('Click a button to <strong>start</strong> a job. Progress updates automatically every few seconds (or refresh the page). Jobs run in the background and can take 10–20 minutes.'),
      } . '</p>',
    ];

    if (!$this->launcher->isShellAvailable()) {
      $form['shell_warning'] = [
        '#type' => 'markup',
        '#markup' => '<p><strong>' . $this->t('Warning:') . '</strong> ' .
          $this->t('PHP cannot run shell commands on this server (common on MAMP). Start/Stop from this page may not work — ask admin to enable <code>exec</code> and <code>shell_exec</code> in php.ini, or use Terminal: <code>cd story-pipeline-worker && ./run.sh storyboard ID</code>') .
          '</p>',
        '#prefix' => '<div class="messages messages--warning">',
        '#suffix' => '</div>',
      ];
    }

    $form['help'] = [
      '#type' => 'details',
      '#title' => $this->t('Which button should I use?'),
      '#open' => FALSE,
    ];
    $form['help']['steps'] = [
      '#theme' => 'item_list',
      '#items' => [
        $this->t('<strong>Write story from YouTube</strong> — when the story only has YouTube URLs, no script yet.'),
        $this->t('<strong>Build storyboard</strong> — when the full script is saved; creates scene + image prompt files.'),
        $this->t('<strong>Build storyboard + narration audio</strong> — storyboard and ElevenLabs MP3s in one job.'),
        $this->t('<strong>Full pipeline (all steps + audio)</strong> — YouTube → script → storyboard → MP3s (best for bulk).'),
        $this->t('<strong>Create narration audio only</strong> — when storyboard is already done; makes MP3s from the script.'),
      ],
    ];

    $ids = $this->entityTypeManager->getStorage('node')->getQuery()
      ->accessCheck(TRUE)
      ->condition('type', 'story')
      ->sort('changed', 'DESC')
      ->execute();

    if (!$ids) {
      $form['empty'] = [
        '#markup' => '<p><em>' . $this->t('No stories yet. @link', [
          '@link' => (string) $this->t('<a href=":url">Create a story</a>', [
            ':url' => Url::fromRoute('node.add', ['node_type' => 'story'])->toString(),
          ]),
        ]) . '</em></p>',
      ];
      return $form;
    }

    $nodes = $this->entityTypeManager->getStorage('node')->loadMultiple($ids);
    $target_bucket = match ($this->tab) {
      'completed' => 'completed',
      'live' => 'live',
      default => 'active',
    };
    $nodes = array_values(array_filter(
      $nodes,
      fn($node) => $node instanceof NodeInterface
        && $this->runListBucket($node) === $target_bucket,
    ));

    if (!$is_archive_tab) {
      usort($nodes, function (NodeInterface $a, NodeInterface $b): int {
        $a_running = $this->launcher->hasActiveJob($a)
          || ($a->get('field_status')->value ?? '') === 'storyboard_running';
        $b_running = $this->launcher->hasActiveJob($b)
          || ($b->get('field_status')->value ?? '') === 'storyboard_running';
        if ($a_running !== $b_running) {
          return $b_running <=> $a_running;
        }
        return $b->getChangedTime() <=> $a->getChangedTime();
      });
    }

    if ($nodes === []) {
      $empty_message = match ($this->tab) {
        'completed' => $this->t('No completed jobs yet — finished stories will appear here.'),
        'live' => $this->t('No live stories yet — move finished stories here from Completed.'),
        default => $this->t('No stories ready or in progress.'),
      };
      $form['empty'] = [
        '#markup' => '<p><em>' . $empty_message . '</em></p>',
      ];
      return $form;
    }

    $header = [
      'title' => $this->t('Story'),
      'type' => $this->t('Type'),
      'progress' => $this->t('Progress'),
      'status' => $this->t('Status'),
      'log' => $this->t('Job log'),
      'outputs' => $this->t('Outputs'),
    ];
    if ($is_completed_tab) {
      $header['move_live'] = $this->t('Move to Live');
    }
    if (!$is_live_tab) {
      $header['stop'] = $this->t('Stop');
      $header['start'] = $this->t('Start job');
    }

    $options = [];
    $pick_options = [];
    foreach ($nodes as $node) {
      if (!$node instanceof NodeInterface) {
        continue;
      }
      $nid = (int) $node->id();
      $pick_options[$nid] = $node->getTitle() . ' (#' . $nid . ')';
      $this->manager->syncAssetFilesToNodeFields($node);
      $serialized = $this->manager->serializeStory($node);
      $term = $node->get('field_story_type')->entity;
      $type_label = $term ? $term->label() : '—';

      $outputs = [];
      foreach ([
        'prompt_file_url' => $this->t('Prompts'),
        'scene_file_url' => $this->t('Scenes'),
        'image_prompts_file_url' => $this->t('Image prompts'),
      ] as $key => $label) {
        if (!empty($serialized[$key])) {
          $outputs[] = '<a href="' . htmlspecialchars($serialized[$key]) . '" target="_blank">' . $label . '</a>';
        }
      }
      foreach ($serialized['eleven_labs_file_urls'] ?? [] as $i => $url) {
        $n = $i + 1;
        $outputs[] = '<a href="' . htmlspecialchars($url) . '" target="_blank">' . $this->t('Audio @n', ['@n' => $n]) . '</a>';
      }
      if (!empty($serialized['story_asset_folder'])) {
        $outputs[] = '<br><small>' . $this->t('Folder: @path', [
          '@path' => htmlspecialchars($serialized['story_asset_folder']),
        ]) . '</small>';
      }

      $last = $this->launcher->lastJobInfo($node);
      $status_extra = '';
      if ($last && !empty($last['started'])) {
        $status_extra = '<br><small>' . $this->t('Started: @time', [
          '@time' => date('M j, g:ia', strtotime($last['started'])),
        ]) . '</small>';
      }

      $log_url = $this->launcher->logPublicUrl($last);
      $log_cell = '—';
      if ($log_url) {
        $log_cell = '<a href="' . htmlspecialchars($log_url) . '" target="_blank">' .
          $this->t('View log') . '</a>';
        if ($last && !empty($last['label'])) {
          $log_cell .= '<br><small>' . htmlspecialchars($last['label']) . '</small>';
        }
      }
      elseif ($last) {
        $log_cell = '<em>' . $this->t('Log not found yet') . '</em>';
      }

      $stop_cell = ['data' => ['#markup' => '—']];
      if ($this->launcher->canStopJob($node)) {
        $stop_cell = [
          'data' => [
            '#type' => 'link',
            '#title' => $this->t('Stop job'),
            '#url' => $this->actionUrl('story_pipeline.stop_job', ['node' => $nid]),
            '#attributes' => ['class' => ['button', 'button--small', 'button--danger']],
          ],
        ];
      }

      $job_links = [
        '#type' => 'container',
        '#attributes' => ['class' => ['story-pipeline-actions']],
      ];
      // Completed tab: narration audio only — storyboard is already done.
      $row_jobs = $is_completed_tab
        ? ['elevenlabs']
        : ['full_pipeline', 'generate', 'storyboard', 'storyboard_elevenlabs', 'elevenlabs'];
      foreach ($row_jobs as $job) {
        $job_links[$job] = [
          '#type' => 'link',
          '#title' => WorkerLauncher::jobLabels()[$job],
          '#url' => $this->actionUrl('story_pipeline.launch_job', ['node' => $nid, 'job' => $job]),
          '#attributes' => ['class' => ['button', 'button--small']],
        ];
      }

      $progress = $this->progressParser->getProgress($node);
      $row = [
        'title' => [
          'data' => [
            '#markup' => '<strong>' . $node->getTitle() . '</strong><br><small>#' . $nid . ' · <a href="' .
              Url::fromRoute('entity.node.edit_form', ['node' => $nid])->toString() . '">' .
              $this->t('Edit story') . '</a></small>',
          ],
        ],
        'type' => $type_label,
        'progress' => [
          'data' => [
            '#theme' => 'story_pipeline_progress',
            '#progress' => $progress,
            '#story_id' => $nid,
          ],
        ],
        'status' => [
          'data' => ['#markup' => $this->launcher->statusLabel($node) . $status_extra],
        ],
        'log' => ['data' => ['#markup' => $log_cell]],
        'outputs' => ['data' => ['#markup' => $outputs ? implode(' · ', $outputs) : '—']],
      ];
      if ($is_completed_tab) {
        $row['move_live'] = [
          'data' => [
            '#type' => 'link',
            '#title' => $this->t('Move to Live'),
            '#url' => $this->actionUrl('story_pipeline.move_to_live', ['node' => $nid]),
            '#attributes' => ['class' => ['button', 'button--small', 'button--primary']],
          ],
        ];
      }
      if (!$is_live_tab) {
        $row['stop'] = $stop_cell;
        $row['start'] = ['data' => $job_links];
      }
      $options[$nid] = $row;
    }

    $form['stories'] = [
      '#type' => 'tableselect',
      '#header' => $header,
      '#options' => $options,
      '#empty' => match ($this->tab) {
        'completed' => $this->t('No completed jobs yet.'),
        'live' => $this->t('No live stories yet.'),
        default => $this->t('No stories ready or in progress.'),
      },
      '#js_select' => TRUE,
      '#multiple' => TRUE,
    ];

    if (!$is_archive_tab) {
      $form['bulk'] = [
      '#type' => 'fieldset',
      '#title' => $this->t('Bulk actions (selected stories)'),
      '#attributes' => ['class' => ['story-pipeline-bulk']],
    ];
    $form['bulk']['hint'] = [
      '#markup' => '<p>' . $this->t('Select stories using the <strong>table checkboxes</strong> (first column) and/or the list below. Bulk jobs launch <strong>in parallel</strong> in the background. Each story can still take many hours.') . '</p>',
    ];
    $form['bulk']['story_pick'] = [
      '#type' => 'checkboxes',
      '#title' => $this->t('Selected stories'),
      '#options' => $pick_options,
      '#description' => $this->t('If table checkboxes misbehave, select stories here instead — both lists are combined.'),
    ];
    $form['bulk']['actions'] = [
      '#type' => 'actions',
    ];
    $form['bulk']['actions']['run_full'] = [
      '#type' => 'submit',
      '#value' => $this->t('Run full pipeline on selected (all steps + audio)'),
      '#submit' => ['::submitBulkJob'],
      '#bulk_job' => 'full_pipeline',
      '#button_type' => 'primary',
    ];
    $form['bulk']['actions']['run_storyboard_audio'] = [
      '#type' => 'submit',
      '#value' => $this->t('Run storyboard + audio on selected'),
      '#submit' => ['::submitBulkJob'],
      '#bulk_job' => 'storyboard_elevenlabs',
    ];
    $form['bulk']['actions']['run_storyboard'] = [
      '#type' => 'submit',
      '#value' => $this->t('Run storyboard only on selected'),
      '#submit' => ['::submitBulkJob'],
      '#bulk_job' => 'storyboard',
    ];
    $form['bulk']['actions']['stop_selected'] = [
      '#type' => 'submit',
      '#value' => $this->t('Stop selected jobs'),
      '#submit' => ['::submitBulkStop'],
    ];
    }

    if ($is_completed_tab) {
      $form['bulk_audio'] = [
        '#type' => 'fieldset',
        '#title' => $this->t('Narration audio (selected stories)'),
        '#attributes' => ['class' => ['story-pipeline-bulk', 'story-pipeline-bulk--audio']],
      ];
      $form['bulk_audio']['hint'] = [
        '#markup' => '<p>' . $this->t('Tick the <strong>checkbox</strong> for one or more finished stories, then click the button below. Only the checked rows run, launched in parallel. Does <strong>not</strong> rebuild storyboard.') . '</p>',
      ];
      $form['bulk_audio']['actions'] = [
        '#type' => 'actions',
      ];
      $form['bulk_audio']['actions']['run_elevenlabs'] = [
        '#type' => 'submit',
        '#value' => $this->t('Create narration audio only for selected'),
        '#submit' => ['::submitBulkJob'],
        '#bulk_job' => 'elevenlabs',
        '#button_type' => 'primary',
      ];

      $form['bulk_live'] = [
        '#type' => 'fieldset',
        '#title' => $this->t('Move to Live (selected stories)'),
        '#attributes' => ['class' => ['story-pipeline-bulk', 'story-pipeline-bulk--live']],
      ];
      $form['bulk_live']['hint'] = [
        '#markup' => '<p>' . $this->t('Select stories using the table checkboxes, then move them to the <strong>Live</strong> tab.') . '</p>',
      ];
      $form['bulk_live']['actions'] = [
        '#type' => 'actions',
      ];
      $form['bulk_live']['actions']['move_live'] = [
        '#type' => 'submit',
        '#value' => $this->t('Move selected to Live'),
        '#submit' => ['::submitBulkMoveToLive'],
        '#button_type' => 'primary',
      ];
    }

    return $form;
  }

  /**
   * URL with CSRF token for launch/stop links.
   */
  private function actionUrl(string $route, array $params): Url {
    $url = Url::fromRoute($route, $params);
    $query = [
      'token' => \Drupal::csrfToken()->get($url->getInternalPath()),
    ];
    if ($this->tab !== 'active') {
      $query['tab'] = $this->tab;
    }
    return $url->setOption('query', $query);
  }

  /**
   * Active, completed, or live tab bucket.
   */
  private function runListBucket(NodeInterface $node): string {
    $launcher_bucket = $this->launcher->runListBucket($node);
    if ($launcher_bucket === 'live') {
      return 'live';
    }
    if ($launcher_bucket === 'completed') {
      return 'completed';
    }
    if ($this->isCompletedFromProgress($node)) {
      return 'completed';
    }
    return 'active';
  }

  /**
   * Job finished (100%) even if Drupal status has not synced yet.
   */
  private function isCompletedFromProgress(NodeInterface $node): bool {
    $status = $node->get('field_status')->value ?? 'draft';
    if ($status === 'live') {
      return FALSE;
    }
    $progress = $this->progressParser->getProgress($node);
    if ($progress['state'] !== 'done' || $progress['percent'] < 100) {
      return FALSE;
    }
    $status = $node->get('field_status')->value ?? 'draft';
    if ($status === 'story_generated') {
      return FALSE;
    }
    $last = $this->launcher->lastJobInfo($node);
    $action = (string) ($last['action'] ?? '');
    return in_array($action, ['storyboard', 'storyboard_elevenlabs', 'full_pipeline', 'elevenlabs'], TRUE);
  }

  /**
   * Selected story node IDs from tableselect + bulk checkboxes.
   *
   * @return int[]
   */
  private function getSelectedStoryIds(array $form, FormStateInterface $form_state): array {
    $nids = [];

    // tableselect: checked rows have value = node ID; unchecked rows are 0.
    $selected = $form_state->getValue('stories');
    if (!is_array($selected) || $selected === []) {
      $selected = $form_state->getUserInput()['stories'] ?? [];
    }
    if (is_array($selected)) {
      foreach ($selected as $value) {
        if (is_numeric($value) && (int) $value > 0) {
          $nids[] = (int) $value;
        }
      }
    }

    // Active tab only: optional duplicate picker (same IDs, deduped below).
    $bulk = $form_state->getValue('bulk');
    if (!is_array($bulk)) {
      $bulk = $form_state->getUserInput()['bulk'] ?? [];
    }
    $pick = is_array($bulk['story_pick'] ?? NULL) ? $bulk['story_pick'] : [];
    foreach ($pick as $key => $value) {
      if (is_numeric($value) && (int) $value > 0) {
        $nids[] = (int) $value;
      }
      elseif (is_numeric($key) && (int) $key > 0 && $value) {
        $nids[] = (int) $key;
      }
    }

    return array_values(array_unique($nids));
  }

  /**
   * Selected story nodes from checkbox column.
   *
   * @return \Drupal\node\NodeInterface[]
   */
  private function getSelectedNodes(array $form, FormStateInterface $form_state): array {
    $nids = $this->getSelectedStoryIds($form, $form_state);
    if ($nids === []) {
      return [];
    }
    $nodes = $this->entityTypeManager->getStorage('node')->loadMultiple($nids);
    return array_values(array_filter($nodes, static fn($n) => $n instanceof NodeInterface));
  }

  /**
   * Bulk start job on selected stories.
   */
  public function submitBulkJob(array &$form, FormStateInterface $form_state): void {
    $trigger = $form_state->getTriggeringElement();
    $job = (string) ($trigger['#bulk_job'] ?? 'full_pipeline');
    $nids = $this->getSelectedStoryIds($form, $form_state);

    if ($nids === []) {
      $this->messenger()->addError($this->t('Select at least one story (table checkboxes or the list in Bulk actions).'));
      return;
    }

    $this->messenger()->addStatus($this->t(
      'Starting “@job” for @count story/stories: @ids',
      [
        '@job' => WorkerLauncher::jobLabels()[$job] ?? $job,
        '@count' => count($nids),
        '@ids' => implode(', ', array_map(static fn(int $id): string => '#' . $id, $nids)),
      ]
    ));

    batch_set([
      'title' => $this->t('Starting selected story jobs…'),
      'operations' => [
        [
          [StoryPipelineBatch::class, 'launchSequentialQueue'],
          [$nids, $job],
        ],
      ],
      'finished' => [StoryPipelineBatch::class, 'finished'],
      'progress_message' => $this->t('Starting jobs…'),
      'results' => ['requested' => count($nids)],
    ]);

    $redirect = match ($this->tab) {
      'completed' => 'story_pipeline.run_completed',
      'live' => 'story_pipeline.run_live',
      default => 'story_pipeline.run',
    };
    $form_state->setRedirect($redirect);
  }

  /**
   * Bulk stop jobs on selected stories.
   */
  public function submitBulkStop(array &$form, FormStateInterface $form_state): void {
    $nodes = $this->getSelectedNodes($form, $form_state);
    if ($nodes === []) {
      $this->messenger()->addError($this->t('Select at least one story (checkbox in the first column).'));
      return;
    }

    $running = array_filter($nodes, fn(NodeInterface $node) => $this->launcher->canStopJob($node));
    if ($running === []) {
      $this->messenger()->addWarning($this->t('None of the selected stories have a job actively running.'));
      return;
    }

    $skipped = count($nodes) - count($running);
    $result = $this->launcher->stopBulk($running);
    $this->messenger()->addStatus($this->t(
      'Stop requested for @count running story/stories (@proc process(es) ended).',
      ['@count' => count($running), '@proc' => $result['stopped']]
    ));
    if ($skipped > 0) {
      $this->messenger()->addWarning($this->t(
        '@count selected story/stories were skipped (not actively running).',
        ['@count' => $skipped]
      ));
    }
    foreach ($result['errors'] as $nid => $msg) {
      $this->messenger()->addError($this->t('Story @id: @msg', ['@id' => $nid, '@msg' => $msg]));
    }
  }

  /**
   * Bulk move selected stories to Live.
   */
  public function submitBulkMoveToLive(array &$form, FormStateInterface $form_state): void {
    $nodes = $this->getSelectedNodes($form, $form_state);
    if ($nodes === []) {
      $this->messenger()->addError($this->t('Select at least one story (checkbox in the first column).'));
      return;
    }

    $moved = 0;
    foreach ($nodes as $node) {
      if ($this->runListBucket($node) !== 'completed') {
        continue;
      }
      try {
        $this->launcher->markLive($node);
        $moved++;
      }
      catch (\Throwable $e) {
        $this->messenger()->addError($this->t('Story @id: @msg', [
          '@id' => $node->id(),
          '@msg' => $e->getMessage(),
        ]));
      }
    }

    if ($moved === 0) {
      $this->messenger()->addWarning($this->t('No selected stories were moved to Live.'));
      return;
    }

    $this->messenger()->addStatus($this->formatPlural(
      $moved,
      '1 story moved to Live.',
      '@count stories moved to Live.',
    ));
    $form_state->setRedirect('story_pipeline.run_live');
  }

  /**
   * {@inheritdoc}
   */
  public function submitForm(array &$form, FormStateInterface $form_state): void {
    // Handled by bulk action submit handlers.
  }

}
