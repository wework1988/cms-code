<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\node\NodeInterface;

/**
 * Parses job log files and story status into progress UI data.
 */
class JobProgressParser {

  public function __construct(
    private readonly WorkerLauncher $launcher,
  ) {}

  /**
   * Progress snapshot for one story.
   *
   * @return array{
   *   state: string,
   *   percent: int,
   *   label: string,
   *   detail: string,
   *   log_url: string|null
   * }
   */
  public function getProgress(NodeInterface $node): array {
    $status = $node->get('field_status')->value ?? 'draft';
    $last = $this->launcher->lastJobInfo($node);
    $log_url = $this->launcher->logPublicUrl($last);
    if (!$log_url && (int) $node->id() > 0) {
      $fallback = $this->findLatestLogUri((int) $node->id());
      if ($fallback) {
        $log_url = \Drupal::service('file_url_generator')->generateAbsoluteString($fallback);
      }
    }
    $log_text = $this->readLogText($last, (int) $node->id());

    $idle = [
      'state' => 'idle',
      'percent' => 0,
      'label' => (string) t('Not running'),
      'detail' => '',
      'log_url' => $log_url,
    ];

    if ($status === 'storyboard_done' || $status === 'live') {
      return [
        'state' => 'done',
        'percent' => 100,
        'label' => $status === 'live'
          ? (string) t('Live')
          : (string) t('Complete'),
        'detail' => $status === 'live'
          ? (string) t('Published or handed off')
          : (string) t('All outputs uploaded to Drupal'),
        'log_url' => $log_url,
      ];
    }

    if ($status === 'stopped') {
      return [
        'state' => 'stopped',
        'percent' => $this->lastPercentFromLog($log_text),
        'label' => (string) t('Stopped'),
        'detail' => (string) t('Job was cancelled'),
        'log_url' => $log_url,
      ];
    }

    if ($status === 'failed') {
      return [
        'state' => 'error',
        'percent' => $this->lastPercentFromLog($log_text),
        'label' => (string) t('Failed'),
        'detail' => $this->errorDetail($log_text) ?: (string) t('See job log for details'),
        'log_url' => $log_url,
      ];
    }

    if ($log_text !== '') {
      $from_log = $this->parseLog($log_text, $last['action'] ?? '');
      $from_log['log_url'] = $log_url;

      if ($from_log['state'] === 'error') {
        return $from_log;
      }

      if ($status === 'storyboard_running' || $this->launcher->hasActiveJob($node)) {
        $from_log['state'] = 'running';
        return $from_log;
      }

      if ($from_log['percent'] >= 100 || $from_log['state'] === 'done') {
        return $from_log;
      }
    }

    if ($status === 'storyboard_running') {
      return [
        'state' => 'running',
        'percent' => 5,
        'label' => (string) t('Starting…'),
        'detail' => (string) t('Worker is launching — open log in a few seconds'),
        'log_url' => $log_url,
      ];
    }

    if ($status === 'story_generated' && ($last['action'] ?? '') === 'generate') {
      return [
        'state' => 'done',
        'percent' => 100,
        'label' => (string) t('Script generated'),
        'detail' => (string) t('Ready for storyboard'),
        'log_url' => $log_url,
      ];
    }

    return $idle;
  }

  /**
   * Progress for multiple stories (AJAX).
   *
   * @param \Drupal\node\NodeInterface[] $nodes
   */
  public function getProgressMultiple(array $nodes): array {
    $out = [];
    foreach ($nodes as $node) {
      if ($node instanceof NodeInterface && $node->bundle() === 'story') {
        $out[(string) $node->id()] = $this->getProgress($node);
      }
    }
    return $out;
  }

  /**
   * Live console data: running jobs + new log lines since last poll.
   *
   * @param \Drupal\node\NodeInterface[] $nodes
   * @param array<string, int|string> $offsets
   *   Byte offsets per story ID from the browser.
   */
  public function getConsoleData(array $nodes, array $offsets = []): array {
    $jobs = [];
    $streams = [];
    $running_count = 0;

    foreach ($nodes as $node) {
      if (!$node instanceof NodeInterface || $node->bundle() !== 'story') {
        continue;
      }

      $nid = (int) $node->id();
      $nid_key = (string) $nid;
      $progress = $this->getProgress($node);
      $last = $this->launcher->lastJobInfo($node);
      $status = $node->get('field_status')->value ?? 'draft';
      $is_running = $progress['state'] === 'running'
        || ($status === 'storyboard_running' && $this->launcher->hasActiveJob($node));

      if ($is_running) {
        $running_count++;
      }

      $log_path = $this->resolveLogPath($last, $nid);
      $has_recent_log = $log_path !== '' && is_readable($log_path)
        && (time() - (int) filemtime($log_path)) < 3600;

      if ($is_running || $has_recent_log) {
        $jobs[] = [
          'id' => $nid_key,
          'title' => $node->getTitle(),
          'job' => (string) ($last['label'] ?? $last['action'] ?? ''),
          'state' => $is_running ? 'running' : $progress['state'],
          'percent' => $progress['percent'],
          'label' => $progress['label'],
        ];
      }

      if ($log_path === '' || !is_readable($log_path)) {
        continue;
      }

      if (!$is_running && $status !== 'storyboard_running' && !$has_recent_log) {
        continue;
      }

      $offset = (int) ($offsets[$nid_key] ?? 0);
      $tail = $this->readLogFromOffset($log_path, $offset);
      if ($tail['chunk'] !== '' || $is_running) {
        $streams[$nid_key] = [
          'offset' => $tail['new_offset'],
          'lines' => $this->formatConsoleLines($tail['chunk'], $nid, $node->getTitle()),
        ];
      }
    }

    usort($jobs, static function (array $a, array $b): int {
      if ($a['state'] === 'running' && $b['state'] !== 'running') {
        return -1;
      }
      if ($b['state'] === 'running' && $a['state'] !== 'running') {
        return 1;
      }
      return strcmp($a['id'], $b['id']);
    });

    return [
      'running_count' => $running_count,
      'jobs' => $jobs,
      'streams' => $streams,
      'updated' => date('c'),
    ];
  }

  /**
   * @return array{chunk: string, new_offset: int}
   */
  private function readLogFromOffset(string $path, int $offset): array {
    $size = filesize($path);
    if ($size === FALSE) {
      return ['chunk' => '', 'new_offset' => 0];
    }

    if ($offset <= 0) {
      $start = max(0, $size - 32768);
      $chunk = @file_get_contents($path, FALSE, NULL, $start, $size - $start);
      return [
        'chunk' => is_string($chunk) ? $chunk : '',
        'new_offset' => $size,
      ];
    }

    if ($offset >= $size) {
      return ['chunk' => '', 'new_offset' => $size];
    }

    $chunk = @file_get_contents($path, FALSE, NULL, $offset);
    return [
      'chunk' => is_string($chunk) ? $chunk : '',
      'new_offset' => $size,
    ];
  }

  /**
   * @return array<int, array{ts: int, text: string}>
   */
  private function formatConsoleLines(string $chunk, int $nid, string $title): array {
    if ($chunk === '') {
      return [];
    }

    $prefix = '[#' . $nid . ' ' . $title . '] ';
    $lines = preg_split('/\r\n|\r|\n/', $chunk) ?: [];
    $out = [];
    $now = time();

    foreach ($lines as $line) {
      $line = rtrim($line);
      if ($line === '') {
        continue;
      }
      if (str_starts_with($line, 'WARNING:') && str_contains($line, 'pip version')) {
        continue;
      }
      if (str_contains($line, 'NotOpenSSLWarning') || str_contains($line, 'urllib3/__init__')) {
        continue;
      }
      $out[] = [
        'ts' => $now,
        'text' => $prefix . $line,
      ];
    }

    return $out;
  }

  /**
   * Resolve absolute path to a story job log file.
   *
   * @param array<string, mixed>|null $last_job
   */
  private function resolveLogPath(?array $last_job, int $story_id): string {
    $path = $last_job['log'] ?? '';
    if ($path !== '' && is_readable($path)) {
      return $path;
    }
    return $this->findLatestLogFile($story_id);
  }

  /**
   * @return array{state: string, percent: int, label: string, detail: string}
   */
  private function parseLog(string $text, string $job_action): array {
    if ($this->looksLikeError($text)) {
      return [
        'state' => 'error',
        'percent' => $this->lastPercentFromLog($text),
        'label' => (string) t('Error'),
        'detail' => $this->errorDetail($text) ?: (string) t('Job failed — see log'),
      ];
    }

    if (preg_match_all('/PROGRESS\s+\[[#-]+\]\s+(\d+)%\s+·\s+(.+)/', $text, $matches, PREG_SET_ORDER)) {
      $last = end($matches);
      $pct = (int) $last[1];
      $rest = trim($last[2]);
      [$caption, $detail] = array_pad(explode(' · ', $rest, 2), 2, '');

      if ($pct >= 100 || stripos($caption, 'Complete') !== FALSE) {
        return [
          'state' => 'done',
          'percent' => 100,
          'label' => $caption ?: (string) t('Complete'),
          'detail' => $detail,
        ];
      }

      return [
        'state' => 'running',
        'percent' => $pct,
        'label' => $caption,
        'detail' => $detail,
      ];
    }

    if (preg_match('/\bdone\.\s*$/m', $text)) {
      return [
        'state' => 'done',
        'percent' => 100,
        'label' => (string) t('Complete'),
        'detail' => '',
      ];
    }

    return $this->parseHeuristicProgress($text, $job_action);
  }

  /**
   * Fallback when pipeline does not emit PROGRESS lines (generate, elevenlabs).
   *
   * @return array{state: string, percent: int, label: string, detail: string}
   */
  private function parseHeuristicProgress(string $text, string $job_action): array {
    $steps = match ($job_action) {
      'generate' => [
        ['[drupal] GET', 10, 'Loading story from Drupal'],
        ['[youtube]', 25, 'Fetching YouTube transcripts'],
        ['[llm]', 55, 'Writing script with AI'],
        ['[drupal] POST', 85, 'Saving script to Drupal'],
        ['done.', 100, 'Complete'],
      ],
      'elevenlabs' => [
        ['[drupal] GET', 10, 'Loading story'],
        ['[elevenlabs] generating', 40, 'Creating narration audio'],
        ['[drupal] POST', 90, 'Uploading MP3 files'],
        ['done.', 100, 'Complete'],
      ],
      'full_pipeline' => [
        ['[full-pipeline] step 1', 15, 'Writing script from YouTube'],
        ['[youtube]', 20, 'Fetching YouTube transcripts'],
        ['[llm]', 30, 'Writing script with AI'],
        ['[full-pipeline] step 2', 40, 'Storyboard + audio'],
        ['PROGRESS', 50, 'Running storyboard pipeline'],
        ['[elevenlabs]', 85, 'Creating narration audio'],
        ['done.', 100, 'Complete'],
      ],
      default => [
        ['[drupal] GET', 8, 'Loading story from Drupal'],
        ['[pipeline]', 15, 'Starting storyboard pipeline'],
        ['[deepseek-pipeline]', 20, 'Running AI stages'],
        ['Stage A', 30, 'Stage A — story config'],
        ['Stage B', 45, 'Stage B — scene breakdown'],
        ['Stage C', 60, 'Stage C — image prompts'],
        ['[drupal] POST', 92, 'Uploading results'],
        ['done.', 100, 'Complete'],
      ],
    };

    $percent = 8;
    $label = (string) t('Starting…');
    $detail = '';

    foreach ($steps as [$needle, $pct, $msg]) {
      if (str_contains($text, $needle)) {
        $percent = $pct;
        $label = $msg;
      }
    }

    if (str_contains($text, '[deepseek-pipeline]')) {
      if (preg_match('/Stage A/i', $text)) {
        $percent = max($percent, 28);
        $label = (string) t('Stage A — story config');
      }
      if (preg_match('/Stage B/i', $text)) {
        $percent = max($percent, 42);
        $label = (string) t('Stage B — scene breakdown');
      }
      if (preg_match('/Stage C/i', $text)) {
        $percent = max($percent, 58);
        $label = (string) t('Stage C — image & motion prompts');
      }
    }

    return [
      'state' => $percent >= 100 ? 'done' : 'running',
      'percent' => min(99, $percent),
      'label' => $label,
      'detail' => $detail,
    ];
  }

  private function looksLikeError(string $text): bool {
    if (stripos($text, 'Traceback (most recent call last)') !== FALSE) {
      return TRUE;
    }
    if (preg_match('/^(error|fatal|exception):/im', $text)) {
      return TRUE;
    }
    if (preg_match('/\b(CalledProcessError|SystemExit|HTTPError)\b/', $text)) {
      return TRUE;
    }
    if (stripos($text, 'Pipeline exit') !== FALSE) {
      return TRUE;
    }
    if (preg_match('/Could not start job:/', $text)) {
      return TRUE;
    }
    return FALSE;
  }

  private function errorDetail(string $text): string {
    $lines = preg_split('/\r\n|\r|\n/', $text) ?: [];
    foreach (array_reverse($lines) as $line) {
      $line = trim($line);
      if ($line === '') {
        continue;
      }
      if (preg_match('/^(error|fatal|exception):\s*(.+)$/i', $line, $m)) {
        return $m[2];
      }
      if (stripos($line, 'error:') !== FALSE) {
        return $line;
      }
      if (str_contains($line, 'Traceback')) {
        continue;
      }
      if (strlen($line) > 10 && strlen($line) < 200 && !str_starts_with($line, '[')) {
        return $line;
      }
    }
    return '';
  }

  private function lastPercentFromLog(string $text): int {
    if (preg_match_all('/PROGRESS\s+\[[#-]+\]\s+(\d+)%/', $text, $m)) {
      return (int) end($m[1]);
    }
    return 0;
  }

  /**
   * @param array<string, mixed>|null $last_job
   */
  private function readLogText(?array $last_job, int $story_id = 0): string {
    $path = $last_job['log'] ?? '';
    if ($path === '' || !is_readable($path)) {
      $path = $this->findLatestLogFile($story_id);
    }
    if ($path === '' || !is_readable($path)) {
      return '';
    }
    $size = filesize($path);
    if ($size === FALSE) {
      return '';
    }
    $tail = @file_get_contents($path, FALSE, NULL, max(0, $size - 65536));
    return is_string($tail) ? $tail : '';
  }

  /**
   * Newest log for a story when meta has no path.
   */
  private function findLatestLogFile(int $story_id): string {
    if ($story_id <= 0) {
      return '';
    }
    $dir = \Drupal::service('file_system')->realpath('public://story-pipeline/logs');
    if ($dir === FALSE || !is_dir($dir)) {
      return '';
    }
    $pattern = $dir . '/story-' . $story_id . '-*.log';
    $files = glob($pattern) ?: [];
    if ($files === []) {
      return '';
    }
    usort($files, static fn($a, $b) => filemtime($b) <=> filemtime($a));
    return $files[0];
  }

  private function findLatestLogUri(int $story_id): ?string {
    $path = $this->findLatestLogFile($story_id);
    if ($path === '') {
      return NULL;
    }
    $root = \Drupal::service('file_system')->realpath('public://');
    if ($root && str_starts_with($path, $root)) {
      $rel = ltrim(substr($path, strlen($root)), '/\\');
      return 'public://' . $rel;
    }
    return NULL;
  }

}
