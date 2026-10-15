<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Form;

use Drupal\Core\Form\FormBase;
use Drupal\Core\Form\FormStateInterface;
use Drupal\story_pipeline\Service\WorkerLauncher;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * View, disable, or remove user-confirmed location spellings.
 */
class LocationAliasForm extends FormBase {

  public function __construct(
    private readonly WorkerLauncher $launcher,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static($container->get('story_pipeline.worker_launcher'));
  }

  public function getFormId(): string {
    return 'story_pipeline_location_aliases';
  }

  public function buildForm(array $form, FormStateInterface $form_state): array {
    try {
      $payload = $this->launcher->runCatalogue(['aliases']);
    }
    catch (\Throwable $error) {
      $form['error'] = ['#markup' => '<p>' . $this->t('Remembered spellings could not be read.') . '</p>'];
      return $form;
    }
    $rows = $payload['aliases'] ?? [];
    if ($rows === []) {
      $form['empty'] = ['#markup' => '<p>' . $this->t('No remembered spellings yet.') . '</p>'];
      return $form;
    }
    $form['help'] = [
      '#markup' => '<p>' . $this->t('A remembered spelling is used only when a later request has the same state or district context. Disabling it stops that automatic match.') . '</p>',
    ];
    foreach ($rows as $row) {
      if (!is_array($row) || empty($row['id'])) {
        continue;
      }
      $id = (string) $row['id'];
      $form['alias_' . $id] = [
        '#type' => 'container',
      ];
      $form['alias_' . $id]['label'] = [
        '#markup' => '<p><strong>' . htmlspecialchars((string) ($row['normalized'] ?? ''), ENT_QUOTES, 'UTF-8') . '</strong> → '
          . htmlspecialchars((string) ($row['place_id'] ?? ''), ENT_QUOTES, 'UTF-8')
          . ' · ' . htmlspecialchars((string) ($row['level'] ?? ''), ENT_QUOTES, 'UTF-8')
          . ' · ' . htmlspecialchars((string) ($row['state_place_id'] ?? ''), ENT_QUOTES, 'UTF-8')
          . ' · ' . ((int) ($row['active'] ?? 0) === 1 ? $this->t('active') : $this->t('disabled'))
          . '</p>',
      ];
      if ((int) ($row['active'] ?? 0) === 1) {
        $form['alias_' . $id]['disable'] = [
          '#type' => 'submit',
          '#value' => $this->t('Disable @id', ['@id' => $id]),
          '#name' => 'disable_' . $id,
          '#submit' => ['::disableAlias'],
          '#limit_validation_errors' => [],
          '#alias_id' => $id,
        ];
      }
      $form['alias_' . $id]['remove'] = [
        '#type' => 'submit',
        '#value' => $this->t('Remove @id', ['@id' => $id]),
        '#name' => 'remove_' . $id,
        '#submit' => ['::removeAlias'],
        '#limit_validation_errors' => [],
        '#alias_id' => $id,
      ];
    }
    return $form;
  }

  public function disableAlias(array &$form, FormStateInterface $form_state): void {
    $this->change('alias-disable', $form_state);
  }

  public function removeAlias(array &$form, FormStateInterface $form_state): void {
    $this->change('alias-remove', $form_state);
  }

  public function submitForm(array &$form, FormStateInterface $form_state): void {}

  private function change(string $command, FormStateInterface $form_state): void {
    $button = $form_state->getTriggeringElement();
    $alias_id = (string) ($button['#alias_id'] ?? '');
    if (!preg_match('/^\d+$/', $alias_id)) {
      $this->messenger()->addError($this->t('That remembered spelling was not found.'));
      return;
    }
    try {
      $this->launcher->runCatalogue([$command, '--alias-id', $alias_id]);
      $active = $command === 'alias-disable' ? 0 : NULL;
      if ($this->database()->schema()->tableExists('story_pipeline_anim_alias')) {
        if ($command === 'alias-remove') {
          $this->database()->delete('story_pipeline_anim_alias')
            ->condition('alias_sqlite_id', (int) $alias_id)
            ->execute();
        }
        else {
          $this->database()->update('story_pipeline_anim_alias')
            ->fields(['active' => 0])
            ->condition('alias_sqlite_id', (int) $alias_id)
            ->execute();
        }
      }
      $this->messenger()->addStatus($active === 0 ? $this->t('Remembered spelling disabled.') : $this->t('Remembered spelling removed.'));
    }
    catch (\Throwable $error) {
      $this->messenger()->addError($error->getMessage());
    }
  }

  private function database() {
    return \Drupal::database();
  }

}
