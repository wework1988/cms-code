<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Commands;

use Drupal\story_pipeline\Service\StoryPipelineManager;
use Drupal\story_pipeline\Service\CharacterLibrary;
use Drush\Commands\DrushCommands;

/**
 * Drush commands for Story Pipeline.
 */
class StoryPipelineCommands extends DrushCommands {

  public function __construct(
    private readonly StoryPipelineManager $manager,
    private readonly CharacterLibrary $characterLibrary,
  ) {
    parent::__construct();
  }

  /**
   * Import prompts from automation repo into Story Type taxonomy terms.
   *
   * @command story-pipeline:import-prompts
   * @aliases sp-import
   * @option repo-path Override automation repo path
   * @usage drush story-pipeline:import-prompts
   * @usage drush story-pipeline:import-prompts --repo-path=/path/to/repo
   */
  public function importPrompts($options = ['repo-path' => NULL]): void {
    $repo = $options['repo-path'] ?? NULL;
    try {
      $report = $this->manager->importPrompts($repo ?: NULL);
      foreach ($report as $type => $status) {
        $this->io()->writeln("$type: $status");
      }
      $this->io()->success('Prompt import finished.');
    }
    catch (\Throwable $e) {
      $this->io()->error($e->getMessage());
    }
  }

  /**
   * Import pipeline API keys from automation repo .env into Drupal config.
   *
   * @command story-pipeline:import-keys
   * @aliases sp-import-keys
   * @option repo-path Override automation repo path
   * @option overwrite Replace keys already saved in Drupal
   * @usage drush story-pipeline:import-keys
   * @usage drush story-pipeline:import-keys --overwrite
   */
  public function importKeys($options = ['repo-path' => NULL, 'overwrite' => FALSE]): void {
    $repo = $options['repo-path'] ?? NULL;
    try {
      $report = $this->manager->importKeysFromEnv($repo ?: NULL, (bool) $options['overwrite']);
      foreach ($report as $field => $status) {
        $this->io()->writeln("$field: $status");
      }
      $this->io()->success('Key import finished. View at /admin/config/content/story-pipeline');
    }
    catch (\Throwable $e) {
      $this->io()->error($e->getMessage());
    }
  }

  /**
   * Show Story Pipeline API key and endpoints.
   *
   * @command story-pipeline:info
   * @aliases sp-info
   */
  public function info(): void {
    $config = \Drupal::config('story_pipeline.settings');
    $manager = \Drupal::service('story_pipeline.manager');
    $this->io()->title('Story Pipeline');
    $this->io()->writeln('Drupal API key: ' . $config->get('api_key'));
    $this->io()->writeln('Repo path: ' . $config->get('automation_repo_path'));
    $this->io()->section('Pipeline API keys (all story types, masked)');
    $keys = $manager->getApiKeysForStoryType('crime');
    foreach ($keys as $name => $value) {
      $status = $value === '' ? '(not set — worker falls back to .env)' : $manager->maskKey($value);
      $this->io()->writeln('  ' . $name . ': ' . $status);
    }
    $this->io()->section('Endpoints');
    $this->io()->writeln('POST /api/story-pipeline/stories');
    $this->io()->writeln('GET  /api/story-pipeline/stories/{id}');
    $this->io()->writeln('GET  /api/story-pipeline/stories/{id}/bundle');
    $this->io()->writeln('POST /api/story-pipeline/generate-story');
    $this->io()->writeln('POST /api/story-pipeline/run-storyboard');
    $this->io()->writeln('POST /api/story-pipeline/stories/{id}/update');
    $this->io()->writeln('Header: X-Story-Pipeline-Key: <api_key>');
  }

  /**
   * Import character.txt into the character library.
   *
   * @command story-pipeline:import-characters
   * @aliases sp-import-chars
   * @option file Path to character.txt (default: general-story/bifuracted-template/character.txt)
   * @option story-type Story type machine name: general, crime, english
   * @option overwrite Update existing library entries from file
   * @usage drush story-pipeline:import-characters
   * @usage drush story-pipeline:import-characters --file=/path/to/character.txt --story-type=general --overwrite
   */
  public function importCharacters($options = ['file' => NULL, 'story-type' => 'general', 'overwrite' => FALSE]): void {
    $config = \Drupal::config('story_pipeline.settings');
    $repo = $config->get('automation_repo_path');
    $path = $options['file'] ?? ($repo . '/general-story/bifuracted-template/character.txt');

    $term = $this->manager->loadStoryTypeTerm($options['story-type'] ?? 'general');
    $tid = $term ? (int) $term->id() : NULL;

    try {
      $report = $this->characterLibrary->importFromFile($path, $tid, !(bool) $options['overwrite']);
      $this->io()->writeln('Imported: ' . $report['imported']);
      if (!empty($report['updated'])) {
        $this->io()->writeln('Updated: ' . $report['updated']);
      }
      $this->io()->writeln('Skipped: ' . $report['skipped']);
      foreach ($report['errors'] as $error) {
        $this->io()->error($error);
      }
      $this->io()->success('Character import finished.');
    }
    catch (\Throwable $e) {
      $this->io()->error($e->getMessage());
    }
  }

}
