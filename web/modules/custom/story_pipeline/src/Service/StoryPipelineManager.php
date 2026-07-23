<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\Core\Config\ConfigFactoryInterface;
use Drupal\Core\Entity\EntityTypeManagerInterface;
use Drupal\Core\File\FileSystemInterface;
use Drupal\Core\Logger\LoggerChannelFactoryInterface;
use Drupal\Core\Url;
use Drupal\file\FileRepositoryInterface;
use Drupal\node\NodeInterface;
use Drupal\taxonomy\TermInterface;
use Drupal\story_pipeline\Service\CharacterLibrary;

/**
 * Business logic for Story Pipeline.
 */
class StoryPipelineManager {

  /**
   * Maps story_type machine keys to repo folder names.
   */
  private const TYPE_MAP = [
    'general' => 'general-story',
    'crime' => 'crime-section',
    'english' => 'english-story',
    'god_story' => 'general-story',
  ];

  /**
   * Master story-writing prompts (repo-relative paths).
   */
  private const MASTER_PROMPT_MAP = [
    'general' => 'story-making-prompts/v1-claude-latest-19june-with-charaacters',
    'crime' => 'story-making-prompts/crime-story-claude-8thjune',
    'english' => 'story-making-prompts/english-story-master',
    'god_story' => 'story-making-prompts/v1-claude-latest-19june-with-charaacters',
  ];

  /**
   * Bifurcated stage template filenames on Story Type terms.
   */
  private const STAGE_TEMPLATE_FILES = [
    'field_stage_a' => 'stage-a-story-config.md',
    'field_stage_b' => 'stage-b-scene-breakdown.md',
    'field_stage_c' => 'stage-c-image-motion.md',
    'field_default_characters' => 'character.txt',
  ];

  public function __construct(
    private readonly EntityTypeManagerInterface $entityTypeManager,
    private readonly FileRepositoryInterface $fileRepository,
    private readonly FileSystemInterface $fileSystem,
    private readonly ConfigFactoryInterface $configFactory,
    private readonly LoggerChannelFactoryInterface $loggerFactory,
    private readonly StoryPipelineAssetStorage $assetStorage,
    private readonly CharacterLibrary $characterLibrary,
  ) {}

  /**
   * Resolve story type term by machine name (general, crime, english, god_story).
   */
  public function loadStoryTypeTerm(string $machine): ?TermInterface {
    $label = match ($machine) {
      'general' => 'General',
      'crime' => 'Crime',
      'english' => 'English',
      'god_story' => 'God Story',
      default => NULL,
    };
    if (!$label) {
      return NULL;
    }
    $terms = $this->entityTypeManager->getStorage('taxonomy_term')
      ->loadByProperties(['vid' => 'story_type', 'name' => $label]);
    $term = $terms ? reset($terms) : NULL;
    return $term instanceof TermInterface ? $term : NULL;
  }

  /**
   * Get machine name from story type term.
   */
  public function getTypeMachine(TermInterface $term): string {
    return match ($term->label()) {
      'General' => 'general',
      'Crime' => 'crime',
      'English' => 'english',
      'God Story' => 'god_story',
      default => strtolower(preg_replace('/\s+/', '_', $term->label()) ?? 'general'),
    };
  }

  /**
   * Whether this story can generate Hindi and/or English narration.
   *
   * English audio options appear when Full story (English) has content.
   */
  public function supportsBilingualAudio(NodeInterface $node): bool {
    if ($node->bundle() !== 'story') {
      return FALSE;
    }
    if (!$node->hasField('field_full_story_english')) {
      return FALSE;
    }
    return trim(strip_tags((string) ($node->get('field_full_story_english')->value ?? ''))) !== '';
  }

  /**
   * ElevenLabs voice ID from the English Story Type taxonomy term (tid 3).
   */
  public function getEnglishVoiceId(): string {
    $term = $this->entityTypeManager->getStorage('taxonomy_term')->load(3);
    if (!$term instanceof TermInterface) {
      $term = $this->loadStoryTypeTerm('english');
    }
    if (!$term instanceof TermInterface || !$term->hasField('field_voice_id')) {
      return '';
    }
    return trim((string) ($term->get('field_voice_id')->value ?? ''));
  }

  /**
   * Build API response array for a story node.
   */
  public function serializeStory(NodeInterface $node): array {
    if ($node->bundle() !== 'story') {
      throw new \InvalidArgumentException('Not a story node.');
    }

    $term = $node->get('field_story_type')->entity;
    $type = $term instanceof TermInterface ? $this->getTypeMachine($term) : NULL;

    $urls = [];
    foreach ($node->get('field_youtube_urls') as $item) {
      if ($item->value) {
        $urls[] = $item->value;
      }
    }

    $prompt_url = NULL;
    $scene_url = NULL;
    $image_prompts_url = NULL;
    $story_asset_folder = NULL;
    $eleven_labs_urls = [];
    $eleven_labs_english_urls = [];

    if ($this->assetStorage->isEnabled()) {
      $index = $this->assetStorage->assetIndex($node);
      $story_asset_folder = $index['folder'] ?? NULL;
      $prompt_url = isset($index['files']['prompt'])
        ? $this->assetDownloadUrl($node, $index['files']['prompt']) : NULL;
      $scene_url = isset($index['files']['scene'])
        ? $this->assetDownloadUrl($node, $index['files']['scene']) : NULL;
      $image_prompts_url = isset($index['files']['image_prompts'])
        ? $this->assetDownloadUrl($node, $index['files']['image_prompts']) : NULL;
      if (!empty($index['files']['audio']) && is_array($index['files']['audio'])) {
        foreach ($index['files']['audio'] as $rel) {
          $url = $this->assetDownloadUrl($node, $rel);
          if ($url) {
            $eleven_labs_urls[] = $url;
          }
        }
      }
      if (!empty($index['files']['audio_english']) && is_array($index['files']['audio_english'])) {
        foreach ($index['files']['audio_english'] as $rel) {
          $url = $this->assetDownloadUrl($node, $rel);
          if ($url) {
            $eleven_labs_english_urls[] = $url;
          }
        }
      }
    }

    $prompt_file = $node->get('field_prompt_file')->entity;
    $scene_file = $node->get('field_scene_file')->entity;
    $image_prompts_file = $node->get('field_image_prompts_file')->entity;
    if (!$prompt_url && $prompt_file) {
      $prompt_url = \Drupal::service('file_url_generator')->generateAbsoluteString($prompt_file->getFileUri());
    }
    if (!$scene_url && $scene_file) {
      $scene_url = \Drupal::service('file_url_generator')->generateAbsoluteString($scene_file->getFileUri());
    }
    if (!$image_prompts_url && $image_prompts_file) {
      $image_prompts_url = \Drupal::service('file_url_generator')->generateAbsoluteString($image_prompts_file->getFileUri());
    }
    if ($eleven_labs_urls === []) {
      foreach ($node->get('field_eleven_labs_files') as $item) {
        $file = $item->entity;
        if ($file) {
          $eleven_labs_urls[] = \Drupal::service('file_url_generator')->generateAbsoluteString($file->getFileUri());
        }
      }
    }
    if ($eleven_labs_english_urls === [] && $node->hasField('field_eleven_labs_files_english')) {
      foreach ($node->get('field_eleven_labs_files_english') as $item) {
        $file = $item->entity;
        if ($file) {
          $eleven_labs_english_urls[] = \Drupal::service('file_url_generator')->generateAbsoluteString($file->getFileUri());
        }
      }
    }

    return [
      'id' => (string) $node->id(),
      'title' => $node->getTitle(),
      'story_type' => $type,
      'status' => $node->get('field_status')->value ?? 'draft',
      'youtube_urls' => $urls,
      'characters_info' => $node->get('field_characters_info')->value ?? '',
      'full_story' => $node->get('field_full_story')->value ?? '',
      'full_story_english' => $node->hasField('field_full_story_english')
        ? ($node->get('field_full_story_english')->value ?? '') : '',
      'bilingual' => $node->hasField('field_bilingual') ? (bool) $node->get('field_bilingual')->value : FALSE,
      'story_meta' => $node->get('field_story_meta')->value ?? '',
      'stage_a_output' => $node->get('field_stage_a_output')->value ?? '',
      'stage_b_output' => $node->get('field_stage_b_output')->value ?? '',
      'prompt_file_url' => $prompt_url,
      'scene_file_url' => $scene_url,
      'image_prompts_file_url' => $image_prompts_url,
      'eleven_labs_file_urls' => $eleven_labs_urls,
      'eleven_labs_file_urls_english' => $eleven_labs_english_urls,
      'story_asset_folder' => $story_asset_folder,
    ];
  }

  /**
   * Build worker bundle payload.
   */
  public function buildBundle(NodeInterface $node, string $pipeline = 'storyboard'): array {
    $term = $node->get('field_story_type')->entity;
    if (!$term instanceof TermInterface) {
      throw new \InvalidArgumentException('Story has no story type.');
    }

    $type = $this->getTypeMachine($term);
    $settings_raw = $term->get('field_pipeline_settings')->value ?? '{}';
    $settings = json_decode($settings_raw, TRUE) ?: [];
    $voice_id = $term->hasField('field_voice_id')
      ? trim((string) ($term->get('field_voice_id')->value ?? ''))
      : '';
    if ($voice_id !== '') {
      $settings['voice_id'] = $voice_id;
    }
    $english_voice_id = $this->getEnglishVoiceId();
    if ($english_voice_id !== '') {
      $settings['english_voice_id'] = $english_voice_id;
    }

    $characters = $node->get('field_characters_info')->value ?? '';
    if ($characters === '' && $term->hasField('field_default_characters')) {
      $characters = $term->get('field_default_characters')->value ?? '';
    }
    if ($characters === '' && $this->characterLibrary) {
      $roster = $this->characterLibrary->loadRoster($node);
      $library_nids = [];
      foreach ($roster as $item) {
        if (!empty($item['library_nid'])) {
          $library_nids[] = (int) $item['library_nid'];
        }
      }
      if ($library_nids !== []) {
        $characters = $this->characterLibrary->exportCharacterTxt($library_nids);
      }
    }

    return [
      'story' => [
        'id' => (string) $node->id(),
        'title' => $node->getTitle(),
        'full_story' => $node->get('field_full_story')->value ?? '',
        'full_story_english' => $node->hasField('field_full_story_english')
          ? ($node->get('field_full_story_english')->value ?? '') : '',
        'bilingual' => $node->hasField('field_bilingual') ? (bool) $node->get('field_bilingual')->value : FALSE,
        'characters_info' => $characters,
        'story_type' => $type,
        'youtube_urls' => array_column($node->get('field_youtube_urls')->getValue(), 'value'),
        'story_meta' => $node->get('field_story_meta')->value ?? '',
      ],
      'prompts' => [
        'master_prompt' => $term->get('field_master_prompt')->value ?? '',
        'stage_a' => $term->get('field_stage_a')->value ?? '',
        'stage_b' => $term->get('field_stage_b')->value ?? '',
        'stage_c' => $term->get('field_stage_c')->value ?? '',
        'characters' => $term->get('field_default_characters')->value ?? '',
      ],
      'settings' => array_merge([
        'model' => 'deepseek-v4-pro',
        'scene_batch' => 8,
        'max_tokens_a' => 65536,
        'max_tokens_b' => 131072,
        'max_tokens_c' => 65536,
      ], $settings),
      'api_keys' => $this->getApiKeysForStoryType($type),
      'pipeline' => $pipeline,
      'story_asset_path' => $this->assetStorage->rootPath(),
      'prior_artifacts' => [
        'story_config' => $node->get('field_stage_a_output')->value ?? NULL,
        'scene_breakdown' => $node->get('field_stage_b_output')->value ?? NULL,
        'prompt_full' => NULL,
      ],
    ];
  }

  /**
   * Create a story node from API payload.
   */
  public function createStory(array $data): NodeInterface {
    $term = $this->loadStoryTypeTerm($data['story_type'] ?? '');
    if (!$term) {
      throw new \InvalidArgumentException('Invalid story_type. Use: general, crime, english, god_story.');
    }

    $values = [
      'type' => 'story',
      'title' => $data['title'] ?? 'Untitled Story',
      'field_story_type' => ['target_id' => $term->id()],
      'field_status' => ['value' => 'draft'],
    ];

    if (!empty($data['characters_info'])) {
      $values['field_characters_info'] = ['value' => $data['characters_info']];
    }
    if (!empty($data['full_story'])) {
      $values['field_full_story'] = ['value' => $data['full_story']];
      $values['field_status'] = ['value' => 'story_generated'];
    }

    $node = $this->entityTypeManager->getStorage('node')->create($values);
    if (!empty($data['youtube_urls']) && is_array($data['youtube_urls'])) {
      $node->set('field_youtube_urls', array_map(fn($u) => ['value' => $u], $data['youtube_urls']));
    }
    $node->save();
    return $node;
  }

  /**
   * Update story fields from worker callback.
   */
  public function updateStoryFromWorker(NodeInterface $node, array $data): NodeInterface {
    $map = [
      'full_story' => 'field_full_story',
      'full_story_english' => 'field_full_story_english',
      'story_meta' => 'field_story_meta',
      'stage_a_output' => 'field_stage_a_output',
      'stage_b_output' => 'field_stage_b_output',
      'characters_info' => 'field_characters_info',
      'status' => 'field_status',
    ];
    foreach ($map as $key => $field) {
      if (array_key_exists($key, $data)) {
        $node->set($field, ['value' => $data[$key]]);
      }
    }

    if ($this->assetStorage->isEnabled()) {
      $slug = $this->assetStorage->slugify($node->getTitle(), 'story-' . $node->id());
      if (array_key_exists('full_story', $data) && (string) $data['full_story'] !== '') {
        $plain = strip_tags((string) $data['full_story']);
        $this->assetStorage->saveText($node, 'script', 'FULL_STORY.txt', $plain);
      }
      if (array_key_exists('full_story_english', $data) && (string) $data['full_story_english'] !== '') {
        $plain = strip_tags((string) $data['full_story_english']);
        $this->assetStorage->saveText($node, 'script', 'FULL_STORY_ENGLISH.txt', $plain);
      }
      if (array_key_exists('story_meta', $data) && (string) $data['story_meta'] !== '') {
        $this->assetStorage->saveText($node, 'script', 'story_meta.txt', (string) $data['story_meta']);
      }
      $this->assetStorage->syncRawStoryFile($node);
      if (!empty($data['stage_a_output'])) {
        $this->assetStorage->saveText($node, 'prompts', 'output_config_' . $slug . '.md', (string) $data['stage_a_output']);
      }
      if (!empty($data['stage_b_output'])) {
        $this->assetStorage->saveText($node, 'scenes', 'output_story_breakdown_' . $slug . '.md', (string) $data['stage_b_output']);
      }
    }

    if (!empty($data['prompt_file_content'])) {
      $this->attachFile($node, 'field_prompt_file', $data['prompt_file_content'], 'prompt.txt');
    }
    if (!empty($data['scene_file_content'])) {
      $this->attachFile($node, 'field_scene_file', $data['scene_file_content'], 'scene.txt');
    }
    if (!empty($data['image_prompts_file_content'])) {
      $this->attachFile($node, 'field_image_prompts_file', $data['image_prompts_file_content'], 'image-prompts-only.txt');
    }
    if (!empty($data['eleven_labs_files']) && is_array($data['eleven_labs_files'])) {
      $this->attachBinaryFiles($node, 'field_eleven_labs_files', $data['eleven_labs_files'], 'audio');
    }
    if (!empty($data['eleven_labs_files_english']) && is_array($data['eleven_labs_files_english'])) {
      $this->attachBinaryFiles($node, 'field_eleven_labs_files_english', $data['eleven_labs_files_english'], 'audio/english');
    }

    if ($this->assetStorage->isEnabled()) {
      $this->syncAssetFilesToNodeFields($node);
    }

    $node->save();
    return $node;
  }

  /**
   * Attach text content as a managed file on the node (and mirror to story-asset).
   */
  public function attachFile(NodeInterface $node, string $field_name, string $content, string $filename): void {
    $directory = 'public://story-pipeline';
    $this->fileSystem->prepareDirectory($directory, FileSystemInterface::CREATE_DIRECTORY | FileSystemInterface::MODIFY_PERMISSIONS);
    $uri = $directory . '/' . $node->id() . '-' . $filename;
    $file = $this->fileRepository->writeData($content, $uri, FileSystemInterface::EXISTS_REPLACE);
    $node->set($field_name, ['target_id' => $file->id()]);

    if ($this->assetStorage->isEnabled()) {
      $subdir = match ($filename) {
        'prompt.txt' => 'prompts',
        'scene.txt' => 'scenes',
        'image-prompts-only.txt' => 'image-prompts',
        default => 'files',
      };
      $this->assetStorage->saveText($node, $subdir, $filename, $content);
    }
  }

  /**
   * Attach multiple binary files (base64) to a multi-value file field.
   *
   * Each item: ['filename' => 'scene-01.mp3', 'content_base64' => '...'].
   */
  public function attachBinaryFiles(NodeInterface $node, string $field_name, array $files, string $asset_subdir = 'audio'): void {
    $directory = $field_name === 'field_eleven_labs_files_english'
      ? 'public://story-pipeline/eleven-labs-english'
      : 'public://story-pipeline/eleven-labs';
    $this->fileSystem->prepareDirectory($directory, FileSystemInterface::CREATE_DIRECTORY | FileSystemInterface::MODIFY_PERMISSIONS);

    $items = [];
    foreach ($files as $entry) {
      if (!is_array($entry)) {
        continue;
      }
      $filename = basename((string) ($entry['filename'] ?? 'audio.mp3'));
      $raw = base64_decode((string) ($entry['content_base64'] ?? ''), TRUE);
      if ($raw === FALSE || $raw === '') {
        continue;
      }
      $uri = $directory . '/' . $node->id() . '-' . $filename;
      $file = $this->fileRepository->writeData($raw, $uri, FileSystemInterface::EXISTS_REPLACE);
      $items[] = ['target_id' => $file->id()];

      if ($this->assetStorage->isEnabled()) {
        $this->assetStorage->saveBinary($node, $asset_subdir, $filename, $raw);
      }
    }

    if ($items !== []) {
      $node->set($field_name, $items);
    }
  }

  /**
   * Fill empty Drupal file fields from files already on disk in story-asset.
   */
  public function syncAssetFilesToNodeFields(NodeInterface $node): bool {
    if (!$this->assetStorage->isEnabled() || $node->bundle() !== 'story') {
      return FALSE;
    }

    $index = $this->assetStorage->assetIndex($node);
    if (empty($index['files'])) {
      return FALSE;
    }

    $changed = FALSE;
    $map = [
      'prompt' => ['field' => 'field_prompt_file', 'filename' => 'prompt.txt'],
      'scene' => ['field' => 'field_scene_file', 'filename' => 'scene.txt'],
      'image_prompts' => ['field' => 'field_image_prompts_file', 'filename' => 'image-prompts-only.txt'],
    ];

    foreach ($map as $key => $info) {
      if (!isset($index['files'][$key]) || !$node->get($info['field'])->isEmpty()) {
        continue;
      }
      $path = $this->assetStorage->resolveRelativePath($node, $index['files'][$key]);
      if ($path === NULL || !is_readable($path)) {
        continue;
      }
      $content = file_get_contents($path);
      if ($content === FALSE || $content === '') {
        continue;
      }
      $this->attachFile($node, $info['field'], $content, $info['filename']);
      $changed = TRUE;
    }

    if ($node->get('field_eleven_labs_files')->isEmpty() && !empty($index['files']['audio']) && is_array($index['files']['audio'])) {
      $entries = [];
      foreach ($index['files']['audio'] as $rel) {
        $path = $this->assetStorage->resolveRelativePath($node, $rel);
        if ($path === NULL || !is_readable($path)) {
          continue;
        }
        $raw = file_get_contents($path);
        if ($raw === FALSE || $raw === '') {
          continue;
        }
        $entries[] = [
          'filename' => basename($path),
          'content_base64' => base64_encode($raw),
        ];
      }
      if ($entries !== []) {
        $this->attachBinaryFiles($node, 'field_eleven_labs_files', $entries, 'audio');
        $changed = TRUE;
      }
    }

    if ($node->hasField('field_eleven_labs_files_english')
      && $node->get('field_eleven_labs_files_english')->isEmpty()
      && !empty($index['files']['audio_english'])
      && is_array($index['files']['audio_english'])) {
      $entries = [];
      foreach ($index['files']['audio_english'] as $rel) {
        $path = $this->assetStorage->resolveRelativePath($node, $rel);
        if ($path === NULL || !is_readable($path)) {
          continue;
        }
        $raw = file_get_contents($path);
        if ($raw === FALSE || $raw === '') {
          continue;
        }
        $entries[] = [
          'filename' => basename($path),
          'content_base64' => base64_encode($raw),
        ];
      }
      if ($entries !== []) {
        $this->attachBinaryFiles($node, 'field_eleven_labs_files_english', $entries, 'audio/english');
        $changed = TRUE;
      }
    }

    if ($changed) {
      $node->save();
    }

    return $changed;
  }

  /**
   * Mark story as queued for pipeline (worker picks up via status).
   */
  public function queueGenerateStory(NodeInterface $node): NodeInterface {
    if ($node->get('field_youtube_urls')->isEmpty()) {
      throw new \InvalidArgumentException('Story needs at least one YouTube URL.');
    }
    $node->set('field_story_meta', ['value' => 'QUEUE:generate-story']);
    $node->save();
    return $node;
  }

  /**
   * Mark story for storyboard pipeline.
   */
  public function queueStoryboard(NodeInterface $node, int $max_step = 4): NodeInterface {
    if ($node->get('field_full_story')->isEmpty()) {
      throw new \InvalidArgumentException('Story needs full_story before storyboard.');
    }
    $meta = json_encode(['QUEUE' => 'run-storyboard', 'max_step' => $max_step]);
    $node->set('field_status', 'storyboard_running');
    $node->set('field_story_meta', ['value' => $meta]);
    $node->save();
    return $node;
  }

  /**
   * API keys for a story type — all types share pipeline_api_keys from config.
   */
  public function getApiKeysForStoryType(string $machine): array {
    $config = $this->configFactory->get('story_pipeline.settings');
    $stored = $config->get('pipeline_api_keys') ?? [];
    if (!is_array($stored)) {
      $stored = [];
    }

    // Backward compat: if global keys empty, fall back to per-type crime/general keys.
    if (($stored['deepseek_api_key'] ?? '') === ''
      && ($stored['anthropic_api_key'] ?? '') === ''
      && ($stored['elevenlabs_api_key'] ?? '') === '') {
      $legacy = $config->get("story_type_keys.$machine") ?? $config->get('story_type_keys.crime') ?? [];
      if (is_array($legacy) && $legacy !== []) {
        $stored = $legacy;
      }
    }

    return [
      'deepseek_api_key' => (string) ($stored['deepseek_api_key'] ?? ''),
      'anthropic_api_key' => (string) ($stored['anthropic_api_key'] ?? ''),
      'elevenlabs_api_key' => (string) ($stored['elevenlabs_api_key'] ?? ''),
    ];
  }

  /**
   * Whether required keys are set for a pipeline run.
   */
  public function hasRequiredKeys(string $machine, string $pipeline): array {
    $keys = $this->getApiKeysForStoryType($machine);
    $missing = [];
    if ($pipeline === 'generate' || $pipeline === 'generate-story') {
      if ($keys['anthropic_api_key'] === '' && $keys['deepseek_api_key'] === '') {
        $missing[] = 'anthropic_api_key or deepseek_api_key';
      }
    }
    if ($pipeline === 'storyboard' || $pipeline === 'run-storyboard') {
      if ($keys['deepseek_api_key'] === '') {
        $missing[] = 'deepseek_api_key';
      }
    }
    return $missing;
  }

  /**
   * Mask a secret for admin display (last 4 chars only).
   */
  public function maskKey(string $key): string {
    if ($key === '') {
      return '';
    }
    if (strlen($key) <= 4) {
      return '****';
    }
    return '…' . substr($key, -4);
  }

  /**
   * Admin download URL for a file in story_asset_path.
   */
  private function assetDownloadUrl(NodeInterface $node, string $relative): ?string {
    if ($this->assetStorage->resolveRelativePath($node, $relative) === NULL) {
      return NULL;
    }
    return Url::fromRoute('story_pipeline.download_asset', ['node' => $node->id()], [
      'query' => ['f' => $relative],
    ])->toString();
  }

  /**
   * Import pipeline API keys from automation repo .env into Drupal config.
   *
   * Only fills keys that are empty in config unless $overwrite is TRUE.
   *
   * @return array<string, string> field => imported|skipped|missing
   */
  public function importKeysFromEnv(?string $repo_path = NULL, bool $overwrite = FALSE): array {
    $repo_path = $repo_path ?: $this->configFactory->get('story_pipeline.settings')->get('automation_repo_path');
    if (!$repo_path || !is_dir($repo_path)) {
      throw new \RuntimeException('Automation repo path not found: ' . $repo_path);
    }

    $env_path = $repo_path . '/.env';
    if (!is_readable($env_path)) {
      throw new \RuntimeException('.env not found: ' . $env_path);
    }

    $env = $this->parseDotEnv($env_path);
    $map = [
      'deepseek_api_key' => ['DEEPSEEK_API_KEY'],
      'anthropic_api_key' => ['ANTHROPIC_API_KEY', 'anthropic_api_key'],
      'elevenlabs_api_key' => ['ELEVENLABS_API_KEY', 'eleven_labs_api_key', 'ELEVEN_LABS_API_KEY'],
    ];

    $config = $this->configFactory->getEditable('story_pipeline.settings');
    $report = [];

    foreach ($map as $field => $env_names) {
      $current = (string) ($config->get("pipeline_api_keys.$field") ?? '');
      $found = '';
      foreach ($env_names as $env_name) {
        if (!empty($env[$env_name])) {
          $found = trim((string) $env[$env_name]);
          break;
        }
      }

      if ($found === '') {
        $report[$field] = 'missing in .env';
        continue;
      }

      if (!$overwrite && $current !== '') {
        $report[$field] = 'skipped (already set)';
        continue;
      }

      $config->set("pipeline_api_keys.$field", $found);
      $report[$field] = 'imported';
    }

    $config->save();
    return $report;
  }

  /**
   * Parse a simple KEY=VALUE .env file.
   *
   * @return array<string, string>
   */
  private function parseDotEnv(string $path): array {
    $out = [];
    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    if ($lines === FALSE) {
      return $out;
    }
    foreach ($lines as $line) {
      $line = trim($line);
      if ($line === '' || str_starts_with($line, '#')) {
        continue;
      }
      if (!str_contains($line, '=')) {
        continue;
      }
      [$name, $value] = explode('=', $line, 2);
      $name = trim($name);
      $value = trim($value);
      if ($value !== '' && (($value[0] === '"' && str_ends_with($value, '"')) || ($value[0] === "'" && str_ends_with($value, "'")))) {
        $value = substr($value, 1, -1);
      }
      $out[$name] = $value;
    }
    return $out;
  }

  /**
   * Import prompts from automation repo into taxonomy terms.
   */
  public function importPrompts(?string $repo_path = NULL): array {
    $repo_path = $repo_path ?: $this->configFactory->get('story_pipeline.settings')->get('automation_repo_path');
    if (!$repo_path || !is_dir($repo_path)) {
      throw new \RuntimeException('Automation repo path not found: ' . $repo_path);
    }

    $report = [];
    foreach (self::TYPE_MAP as $machine => $folder) {
      $term = $this->loadStoryTypeTerm($machine);
      if (!$term) {
        $report[$machine] = 'term not found';
        continue;
      }

      foreach (self::STAGE_TEMPLATE_FILES as $field => $filename) {
        $path = $this->resolveBifurcatedTemplatePath($repo_path, $folder, $filename);
        if ($path) {
          $term->set($field, ['value' => file_get_contents($path)]);
        }
      }

      $master_rel = self::MASTER_PROMPT_MAP[$machine] ?? '';
      $master_path = $master_rel !== '' ? $repo_path . '/' . $master_rel : '';
      if ($master_path !== '' && is_readable($master_path)) {
        $term->set('field_master_prompt', ['value' => file_get_contents($master_path)]);
      }

      $ini_path = $repo_path . '/' . $folder . '/deepseek.config.example.ini';
      if (is_readable($ini_path)) {
        $term->set('field_pipeline_settings', ['value' => $this->iniToJson($ini_path)]);
      }

      $term->save();
      $report[$machine] = 'imported';
    }

    return $report;
  }

  /**
   * Resolve a bifurcated template file (automation repo, then CMS module bundle).
   */
  public function resolveBifurcatedTemplatePath(string $repo_path, string $folder, string $filename): ?string {
    $candidates = [
      $repo_path . '/' . $folder . '/bifuracted-template/' . $filename,
    ];
    if ($folder === 'general-story') {
      $candidates[] = $this->modulePath() . '/prompts/general-story/bifuracted-template/' . $filename;
    }
    foreach ($candidates as $path) {
      if (is_readable($path)) {
        return $path;
      }
    }
    return NULL;
  }

  /**
   * Absolute path to the story_pipeline module directory.
   */
  private function modulePath(): string {
    return \Drupal::service('extension.list.module')->getPath('story_pipeline');
  }

  /**
   * Convert key INI values to JSON for pipeline settings field.
   */
  private function iniToJson(string $ini_path): string {
    $parsed = parse_ini_file($ini_path, TRUE, INI_SCANNER_RAW) ?: [];
    $tokens = $parsed['token_budget'] ?? [];
    $conn = $parsed['deepseek_connection'] ?? [];
    $out = [
      'model' => $conn['model'] ?? 'deepseek-v4-pro',
      'scene_batch' => (int) ($tokens['scene_batch'] ?? 8),
      'max_tokens_a' => (int) ($tokens['max_tokens_stage_a'] ?? 65536),
      'max_tokens_b' => (int) ($tokens['max_tokens_stage_b'] ?? 131072),
      'max_tokens_c' => (int) ($tokens['max_tokens_stage_c'] ?? 65536),
    ];
    return json_encode($out, JSON_PRETTY_PRINT);
  }

  /**
   * List stories waiting for worker (meta contains QUEUE:).
   */
  public function listQueuedStories(): array {
    $storage = $this->entityTypeManager->getStorage('node');
    $ids = $storage->getQuery()
      ->accessCheck(FALSE)
      ->condition('type', 'story')
      ->condition('field_story_meta', 'QUEUE:', 'STARTS_WITH')
      ->range(0, 10)
      ->execute();
    $nodes = $storage->loadMultiple($ids);
    $out = [];
    foreach ($nodes as $node) {
      $out[] = $this->serializeStory($node);
    }
    return $out;
  }

}
