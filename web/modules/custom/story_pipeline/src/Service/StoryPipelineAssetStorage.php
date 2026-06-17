<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Service;

use Drupal\Core\Config\ConfigFactoryInterface;
use Drupal\node\NodeInterface;
use Drupal\taxonomy\TermInterface;

/**
 * Saves story pipeline files under story_asset_path/{type}/{slug}/ on disk.
 */
class StoryPipelineAssetStorage {

  private const VALID_TYPES = ['general', 'crime', 'english', 'god_story'];

  public function __construct(
    private readonly ConfigFactoryInterface $configFactory,
  ) {}

  /**
   * Configured root, e.g. /Users/averma/project/story-asset.
   */
  public function rootPath(): ?string {
    $path = trim((string) $this->configFactory->get('story_pipeline.settings')->get('story_asset_path'));
    if ($path === '') {
      return NULL;
    }
    $real = realpath($path);
    if ($real !== FALSE) {
      return $real;
    }
    if (@mkdir($path, 0775, TRUE) || is_dir($path)) {
      $real = realpath($path);
      return $real !== FALSE ? $real : $path;
    }
    return NULL;
  }

  /**
   * Whether external asset storage is enabled.
   */
  public function isEnabled(): bool {
    return $this->rootPath() !== NULL;
  }

  /**
   * Slug from node title (matches worker workspace.slugify).
   */
  public function slugify(string $text, string $fallback = 'story'): string {
    $text = html_entity_decode(strip_tags($text), ENT_QUOTES | ENT_HTML5, 'UTF-8');
    $text = strtolower(trim($text));
    $text = preg_replace('/[^a-z0-9]+/', '-', $text) ?? '';
    $text = trim($text, '-');
    $text = substr($text, 0, 64);
    return $text !== '' ? $text : $fallback;
  }

  /**
   * Machine name from story type term (general, crime, english, god_story).
   */
  public function storyTypeMachine(NodeInterface $node): string {
    $term = $node->get('field_story_type')->entity;
    if (!$term instanceof TermInterface) {
      return 'general';
    }
    $machine = match ($term->label()) {
      'General' => 'general',
      'Crime' => 'crime',
      'English' => 'english',
      'God Story' => 'god_story',
      default => strtolower(preg_replace('/\s+/', '_', $term->label()) ?? 'general'),
    };
    return in_array($machine, self::VALID_TYPES, TRUE) ? $machine : 'general';
  }

  /**
   * Absolute path to one story's asset folder.
   */
  public function storyDir(NodeInterface $node): ?string {
    $root = $this->rootPath();
    if ($root === NULL || $node->bundle() !== 'story') {
      return NULL;
    }

    $slug = $this->slugify($node->getTitle(), 'story-' . $node->id());
    $type = $this->storyTypeMachine($node);
    $type_root = $root . DIRECTORY_SEPARATOR . $type;
    $dest = $type_root . DIRECTORY_SEPARATOR . $slug;
    $legacy = $root . DIRECTORY_SEPARATOR . $slug;
    $meta_id = $dest . DIRECTORY_SEPARATOR . 'meta' . DIRECTORY_SEPARATOR . 'drupal-node-id.txt';

    if (!is_dir($dest) && is_dir($legacy)) {
      $legacy_meta = $legacy . DIRECTORY_SEPARATOR . 'meta' . DIRECTORY_SEPARATOR . 'drupal-node-id.txt';
      if (is_file($legacy_meta)) {
        $existing = trim((string) file_get_contents($legacy_meta));
        if ($existing === '' || $existing === (string) $node->id()) {
          $dest = $legacy;
          $meta_id = $legacy_meta;
        }
      }
    }

    if (is_dir($dest) && is_file($meta_id)) {
      $existing = trim((string) file_get_contents($meta_id));
      if ($existing !== '' && $existing !== (string) $node->id()) {
        $dest = $type_root . DIRECTORY_SEPARATOR . $slug . '-' . $node->id();
      }
    }
    elseif (is_dir($dest) && !is_file($meta_id)) {
      $dest = $type_root . DIRECTORY_SEPARATOR . $slug . '-' . $node->id();
    }

    if (!is_dir($type_root)) {
      mkdir($type_root, 0775, TRUE);
    }

    foreach (['meta', 'script', 'prompts', 'scenes', 'image-prompts', 'audio'] as $sub) {
      $dir = $dest . DIRECTORY_SEPARATOR . $sub;
      if (!is_dir($dir)) {
        mkdir($dir, 0775, TRUE);
      }
    }

    $meta_dir = $dest . DIRECTORY_SEPARATOR . 'meta';
    if (!is_dir($meta_dir)) {
      mkdir($meta_dir, 0775, TRUE);
    }
    file_put_contents($meta_dir . DIRECTORY_SEPARATOR . 'drupal-node-id.txt', (string) $node->id() . "\n");
    file_put_contents($meta_dir . DIRECTORY_SEPARATOR . 'story-title.txt', $node->getTitle() . "\n");
    file_put_contents($meta_dir . DIRECTORY_SEPARATOR . 'story-type.txt', $type . "\n");

    return $dest;
  }

  /**
   * Write a text file under a story folder subdir.
   */
  public function saveText(NodeInterface $node, string $subdir, string $filename, string $content): ?string {
    $story_dir = $this->storyDir($node);
    if ($story_dir === NULL) {
      return NULL;
    }
    $dir = $story_dir . DIRECTORY_SEPARATOR . $subdir;
    if (!is_dir($dir)) {
      mkdir($dir, 0775, TRUE);
    }
    $path = $dir . DIRECTORY_SEPARATOR . $filename;
    file_put_contents($path, $content);
    return $path;
  }

  /**
   * Write binary file under a story folder subdir.
   */
  public function saveBinary(NodeInterface $node, string $subdir, string $filename, string $raw): ?string {
    return $this->saveText($node, $subdir, $filename, $raw);
  }

  /**
   * List known asset files for API / UI.
   *
   * @return array<string, mixed>
   */
  public function assetIndex(NodeInterface $node): array {
    $dir = $this->storyDir($node);
    if ($dir === NULL || !is_dir($dir)) {
      return [];
    }

    $index = [
      'folder' => $dir,
      'files' => [],
    ];

    $map = [
      'script/FULL_STORY.txt' => 'full_story',
      'script/story_meta.txt' => 'story_meta',
      'prompts/prompt.txt' => 'prompt',
      'scenes/scene.txt' => 'scene',
      'image-prompts/image-prompts-only.txt' => 'image_prompts',
    ];

    foreach ($map as $rel => $key) {
      $full = $dir . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $rel);
      if (is_file($full)) {
        $index['files'][$key] = $rel;
      }
    }

    $audio_dir = $dir . DIRECTORY_SEPARATOR . 'audio';
    if (is_dir($audio_dir)) {
      $audio = [];
      foreach (glob($audio_dir . DIRECTORY_SEPARATOR . '*.mp3') ?: [] as $mp3) {
        $audio[] = 'audio/' . basename($mp3);
      }
      if ($audio !== []) {
        $index['files']['audio'] = $audio;
      }
    }

    return $index;
  }

  /**
   * Resolve relative path inside story folder; blocks traversal.
   */
  public function resolveRelativePath(NodeInterface $node, string $relative): ?string {
    $dir = $this->storyDir($node);
    if ($dir === NULL) {
      return NULL;
    }
    $relative = str_replace('\\', '/', $relative);
    $relative = ltrim($relative, '/');
    if ($relative === '' || str_contains($relative, '..')) {
      return NULL;
    }
    $full = $dir . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $relative);
    $real_dir = realpath($dir);
    $real_full = realpath($full);
    if ($real_dir === FALSE || $real_full === FALSE || !str_starts_with($real_full, $real_dir)) {
      return is_file($full) ? $full : NULL;
    }
    return is_file($real_full) ? $real_full : NULL;
  }

}
