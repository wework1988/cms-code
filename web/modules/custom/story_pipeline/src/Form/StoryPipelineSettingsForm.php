<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Form;

use Drupal\Core\Form\ConfigFormBase;
use Drupal\Core\Form\FormStateInterface;
use Drupal\story_pipeline\Service\StoryPipelineManager;

/**
 * Admin settings for Story Pipeline (Drupal API key + shared LLM/TTS keys).
 */
class StoryPipelineSettingsForm extends ConfigFormBase {

  /**
   * Shared pipeline API key fields (used for all story types).
   */
  private const KEY_FIELDS = [
    'deepseek_api_key' => 'DeepSeek API key (storyboard Stages A–C)',
    'anthropic_api_key' => 'Anthropic API key (optional — story writing)',
    'elevenlabs_api_key' => 'ElevenLabs API key (narration TTS)',
  ];

  /**
   * {@inheritdoc}
   */
  protected function getEditableConfigNames(): array {
    return ['story_pipeline.settings'];
  }

  /**
   * {@inheritdoc}
   */
  public function getFormId(): string {
    return 'story_pipeline_settings_form';
  }

  /**
   * {@inheritdoc}
   */
  public function buildForm(array $form, FormStateInterface $form_state): array {
    $config = $this->config('story_pipeline.settings');
    /** @var \Drupal\story_pipeline\Service\StoryPipelineManager $manager */
    $manager = \Drupal::service('story_pipeline.manager');

    $form['site'] = [
      '#type' => 'details',
      '#title' => $this->t('Site & worker access'),
      '#open' => TRUE,
    ];

    $form['site']['api_key'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Drupal API key'),
      '#description' => $this->t('Workers send this as header <code>X-Story-Pipeline-Key</code>. Stored in worker <code>.env</code> as <code>DRUPAL_API_KEY</code>.'),
      '#default_value' => $config->get('api_key'),
      '#required' => TRUE,
      '#maxlength' => 128,
    ];

    $form['site']['automation_repo_path'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Automation repo path'),
      '#description' => $this->t('Used by <code>drush story-pipeline:import-prompts</code> and <code>drush story-pipeline:import-keys</code>.'),
      '#default_value' => $config->get('automation_repo_path'),
      '#required' => TRUE,
    ];

    $form['site']['worker_path'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Worker folder path'),
      '#description' => $this->t('Folder containing <code>run.sh</code> (story-pipeline-worker). Used when staff click “Run story jobs” in the admin UI.'),
      '#default_value' => $config->get('worker_path') ?: dirname(\Drupal::root()) . '/story-pipeline-worker',
      '#required' => TRUE,
    ];

    $form['site']['story_asset_path'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Story asset folder path'),
      '#description' => $this->t('Permanent folder for prompts, scenes, image prompts, audio, etc. Each story gets a subfolder under its type (<code>crime</code>, <code>general</code>, <code>english</code>), e.g. <code>/Users/averma/project/research-story-17thmay-automation/cms-generate-stories/crime/blue-drum/prompts/prompt.txt</code>. When set, files are saved here instead of Drupal <code>public://story-pipeline</code>. Also set <code>STORY_ASSET_ROOT</code> in worker <code>.env</code> to the same path.'),
      '#default_value' => $config->get('story_asset_path') ?: '/Users/averma/project/research-story-17thmay-automation/cms-generate-stories',
      '#required' => TRUE,
    ];

    $form['site']['regenerate_key'] = [
      '#type' => 'checkbox',
      '#title' => $this->t('Generate new Drupal API key on save'),
    ];

    $form['prompts'] = [
      '#type' => 'details',
      '#title' => $this->t('Story type prompts'),
      '#description' => $this->t('Stage A/B/C templates and character library are imported from <code>general-story/bifuracted-template/</code> in the automation repo (with CMS module fallback).'),
      '#open' => FALSE,
      '#weight' => 3,
    ];
    $form['prompts']['import_prompts'] = [
      '#type' => 'submit',
      '#value' => $this->t('Import prompts from automation repo'),
      '#submit' => ['::importPrompts'],
      '#limit_validation_errors' => [],
    ];

    $form['keys'] = [
      '#type' => 'details',
      '#title' => $this->t('Pipeline API keys (all story types)'),
      '#description' => $this->t('These keys are sent to the worker on every run — General, Crime, and English all use the same keys. Leave a password field empty to keep the saved value.'),
      '#open' => TRUE,
      '#weight' => 5,
    ];

    foreach (self::KEY_FIELDS as $field_key => $field_label) {
      $saved = $config->get("pipeline_api_keys.$field_key") ?? '';
      $form['keys'][$field_key] = [
        '#type' => 'password',
        '#title' => $this->t('@label', ['@label' => $field_label]),
        '#description' => $saved !== ''
          ? $this->t('Saved (ends with …@suffix). Enter a new value to replace.', [
            '@suffix' => $manager->maskKey($saved),
          ])
          : $this->t('Not set — run <code>drush story-pipeline:import-keys</code> or paste here.'),
        '#size' => 60,
        '#maxlength' => 512,
      ];
    }

    return parent::buildForm($form, $form_state);
  }

  /**
   * {@inheritdoc}
   */
  public function submitForm(array &$form, FormStateInterface $form_state): void {
    $config = $this->config('story_pipeline.settings');

    $api_key = $form_state->getValue('api_key');
    if ($form_state->getValue('regenerate_key')) {
      $api_key = bin2hex(random_bytes(16));
    }

    $config
      ->set('api_key', $api_key)
      ->set('automation_repo_path', $form_state->getValue('automation_repo_path'))
      ->set('worker_path', $form_state->getValue('worker_path'))
      ->set('story_asset_path', $form_state->getValue('story_asset_path'));

    foreach (array_keys(self::KEY_FIELDS) as $field_key) {
      $new_value = trim((string) $form_state->getValue($field_key));
      if ($new_value !== '') {
        $config->set("pipeline_api_keys.$field_key", $new_value);
      }
    }

    $config->save();
    parent::submitForm($form, $form_state);
  }

  /**
   * Re-import stage templates and master prompts into Story Type terms.
   */
  public function importPrompts(array &$form, FormStateInterface $form_state): void {
    try {
      $report = \Drupal::service('story_pipeline.manager')->importPrompts();
      $parts = [];
      foreach ($report as $type => $status) {
        $parts[] = $type . ': ' . $status;
      }
      $this->messenger()->addStatus($this->t('Prompt import finished: @report', [
        '@report' => implode('; ', $parts),
      ]));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($this->t('Prompt import failed: @msg', ['@msg' => $e->getMessage()]));
    }
    $form_state->setRedirect('story_pipeline.settings');
  }

}
