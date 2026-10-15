<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Form;

use Drupal\Core\Form\FormBase;
use Drupal\Core\Form\FormStateInterface;
use Drupal\story_pipeline\Service\AnimationManager;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Editable animation-planning master prompt with explicit revisions.
 */
class AnimationPromptForm extends FormBase {

  public function __construct(
    private readonly AnimationManager $animations,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static($container->get('story_pipeline.animations'));
  }

  public function getFormId(): string {
    return 'story_pipeline_animation_prompt';
  }

  public function buildForm(array $form, FormStateInterface $form_state): array {
    $type = (string) $this->getRequest()->query->get('animation_type', 'map');
    $labels = AnimationManager::typeLabels();
    if (!isset($labels[$type])) {
      $type = 'map';
    }
    $current = $this->animations->currentPrompt($type);
    $form['editing'] = [
      '#markup' => '<p><strong>' . $this->t('Editing the @type prompt.', ['@type' => $labels[$type]]) . '</strong> '
        . $this->t('Each animation type keeps its own revision history. Editorial text cannot add executable fields.') . '</p>',
    ];
    $options = [];
    foreach ($labels as $id => $label) {
      $options[$id] = $label;
    }
    $form['animation_type'] = [
      '#type' => 'select',
      '#title' => $this->t('Prompt type'),
      '#options' => $options,
      '#default_value' => $type,
    ];
    $form['load'] = [
      '#type' => 'submit',
      '#value' => $this->t('Edit this type'),
      '#submit' => ['::loadType'],
      '#limit_validation_errors' => [['animation_type']],
    ];
    $form['editing_type'] = [
      '#type' => 'hidden',
      '#value' => $type,
    ];
    $form['body'] = [
      '#type' => 'textarea',
      '#title' => $this->t('@type planning prompt', ['@type' => $labels[$type]]),
      '#description' => $this->t('Editorial direction only. Schemas and supported actions stay fixed in code. Do not paste API keys.'),
      '#default_value' => $current['body'],
      '#rows' => 18,
      '#required' => TRUE,
    ];
    $form['save'] = [
      '#type' => 'submit',
      '#value' => $this->t('Save new revision'),
      '#button_type' => 'primary',
    ];

    $rows = [];
    foreach ($this->animations->promptRevisions($type) as $rev) {
      $rows[] = [
        $rev['id'],
        $rev['animation_type'] ?? $type,
        date('Y-m-d H:i', (int) $rev['created']),
        (string) $rev['uid'],
        strlen((string) $rev['body']) . ' chars',
      ];
    }
    $form['history'] = [
      '#type' => 'details',
      '#title' => $this->t('Previous revisions for this type'),
      '#open' => TRUE,
      'table' => [
        '#type' => 'table',
        '#header' => [$this->t('Revision'), $this->t('Type'), $this->t('Saved'), $this->t('User'), $this->t('Size')],
        '#rows' => $rows,
        '#empty' => $this->t('No revisions yet.'),
      ],
    ];
    $form['history']['restore_id'] = [
      '#type' => 'number',
      '#title' => $this->t('Restore revision'),
      '#min' => 1,
      '#description' => $this->t('Creates a new current revision copied from the chosen id. It does not delete history.'),
    ];
    $form['history']['restore'] = [
      '#type' => 'submit',
      '#value' => $this->t('Restore as new current revision'),
      '#submit' => ['::restore'],
      '#limit_validation_errors' => [['restore_id']],
    ];
    return $form;
  }

  public function validateForm(array &$form, FormStateInterface $form_state): void {
    $body = trim((string) $form_state->getValue('body'));
    if ($body === '' || strlen($body) > 20000) {
      $form_state->setErrorByName('body', $this->t('Enter a prompt of at most 20000 characters.'));
    }
    if (preg_match('/api[_-]?key|sk-[a-z0-9]/i', $body)) {
      $form_state->setErrorByName('body', $this->t('Do not store API keys in this prompt.'));
    }
  }

  public function submitForm(array &$form, FormStateInterface $form_state): void {
    $type = (string) $form_state->getValue('editing_type');
    if (!isset(AnimationManager::typeLabels()[$type])) {
      $type = 'map';
    }
    try {
      $id = $this->animations->savePrompt((string) $form_state->getValue('body'), (int) $this->currentUser()->id(), $type);
      $this->messenger()->addStatus($this->t('Saved @type prompt revision @id.', ['@type' => $type, '@id' => $id]));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($e->getMessage());
    }
  }

  public function loadType(array &$form, FormStateInterface $form_state): void {
    $type = (string) $form_state->getValue('animation_type');
    if (!isset(AnimationManager::typeLabels()[$type])) {
      $type = 'map';
    }
    $form_state->setRedirect('story_pipeline.animation_prompt', [], ['query' => ['animation_type' => $type]]);
  }

  public function restore(array &$form, FormStateInterface $form_state): void {
    $id = (int) $form_state->getValue('restore_id');
    if ($id < 1) {
      $this->messenger()->addError($this->t('Enter a revision id to restore.'));
      return;
    }
    try {
      $new = $this->animations->restorePrompt($id, (int) $this->currentUser()->id());
      $this->messenger()->addStatus($this->t('Restored revision @old as new revision @new.', ['@old' => $id, '@new' => $new]));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($e->getMessage());
    }
  }

}
