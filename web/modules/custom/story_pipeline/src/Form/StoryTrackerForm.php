<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Form;

use Drupal\Core\Form\FormBase;
use Drupal\Core\Form\FormStateInterface;
use Drupal\Core\Url;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\StoryPlannerNav;
use Drupal\story_pipeline\StoryPlannerTypes;
use Drupal\story_pipeline\Service\StoryTracker;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Story planner — Planning, In progress, and Completed sections.
 */
class StoryTrackerForm extends FormBase {

  public function __construct(
    private readonly StoryTracker $tracker,
    private readonly StoryPlannerTypes $plannerTypes,
    private string $tab = 'planning',
  ) {}

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container): static {
    $route_match = \Drupal::routeMatch();
    $tab = $route_match->getRouteObject()?->getDefault('tab') ?? 'planning';
    return new static(
      $container->get('story_pipeline.tracker'),
      $container->get('story_pipeline.planner_types'),
      $tab,
    );
  }

  /**
   * {@inheritdoc}
   */
  public function getFormId(): string {
    return 'story_pipeline_tracker_form';
  }

  /**
   * {@inheritdoc}
   */
  public function buildForm(array $form, FormStateInterface $form_state, ?string $tab = 'planning'): array {
    $this->tab = $tab;

    $form['#attached']['library'][] = 'story_pipeline/story-tracker';
    $form['#attributes']['class'][] = 'story-tracker-form';

    $form['planner_nav'] = StoryPlannerNav::buildTopNav();

    return match ($this->tab) {
      'in_progress' => $this->buildInProgressForm($form),
      'completed' => $this->buildCompletedForm($form),
      default => $this->buildPlanningForm($form),
    };
  }

  /**
   * Planning queue — add stories, set priority, reorder, start.
   */
  private function buildPlanningForm(array $form): array {
    $type_options = $this->plannerTypes->selectOptions();
    $default_type = $this->plannerTypes->defaultTermId();

    $form['intro'] = [
      '#type' => 'markup',
      '#markup' => '<p>' . $this->t(
        'Add stories by type (General, Crime, English, God Story). Stories are grouped below. Link each row to a <strong>Story node</strong> when the CMS episode exists. <strong>Drag the ⋮⋮ handle</strong> within each section to reorder priority, then click <strong>Save order &amp; dates</strong>.'
      ) . '</p>',
    ];

    $form['add'] = [
      '#type' => 'fieldset',
      '#title' => $this->t('Add a story'),
    ];
    $form['add']['new_story_type'] = [
      '#type' => 'select',
      '#title' => $this->t('Type'),
      '#options' => $type_options,
      '#default_value' => $default_type,
      '#required' => TRUE,
    ];
    $form['add']['new_title'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Story title'),
      '#size' => 60,
      '#maxlength' => 512,
      '#placeholder' => $this->t('e.g. London Case — Crime episode'),
    ];
    $form['add']['new_expected_publish'] = [
      '#type' => 'date',
      '#title' => $this->t('Expected publish date'),
    ];
    $form['add']['new_story_node'] = $this->buildStoryNodeElement(
      $this->t('Link to story node'),
      NULL,
      ['new_story_node']
    );
    $form['add']['add_submit'] = [
      '#type' => 'submit',
      '#value' => $this->t('Add to planning'),
      '#submit' => ['::addStory'],
      '#limit_validation_errors' => [['new_title'], ['new_story_type']],
    ];

    $stories = $this->tracker->loadByStatus(StoryTracker::STATUS_PLANNING);
    $grouped = $this->plannerTypes->groupStories($stories);
    $terms = $this->plannerTypes->loadOrderedTerms();

    if (empty($stories)) {
      $form['empty'] = [
        '#type' => 'markup',
        '#markup' => '<p><em>' . $this->t('No stories in planning — add one above.') . '</em></p>',
      ];
      return $form;
    }

    $form['#attached']['library'][] = 'story_pipeline/story-planner-drag';

    foreach (StoryPlannerTypes::ORDER as $machine) {
      $term = $terms[$machine] ?? NULL;
      $label = $term?->label() ?? ucfirst($machine);
      $section_stories = $grouped[$machine] ?? [];

      $form['type_' . $machine] = [
        '#type' => 'fieldset',
        '#title' => $label,
        '#tree' => TRUE,
        '#attributes' => [
          'class' => [
            'story-planner-type-section',
            'story-planner-type--' . $machine,
          ],
        ],
      ];

      if (empty($section_stories)) {
        $form['type_' . $machine]['empty'] = [
          '#type' => 'markup',
          '#markup' => '<p class="story-planner-type-empty"><em>' . $this->t('No @type stories in planning.', ['@type' => $label]) . '</em></p>',
        ];
        continue;
      }

      $form['type_' . $machine]['stories'] = $this->buildPlanningTable($section_stories, $machine, $type_options);
    }

    $form['actions'] = ['#type' => 'actions'];
    $form['actions']['save_order'] = [
      '#type' => 'submit',
      '#value' => $this->t('Save order & dates'),
      '#button_type' => 'primary',
      '#submit' => ['::savePlanning'],
    ];

    return $form;
  }

  /**
   * @param object[] $stories
   * @param array<int|string, string> $type_options
   */
  private function buildPlanningTable(array $stories, string $machine, array $type_options): array {
    $table = [
      '#type' => 'table',
      '#header' => [
        $this->t('Drag'),
        $this->t('Priority'),
        $this->t('Story'),
        $this->t('Story node'),
        $this->t('Type'),
        $this->t('Expected publish'),
        $this->t('Actions'),
      ],
      '#attributes' => [
        'id' => 'story-planner-order-table-' . $machine,
        'class' => [
          'story-tracker-table',
          'story-planner-planning-table',
          'story-planner-order-table',
        ],
        'data-story-type' => $machine,
      ],
    ];

    $rank = 1;
    foreach ($stories as $story) {
      $id = (int) $story->id;
      $table[$id]['#attributes']['class'][] = 'story-planner-draggable-row';
      $table[$id]['#weight'] = (int) $story->weight;

      $table[$id]['drag'] = [
        '#markup' => '<span class="story-planner-drag-grip" title="' . $this->t('Drag to reorder') . '">⋮⋮</span>',
        '#wrapper_attributes' => ['class' => ['story-planner-drag-cell']],
      ];
      $table[$id]['weight'] = [
        '#type' => 'hidden',
        '#default_value' => (int) $story->weight,
        '#attributes' => ['class' => ['story-planner-weight-input']],
      ];
      $table[$id]['priority'] = [
        '#markup' => '<span class="story-planner-priority">#' . $rank++ . '</span>',
        '#wrapper_attributes' => ['class' => ['story-planner-priority-cell']],
      ];
      $table[$id]['title'] = [
        '#wrapper_attributes' => ['class' => ['story-col']],
        '#markup' => '<strong>' . htmlspecialchars($story->title, ENT_QUOTES, 'UTF-8') . '</strong>',
      ];
      $table[$id]['story_node'] = $this->buildStoryNodeElement(
        $this->t('Story node'),
        !empty($story->story_nid) ? (int) $story->story_nid : NULL,
        ['type_' . $machine, 'stories', $id, 'story_node']
      );
      $table[$id]['story_type_tid'] = [
        '#type' => 'select',
        '#title_display' => 'invisible',
        '#options' => $type_options,
        '#default_value' => $story->story_type_tid ?: $this->plannerTypes->defaultTermId(),
        '#attributes' => ['class' => ['story-planner-type-select']],
      ];
      $table[$id]['expected_publish'] = [
        '#type' => 'date',
        '#title_display' => 'invisible',
        '#default_value' => $story->expected_publish ?: '',
      ];
      $table[$id]['actions'] = [
        '#type' => 'container',
        '#attributes' => ['class' => ['story-planner-actions']],
        'start' => [
          '#type' => 'submit',
          '#value' => $this->t('Start'),
          '#name' => 'start_' . $id,
          '#story_id' => $id,
          '#submit' => ['::startStory'],
          '#limit_validation_errors' => [],
          '#attributes' => ['class' => ['button', 'button--primary', 'button--small']],
        ],
        'delete' => [
          '#type' => 'submit',
          '#value' => $this->t('Delete'),
          '#name' => 'delete_' . $id,
          '#story_id' => $id,
          '#submit' => ['::deleteStory'],
          '#limit_validation_errors' => [],
          '#attributes' => ['class' => ['button', 'button--danger', 'button--small']],
        ],
      ];
    }

    return $table;
  }

  /**
   * In progress — production checklist grouped by story type.
   */
  private function buildInProgressForm(array $form): array {
    $form['intro'] = [
      '#type' => 'markup',
      '#markup' => '<p>' . $this->t(
        'Stories you have started, grouped by type. Link each row to its CMS <strong>Story node</strong> when available. Tick off each production step. Check <strong>Completed assigned</strong> when done — the story moves to Completed.'
      ) . '</p>',
    ];

    $stories = $this->tracker->loadByStatus(StoryTracker::STATUS_IN_PROGRESS);

    if (empty($stories)) {
      $form['empty'] = [
        '#type' => 'markup',
        '#markup' => '<p><em>' . $this->t('Nothing in progress — click Start on a story in Planning.') . '</em></p>',
      ];
      return $form;
    }

    $form = $this->appendGroupedChecklistSections($form, $stories);

    $form['actions'] = ['#type' => 'actions'];
    $form['actions']['save'] = [
      '#type' => 'submit',
      '#value' => $this->t('Save changes'),
      '#button_type' => 'primary',
    ];

    return $form;
  }

  /**
   * Completed — archive grouped by story type.
   */
  private function buildCompletedForm(array $form): array {
    $form['intro'] = [
      '#type' => 'markup',
      '#markup' => '<p>' . $this->t('Stories marked as completed, grouped by type. Linked Story nodes stay editable if you need to fix a reference.') . '</p>',
    ];

    $stories = $this->tracker->loadByStatus(StoryTracker::STATUS_COMPLETED);

    if (empty($stories)) {
      $form['empty'] = [
        '#type' => 'markup',
        '#markup' => '<p><em>' . $this->t('No completed stories yet.') . '</em></p>',
      ];
      return $form;
    }

    $form = $this->appendGroupedChecklistSections($form, $stories, TRUE);

    $form['actions'] = ['#type' => 'actions'];
    $form['actions']['save'] = [
      '#type' => 'submit',
      '#value' => $this->t('Save changes'),
      '#button_type' => 'primary',
    ];

    return $form;
  }

  /**
   * @param object[] $stories
   */
  private function appendGroupedChecklistSections(array $form, array $stories, bool $completed_tab = FALSE): array {
    $grouped = $this->plannerTypes->groupStories($stories);
    $terms = $this->plannerTypes->loadOrderedTerms();
    $type_options = $this->plannerTypes->selectOptions();

    foreach (StoryPlannerTypes::ORDER as $machine) {
      $term = $terms[$machine] ?? NULL;
      $label = $term?->label() ?? ucfirst($machine);
      $section_stories = $grouped[$machine] ?? [];

      $form['type_' . $machine] = [
        '#type' => 'fieldset',
        '#title' => $label,
        '#tree' => TRUE,
        '#attributes' => [
          'class' => [
            'story-planner-type-section',
            'story-planner-type--' . $machine,
          ],
        ],
      ];

      if (empty($section_stories)) {
        $form['type_' . $machine]['empty'] = [
          '#type' => 'markup',
          '#markup' => '<p class="story-planner-type-empty"><em>' . $this->t('No @type stories here.', ['@type' => $label]) . '</em></p>',
        ];
        continue;
      }

      $form['type_' . $machine]['stories'] = $this->buildChecklistTable($section_stories, $machine, $completed_tab, $type_options);
    }

    return $form;
  }

  /**
   * @param object[] $stories
   * @param array<int|string, string> $type_options
   */
  private function buildChecklistTable(array $stories, string $machine, bool $completed_tab = FALSE, array $type_options = []): array {
    $table = [
      '#type' => 'table',
      '#header' => [
        $this->t('Story'),
        $this->t('Story node'),
        $this->t('Type'),
        $this->t('Story written'),
        $this->t('Image prompt generated'),
        $this->t('Image generated'),
        $this->t('Digen video generated'),
        $this->t('Completed assigned'),
        $this->t('Expected publish'),
        $this->t('Actions'),
      ],
      '#attributes' => ['class' => ['story-tracker-table']],
    ];

    foreach ($stories as $story) {
      $id = (int) $story->id;
      $table[$id]['title'] = [
        '#markup' => '<strong>' . htmlspecialchars($story->title, ENT_QUOTES, 'UTF-8') . '</strong>',
      ];
      $table[$id]['story_node'] = $this->buildStoryNodeElement(
        $this->t('Story node'),
        !empty($story->story_nid) ? (int) $story->story_nid : NULL,
        ['type_' . $machine, 'stories', $id, 'story_node']
      );
      $table[$id]['story_type_tid'] = $completed_tab
        ? ['#markup' => htmlspecialchars($this->plannerTypes->labelForTid(isset($story->story_type_tid) ? (int) $story->story_type_tid : NULL), ENT_QUOTES, 'UTF-8')]
        : [
          '#type' => 'select',
          '#title_display' => 'invisible',
          '#options' => $type_options,
          '#default_value' => $story->story_type_tid ?: $this->plannerTypes->defaultTermId(),
          '#attributes' => ['class' => ['story-planner-type-select']],
        ];
      $table[$id]['story_written'] = [
        '#type' => 'checkbox',
        '#title_display' => 'invisible',
        '#default_value' => (bool) $story->story_written,
      ];
      $table[$id]['image_prompt_generated'] = [
        '#type' => 'checkbox',
        '#title_display' => 'invisible',
        '#default_value' => (bool) $story->image_prompt_generated,
      ];
      $table[$id]['image_generated'] = [
        '#type' => 'checkbox',
        '#title_display' => 'invisible',
        '#default_value' => (bool) $story->image_generated,
      ];
      $table[$id]['digen_video_generated'] = [
        '#type' => 'checkbox',
        '#title_display' => 'invisible',
        '#default_value' => (bool) $story->digen_video_generated,
      ];
      $table[$id]['completed_assigned'] = $completed_tab
        ? ['#markup' => '✓']
        : [
          '#type' => 'checkbox',
          '#title_display' => 'invisible',
          '#default_value' => (bool) $story->completed_assigned,
        ];
      $table[$id]['expected_publish'] = [
        '#type' => 'date',
        '#title_display' => 'invisible',
        '#default_value' => $story->expected_publish ?: '',
      ];
      $table[$id]['delete'] = [
        '#type' => 'submit',
        '#value' => $this->t('Delete'),
        '#name' => 'delete_' . $id,
        '#story_id' => $id,
        '#submit' => ['::deleteStory'],
        '#limit_validation_errors' => [],
        '#attributes' => ['class' => ['button', 'button--danger', 'button--small']],
      ];
    }

    return $table;
  }

  /**
   * Collects story rows from grouped type sections in form values.
   *
   * @return array<int, array<string, mixed>>
   */
  private function collectSectionStories(FormStateInterface $form_state): array {
    $all = [];
    foreach (StoryPlannerTypes::ORDER as $machine) {
      $rows = $form_state->getValue(['type_' . $machine, 'stories']) ?? [];
      if (!is_array($rows)) {
        continue;
      }
      foreach ($rows as $id => $row) {
        if (is_numeric($id) && is_array($row)) {
          $all[(int) $id] = $row;
        }
      }
    }
    return $all;
  }

  /**
   * {@inheritdoc}
   */
  public function validateForm(array &$form, FormStateInterface $form_state): void {
    $trigger = $form_state->getTriggeringElement();
    if (($trigger['#submit'][0] ?? '') === '::addStory') {
      $title = trim((string) $form_state->getValue('new_title'));
      if ($title === '') {
        $form_state->setErrorByName('new_title', $this->t('Enter a story title.'));
      }
      $type = $form_state->getValue('new_story_type');
      if ($type === NULL || $type === '') {
        $form_state->setErrorByName('new_story_type', $this->t('Select a story type.'));
      }
    }
  }

  /**
   * {@inheritdoc}
   */
  public function submitForm(array &$form, FormStateInterface $form_state): void {
    $stories = $this->collectSectionStories($form_state);
    $moved = 0;
    foreach ($stories as $id => $row) {
      $existing = $this->tracker->load($id);
      if (!$existing) {
        continue;
      }
      $was_completed = $existing->status === StoryTracker::STATUS_COMPLETED;
      $row['story_nid'] = $this->tracker->normalizeStoryNid($this->storyNodeValueFromRow($row));
      $this->tracker->update($id, $row);
      if (!$was_completed && !empty($row['completed_assigned'])) {
        $moved++;
      }
    }

    if ($moved > 0) {
      $this->messenger()->addStatus($this->formatPlural(
        $moved,
        '1 story moved to Completed.',
        '@count stories moved to Completed.',
      ));
    }
    else {
      $this->messenger()->addStatus($this->t('Changes saved.'));
    }

    $form_state->setRedirectUrl(Url::fromRoute($this->redirectRoute()));
  }

  /**
   * Submit handler: save planning order and publish dates.
   */
  public function savePlanning(array &$form, FormStateInterface $form_state): void {
    $stories = $this->collectSectionStories($form_state);
    $weights = [];
    foreach ($stories as $id => $row) {
      if (isset($row['weight'])) {
        $weights[$id] = $row['weight'];
      }
      $type_tid = !empty($row['story_type_tid']) ? (int) $row['story_type_tid'] : NULL;
      $this->tracker->updatePlanningMeta(
        $id,
        !empty($row['expected_publish']) ? $row['expected_publish'] : NULL,
        $type_tid,
        $this->tracker->normalizeStoryNid($this->storyNodeValueFromRow($row)),
        TRUE,
      );
    }
    if ($weights !== []) {
      $this->tracker->savePlanningOrder($weights);
    }
    $this->messenger()->addStatus($this->t('Planning order saved. Drag rows within each type section, then save to keep priority.'));
    $form_state->setRedirectUrl(Url::fromRoute('story_pipeline.tracker'));
  }

  /**
   * Submit handler: add a story to Planning.
   */
  public function addStory(array &$form, FormStateInterface $form_state): void {
    $title = trim((string) $form_state->getValue('new_title'));
    $date = $form_state->getValue('new_expected_publish') ?: NULL;
    $type_tid = (int) $form_state->getValue('new_story_type');
    $story_nid = $this->tracker->normalizeStoryNid($form_state->getValue('new_story_node'));
    $this->tracker->add($title, $date, $type_tid, $story_nid);
    $this->messenger()->addStatus($this->t('Story "@title" added to Planning (@type).', [
      '@title' => $title,
      '@type' => $this->plannerTypes->labelForTid($type_tid),
    ]));
    $form_state->setRedirectUrl(Url::fromRoute('story_pipeline.tracker'));
  }

  /**
   * Submit handler: move a story to In progress.
   */
  public function startStory(array &$form, FormStateInterface $form_state): void {
    $trigger = $form_state->getTriggeringElement();
    $id = (int) ($trigger['#story_id'] ?? 0);
    if ($id > 0) {
      $row = $this->tracker->load($id);
      $this->tracker->start($id);
      $this->messenger()->addStatus($this->t('Started "@title" — now in In progress.', [
        '@title' => $row?->title ?? $id,
      ]));
    }
    $form_state->setRedirectUrl(Url::fromRoute('story_pipeline.tracker_in_progress'));
  }

  /**
   * Submit handler: delete a story row.
   */
  public function deleteStory(array &$form, FormStateInterface $form_state): void {
    $trigger = $form_state->getTriggeringElement();
    $id = (int) ($trigger['#story_id'] ?? 0);
    if ($id > 0) {
      $row = $this->tracker->load($id);
      $this->tracker->delete($id);
      $this->messenger()->addStatus($this->t('Deleted "@title".', [
        '@title' => $row?->title ?? $id,
      ]));
    }
    $form_state->setRedirectUrl(Url::fromRoute($this->redirectRoute()));
  }

  /**
   * Route name for the current planner tab.
   */
  private function redirectRoute(): string {
    return match ($this->tab) {
      'in_progress' => 'story_pipeline.tracker_in_progress',
      'completed' => 'story_pipeline.tracker_completed',
      default => 'story_pipeline.tracker',
    };
  }

  /**
   * Entity autocomplete for linking a planner row to a Story node.
   *
   * @param \Drupal\Core\StringTranslation\TranslatableMarkup|string $title
   * @param list<int|string> $parents
   */
  private function buildStoryNodeElement(string|\Drupal\Core\StringTranslation\TranslatableMarkup $title, ?int $story_nid, array $parents): array {
    $default = NULL;
    if ($story_nid) {
      $node = \Drupal::entityTypeManager()->getStorage('node')->load($story_nid);
      if ($node instanceof NodeInterface && $node->bundle() === 'story') {
        $default = $node;
      }
    }

    $element = [
      '#type' => 'entity_autocomplete',
      '#title' => $title,
      '#title_display' => 'invisible',
      '#target_type' => 'node',
      '#selection_settings' => [
        'target_bundles' => ['story' => 'story'],
      ],
      '#default_value' => $default,
      '#parents' => $parents,
      '#size' => 30,
      '#attributes' => ['class' => ['story-planner-story-node']],
    ];

    if ($default instanceof NodeInterface) {
      $element['#field_suffix'] = [
        '#markup' => '<div class="story-planner-node-links">'
          . '<a href="' . htmlspecialchars($default->toUrl('edit-form')->toString(), ENT_QUOTES, 'UTF-8') . '" class="story-planner-node-link">'
          . $this->t('Edit') . '</a> · '
          . '<a href="' . htmlspecialchars(Url::fromRoute('story_pipeline.story_characters', ['node' => $default->id()])->toString(), ENT_QUOTES, 'UTF-8') . '" class="story-planner-node-link">'
          . $this->t('Characters') . '</a></div>',
      ];
    }

    return $element;
  }

  /**
   * Read story node autocomplete value from a table row.
   */
  private function storyNodeValueFromRow(array $row): mixed {
    $value = $row['story_node'] ?? NULL;
    if (is_array($value) && array_key_exists('autocomplete', $value)) {
      return $value['autocomplete'];
    }
    return $value;
  }

}
