<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Form;

use Drupal\Core\Form\FormBase;
use Drupal\Core\Form\FormStateInterface;
use Drupal\Core\Url;
use Drupal\story_pipeline\Service\CharacterLibrary;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Browse and import the global character library.
 */
class CharacterLibraryBrowseForm extends FormBase {

  public function __construct(
    private readonly CharacterLibrary $library,
  ) {}

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container): static {
    return new static(
      $container->get('story_pipeline.character_library'),
    );
  }

  /**
   * {@inheritdoc}
   */
  public function getFormId(): string {
    return 'story_pipeline_character_library_form';
  }

  /**
   * {@inheritdoc}
   */
  public function buildForm(array $form, FormStateInterface $form_state): array {
    $form['#attached']['library'][] = 'story_pipeline/story-characters';

    $form['intro'] = [
      '#markup' => '<p>' . $this->t('Shared character looks used across stories. Import from character.txt or add entries manually.') . '</p>',
    ];

    $form['actions_top'] = ['#type' => 'actions'];
    $form['actions_top']['add'] = [
      '#type' => 'link',
      '#title' => $this->t('Add character'),
      '#url' => Url::fromRoute('node.add', ['node_type' => 'character_library']),
      '#attributes' => ['class' => ['button', 'button--primary']],
    ];
    $form['actions_top']['import'] = [
      '#type' => 'submit',
      '#value' => $this->t('Import from repo character.txt (General)'),
      '#submit' => ['::submitImport'],
    ];

    $entries = $this->library->loadAll();
    if ($entries === []) {
      $form['empty'] = [
        '#markup' => '<p><em>' . $this->t('No characters in library yet.') . '</em></p>',
      ];
      return $form;
    }

    $form['library'] = [
      '#type' => 'table',
      '#header' => [
        $this->t('ID'),
        $this->t('Name'),
        $this->t('Context'),
        $this->t('Aliases'),
        $this->t('Actions'),
      ],
    ];

    foreach ($entries as $entry) {
      $nid = $entry['nid'];
      $form['library'][$nid]['id'] = ['#markup' => '<code>' . htmlspecialchars($entry['char_id'], ENT_QUOTES, 'UTF-8') . '</code>'];
      $form['library'][$nid]['name'] = ['#markup' => htmlspecialchars($entry['title'], ENT_QUOTES, 'UTF-8')];
      $form['library'][$nid]['context'] = ['#markup' => htmlspecialchars($entry['context_label'], ENT_QUOTES, 'UTF-8')];
      $alias_preview = implode(', ', array_slice($entry['aliases'], 0, 4));
      if (count($entry['aliases']) > 4) {
        $alias_preview .= '…';
      }
      $form['library'][$nid]['aliases'] = ['#markup' => htmlspecialchars($alias_preview, ENT_QUOTES, 'UTF-8')];
      $form['library'][$nid]['actions'] = [
        '#type' => 'link',
        '#title' => $this->t('Edit'),
        '#url' => Url::fromRoute('entity.node.edit_form', ['node' => $nid]),
      ];
    }

    return $form;
  }

  /**
   * Import character.txt from automation repo.
   */
  public function submitImport(array &$form, FormStateInterface $form_state): void {
    $config = \Drupal::config('story_pipeline.settings');
    $repo = $config->get('automation_repo_path');
    $path = $repo . '/general-story/bifuracted-template/character.txt';

    try {
      $term = \Drupal::service('story_pipeline.manager')->loadStoryTypeTerm('general');
      $tid = $term ? (int) $term->id() : NULL;
      $report = $this->library->importFromFile($path, $tid, TRUE);
      $this->messenger()->addStatus($this->t('Imported @n character(s), skipped @s existing.', [
        '@n' => $report['imported'],
        '@s' => $report['skipped'],
      ]));
      foreach ($report['errors'] as $error) {
        $this->messenger()->addError($error);
      }
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($e->getMessage());
    }

    $form_state->setRebuild(TRUE);
  }

  /**
   * {@inheritdoc}
   */
  public function submitForm(array &$form, FormStateInterface $form_state): void {
  }

}
