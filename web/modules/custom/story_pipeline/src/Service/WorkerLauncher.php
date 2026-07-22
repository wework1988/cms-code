<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\Core\Config\ConfigFactoryInterface;
use Drupal\Core\File\FileSystemInterface;
use Drupal\Core\Logger\LoggerChannelFactoryInterface;
use Drupal\Core\File\FileUrlGeneratorInterface;
use Drupal\node\NodeInterface;

/**
 * Starts background worker jobs (Python) — work runs outside the browser.
 */
class WorkerLauncher {

  /**
   * Allowed job commands → run.sh subcommand + extra args.
   */
  private const JOBS = [
    'generate' => ['cmd' => 'generate', 'args' => []],
    'storyboard' => ['cmd' => 'storyboard', 'args' => []],
    'storyboard_elevenlabs' => ['cmd' => 'storyboard', 'args' => ['--elevenlabs']],
    'elevenlabs' => ['cmd' => 'elevenlabs', 'args' => []],
    'full_pipeline' => ['cmd' => 'full', 'args' => []],
  ];

  public function __construct(
    private readonly ConfigFactoryInterface $configFactory,
    private readonly FileSystemInterface $fileSystem,
    private readonly LoggerChannelFactoryInterface $loggerFactory,
    private readonly FileUrlGeneratorInterface $fileUrlGenerator,
    private readonly StoryPipelineAssetStorage $assetStorage,
  ) {}

  /**
   * Human-readable job labels for the UI.
   */
  public static function jobLabels(): array {
    return [
      'generate' => t('Write story from YouTube'),
      'storyboard' => t('Build storyboard'),
      'storyboard_elevenlabs' => t('Build storyboard + narration audio'),
      'elevenlabs' => t('Create narration audio only'),
      'full_pipeline' => t('Full pipeline (all steps + audio)'),
    ];
  }

  /**
   * Start a background worker job for a story node.
   *
   * @throws \RuntimeException
   */
  public function launch(NodeInterface $node, string $job): void {
    if ($node->bundle() !== 'story') {
      throw new \InvalidArgumentException('Not a story node.');
    }
    if (!isset(self::JOBS[$job])) {
      throw new \InvalidArgumentException('Unknown job: ' . $job);
    }

    if ($this->assetStorage->isEnabled() && $job !== 'elevenlabs') {
      $this->assetStorage->syncRawStoryFile($node);
    }

    $worker_path = $this->workerPath();
    $run_sh = $worker_path . '/run.sh';
    if (!is_file($run_sh)) {
      throw new \RuntimeException('Worker not found: ' . $run_sh);
    }

    [$log_uri, $log_path] = $this->prepareLogFile((int) $node->id(), $job);
    $spec = self::JOBS[$job];
    $args = array_merge([$spec['cmd'], (string) $node->id()], $spec['args']);
    $escaped_args = implode(' ', array_map('escapeshellarg', $args));

    $asset_root = trim((string) $this->configFactory->get('story_pipeline.settings')->get('story_asset_path'));
    $env_prefix = '';
    if ($asset_root !== '') {
      $env_prefix = 'export STORY_ASSET_ROOT=' . escapeshellarg($asset_root) . ' && ';
    }

    $shell = sprintf(
      'cd %s && %snohup %s %s >> %s 2>&1 & echo $!',
      escapeshellarg($worker_path),
      $env_prefix,
      escapeshellarg('./run.sh'),
      $escaped_args,
      escapeshellarg($log_path)
    );

    $this->loggerFactory->get('story_pipeline')->info('Launching job @job for story @id: @cmd', [
      '@job' => $job,
      '@id' => $node->id(),
      '@cmd' => $shell,
    ]);

    $pid_raw = trim((string) shell_exec($shell));
    $pid = is_numeric($pid_raw) ? (int) $pid_raw : NULL;

    $meta = json_encode([
      'last_job' => [
        'action' => $job,
        'label' => (string) self::jobLabels()[$job],
        'started' => date('c'),
        'log' => $log_path,
        'log_uri' => $log_uri,
        'pid' => $pid,
      ],
    ], JSON_UNESCAPED_SLASHES);

    $status_map = [
      'generate' => 'storyboard_running',
      'storyboard' => 'storyboard_running',
      'storyboard_elevenlabs' => 'storyboard_running',
      'elevenlabs' => 'storyboard_running',
      'full_pipeline' => 'storyboard_running',
    ];
    $node->set('field_status', ['value' => $status_map[$job] ?? 'storyboard_running']);
    $node->set('field_story_meta', ['value' => $meta]);
    $node->save();
  }

  /**
   * Map Drupal job key → run_multi.sh job name.
   */
  private function multiJobName(string $job): string {
    return match ($job) {
      'full_pipeline' => 'full',
      'storyboard_elevenlabs' => 'storyboard-elevenlabs',
      default => $job,
    };
  }

  /**
   * Start the same job on multiple stories.
   *
   * @param \Drupal\node\NodeInterface[] $nodes
   *
   * @return array{started: int[], errors: array<int, string>}
   */
  public function launchBulk(array $nodes, string $job, int $stagger_seconds = 0): array {
    if (!isset(self::JOBS[$job])) {
      throw new \InvalidArgumentException('Unknown job: ' . $job);
    }

    $ids = [];
    foreach ($nodes as $node) {
      if ($node instanceof NodeInterface && $node->bundle() === 'story') {
        $ids[] = (int) $node->id();
      }
    }
    $ids = array_values(array_unique($ids));

    if ($ids === []) {
      return ['started' => [], 'errors' => []];
    }

    // Keep single-story behavior exactly the same.
    if (count($ids) === 1) {
      try {
        foreach ($nodes as $node) {
          if ($node instanceof NodeInterface && (int) $node->id() === $ids[0]) {
            $this->launch($node, $job);
            return ['started' => $ids, 'errors' => []];
          }
        }
      }
      catch (\Throwable $e) {
        return ['started' => [], 'errors' => [$ids[0] => $e->getMessage()]];
      }
    }

    // Multi-story bulk: use run_multi.sh --parallel so CMS reliably launches
    // all selected stories in one background command.
    $worker_path = $this->workerPath();
    $run_multi = $worker_path . '/run_multi.sh';
    if (!is_file($run_multi)) {
      throw new \RuntimeException('run_multi.sh not found: ' . $run_multi);
    }

    [$log_uri, $log_path] = $this->prepareLogFile($ids[0], 'bulk-' . $job);
    $multi_job = $this->multiJobName($job);
    $escaped_ids = implode(' ', array_map('escapeshellarg', array_map('strval', $ids)));

    $asset_root = trim((string) $this->configFactory->get('story_pipeline.settings')->get('story_asset_path'));
    $env_prefix = '';
    if ($asset_root !== '') {
      $env_prefix = 'export STORY_ASSET_ROOT=' . escapeshellarg($asset_root) . ' && ';
    }

    $shell = sprintf(
      'cd %s && %snohup %s --parallel %s %s >> %s 2>&1 & echo $!',
      escapeshellarg($worker_path),
      $env_prefix,
      escapeshellarg('./run_multi.sh'),
      escapeshellarg($multi_job),
      $escaped_ids,
      escapeshellarg($log_path)
    );

    $this->loggerFactory->get('story_pipeline')->info('Launching parallel bulk @job for stories @ids', [
      '@job' => $job,
      '@ids' => implode(',', $ids),
    ]);

    $pid_raw = trim((string) shell_exec($shell));
    $pid = is_numeric($pid_raw) ? (int) $pid_raw : NULL;

    $errors = [];
    $started = [];
    $bulk_meta = json_encode([
      'parallel_bulk' => TRUE,
      'job' => $job,
      'story_ids' => $ids,
      'started' => date('c'),
      'log' => $log_path,
      'log_uri' => $log_uri,
      'pid' => $pid,
    ], JSON_UNESCAPED_SLASHES);

    $status = 'storyboard_running';
    foreach ($nodes as $node) {
      if (!$node instanceof NodeInterface || !in_array((int) $node->id(), $ids, TRUE)) {
        continue;
      }
      try {
        $meta = json_encode([
          'last_job' => [
            'action' => $job,
            'label' => (string) self::jobLabels()[$job] . ' (parallel bulk)',
            'started' => date('c'),
            'log' => $log_path,
            'log_uri' => $log_uri,
            'pid' => $pid,
            'bulk' => json_decode($bulk_meta, TRUE),
          ],
        ], JSON_UNESCAPED_SLASHES);
        $node->set('field_status', ['value' => $status]);
        $node->set('field_story_meta', ['value' => $meta]);
        $node->save();
        $started[] = (int) $node->id();
      }
      catch (\Throwable $e) {
        $errors[(int) $node->id()] = $e->getMessage();
      }
    }

    return ['started' => $started, 'errors' => $errors];
  }

  /**
   * One background queue: story N+1 starts only after story N finishes.
   *
   * @param \Drupal\node\NodeInterface[] $nodes
   *
   * @return array{started: int[], errors: array<int, string>}
   */
  public function launchSequential(array $nodes, string $job): array {
    if (!isset(self::JOBS[$job])) {
      throw new \InvalidArgumentException('Unknown job: ' . $job);
    }

    $ids = [];
    foreach ($nodes as $node) {
      if ($node instanceof NodeInterface && $node->bundle() === 'story') {
        $ids[] = (int) $node->id();
      }
    }
    $ids = array_values(array_unique($ids));

    if ($ids === []) {
      return ['started' => [], 'errors' => []];
    }

    if (count($ids) === 1) {
      try {
        $node = reset($nodes);
        if ($node instanceof NodeInterface) {
          $this->launch($node, $job);
          return ['started' => $ids, 'errors' => []];
        }
      }
      catch (\Throwable $e) {
        return ['started' => [], 'errors' => [$ids[0] => $e->getMessage()]];
      }
    }

    $worker_path = $this->workerPath();
    $run_multi = $worker_path . '/run_multi.sh';
    if (!is_file($run_multi)) {
      throw new \RuntimeException('run_multi.sh not found: ' . $run_multi);
    }

    [$log_uri, $log_path] = $this->prepareLogFile($ids[0], 'queue-' . $job);
    $multi_job = $this->multiJobName($job);
    $escaped_ids = implode(' ', array_map('escapeshellarg', array_map('strval', $ids)));

    $asset_root = trim((string) $this->configFactory->get('story_pipeline.settings')->get('story_asset_path'));
    $env_prefix = '';
    if ($asset_root !== '') {
      $env_prefix = 'export STORY_ASSET_ROOT=' . escapeshellarg($asset_root) . ' && ';
    }

    $shell = sprintf(
      'cd %s && %snohup %s --sequential %s %s >> %s 2>&1 & echo $!',
      escapeshellarg($worker_path),
      $env_prefix,
      escapeshellarg('./run_multi.sh'),
      escapeshellarg($multi_job),
      $escaped_ids,
      escapeshellarg($log_path)
    );

    $this->loggerFactory->get('story_pipeline')->info('Launching sequential queue @job for stories @ids', [
      '@job' => $job,
      '@ids' => implode(',', $ids),
    ]);

    $pid_raw = trim((string) shell_exec($shell));
    $pid = is_numeric($pid_raw) ? (int) $pid_raw : NULL;

    $errors = [];
    $started = [];
    $queue_meta = json_encode([
      'sequential_queue' => TRUE,
      'job' => $job,
      'story_ids' => $ids,
      'started' => date('c'),
      'log' => $log_path,
      'log_uri' => $log_uri,
      'pid' => $pid,
    ], JSON_UNESCAPED_SLASHES);

    $status = 'storyboard_running';
    foreach ($nodes as $node) {
      if (!$node instanceof NodeInterface || !in_array((int) $node->id(), $ids, TRUE)) {
        continue;
      }
      try {
        $meta = json_encode([
          'last_job' => [
            'action' => $job,
            'label' => (string) self::jobLabels()[$job] . ' (queued sequential)',
            'started' => date('c'),
            'log' => $log_path,
            'log_uri' => $log_uri,
            'pid' => $pid,
            'queue' => json_decode($queue_meta, TRUE),
          ],
        ], JSON_UNESCAPED_SLASHES);
        $node->set('field_status', ['value' => $status]);
        $node->set('field_story_meta', ['value' => $meta]);
        $node->save();
        $started[] = (int) $node->id();
      }
      catch (\Throwable $e) {
        $errors[(int) $node->id()] = $e->getMessage();
      }
    }

    return ['started' => $started, 'errors' => $errors];
  }

  /**
   * Stop jobs on multiple stories.
   *
   * @param \Drupal\node\NodeInterface[] $nodes
   *
   * @return array{stopped: int, errors: array<int, string>}
   */
  public function stopBulk(array $nodes): array {
    $stopped = 0;
    $errors = [];
    foreach ($nodes as $node) {
      if (!$node instanceof NodeInterface) {
        continue;
      }
      try {
        $stopped += $this->stopJob($node);
      }
      catch (\Throwable $e) {
        $errors[(int) $node->id()] = $e->getMessage();
      }
    }
    return ['stopped' => $stopped, 'errors' => $errors];
  }

  /**
   * Resolve worker folder from config.
   */
  public function workerPath(): string {
    $path = trim((string) $this->configFactory->get('story_pipeline.settings')->get('worker_path'));
    if ($path === '') {
      $path = '/Applications/MAMP/htdocs/story-pipeline-worker';
    }
    $real = realpath($path);
    if ($real === FALSE) {
      throw new \RuntimeException('Worker path does not exist: ' . $path);
    }
    return $real;
  }

  /**
   * Last job info from story meta (for UI).
   */
  public function lastJobInfo(NodeInterface $node): ?array {
    $raw = $node->get('field_story_meta')->value ?? '';
    if ($raw === '') {
      return NULL;
    }
    $data = json_decode($raw, TRUE);
    return is_array($data['last_job'] ?? NULL) ? $data['last_job'] : NULL;
  }

  /**
   * Friendly status label for non-technical users.
   */
  public function statusLabel(NodeInterface $node): string {
    $status = $node->get('field_status')->value ?? 'draft';
    return match ($status) {
      'draft' => (string) t('Draft — add script or YouTube links'),
      'story_generated' => (string) t('Script ready — run storyboard next'),
      'storyboard_running' => (string) t('Job running… refresh in a few minutes'),
      'storyboard_done' => (string) t('Complete'),
      'live' => (string) t('Live'),
      'stopped' => (string) t('Stopped'),
      'failed' => (string) t('Failed — ask admin or check log'),
      default => $status,
    };
  }

  /**
   * Public URL for a job log file (if readable).
   */
  public function logPublicUrl(?array $last_job): ?string {
    if (!$last_job) {
      return NULL;
    }
    if (!empty($last_job['log_uri'])) {
      return $this->fileUrlGenerator->generateAbsoluteString($last_job['log_uri']);
    }
    $log_path = $last_job['log'] ?? '';
    if ($log_path === '' || !is_file($log_path)) {
      return NULL;
    }
    $files_root = $this->fileSystem->realpath('public://');
    if ($files_root && str_starts_with($log_path, $files_root)) {
      $relative = ltrim(substr($log_path, strlen($files_root)), '/\\');
      return $this->fileUrlGenerator->generateAbsoluteString('public://' . $relative);
    }
    return NULL;
  }

  /**
   * Whether a background worker is actively executing for this story right now.
   */
  public function isJobRunning(NodeInterface $node): bool {
    if ($node->bundle() !== 'story') {
      return FALSE;
    }
    return $this->findStoryRunningPids((int) $node->id()) !== [];
  }

  /**
   * Whether the UI should show Stop (only when a worker process is running).
   */
  public function canStopJob(NodeInterface $node): bool {
    return $this->isJobRunning($node);
  }

  /**
   * Whether this story likely has work in progress (queued or executing).
   */
  public function hasActiveJob(NodeInterface $node): bool {
    $status = $node->get('field_status')->value ?? '';
    if ($status === 'storyboard_running') {
      return TRUE;
    }
    return $this->findStoryRunningPids((int) $node->id()) !== [];
  }

  /**
   * Run jobs page tab: active, completed, or live.
   */
  public function runListBucket(NodeInterface $node): string {
    $status = $node->get('field_status')->value ?? 'draft';
    if ($status === 'live') {
      return 'live';
    }
    if ($status === 'storyboard_done') {
      return 'completed';
    }
    return 'active';
  }

  /**
   * Mark a finished story as live (moves it off the Completed tab).
   */
  public function markLive(NodeInterface $node): void {
    if ($node->bundle() !== 'story') {
      throw new \InvalidArgumentException('Not a story node.');
    }
    $node->set('field_status', ['value' => 'live']);
    $node->save();
  }

  /**
   * Whether a story belongs on the active (first) tab.
   */
  public function isRunListActive(NodeInterface $node): bool {
    return $this->runListBucket($node) === 'active';
  }

  /**
   * Stop background worker(s) for a story and mark it stopped in Drupal.
   *
   * @return int Number of processes signalled to stop.
   */
  public function stopJob(NodeInterface $node): int {
    if ($node->bundle() !== 'story') {
      throw new \InvalidArgumentException('Not a story node.');
    }

    $story_id = (int) $node->id();
    $pids = $this->findStoryRunningPids($story_id);

    $last = $this->lastJobInfo($node);
    if ($last && !empty($last['pid']) && is_numeric($last['pid'])) {
      $saved_pid = (int) $last['pid'];
      if (!in_array($saved_pid, $pids, TRUE)) {
        $pids[] = $saved_pid;
      }
    }

    $killed = 0;
    foreach ($pids as $pid) {
      if ($this->killPid($pid)) {
        $killed++;
      }
    }

    $current_status = $node->get('field_status')->value ?? '';
    $should_mark_stopped = $killed > 0 || $current_status === 'storyboard_running';

    if ($should_mark_stopped) {
      $meta_data = json_decode($node->get('field_story_meta')->value ?? '{}', TRUE) ?: [];
      $meta_data['last_job'] = array_merge($meta_data['last_job'] ?? [], [
        'stopped' => date('c'),
        'stopped_by' => 'ui',
      ]);
      $node->set('field_story_meta', ['value' => json_encode($meta_data, JSON_UNESCAPED_SLASHES)]);
      $node->set('field_status', ['value' => 'stopped']);
      $node->save();
    }

    $this->loggerFactory->get('story_pipeline')->info('Stopped job for story @id (@count process(es))', [
      '@id' => $story_id,
      '@count' => $killed,
    ]);

    return $killed;
  }

  /**
   * PIDs of worker processes for a story node ID (includes queue shell if any).
   *
   * @return int[]
   */
  private function findRunningPids(int $story_id): array {
    return array_values(array_unique(array_merge(
      $this->findStoryRunningPids($story_id),
      $this->findQueueRunningPids()
    )));
  }

  /**
   * PIDs of processes actively running this story's pipeline (not the queue waiter).
   *
   * @return int[]
   */
  private function findStoryRunningPids(int $story_id): array {
    if (!$this->shellCommandsAllowed()) {
      return [];
    }

    $patterns = [
      'run_storyboard.py ' . $story_id,
      'run_generate_story.py ' . $story_id,
      'run_elevenlabs.py ' . $story_id,
      'run_full_pipeline.py ' . $story_id,
      'run.sh storyboard ' . $story_id,
      'run.sh generate ' . $story_id,
      'run.sh elevenlabs ' . $story_id,
      'run.sh full ' . $story_id,
    ];
    return $this->pidsMatchingPatterns($patterns);
  }

  /**
   * PIDs of sequential multi-story queue shells.
   *
   * @return int[]
   */
  private function findQueueRunningPids(): array {
    if (!$this->shellCommandsAllowed()) {
      return [];
    }
    return $this->pidsMatchingPatterns(['run_multi.sh']);
  }

  /**
   * @param string[] $patterns
   *
   * @return int[]
   */
  private function pidsMatchingPatterns(array $patterns): array {
    $pids = [];
    foreach ($patterns as $pattern) {
      $cmd = 'pgrep -f ' . escapeshellarg($pattern) . ' 2>/dev/null';
      $output = shell_exec($cmd);
      if (!$output) {
        continue;
      }
      foreach (preg_split('/\s+/', trim($output)) as $pid) {
        if (is_numeric($pid)) {
          $pids[] = (int) $pid;
        }
      }
    }
    return array_values(array_unique($pids));
  }

  /**
   * Send SIGTERM, then SIGKILL if the process is still alive.
   */
  private function killPid(int $pid): bool {
    if ($pid <= 0 || !$this->shellCommandsAllowed()) {
      return FALSE;
    }
    if (!$this->pidExists($pid)) {
      return FALSE;
    }
    exec(sprintf('kill %d 2>/dev/null', $pid));
    usleep(500000);
    if ($this->pidExists($pid)) {
      exec(sprintf('kill -9 %d 2>/dev/null', $pid));
    }
    return !$this->pidExists($pid);
  }

  /**
   * Check whether a PID is still running.
   */
  private function pidExists(int $pid): bool {
    if (!$this->shellCommandsAllowed()) {
      return FALSE;
    }
    exec(sprintf('kill -0 %d 2>/dev/null', $pid), $out, $code);
    return $code === 0;
  }

  /**
   * Whether PHP can spawn/kill background worker processes.
   */
  public function isShellAvailable(): bool {
    return $this->shellCommandsAllowed();
  }

  /**
   * Whether PHP can run shell commands (often disabled in MAMP web PHP).
   */
  private function shellCommandsAllowed(): bool {
    if (!function_exists('exec') || !function_exists('shell_exec')) {
      return FALSE;
    }
    $disabled = array_map('trim', explode(',', (string) ini_get('disable_functions')));
    return !in_array('exec', $disabled, TRUE) && !in_array('shell_exec', $disabled, TRUE);
  }

  /**
   * Create log file for a job run.
   *
   * @return array{0: string, 1: string} URI and absolute filesystem path.
   */
  private function prepareLogFile(int $story_id, string $job): array {
    $directory = 'public://story-pipeline/logs';
    $this->fileSystem->prepareDirectory($directory, FileSystemInterface::CREATE_DIRECTORY | FileSystemInterface::MODIFY_PERMISSIONS);
    $uri = $directory . '/story-' . $story_id . '-' . $job . '-' . date('Ymd-His') . '.log';
    $dir_path = $this->fileSystem->realpath($directory);
    if ($dir_path === FALSE) {
      throw new \RuntimeException('Could not resolve log directory.');
    }
    $full = $dir_path . '/' . basename($uri);
    touch($full);
    return [$uri, $full];
  }

}
