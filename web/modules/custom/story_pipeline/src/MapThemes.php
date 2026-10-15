<?php

declare(strict_types=1);

namespace Drupal\story_pipeline;

/**
 * Built-in map appearance templates exported from the animation lab.
 */
final class MapThemes {

  public const DEFAULT_ID = 'documentary_relief_bold';

  public static function path(): string {
    return dirname(\Drupal::root()) . '/animation-lab/assets/maps/themes/builtin.json';
  }

  public static function document(): array {
    $path = self::path();
    if (!is_file($path)) {
      return ['schema_version' => 1, 'default_theme_id' => self::DEFAULT_ID, 'themes' => [], 'fonts' => []];
    }
    $decoded = json_decode((string) file_get_contents($path), TRUE);
    return is_array($decoded) ? $decoded : ['themes' => []];
  }

  /**
   * @return array<string, array<string, mixed>>
   */
  public static function builtins(): array {
    $themes = [];
    foreach (self::document()['themes'] ?? [] as $theme) {
      if (is_array($theme) && !empty($theme['id'])) {
        $themes[(string) $theme['id']] = $theme;
      }
    }
    return $themes;
  }

  public static function resolved(string $id): ?array {
    $theme = self::builtins()[$id] ?? NULL;
    if (!is_array($theme)) {
      return NULL;
    }
    $resolved = $theme['resolved'] ?? NULL;
    return is_array($resolved) ? $resolved : NULL;
  }

  /**
   * @return array<string, string>
   */
  public static function options(): array {
    $options = [];
    foreach (self::builtins() as $id => $theme) {
      $options[$id] = (string) ($theme['name'] ?? $id);
    }
    return $options;
  }

  /**
   * @return list<string>
   */
  public static function fonts(): array {
    $fonts = self::document()['fonts'] ?? [];
    return is_array($fonts) ? array_values(array_map('strval', $fonts)) : [];
  }

}
