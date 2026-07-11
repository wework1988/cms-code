<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Form;

use Drupal\Core\Form\FormBase;
use Drupal\Core\Form\FormStateInterface;
use Drupal\Core\Url;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\Service\CharacterAiExtractor;
use Drupal\story_pipeline\Service\CharacterLibrary;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * Manage story characters: extract, match library, save, apply to pipeline.
 */
class StoryCharactersForm extends FormBase {

  private ?CharacterLibrary $characterLibrary = NULL;

  private ?CharacterAiExtractor $characterAiExtractor = NULL;

  /**
   * {@inheritdoc}
   */
  public static function create(ContainerInterface $container): static {
    $instance = new static();
    $instance->characterLibrary = $container->get('story_pipeline.character_library');
    $instance->characterAiExtractor = $container->get('story_pipeline.character_ai_extractor');
    return $instance;
  }

  /**
   * Character library service (lazy fallback if form object was rebuilt without DI).
   */
  protected function library(): CharacterLibrary {
    return $this->characterLibrary ??= \Drupal::service('story_pipeline.character_library');
  }

  /**
   * DeepSeek character extraction service.
   */
  protected function aiExtractor(): CharacterAiExtractor {
    return $this->characterAiExtractor ??= \Drupal::service('story_pipeline.character_ai_extractor');
  }

  /**
   * {@inheritdoc}
   */
  public function getFormId(): string {
    return 'story_pipeline_story_characters_form';
  }

  /**
   * {@inheritdoc}
   */
  public function buildForm(array $form, FormStateInterface $form_state, ?NodeInterface $node = NULL): array {
    if (!$node instanceof NodeInterface || $node->bundle() !== 'story') {
      $form['error'] = ['#markup' => $this->t('Story not found.')];
      return $form;
    }

    $form_state->set('story_nid', (int) $node->id());

    $characters = $form_state->get('characters');
    if ($characters === NULL) {
      $characters = $this->library()->loadCharactersForStory($node);
      $form_state->set('characters', $characters);
    }

    $status = $this->library()->getCharacterStatus($node);

    $form['#attached']['library'][] = 'story_pipeline/story-characters';

    $form['intro'] = [
      '#type' => 'markup',
      '#markup' => '<p>' . $this->t(
        'Fastest: paste your <strong>TOP 10 CHARACTERS</strong> block below and click <strong>Import pasted characters</strong>. Or extract from the story plan with DeepSeek / local parser. The full list is saved on this story — reopen anytime to tag more. Then <strong>Apply all to story pipeline</strong> when ready.'
      ) . '</p>',
    ];

    $form['story_links'] = [
      '#type' => 'container',
      '#attributes' => ['class' => ['story-characters-links']],
    ];
    $form['story_links']['edit'] = [
      '#type' => 'link',
      '#title' => $this->t('Edit story'),
      '#url' => $node->toUrl('edit-form'),
      '#attributes' => ['class' => ['button']],
    ];
    $form['story_links']['library'] = [
      '#type' => 'link',
      '#title' => $this->t('Browse character library'),
      '#url' => Url::fromRoute('story_pipeline.character_library'),
      '#attributes' => ['class' => ['button', 'button--small']],
    ];

    if ($status['total'] > 0 || $status['applied'] > 0) {
      $form['status_summary'] = [
        '#type' => 'markup',
        '#markup' => $this->buildStatusSummary($status),
        '#weight' => -10,
      ];
    }

    $form['paste_import'] = [
      '#type' => 'details',
      '#title' => $this->t('Paste character list directly'),
      '#open' => $characters === [],
      '#attributes' => ['class' => ['story-characters-paste']],
      '#weight' => -5,
    ];
    $form['paste_import']['format_help'] = [
      '#type' => 'markup',
      '#markup' => '<p class="story-characters-paste-help">' . $this->t(
        'Paste your <code>TOP 10 CHARACTERS IN THE STORY</code> block here (with <code>1. Name</code>, Story importance, Visual identity, etc.). No DeepSeek needed. Existing library tags are kept when names match.'
      ) . '</p>',
    ];
    $form['paste_import']['paste_text'] = [
      '#type' => 'textarea',
      '#title' => $this->t('Character data'),
      '#title_display' => 'invisible',
      '#rows' => 18,
      '#default_value' => $form_state->get('paste_text') ?? '',
      '#attributes' => ['class' => ['story-characters-paste-textarea']],
      '#placeholder' => "TOP 10 CHARACTERS IN THE STORY\n==================================================\n\n1. Ajit Doval / National Security Advisor\n  Story importance: ...\n  Visual identity: ...\n  Clothing / era look: ...\n  Emotional arc: ...\n  Continuity note: ...",
    ];
    $form['paste_import']['actions'] = ['#type' => 'actions'];
    $form['paste_import']['actions']['import_paste'] = [
      '#type' => 'submit',
      '#value' => $this->t('Import pasted characters'),
      '#submit' => ['::submitImportPaste'],
      '#limit_validation_errors' => [['paste_import', 'paste_text']],
      '#button_type' => $characters === [] ? 'primary' : 'default',
    ];
    if ($this->library()->hasRawStoryFile($node)) {
      $form['paste_import']['actions']['import_raw_file'] = [
        '#type' => 'submit',
        '#value' => $this->t('Import from uploaded raw story file'),
        '#submit' => ['::submitImportRawFile'],
        '#limit_validation_errors' => [],
      ];
    }

    $plan_text = trim($this->library()->getStoryPlanText($node));
    $has_source = $plan_text !== '' || !$node->get('field_full_story')->isEmpty();
    if (!$has_source) {
      $form['warning'] = [
        '#type' => 'markup',
        '#markup' => '<div class="messages messages--warning">' . $this->t('No story text yet. On the story edit form, paste your planned file or full script into <strong>Story plan (with characters)</strong> and/or <strong>Full story</strong>, then save.') . '</div>',
      ];
    }

    $form['actions_top'] = ['#type' => 'actions'];
    if ($this->aiExtractor()->isAvailable()) {
      $form['actions_top']['extract_ai'] = [
        '#type' => 'submit',
        '#value' => $this->t('Extract with DeepSeek'),
        '#submit' => ['::submitExtractAi'],
        '#limit_validation_errors' => [],
      ];
    }
    else {
      $form['actions_top']['extract_ai_unavailable'] = [
        '#type' => 'markup',
        '#markup' => '<div class="messages messages--warning">' . $this->t('DeepSeek API key not set — add it at <a href=":url">Story Pipeline settings</a> to use AI extraction.', [
          ':url' => Url::fromRoute('story_pipeline.settings')->toString(),
        ]) . '</div>',
      ];
    }
    $form['actions_top']['extract'] = [
      '#type' => 'submit',
      '#value' => $this->t('Extract from text (local parser)'),
      '#submit' => ['::submitExtract'],
      '#limit_validation_errors' => [],
    ];

    if ($characters === []) {
      if ($status['applied'] > 0) {
        $form['empty'] = [
          '#markup' => '<p><em>' . $this->t('Could not re-parse characters from story plan, but @count character(s) are already applied to the pipeline. Re-extract to edit tagging.', [
            '@count' => $status['applied'],
          ]) . '</em></p>',
        ];
      }
      else {
        $form['empty'] = [
          '#markup' => '<p><em>' . $this->t('No characters loaded yet. Paste your TOP 10 CHARACTERS block above and click <strong>Import pasted characters</strong>, or extract from the story plan below.') . '</em></p>',
        ];
      }
      return $form;
    }

    $story_type_tid = $this->library()->storyTypeTid($node);

    $form['characters'] = [
      '#type' => 'table',
      '#header' => [
        $this->t('#'),
        $this->t('Character'),
        $this->t('Tag to library'),
        $this->t('Visual prompt'),
        $this->t('Actions'),
      ],
      '#attributes' => ['class' => ['story-characters-table']],
    ];

    foreach ($characters as $index => $character) {
      $is_linked = !empty($character['library_nid']);
      $match_status = $character['match_status'] ?? 'new';

      if ($is_linked && $match_status === 'matched') {
        $badge = '<span class="story-characters-badge story-characters-badge--matched">' . $this->t('Auto-matched: @id', ['@id' => $character['char_id']]) . '</span>';
      }
      elseif ($is_linked && $match_status === 'linked') {
        $badge = '<span class="story-characters-badge story-characters-badge--matched">' . $this->t('Tagged: @id', ['@id' => $character['char_id']]) . '</span>';
      }
      elseif (!empty($character['applied_to_pipeline'])) {
        $badge = '<span class="story-characters-badge story-characters-badge--applied">' . $this->t('Applied to pipeline: @id', ['@id' => $character['char_id']]) . '</span>';
      }
      elseif ($is_linked) {
        $badge = '<span class="story-characters-badge story-characters-badge--matched">' . $this->t('Tagged: @id', ['@id' => $character['char_id']]) . '</span>';
      }
      else {
        $badge = '<span class="story-characters-badge story-characters-badge--new">' . $this->t('Not tagged') . '</span>';
      }

      $default_tag = $character['library_label'] ?? '';
      if ($default_tag === '' && $is_linked && !empty($character['library_nid'])) {
        $lib_node = \Drupal::entityTypeManager()->getStorage('node')->load((int) $character['library_nid']);
        if ($lib_node instanceof NodeInterface) {
          $record = $this->library()->nodeToRecord($lib_node);
          if ($record) {
            $default_tag = $this->library()->formatAutocompleteLabel($record);
          }
        }
      }

      $form['characters'][$index]['num'] = [
        '#markup' => (string) ($index + 1),
      ];
      $form['characters'][$index]['name'] = [
        '#markup' => '<strong>' . htmlspecialchars($character['name'], ENT_QUOTES, 'UTF-8') . '</strong>'
          . ($character['story_importance'] ? '<br><small>' . htmlspecialchars($character['story_importance'], ENT_QUOTES, 'UTF-8') . '</small>' : ''),
      ];
      $form['characters'][$index]['match'] = [
        '#type' => 'container',
        'badge' => [
          '#markup' => $badge,
        ],
        'library_tag' => [
          '#type' => 'textfield',
          '#title' => $this->t('Search library'),
          '#title_display' => 'invisible',
          '#default_value' => $default_tag,
          '#size' => 50,
          '#maxlength' => 512,
          '#placeholder' => $this->t('Type name or CHAR_ID…'),
          '#autocomplete_route_name' => 'story_pipeline.character_autocomplete',
          '#autocomplete_route_parameters' => [
            'story_type' => $story_type_tid ?? '',
          ],
          '#parents' => ['characters', $index, 'library_tag'],
          '#attributes' => ['class' => ['story-characters-autocomplete']],
        ],
        'add_alias' => [
          '#type' => 'checkbox',
          '#title' => $this->t('Add story name as alias'),
          '#default_value' => TRUE,
          '#parents' => ['characters', $index, 'add_alias'],
        ],
        'link' => [
          '#type' => 'submit',
          '#value' => $is_linked ? $this->t('Re-link') : $this->t('Link'),
          '#name' => 'link_library_' . $index,
          '#submit' => ['::submitLinkToLibrary'],
          '#limit_validation_errors' => [
            ['characters', $index],
          ],
        ],
        'character_name' => [
          '#type' => 'hidden',
          '#value' => $character['name'],
          '#parents' => ['characters', $index, 'character_name'],
        ],
      ];

      if ($is_linked) {
        $anchor_preview = mb_substr($character['locked_anchor'], 0, 180);
        if (mb_strlen($character['locked_anchor']) > 180) {
          $anchor_preview .= '…';
        }
        $form['characters'][$index]['prompt'] = [
          '#markup' => '<code class="story-characters-preview">' . htmlspecialchars($anchor_preview, ENT_QUOTES, 'UTF-8') . '</code>',
        ];
        $form['characters'][$index]['actions'] = [
          'use_library' => [
            '#type' => 'checkbox',
            '#title' => $this->t('Include in pipeline'),
            '#default_value' => TRUE,
            '#parents' => ['characters', $index, 'use_library'],
          ],
          'library_nid' => [
            '#type' => 'hidden',
            '#value' => (int) $character['library_nid'],
            '#parents' => ['characters', $index, 'library_nid'],
          ],
        ];
        if (!empty($character['library_nid'])) {
          $form['characters'][$index]['match']['view'] = [
            '#type' => 'link',
            '#title' => $this->t('Edit library entry'),
            '#url' => Url::fromRoute('entity.node.edit_form', ['node' => $character['library_nid']]),
            '#attributes' => ['class' => ['story-characters-edit-link']],
          ];
        }
      }
      else {
        $draft = $character['locked_anchor'] ?: $this->library()->draftAnchor($character);
        $form['characters'][$index]['prompt'] = [
          'char_id' => [
            '#type' => 'textfield',
            '#title' => $this->t('Character ID'),
            '#default_value' => $character['char_id'] ?: $this->library()->suggestCharId($character['name']),
            '#size' => 20,
            '#parents' => ['characters', $index, 'char_id'],
          ],
          'context_label' => [
            '#type' => 'textfield',
            '#title' => $this->t('Context label'),
            '#default_value' => $character['context_label'] ?: $this->t('general')->render(),
            '#size' => 30,
            '#parents' => ['characters', $index, 'context_label'],
          ],
          'aliases' => [
            '#type' => 'textarea',
            '#title' => $this->t('Match aliases (one per line)'),
            '#default_value' => implode("\n", $character['aliases'] ?? []),
            '#rows' => 3,
            '#parents' => ['characters', $index, 'aliases'],
          ],
          'locked_anchor' => [
            '#type' => 'textarea',
            '#title' => $this->t('Locked visual prompt'),
            '#default_value' => $draft,
            '#rows' => 5,
            '#description' => $this->t('Or tag an existing library character instead of creating a new one.'),
            '#parents' => ['characters', $index, 'locked_anchor'],
          ],
          'negative_firewall' => [
            '#type' => 'textarea',
            '#title' => $this->t('Do-not-misclassify (optional)'),
            '#default_value' => $character['negative_firewall'] ?? '',
            '#rows' => 2,
            '#parents' => ['characters', $index, 'negative_firewall'],
          ],
        ];
        $form['characters'][$index]['actions'] = [
          'save_library' => [
            '#type' => 'submit',
            '#value' => $this->t('Save as new'),
            '#name' => 'save_library_' . $index,
            '#submit' => ['::submitSaveOne'],
            '#limit_validation_errors' => [
              ['characters', $index],
            ],
          ],
        ];
      }
    }

    $form['actions'] = ['#type' => 'actions'];
    $form['actions']['apply'] = [
      '#type' => 'submit',
      '#value' => $this->t('Apply all to story pipeline'),
      '#submit' => ['::submitApply'],
      '#button_type' => 'primary',
    ];

    return $form;
  }

  /**
   * Import characters from pasted text block.
   */
  public function submitImportPaste(array &$form, FormStateInterface $form_state): void {
    $nid = (int) $form_state->get('story_nid');
    $node = $this->loadStory($nid);
    if (!$node) {
      return;
    }

    $paste = trim((string) $form_state->getValue(['paste_import', 'paste_text']));
    $form_state->set('paste_text', $paste);

    if ($paste === '') {
      $this->messenger()->addError($this->t('Paste your character list first.'));
      $form_state->setRebuild(TRUE);
      return;
    }

    try {
      $characters = $this->library()->parsePastedCharacters($paste, $node);
      $this->aiExtractor()->mergeCharactersIntoPlan($node, $characters);
      $node = $this->loadStory($nid);
      if (!$node) {
        return;
      }
      $this->library()->saveRoster($node, $characters);
      $form_state->set('characters', $characters);
      $this->messenger()->addStatus($this->t('Imported @count character(s) from paste. List saved — reopen anytime without re-importing.', [
        '@count' => count($characters),
      ]));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($this->t('Import failed: @msg', ['@msg' => $e->getMessage()]));
    }

    $form_state->setRebuild(TRUE);
  }

  /**
   * Import characters from the story node's uploaded raw story file.
   */
  public function submitImportRawFile(array &$form, FormStateInterface $form_state): void {
    $nid = (int) $form_state->get('story_nid');
    $node = $this->loadStory($nid);
    if (!$node) {
      return;
    }

    $raw = $this->library()->getRawStoryFileText($node);
    if ($raw === '') {
      $this->messenger()->addError($this->t('No raw story file found. Upload one on the story edit form (Raw story file field) and save.'));
      $form_state->setRebuild(TRUE);
      return;
    }

    try {
      $characters = $this->library()->parsePastedCharacters($raw, $node);
      $this->aiExtractor()->mergeCharactersIntoPlan($node, $characters);
      $node = $this->loadStory($nid);
      if (!$node) {
        return;
      }
      $this->library()->saveRoster($node, $characters);
      $form_state->set('characters', $characters);
      $form_state->set('paste_text', $raw);
      $this->messenger()->addStatus($this->t('Imported @count character(s) from raw story file.', [
        '@count' => count($characters),
      ]));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($this->t('Import failed: @msg', ['@msg' => $e->getMessage()]));
    }

    $form_state->setRebuild(TRUE);
  }

  /**
   * Re-extract characters using the local text parser.
   */
  public function submitExtract(array &$form, FormStateInterface $form_state): void {
    $nid = (int) $form_state->get('story_nid');
    $node = $this->loadStory($nid);
    if (!$node) {
      return;
    }
    $characters = $this->library()->extractWithMatches($node);
    if ($characters === []) {
      $characters = $this->library()->loadCharactersForStory($node);
    }
    else {
      $this->library()->saveRoster($node, $characters);
    }
    $form_state->set('characters', $characters);
    $this->messenger()->addStatus($this->t('Extracted @count character(s) using local parser.', ['@count' => count($characters)]));
    if ($characters === []) {
      $this->messenger()->addWarning($this->t('No characters found. Try <strong>Extract with DeepSeek</strong> if your paste is not in TOP 10 CHARACTERS format.'));
    }
    $form_state->setRebuild(TRUE);
  }

  /**
   * Extract characters via DeepSeek and write formatted block to story plan.
   */
  public function submitExtractAi(array &$form, FormStateInterface $form_state): void {
    $nid = (int) $form_state->get('story_nid');
    $node = $this->loadStory($nid);
    if (!$node) {
      return;
    }

    try {
      $extracted = $this->aiExtractor()->extractCharacters($node);
      $this->aiExtractor()->mergeCharactersIntoPlan($node, $extracted);
      $node = $this->loadStory($nid);
      if (!$node) {
        return;
      }
      $characters = $this->library()->attachLibraryMatches($node, $extracted);
      $form_state->set('characters', $characters);
      $this->library()->saveRoster($node, $characters);
      $this->messenger()->addStatus($this->t('DeepSeek extracted @count character(s). Full list saved — reopen this tab anytime without re-running DeepSeek.', [
        '@count' => count($characters),
      ]));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($this->t('DeepSeek extraction failed: @msg', ['@msg' => $e->getMessage()]));
    }

    $form_state->setRebuild(TRUE);
  }

  /**
   * Link a story character row to an existing library entry.
   */
  public function submitLinkToLibrary(array &$form, FormStateInterface $form_state): void {
    $trigger = $form_state->getTriggeringElement();
    $index = (int) str_replace('link_library_', '', $trigger['#name'] ?? '0');
    $row = $form_state->getValue(['characters', $index]) ?? [];

    $nid = (int) $form_state->get('story_nid');
    $story = $this->loadStory($nid);
    if (!$story) {
      return;
    }

    $library_nid = $this->library()->parseAutocompleteNid((string) ($row['library_tag'] ?? ''));
    if (!$library_nid) {
      $this->messenger()->addError($this->t('Pick a library character from the autocomplete list, then click Link.'));
      $form_state->setRebuild(TRUE);
      return;
    }

    $characters = $form_state->get('characters') ?? [];
    if (!isset($characters[$index])) {
      return;
    }

    try {
      $add_alias = !empty($row['add_alias']);
      $characters[$index] = $this->library()->applyLibraryLink(
        $characters[$index],
        $library_nid,
        $add_alias
      );
      $form_state->set('characters', $characters);
      $this->library()->saveRoster($story, $characters);

      $msg = $this->t('Linked “@story” to @id.', [
        '@story' => $characters[$index]['name'],
        '@id' => $characters[$index]['char_id'],
      ]);
      if ($add_alias) {
        $msg = $this->t('Linked “@story” to @id and added story name as alias.', [
          '@story' => $characters[$index]['name'],
          '@id' => $characters[$index]['char_id'],
        ]);
      }
      $this->messenger()->addStatus($msg);
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($e->getMessage());
    }

    $form_state->setRebuild(TRUE);
  }

  /**
   * Save one new character to the library.
   */
  public function submitSaveOne(array &$form, FormStateInterface $form_state): void {
    $trigger = $form_state->getTriggeringElement();
    $index = (int) str_replace('save_library_', '', $trigger['#name'] ?? '0');
    $row = $form_state->getValue(['characters', $index]) ?? [];

    $nid = (int) $form_state->get('story_nid');
    $node = $this->loadStory($nid);
    if (!$node) {
      return;
    }

    try {
      $saved = $this->library()->saveCharacter([
        'name' => $row['character_name'] ?? ('Character ' . ($index + 1)),
        'char_id' => $row['char_id'] ?? '',
        'context_label' => $row['context_label'] ?? '',
        'aliases' => $row['aliases'] ?? '',
        'locked_anchor' => $row['locked_anchor'] ?? '',
        'negative_firewall' => $row['negative_firewall'] ?? '',
        'story_type_tid' => $this->library()->storyTypeTid($node),
      ]);

      $characters = $form_state->get('characters') ?? [];
      if (isset($characters[$index])) {
        $record = $this->library()->nodeToRecord($saved);
        if ($record) {
          $characters[$index] = array_merge($characters[$index], [
            'library_nid' => $record['nid'],
            'char_id' => $record['char_id'],
            'locked_anchor' => $record['locked_anchor'],
            'negative_firewall' => $record['negative_firewall'],
            'match_status' => 'linked',
            'library_label' => $this->library()->formatAutocompleteLabel($record),
          ]);
        }
      }
      $form_state->set('characters', $characters);
      $this->library()->saveRoster($node, $characters);

      $this->messenger()->addStatus($this->t('Saved @name as @id to character library.', [
        '@name' => $saved->getTitle(),
        '@id' => $saved->get('field_char_id')->value,
      ]));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($e->getMessage());
    }

    $form_state->setRebuild(TRUE);
  }

  /**
   * Apply selected library characters to field_characters_info.
   */
  public function submitApply(array &$form, FormStateInterface $form_state): void {
    $nid = (int) $form_state->get('story_nid');
    $node = $this->loadStory($nid);
    if (!$node) {
      return;
    }

    $characters = $form_state->get('characters') ?? [];
    $library_nids = [];

    foreach ($characters as $index => $character) {
      $row = $form_state->getValue(['characters', $index]) ?? [];

      // If user picked a tag but did not click Link, link on apply.
      if (empty($row['library_nid']) && !empty($row['library_tag'])) {
        $pick_nid = $this->library()->parseAutocompleteNid((string) $row['library_tag']);
        if ($pick_nid) {
          try {
            $characters[$index] = $this->library()->applyLibraryLink(
              $characters[$index],
              $pick_nid,
              !empty($row['add_alias'])
            );
            $row['library_nid'] = $characters[$index]['library_nid'];
          }
          catch (\Throwable $e) {
            $this->messenger()->addError($this->t('Row @n: @msg', ['@n' => $index + 1, '@msg' => $e->getMessage()]));
          }
        }
      }

      if (!empty($row['library_nid'])) {
        if (!isset($row['use_library']) || $row['use_library']) {
          $library_nids[] = (int) $row['library_nid'];
        }
        continue;
      }
      if (!empty($character['library_nid'])) {
        $library_nids[] = (int) $character['library_nid'];
      }
    }

    $library_nids = array_values(array_unique(array_filter($library_nids)));
    if ($library_nids === []) {
      $this->messenger()->addWarning($this->t('No characters selected. Save new characters to the library first, or extract again.'));
      return;
    }

    $this->library()->applyToStory($node, $library_nids);
    $node = $this->loadStory($nid) ?? $node;
    $this->library()->saveRoster($node, $characters);
    $this->messenger()->addStatus($this->t('Applied @count character(s) to story pipeline. @total total character(s) kept in this list.', [
      '@count' => count($library_nids),
      '@total' => count($characters),
    ]));
  }

  /**
   * {@inheritdoc}
   */
  public function submitForm(array &$form, FormStateInterface $form_state): void {
    // Default submit unused — actions use custom handlers.
  }

  /**
   * Load story node by ID.
   */
  private function loadStory(int $nid): ?NodeInterface {
    $node = \Drupal::entityTypeManager()->getStorage('node')->load($nid);
    return $node instanceof NodeInterface && $node->bundle() === 'story' ? $node : NULL;
  }

  /**
   * Render tagged/applied summary banner.
   *
   * @param array{total: int, tagged: int, untagged: int, applied: int} $status
   */
  private function buildStatusSummary(array $status): string {
    $items = [];
    if ($status['total'] > 0) {
      $items[] = $this->t('<strong>@tagged</strong> of <strong>@total</strong> tagged to library', [
        '@tagged' => $status['tagged'],
        '@total' => $status['total'],
      ])->render();
      if ($status['untagged'] > 0) {
        $items[] = $this->t('<strong>@count</strong> not tagged yet', ['@count' => $status['untagged']])->render();
      }
    }
    if ($status['applied'] > 0) {
      $items[] = $this->t('<strong>@count</strong> applied to story pipeline (Characters info)', [
        '@count' => $status['applied'],
      ])->render();
    }

    return '<div class="story-characters-status messages messages--status"><ul class="story-characters-status-list"><li>'
      . implode('</li><li>', $items)
      . '</li></ul></div>';
  }

}
