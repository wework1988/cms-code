<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\Core\Database\Connection;
use Drupal\Core\File\FileSystemInterface;
use Drupal\Core\Session\AccountInterface;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\MapThemes;

/**
 * Animation prompt revisions and map-animation jobs.
 *
 * Jobs snapshot the script and prompt. Workers read that snapshot only.
 */
class AnimationManager {

  public const DEFAULT_PROMPT = <<<'TXT'
You are a documentary animation director. Read the full script and
identify passages where a map animation materially improves the viewer’s
understanding of location, geographic relationships, movement, or changes
in geographic focus.

Select only passages supported by the script and the supplied geographic
coverage. Prefer distinct, useful inserts rather than animating every
sentence. Respect the requested maximum clip count.

Return fewer clips when only one passage deserves a map. Do not treat
every place name as a map. A passage needs a location, a geographic
hierarchy, several places, or a spatial relationship.

The local planner counts narration units and chooses three or four focus
stages. Do not invent a place, a beat, or a color to fill that count.
A closer view or a readable name can be a stage. Quote the exact passage.

Preserve the story language for labels. Visual styling is applied locally:
natural terrain, deep crimson country context, the approved yellow, cyan,
and royal-blue region palette, pale-gold borders, and white labels.

Do not invent facts, locations, administrative relationships, coordinates,
boundaries, narration timestamps, or unsupported effects.

If no passage supports a useful map animation, return no suitable
selections with an explanation. Do not force an animation.
TXT;

  public const DEFAULT_TIMELINE_PROMPT = <<<'TXT'
You are a documentary animation director. Read the full script and
identify passages where a timeline materially improves the viewer’s
understanding of chronology: career milestones, historical transitions,
a sequence of discoveries, the development of an organisation, or
political and social changes over time.

Select only passages the script itself supports. Respect the requested
maximum clip count. Return fewer clips, or none, when that is all the
script can support.

Each clip should propose 3 or 4 milestones that are explicit in one
contiguous passage, plus a title and why a timeline helps. Quote the
passage exactly.

Use the story language for titles and captions. Prefer a dark,
restrained documentary timeline: a charcoal background, a gold line,
large year labels, and short captions.

Do not invent dates, milestones, narration timestamps, or an extra
event to fill a layout. If a stage has no date, leave it undated and
keep narrative order. Do not turn an implied sequence into a year.
Do not request maps, routes, photographs, or effects this timeline
cannot show.

If no passage supports a timeline, return no selections and explain why.
TXT;

  public const DOCUMENTARY_PROMPTS = [
    'text_highlighting' => <<<'TXT'
You are a documentary animation director. Find a statement, contrast,
question, or turning point that is clearer when a phrase is emphasized.
Templates: editorial_statement, quote_annotation, contrast_reveal.
Use quote_annotation only when the passage itself names the speaker.
Emphasize a phrase that already appears. Do not split Hindi letters.
Quote the passage exactly. If nothing should be emphasized, return no selection.
TXT,
    'photo_sequences' => <<<'TXT'
You are a documentary animation director. Find a passage that is clearer
as a sequence of 2 to 4 supplied photographs.
Templates: fullscreen_caption, archival_frame, paired_annotation.
Say which supplied image supports each beat. Do not invent a photograph,
unseen detail, or 3D parallax. If the images are not attached, say assets
are required.
TXT,
    'before_after' => <<<'TXT'
You are a documentary animation director. Find a documented change that has
both a before state and an after state.
Templates: split_divider, matched_crossfade, editorial_panels.
Use editorial_panels when the pictures are different viewpoints.
Do not invent a missing picture or a date. If an asset is missing, say so.
TXT,
    'document_highlighting' => <<<'TXT'
You are a documentary animation director. Find a passage that should be
shown on a supplied PDF or scan.
Templates: archival_desk, full_frame, excerpt_panel.
A scan has no selectable PDF text. If the target region is uncertain,
ask for review. Do not invent a masthead, seal, or excerpt.
Keep the asset, page, excerpt, and region.
TXT,
    'relationship_diagrams' => <<<'TXT'
You are a documentary animation director. Explain entities and connections
the passage itself supports.
Templates: chain, radial, hierarchy.
Every relationship needs one quote that names both entities and the link.
Do not infer cause, ownership, or affiliation because two names appear
near each other. If support is missing, ask for review.
TXT,
    'data_animations' => <<<'TXT'
You are a documentary animation director. Explain numbers that are written
in the passage.
Templates: bar_comparison, line_trend, number_counter.
Do not invent values or intermediate observations. State the unit and the
source. A percentage needs an interpretation. Bar charts start at zero
unless another baseline is explicitly configured and disclosed.
TXT,
    'storyboard_reconstructions' => <<<'TXT'
You are a documentary animation director. Build a sequence from 2 or 3
approved still images.
Templates: cinematic_sequence, panel_expand, detail_focus.
Do not request a new image generator. If the pictures are reconstructions,
keep their provenance and the label Illustrative reconstruction.
Do not describe character movement.
TXT,
  ];

  private const ACTIVE = [
    'queued',
    'analysing_script',
    'planning_clips',
    'resolving_geography',
    'validating_timeline',
    'rendering',
    'uploading_assets',
    'registering_assets',
  ];

  public function __construct(
    private readonly Connection $database,
    private readonly FileSystemInterface $fileSystem,
    private readonly StoryPipelineAssetStorage $assetStorage,
    private readonly WorkerLauncher $launcher,
    private readonly ?MapThemeRepository $mapThemes = NULL,
  ) {}

  public static function typeLabels(): array {
    return [
      'map' => 'Map',
      'timeline' => 'Timeline',
      'text_highlighting' => 'Text highlighting',
      'photo_sequences' => 'Photo sequence',
      'before_after' => 'Before / after',
      'document_highlighting' => 'Document highlighting',
      'relationship_diagrams' => 'Relationship diagram',
      'data_animations' => 'Data animation',
      'storyboard_reconstructions' => 'Storyboard reconstruction',
    ];
  }

  public static function allowedTypes(): array {
    return array_keys(self::typeLabels());
  }

  public function defaultPromptBody(string $animation_type): string {
    if ($animation_type === 'timeline') {
      return self::DEFAULT_TIMELINE_PROMPT;
    }
    return self::DOCUMENTARY_PROMPTS[$animation_type] ?? self::DEFAULT_PROMPT;
  }

  public function ensureSchema(): void {
    if (!$this->database->schema()->tableExists('story_pipeline_anim_prompt')) {
      return;
    }
    $typed = $this->database->schema()->fieldExists('story_pipeline_anim_prompt', 'animation_type');
    if (!$typed) {
      $count = (int) $this->database->select('story_pipeline_anim_prompt', 'p')->countQuery()->execute()->fetchField();
      if ($count === 0) {
        $this->savePrompt(self::DEFAULT_PROMPT, 0, 'map');
      }
      return;
    }
    foreach (['map' => self::DEFAULT_PROMPT, 'timeline' => self::DEFAULT_TIMELINE_PROMPT] + self::DOCUMENTARY_PROMPTS as $type => $body) {
      $count = (int) $this->database->select('story_pipeline_anim_prompt', 'p')
        ->condition('animation_type', $type)
        ->countQuery()
        ->execute()
        ->fetchField();
      if ($count === 0) {
        $this->savePrompt($body, 0, $type);
      }
    }
  }

  public function catalogStatus(): array {
    return $this->launcher->catalogStatus();
  }

  /**
   * Countries and feature types currently installed in the catalogue.
   *
   * @return array{countries: array<int, array<string, mixed>>, levels: array<int, array<string, mixed>>}
   */
  public function geographyFilters(): array {
    try {
      $payload = $this->launcher->runCatalogue(['filters']);
    }
    catch (\Throwable) {
      return ['countries' => [], 'levels' => []];
    }
    $countries = is_array($payload['countries'] ?? NULL) ? $payload['countries'] : [];
    $levels = is_array($payload['levels'] ?? NULL) ? $payload['levels'] : [];
    return ['countries' => $countries, 'levels' => $levels];
  }

  public function currentPrompt(string $animation_type = 'map'): array {
    $this->ensureSchema();
    $query = $this->database->select('story_pipeline_anim_prompt', 'p')
      ->fields('p')
      ->orderBy('id', 'DESC')
      ->range(0, 1);
    if ($this->database->schema()->fieldExists('story_pipeline_anim_prompt', 'animation_type')) {
      $query->condition('animation_type', $animation_type);
    }
    $row = $query->execute()->fetchAssoc();
    $fallback = $this->defaultPromptBody($animation_type);
    if (!$row) {
      return ['id' => 0, 'body' => $fallback, 'uid' => 0, 'created' => 0, 'animation_type' => $animation_type];
    }
    $row['animation_type'] = $row['animation_type'] ?? $animation_type;
    return $row;
  }

  /**
   * @return array<int, array<string, mixed>>
   */
  public function promptRevisions(string $animation_type = 'map'): array {
    $this->ensureSchema();
    $query = $this->database->select('story_pipeline_anim_prompt', 'p')
      ->fields('p')
      ->orderBy('id', 'DESC');
    if ($this->database->schema()->fieldExists('story_pipeline_anim_prompt', 'animation_type')) {
      $query->condition('animation_type', $animation_type);
    }
    return $query->execute()->fetchAll(\PDO::FETCH_ASSOC);
  }

  public function savePrompt(string $body, int $uid, string $animation_type = 'map'): int {
    $body = trim($body);
    if (!in_array($animation_type, self::allowedTypes(), TRUE)) {
      throw new \InvalidArgumentException('Unsupported animation type.');
    }
    if ($body === '' || strlen($body) > 20000) {
      throw new \InvalidArgumentException('The master prompt must be between 1 and 20000 characters.');
    }
    if (preg_match('/api[_-]?key|sk-[a-z0-9]/i', $body)) {
      throw new \InvalidArgumentException('Do not store API keys in the animation prompt.');
    }
    $fields = [
      'body' => $body,
      'uid' => $uid,
      'created' => \Drupal::time()->getRequestTime(),
    ];
    if ($this->database->schema()->fieldExists('story_pipeline_anim_prompt', 'animation_type')) {
      $fields['animation_type'] = $animation_type;
    }
    return (int) $this->database->insert('story_pipeline_anim_prompt')
      ->fields($fields)
      ->execute();
  }

  public function restorePrompt(int $revision_id, int $uid): int {
    $row = $this->database->select('story_pipeline_anim_prompt', 'p')
      ->fields('p')
      ->condition('id', $revision_id)
      ->execute()
      ->fetchAssoc();
    if (!$row || !is_string($row['body'] ?? NULL) || $row['body'] === '') {
      throw new \InvalidArgumentException('Prompt revision not found.');
    }
    return $this->savePrompt($row['body'], $uid, (string) ($row['animation_type'] ?? 'map'));
  }

  public function activeJob(int $nid): ?array {
    if (!$this->database->schema()->tableExists('story_pipeline_anim_job')) {
      return NULL;
    }
    $row = $this->database->select('story_pipeline_anim_job', 'j')
      ->fields('j')
      ->condition('nid', $nid)
      ->condition('status', self::ACTIVE, 'IN')
      ->orderBy('created', 'DESC')
      ->range(0, 1)
      ->execute()
      ->fetchAssoc();
    if (!$row) {
      return NULL;
    }
    $row = $this->syncFromDisk($row);
    if (!in_array($row['status'], self::ACTIVE, TRUE)) {
      return NULL;
    }
    return $row;
  }

  /**
   * @return array<int, array<string, mixed>>
   */
  public function jobsForStory(int $nid): array {
    if (!$this->database->schema()->tableExists('story_pipeline_anim_job')) {
      return [];
    }
    $rows = $this->database->select('story_pipeline_anim_job', 'j')
      ->fields('j')
      ->condition('nid', $nid)
      ->orderBy('created', 'DESC')
      ->execute()
      ->fetchAll(\PDO::FETCH_ASSOC);
    foreach ($rows as &$row) {
      $row = $this->syncFromDisk($row);
    }
    return $rows;
  }

  /**
   * Launch a background map-animation job and return immediately.
   */
  public function launch(NodeInterface $node, AccountInterface $account, array $settings): string {
    if ($node->bundle() !== 'story') {
      throw new \InvalidArgumentException('Not a story.');
    }
    $input_mode = ($settings['input_mode'] ?? 'full_story') === 'scene_breakdown' ? 'scene_breakdown' : 'full_story';
    $scene_info = NULL;
    if ($input_mode === 'scene_breakdown') {
      $scene_info = $this->inspectSceneFile($node, TRUE);
      if (empty($scene_info['ok'])) {
        throw new \InvalidArgumentException((string) ($scene_info['error'] ?? 'Saved scenes are not ready.'));
      }
      $script = (string) $scene_info['text'];
    }
    else {
      $script = trim(strip_tags((string) ($node->get('field_full_story')->value ?? '')));
      if ($script === '') {
        throw new \InvalidArgumentException('This story has no complete script yet.');
      }
    }
    if (array_key_exists('auto_scene_maps', $settings)) {
      \Drupal::state()->set('story_pipeline.map_auto_scenes.' . (int) $node->id(), empty($settings['auto_scene_maps']) ? 0 : 1);
    }
    $lock = $this->acquireLaunchLock($node);
    try {
    if ($this->activeJob((int) $node->id())) {
      throw new \InvalidArgumentException('An animation job is already running for this story.');
    }
    $animation_type = $settings['animation_type'] ?? 'map';
    if (!in_array($animation_type, self::allowedTypes(), TRUE)) {
      throw new \InvalidArgumentException('Unsupported animation type.');
    }
    $renderer = $settings['renderer'] ?? 'maplibre';
    if ($animation_type === 'map') {
      if (!in_array($renderer, ['maplibre', 'openlayers'], TRUE)) {
        throw new \InvalidArgumentException('Unsupported renderer.');
      }
    }
    else {
      $renderer = $animation_type;
    }
    $max = $input_mode === 'scene_breakdown' ? (int) ($settings['max_selected_scenes'] ?? 10) : 3;
    if ($input_mode === 'scene_breakdown' && ($max < 1 || $max > 30)) {
      throw new \InvalidArgumentException('Choose between 1 and 30 suitable scenes.');
    }
    $duration = (float) ($settings['duration_seconds'] ?? 18);
    if ($duration < 6 || $duration > 30) {
      throw new \InvalidArgumentException('Clip duration must be between 6 and 30 seconds.');
    }
    if ($animation_type !== 'map' && $animation_type !== 'timeline' && $duration < 10) {
      throw new \InvalidArgumentException('This animation type needs at least 10 seconds so the last hold stays readable.');
    }
    $this->launcher->animationPython();
    $prompt = $this->currentPrompt($animation_type);
    $job_id = bin2hex(random_bytes(8));
    $job_dir = $this->jobDirectory($node, $job_id);
    $this->fileSystem->prepareDirectory($job_dir, FileSystemInterface::CREATE_DIRECTORY | FileSystemInterface::MODIFY_PERMISSIONS);
    $real = $this->fileSystem->realpath($job_dir);
    if ($real === FALSE) {
      throw new \RuntimeException('Could not create the animation job directory.');
    }
    $job_dir = $real;
    $hash = $input_mode === 'scene_breakdown' ? (string) $scene_info['sha256'] : hash('sha256', $script);
    $prompt_body = (string) $prompt['body'];
    if ($animation_type === 'map' && (int) $prompt['id'] < 1) {
      throw new \InvalidArgumentException('No saved map master-prompt revision. Save one before generating. A generic prompt was not substituted.');
    }
    if (trim($prompt_body) === '') {
      throw new \InvalidArgumentException('The saved master prompt is empty. A generic prompt was not substituted.');
    }
    $prompt_hash = hash('sha256', $prompt_body);
    $map_theme = $animation_type === 'map' ? $this->resolveMapTheme($settings, $account) : NULL;
    $map_style = is_array($map_theme) ? (string) ($map_theme['base_id'] ?? $map_theme['id']) : NULL;
    if (is_string($map_style) && str_starts_with((string) ($map_theme['id'] ?? ''), 'custom_')) {
      $map_style = (string) $map_theme['id'];
    }
    $snapshot = [
      'job_id' => $job_id,
      'nid' => (int) $node->id(),
      'vid' => (int) $node->getRevisionId(),
      'script' => $script,
      'input_mode' => $input_mode,
      'max_selected_scenes' => $max,
      'scene_batch_scenes' => 12,
      'scene_batch_chars' => 12000,
      'story_root' => $this->assetStorage->storyDir($node) ?: NULL,
      'created_unix' => \Drupal::time()->getRequestTime(),
      'scene_source' => $scene_info ? [
        'path' => $scene_info['path'],
        'text' => $scene_info['text'],
        'sha256' => $scene_info['sha256'],
        'parser_version' => $scene_info['parser_version'],
        'scene_count' => $scene_info['scene_count'],
      ] : NULL,
      'script_source' => $input_mode === 'scene_breakdown' ? 'scenes/scene.txt' : 'field_full_story',
      'script_field' => $input_mode === 'scene_breakdown' ? 'scenes/scene.txt' : 'field_full_story',
      'script_hash' => $hash,
      'prompt_id' => (int) $prompt['id'],
      'prompt_source' => 'cms_prompt_revision',
      'prompt_hash' => $prompt_hash,
      'master_prompt' => $prompt_body,
      'language' => $settings['language'] ?? 'hi',
      'renderer' => $renderer,
      'style' => $map_style,
      'map_theme' => $map_theme,
      'duration_seconds' => $duration,
      'max_clips' => $max,
      'animation_type' => $animation_type,
      'contract_version' => '1.0',
      'prompt_revision' => (int) $prompt['id'],
      'planning_settings' => [
        'max_clips' => $max,
        'duration_seconds' => $duration,
        'language' => $settings['language'] ?? 'hi',
        'selection_provider' => 'deepseek',
        'focus_planning_provider' => 'deepseek',
      ],
      'renderer_settings' => [
        'engine' => $renderer,
        'width' => 1920,
        'height' => 1080,
        'fps' => 30,
        'style' => $map_style,
      ],
      'inputs' => $settings['inputs'] ?? [],
      'scene_text' => $this->sceneText($node),
      'uid' => (int) $account->id(),
      'created' => date('c'),
      'planner' => 'deepseek',
      'selection_provider' => 'deepseek',
      'focus_planning_provider' => 'deepseek',
      'presentation_version' => '2026.03-country-opening-v1',
      'opening_policy_default' => 'country_centered',
      'identity_fallback' => $animation_type === 'map',
      'identity_fallback_max_calls' => 24,
      'identity_fallback_version' => '2026.10-identity-fallback-v1',
    ];
    file_put_contents($job_dir . '/snapshot.json', json_encode($snapshot, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    file_put_contents($job_dir . '/progress.json', json_encode([
      'status' => 'queued',
      'message' => $input_mode === 'scene_breakdown'
        ? 'Queued. Scanning saved scenes in order.'
        : 'Queued. Script source: field_full_story. Prompt source: cms_prompt_revision ' . (int) $prompt['id'] . '.',
      'job_id' => $job_id,
      'input_mode' => $input_mode,
      'script_source' => $input_mode === 'scene_breakdown' ? 'scenes/scene.txt' : 'field_full_story',
      'script_hash' => $hash,
      'prompt_source' => 'cms_prompt_revision',
      'prompt_id' => (int) $prompt['id'],
      'prompt_hash' => $prompt_hash,
      'selection_provider' => 'deepseek',
      'focus_planning_provider' => 'deepseek',
      'style' => $snapshot['style'],
      'clips' => [],
    ], JSON_UNESCAPED_UNICODE));

    $this->database->insert('story_pipeline_anim_job')->fields([
      'job_id' => $job_id,
      'nid' => (int) $node->id(),
      'vid' => (int) $node->getRevisionId(),
      'script_hash' => $hash,
      'script' => $script,
      'prompt_id' => (int) $prompt['id'],
      'prompt_text' => $prompt['body'],
      'language' => $snapshot['language'],
      'renderer' => $renderer,
      'duration_seconds' => $duration,
      'max_clips' => $max,
      'animation_type' => $animation_type,
      'uid' => (int) $account->id(),
      'created' => \Drupal::time()->getRequestTime(),
      'status' => 'queued',
      'message' => 'Queued',
      'job_dir' => $job_dir,
    ])->execute();

    $this->launcher->launchAnimation($job_dir . '/snapshot.json', $job_dir . '/worker.log');
    return $job_id;
    }
    finally {
      $this->releaseLaunchLock($lock);
    }
  }

  /**
   * Re-run an existing job with the current map presentation (new compile/render).
   *
   * Does not delete the previous job folder; use a new job id when a fresh URL is needed.
   */
  public function regeneratePresentation(NodeInterface $node, string $job_id): void {
    $lock = $this->acquireLaunchLock($node);
    try {
      $job = $this->loadJob($job_id, (int) $node->id());
      if (in_array($job['status'], self::ACTIVE, TRUE)) {
        throw new \InvalidArgumentException('Wait until the current animation job finishes before regenerating.');
      }
      $snapshot_path = $job['job_dir'] . '/snapshot.json';
      $snapshot = json_decode((string) file_get_contents($snapshot_path), TRUE);
      if (!is_array($snapshot)) {
        throw new \RuntimeException('Job snapshot is unreadable.');
      }
      $snapshot['regenerate_presentation'] = TRUE;
      $snapshot['presentation_version'] = '2026.03-country-opening-v1';
      $snapshot['opening_policy_default'] = 'country_centered';
      file_put_contents($snapshot_path, json_encode($snapshot, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
      $this->database->update('story_pipeline_anim_job')
        ->fields(['status' => 'queued', 'message' => 'Regenerating with current presentation'])
        ->condition('job_id', $job_id)
        ->execute();
      $this->launcher->launchAnimation($snapshot_path, $job['job_dir'] . '/worker.log', NULL, TRUE);
    }
    finally {
      $this->releaseLaunchLock($lock);
    }
  }

  /**
   * @return array<string, mixed>
   */
  private function resolveMapTheme(array $settings, AccountInterface $account): array {
    $theme_id = (string) ($settings['map_theme_id'] ?? 'documentary_relief_bold');
    if ($theme_id === '') {
      $theme_id = 'documentary_relief_bold';
    }
    $overrides = is_array($settings['map_theme_overrides'] ?? NULL) ? $settings['map_theme_overrides'] : [];
    $action = (string) ($settings['map_theme_action'] ?? 'job');
    $name = trim((string) ($settings['map_theme_name'] ?? ''));
    $stored = NULL;
    if (str_starts_with($theme_id, 'custom_')) {
      foreach ($this->mapThemes?->customThemes() ?? [] as $custom) {
        if ($custom['theme_id'] === $theme_id && is_array($custom['document'])) {
          $stored = $custom['document'];
        }
      }
      if (!is_array($stored)) {
        throw new \InvalidArgumentException('That map template is not available.');
      }
    }
    $base_style = is_array($stored) ? (string) ($stored['base_id'] ?? MapThemes::DEFAULT_ID) : $theme_id;
    if (!isset(MapThemes::options()[$base_style])) {
      $base_style = MapThemes::DEFAULT_ID;
    }
    $custom_id = NULL;
    if ($action === 'save' || $action === 'update') {
      if (!$account->hasPermission('manage map appearance templates')) {
        throw new \InvalidArgumentException('You cannot save a shared map template.');
      }
    }
    if ($action === 'update') {
      if (!is_array($stored)) {
        throw new \InvalidArgumentException('Built-in templates stay unchanged. Save a new template instead.');
      }
      $theme = $this->launcher->resolveMapTheme($base_style, $overrides, $theme_id, $name !== '' ? $name : NULL, $stored);
      $this->mapThemes?->saveCustom($theme, $account, TRUE);
      return $theme;
    }
    if ($action === 'save') {
      $custom_id = 'custom_' . bin2hex(random_bytes(4));
      if ($name === '') {
        $name = 'Custom map appearance';
      }
    }
    $theme = $this->launcher->resolveMapTheme($base_style, $overrides, $custom_id, $custom_id ? $name : NULL, $stored);
    if ($action === 'save' && $this->mapThemes) {
      $this->mapThemes->saveCustom($theme, $account, FALSE);
    }
    if ($action === 'default') {
      if (!$account->hasPermission('manage map appearance templates')) {
        throw new \InvalidArgumentException('You cannot change the default map appearance.');
      }
      $this->mapThemes?->setDefault($theme_id);
    }
    return $theme;
  }

  /**
   * Queue a theme-only render that keeps the original video and plan.
   */
  public function restyleJob(NodeInterface $node, string $job_id, string $theme_id, AccountInterface $account): string {
    $job = $this->loadJob($job_id, (int) $node->id());
    if (($job['animation_type'] ?? 'map') !== 'map') {
      throw new \InvalidArgumentException('Only map animations can change appearance.');
    }
    if (in_array($job['status'], self::ACTIVE, TRUE)) {
      throw new \InvalidArgumentException('Wait until the current animation job finishes.');
    }
    $stored = NULL;
    if (str_starts_with($theme_id, 'custom_')) {
      foreach ($this->mapThemes?->customThemes() ?? [] as $custom) {
        if ($custom['theme_id'] === $theme_id && is_array($custom['document'])) {
          $stored = $custom['document'];
        }
      }
      if (!is_array($stored)) {
        throw new \InvalidArgumentException('That map template is not available.');
      }
    }
    $base_style = is_array($stored) ? (string) ($stored['base_id'] ?? MapThemes::DEFAULT_ID) : $theme_id;
    if (!isset(MapThemes::options()[$base_style])) {
      $base_style = MapThemes::DEFAULT_ID;
    }
    $theme = $this->launcher->resolveMapTheme($base_style, [], NULL, NULL, $stored);
    $hash = substr((string) ($theme['theme_hash'] ?? ''), 0, 16);
    if ($hash === '') {
      throw new \RuntimeException('Theme hash is missing.');
    }
    $variant = $job['job_dir'] . '/variants/' . $hash;
    if (is_file($variant . '/render.lock')) {
      throw new \InvalidArgumentException('That appearance is already rendering.');
    }
    $this->fileSystem->prepareDirectory($variant, FileSystemInterface::CREATE_DIRECTORY | FileSystemInterface::MODIFY_PERMISSIONS);
    $revision = 1;
    if (is_file($variant . '/revision.txt')) {
      $revision = ((int) file_get_contents($variant . '/revision.txt')) + 1;
    }
    file_put_contents($variant . '/revision.txt', (string) $revision);
    $snapshot = [
      'job_id' => $job_id,
      'source_job_dir' => $job['job_dir'],
      'style' => $theme['base_id'] ?? $theme['id'],
      'map_theme' => $theme,
      'renderer' => $job['renderer'] ?? 'maplibre',
      'variant_revision' => $revision,
      'deepseek' => FALSE,
    ];
    if (str_starts_with((string) $theme['id'], 'custom_')) {
      $snapshot['style'] = $theme['id'];
    }
    file_put_contents($variant . '/snapshot.json', json_encode($snapshot, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    $this->launcher->launchAnimation($variant . '/snapshot.json', $variant . '/worker.log', NULL, FALSE, FALSE, TRUE);
    return $hash;
  }

  public function retryClip(NodeInterface $node, string $job_id, string $clip_id): void {
    if (!preg_match('/^clip_\d{2}$/', $clip_id)) {
      throw new \InvalidArgumentException('Invalid clip id.');
    }
    $lock = $this->acquireLaunchLock($node);
    try {
    $job = $this->loadJob($job_id, (int) $node->id());
    if (in_array($job['status'], self::ACTIVE, TRUE)) {
      throw new \InvalidArgumentException('Wait until the current animation job finishes before retrying.');
    }
    $this->database->update('story_pipeline_anim_job')
      ->fields(['status' => 'queued', 'message' => 'Retrying ' . $clip_id])
      ->condition('job_id', $job_id)
      ->execute();
    $this->launcher->launchAnimation($job['job_dir'] . '/snapshot.json', $job['job_dir'] . '/worker.log', $clip_id);
    }
    finally {
      $this->releaseLaunchLock($lock);
    }
  }

  /**
   * Save validated location choices and resume the existing animation job.
   *
   * @return array<string, mixed>
   */
  public function saveLocationMappings(NodeInterface $node, string $job_id, array $selections, int $uid): array {
    if (!preg_match('/^[a-f0-9]{16}$/', $job_id)) {
      throw new \InvalidArgumentException('Invalid animation job.');
    }
    $lock = $this->acquireLaunchLock($node);
    try {
      $job = $this->loadJob($job_id, (int) $node->id());
      if (($job['animation_type'] ?? 'map') !== 'map') {
        throw new \InvalidArgumentException('Location mapping applies only to map animations.');
      }
      if (in_array($job['status'], self::ACTIVE, TRUE)) {
        throw new \InvalidArgumentException('Wait until the current animation job finishes before saving locations.');
      }
      if ($selections !== []) {
        $result = $this->launcher->runCatalogue(['apply'], json_encode([
          'job_dir' => $job['job_dir'],
          'job_id' => $job_id,
          'script_hash' => $job['script_hash'],
          'uid' => $uid,
          'selections' => array_values($selections),
        ], JSON_UNESCAPED_UNICODE));
        $this->storeOverrides($job_id, (int) $node->id(), $result['overrides'] ?? [], $uid);
        foreach ($result['remembered'] ?? [] as $alias) {
          if (is_array($alias)) {
            $this->storeAlias($alias, $uid);
          }
        }
      }
      else {
        $result = [
          'changed' => FALSE,
          'errors' => [],
          'overrides' => [],
          'remaining' => [],
        ];
      }
      $resume = !empty($result['changed']) || ($this->hasLocationOverrides($job) && $this->clipsAwaitingLocations($job));
      if ($resume) {
        $this->database->update('story_pipeline_anim_job')
          ->fields([
            'status' => 'queued',
            'message' => 'Mappings saved. Queued for retry.',
          ])
          ->condition('job_id', $job_id)
          ->condition('nid', (int) $node->id())
          ->execute();
        $this->launcher->launchAnimation($job['job_dir'] . '/snapshot.json', $job['job_dir'] . '/worker.log', NULL, FALSE, TRUE);
        $result['resumed'] = TRUE;
      }
      return $result;
    }
    finally {
      $this->releaseLaunchLock($lock);
    }
  }

  private function hasLocationOverrides(array $job): bool {
    $path = ($job['job_dir'] ?? '') . '/location-overrides.json';
    if (!is_file($path)) {
      return FALSE;
    }
    $document = json_decode((string) file_get_contents($path), TRUE);
    return is_array($document) && !empty($document['overrides']);
  }

  private function clipsAwaitingLocations(array $job): bool {
    foreach ($job['clips'] ?? [] as $clip) {
      if (!is_array($clip)) {
        continue;
      }
      $status = (string) ($clip['status'] ?? '');
      $location = (string) ($clip['location_status'] ?? '');
      if ($location === 'needs_location_selection' || in_array($status, ['needs_geographic_data', 'needs_location_clarification'], TRUE)) {
        return TRUE;
      }
    }
    return FALSE;
  }

  private function storeOverrides(string $job_id, int $nid, array $overrides, int $uid): void {
    if (!$this->database->schema()->tableExists('story_pipeline_anim_override')) {
      return;
    }
    $now = \Drupal::time()->getRequestTime();
    foreach ($overrides as $row) {
      if (!is_array($row) || empty($row['request_id'])) {
        continue;
      }
      $fields = [
        'job_id' => $job_id,
        'nid' => $nid,
        'clip_id' => substr((string) ($row['clip_id'] ?? ''), 0, 16),
        'request_id' => substr((string) $row['request_id'], 0, 80),
        'original_name' => (string) ($row['original_name'] ?? ''),
        'original_level' => substr((string) ($row['original_level'] ?? ''), 0, 32),
        'place_id' => substr((string) ($row['place_id'] ?? ''), 0, 80),
        'source' => substr((string) ($row['source'] ?? ''), 0, 40),
        'catalogue_version' => substr((string) ($row['catalogue_version'] ?? ''), 0, 128),
        'fingerprint' => substr((string) ($row['fingerprint'] ?? ''), 0, 64),
        'script_hash' => substr((string) ($row['script_hash'] ?? ''), 0, 64),
        'uid' => $uid,
        'revision' => (int) ($row['revision'] ?? 0),
        'updated' => $now,
      ];
      $existing = $this->database->select('story_pipeline_anim_override', 'o')
        ->fields('o', ['id'])
        ->condition('job_id', $job_id)
        ->condition('request_id', $fields['request_id'])
        ->execute()
        ->fetchField();
      if ($existing) {
        $this->database->update('story_pipeline_anim_override')
          ->fields($fields)
          ->condition('id', $existing)
          ->execute();
      }
      else {
        $fields['created'] = $now;
        $this->database->insert('story_pipeline_anim_override')->fields($fields)->execute();
      }
    }
  }

  private function storeAlias(array $alias, int $uid): void {
    if (!$this->database->schema()->tableExists('story_pipeline_anim_alias') || empty($alias['alias_id'])) {
      return;
    }
    $this->database->insert('story_pipeline_anim_alias')->fields([
      'alias_sqlite_id' => (int) $alias['alias_id'],
      'place_id' => substr((string) ($alias['place_id'] ?? ''), 0, 80),
      'request_id' => substr((string) ($alias['request_id'] ?? ''), 0, 80),
      'uid' => $uid,
      'active' => 1,
      'created' => \Drupal::time()->getRequestTime(),
    ])->execute();
  }

  public function loadJob(string $job_id, int $nid): array {
    $row = $this->database->select('story_pipeline_anim_job', 'j')
      ->fields('j')
      ->condition('job_id', $job_id)
      ->condition('nid', $nid)
      ->execute()
      ->fetchAssoc();
    if (!$row) {
      throw new \InvalidArgumentException('Animation job not found.');
    }
    return $this->syncFromDisk($row);
  }

  /**
   * Safe file inside a job directory (no symlink escape).
   */
  public function resolveJobFile(array $job, string $relative): string {
    if (str_starts_with($relative, 'published/')) {
      $story_node = \Drupal::entityTypeManager()->getStorage('node')->load((int) $job['nid']);
      $story = $story_node instanceof NodeInterface ? $this->assetStorage->storyDir($story_node) : NULL;
      $animation = is_string($story) ? realpath($story . '/animation') : FALSE;
      $name = basename($relative);
      if ($animation === FALSE || !preg_match('/^(scene_\\d+\\.mp4|manifest\\.json)$/', $name)) {
        throw new \InvalidArgumentException('File is not available.');
      }
      $real = realpath($animation . '/' . $name);
      if ($real === FALSE || !str_starts_with($real, $animation . DIRECTORY_SEPARATOR)) {
        throw new \InvalidArgumentException('File is not available.');
      }
      return $real;
    }
    $root = realpath($job['job_dir']);
    if ($root === FALSE) {
      throw new \InvalidArgumentException('Job directory is missing.');
    }
    $candidate = $root . '/' . ltrim($relative, '/');
    $real = realpath($candidate);
    if ($real === FALSE || !str_starts_with($real, $root . DIRECTORY_SEPARATOR)) {
      throw new \InvalidArgumentException('File is not available.');
    }
    return $real;
  }

  private function syncFromDisk(array $row): array {
    $progress_path = $row['job_dir'] . '/progress.json';
    if (is_file($progress_path)) {
      $progress = json_decode((string) file_get_contents($progress_path), TRUE);
      if (is_array($progress) && !empty($progress['status']) && $progress['status'] !== $row['status']) {
        $this->database->update('story_pipeline_anim_job')
          ->fields([
            'status' => substr((string) $progress['status'], 0, 40),
            'message' => substr((string) ($progress['message'] ?? ''), 0, 1000),
          ])
          ->condition('job_id', $row['job_id'])
          ->execute();
        $row['status'] = $progress['status'];
        $row['message'] = $progress['message'] ?? '';
      }
      $row['clips'] = $progress['clips'] ?? [];
    }
    else {
      $row['clips'] = [];
    }
    $current_hash = hash('sha256', (string) $row['script']);
    $row['script_unchanged'] = hash_equals($current_hash, (string) $row['script_hash']);
    return $row;
  }

  /**
   * Scene breakdown captured with the job so names stay scene_1_2_3.
   */
  private function sceneText(NodeInterface $node): string {
    $dir = $this->assetStorage->storyDir($node);
    if (!is_string($dir) || $dir === '') {
      return '';
    }
    $path = $dir . '/scenes/scene.txt';
    if (!is_file($path)) {
      return '';
    }
    return (string) file_get_contents($path);
  }

  /**
   * @return resource
   */
  private function acquireLaunchLock(NodeInterface $node) {
    $dir = $this->assetStorage->storyDir($node);
    if (!is_string($dir) || $dir === '') {
      $dir = 'public://story-pipeline/animations/' . $node->id();
      $this->fileSystem->prepareDirectory($dir, FileSystemInterface::CREATE_DIRECTORY | FileSystemInterface::MODIFY_PERMISSIONS);
      $real = $this->fileSystem->realpath($dir);
      $dir = $real === FALSE ? sys_get_temp_dir() : $real;
    }
    $lock_dir = $dir . '/animations';
    if (!is_dir($lock_dir) && !mkdir($lock_dir, 0775, TRUE) && !is_dir($lock_dir)) {
      throw new \RuntimeException('Could not create the animation lock directory.');
    }
    $handle = fopen($lock_dir . '/.launch.lock', 'c');
    if ($handle === FALSE || !flock($handle, LOCK_EX)) {
      throw new \RuntimeException('Could not lock animation launch for this story.');
    }
    return $handle;
  }

  /**
   * @param resource $handle
   */
  private function releaseLaunchLock($handle): void {
    flock($handle, LOCK_UN);
    fclose($handle);
  }

  private function jobDirectory(NodeInterface $node, string $job_id): string {
    $folder = $this->assetStorage->storyDir($node);
    if (is_string($folder) && $folder !== '') {
      return $folder . '/animations/' . $job_id;
    }
    return 'public://story-pipeline/animations/' . $node->id() . '/' . $job_id;
  }

  /**
   * Parse scenes/scene.txt with the same Python loader the worker uses.
   *
   * @return array<string, mixed>
   */
  public function inspectSceneFile(NodeInterface $node, bool $include_text = FALSE): array {
    $dir = $this->assetStorage->storyDir($node);
    $path = is_string($dir) && $dir !== '' ? $dir . '/scenes/scene.txt' : '';
    if ($path === '' || !is_file($path)) {
      return [
        'ok' => FALSE,
        'error' => 'Saved scene file was not found at scenes/scene.txt. Finish the scene breakdown first. The Full story field was not used instead.',
        'path' => $path,
      ];
    }
    $python = $this->launcher->animationPython();
    $script = dirname($this->launcher->workerPath()) . '/animation-lab/map_story/scene_source.py';
    $command = [$python, $script, '--inspect', $path];
    if ($include_text) {
      $command[] = '--include-text';
    }
    $descriptor = [1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    $process = proc_open($command, $descriptor, $pipes);
    if (!is_resource($process)) {
      return ['ok' => FALSE, 'error' => 'Could not read the saved scene file.', 'path' => $path];
    }
    $stdout = stream_get_contents($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    $code = proc_close($process);
    $payload = json_decode((string) $stdout, TRUE);
    if ($code !== 0 || !is_array($payload)) {
      $detail = trim((string) $stderr);
      return [
        'ok' => FALSE,
        'error' => 'Could not parse the saved scene file.' . ($detail !== '' ? ' ' . $detail : ''),
        'path' => $path,
      ];
    }
    return $payload;
  }

  /**
   * Queue scene maps after the scene file is finalized. Never throws into the caller.
   */
  public function enqueueSceneMapsIfEnabled(NodeInterface $node): ?string {
    try {
      return $this->enqueueSceneMaps($node);
    }
    catch (\Throwable $error) {
      \Drupal::logger('story_pipeline')->error('Map scene enqueue did not start: @message', ['@message' => $error->getMessage()]);
      return NULL;
    }
  }

  private function enqueueSceneMaps(NodeInterface $node): ?string {
    if ((int) \Drupal::state()->get('story_pipeline.map_auto_scenes.' . (int) $node->id(), 0) !== 1) {
      return NULL;
    }
    $info = $this->inspectSceneFile($node, FALSE);
    if (empty($info['ok'])) {
      return NULL;
    }
    if ($this->activeJob((int) $node->id())) {
      return NULL;
    }
    $prompt = $this->currentPrompt('map');
    $theme_id = (string) \Drupal::state()->get('story_pipeline.map_theme_default', MapThemes::DEFAULT_ID);
    $theme = MapThemes::resolved($theme_id);
    $theme_hash = is_array($theme) ? (string) ($theme['theme_hash'] ?? '') : '';
    $key = $this->sceneGenerationKey((string) $info['sha256'], hash('sha256', (string) $prompt['body']), $theme_hash, 10, 'maplibre', 14);
    $state_key = 'story_pipeline.map_scene_enqueued.' . (int) $node->id();
    if (\Drupal::state()->get($state_key) === $key) {
      return NULL;
    }
    $account = \Drupal::currentUser();
    $job_id = $this->launch($node, $account, [
      'input_mode' => 'scene_breakdown',
      'animation_type' => 'map',
      'renderer' => 'maplibre',
      'max_selected_scenes' => 10,
      'duration_seconds' => 14,
      'language' => 'hi',
      'map_theme_id' => $theme_id,
      'map_theme_action' => 'job',
    ]);
    \Drupal::state()->set($state_key, $key);
    return $job_id;
  }

  private function sceneGenerationKey(string $source_hash, string $prompt_hash, string $theme_hash, int $limit, string $renderer, float $duration): string {
    $python = $this->launcher->animationPython();
    $script = dirname($this->launcher->workerPath()) . '/animation-lab/map_story/scene_source.py';
    $command = [
      $python, $script, '--enqueue-key',
      '--source-hash', $source_hash,
      '--prompt-hash', $prompt_hash,
      '--theme-hash', $theme_hash,
      '--limit', (string) $limit,
      '--renderer', $renderer,
      '--duration', (string) $duration,
    ];
    $descriptor = [1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    $process = proc_open($command, $descriptor, $pipes);
    if (!is_resource($process)) {
      return '';
    }
    $stdout = trim((string) stream_get_contents($pipes[1]));
    fclose($pipes[1]);
    fclose($pipes[2]);
    proc_close($process);
    return $stdout;
  }

}
