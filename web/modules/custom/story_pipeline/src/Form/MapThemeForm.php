<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Form;

use Drupal\Core\Form\FormBase;
use Drupal\Core\Form\FormStateInterface;
use Drupal\story_pipeline\MapThemes;
use Drupal\story_pipeline\Service\MapThemeRepository;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * List built-in and custom map appearance templates.
 */
class MapThemeForm extends FormBase {

  public function __construct(
    private readonly MapThemeRepository $themes,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static($container->get('story_pipeline.map_themes'));
  }

  public function getFormId(): string {
    return 'story_pipeline_map_themes';
  }

  public function buildForm(array $form, FormStateInterface $form_state): array {
    $form['help'] = [
      '#markup' => '<p>' . $this->t('Use Edit on a row to change colours, the marker, and the basemap. Editing a built-in template saves a new copy and leaves the original unchanged.') . '</p>'
        . '<p>' . $this->t('Archiving a custom template does not change jobs that already stored a theme snapshot.') . '</p>',
    ];
    $header = [
      $this->t('Name'),
      $this->t('Id'),
      $this->t('Kind'),
      $this->t('Status'),
      $this->t('Revision'),
      $this->t('Operations'),
    ];
    $rows = [];
    foreach (MapThemes::builtins() as $id => $theme) {
      $rows[] = [
        $theme['name'] ?? $id,
        $id,
        $this->t('Built-in'),
        $this->t('Available'),
        (string) ($theme['revision'] ?? 1),
        $this->editLink((string) $id),
      ];
    }
    foreach ($this->themes->customThemes(TRUE) as $theme) {
      $rows[] = [
        $theme['name'],
        $theme['theme_id'],
        $this->t('Custom'),
        $theme['status'],
        (string) $theme['revision'],
        $this->editLink((string) $theme['theme_id']),
      ];
    }
    $form['table'] = [
      '#type' => 'table',
      '#header' => $header,
      '#rows' => $rows,
      '#empty' => $this->t('No templates found.'),
    ];
    $options = MapThemes::options();
    foreach ($this->themes->customThemes(FALSE) as $theme) {
      $options[$theme['theme_id']] = $theme['name'];
    }
    $form['default_theme'] = [
      '#type' => 'select',
      '#title' => $this->t('Default for future map jobs'),
      '#options' => $options,
      '#default_value' => $this->themes->defaultId(),
    ];
    $form['duplicate_from'] = [
      '#type' => 'select',
      '#title' => $this->t('Duplicate template'),
      '#options' => $options,
    ];
    $form['duplicate_name'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Name for the copy'),
      '#size' => 40,
    ];
    $form['archive_id'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Custom template id to archive'),
      '#size' => 32,
    ];
    $form['actions'] = ['#type' => 'actions'];
    $form['actions']['save'] = [
      '#type' => 'submit',
      '#value' => $this->t('Save default'),
      '#button_type' => 'primary',
    ];
    $form['actions']['duplicate'] = [
      '#type' => 'submit',
      '#value' => $this->t('Duplicate'),
      '#submit' => ['::duplicate'],
    ];
    $form['actions']['archive'] = [
      '#type' => 'submit',
      '#value' => $this->t('Archive custom template'),
      '#submit' => ['::archive'],
    ];
    return $form;
  }

  public function submitForm(array &$form, FormStateInterface $form_state): void {
    $theme_id = (string) $form_state->getValue('default_theme');
    $this->themes->setDefault($theme_id);
    $this->messenger()->addStatus($this->t('Future map jobs default to @id.', ['@id' => $theme_id]));
  }

  public function duplicate(array &$form, FormStateInterface $form_state): void {
    $source_id = (string) $form_state->getValue('duplicate_from');
    $name = trim((string) $form_state->getValue('duplicate_name'));
    if ($name === '') {
      $this->messenger()->addError($this->t('Give the copy a name.'));
      return;
    }
    $base = MapThemes::resolved($source_id);
    if (!is_array($base)) {
      foreach ($this->themes->customThemes(TRUE) as $custom) {
        if ($custom['theme_id'] === $source_id) {
          $base = $custom['document'];
        }
      }
    }
    if (!is_array($base)) {
      $this->messenger()->addError($this->t('That template could not be copied.'));
      return;
    }
    $style = (string) ($base['base_id'] ?? $source_id);
    if (!isset(MapThemes::options()[$style])) {
      $style = MapThemes::DEFAULT_ID;
    }
    $theme_id = 'custom_' . bin2hex(random_bytes(4));
    $resolved = \Drupal::service('story_pipeline.worker_launcher')->resolveMapTheme($style, [], $theme_id, $name, $base);
    $resolved['description'] = (string) ($base['description'] ?? '');
    $this->themes->saveCustom($resolved, $this->currentUser(), FALSE);
    $this->messenger()->addStatus($this->t('Saved @name as @id.', ['@name' => $name, '@id' => $theme_id]));
  }

  public function archive(array &$form, FormStateInterface $form_state): void {
    $theme_id = trim((string) $form_state->getValue('archive_id'));
    if (!str_starts_with($theme_id, 'custom_')) {
      $this->messenger()->addError($this->t('Only a custom template can be archived. Built-in templates stay available.'));
      return;
    }
    $this->themes->setStatus($theme_id, 'archived');
    $this->messenger()->addStatus($this->t('Archived @id. Existing jobs keep the snapshot they already stored.', ['@id' => $theme_id]));
  }

}
