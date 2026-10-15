<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Form;

use Drupal\Core\Form\FormBase;
use Drupal\Core\Form\FormStateInterface;
use Drupal\Core\Url;
use Drupal\node\NodeInterface;
use Drupal\story_pipeline\MapThemes;
use Drupal\story_pipeline\Service\AnimationManager;
use Symfony\Component\DependencyInjection\ContainerInterface;

/**
 * “Generate animation videos” for one story. Does not start the main pipeline.
 */
class StoryAnimationsForm extends FormBase {

  /**
   * @var array{countries: array<int, mixed>, levels: array<int, mixed>}|null
   */
  private ?array $geographyFilters = NULL;

  public function __construct(
    private readonly AnimationManager $animations,
  ) {}

  public static function create(ContainerInterface $container): static {
    return new static($container->get('story_pipeline.animations'));
  }

  public function getFormId(): string {
    return 'story_pipeline_animations';
  }

  public function buildForm(array $form, FormStateInterface $form_state, ?NodeInterface $node = NULL): array {
    if (!$node instanceof NodeInterface || $node->bundle() !== 'story') {
      $form['missing'] = ['#markup' => $this->t('Open this from a story.')];
      return $form;
    }
    $form['#attached']['library'][] = 'story_pipeline/location-resolution';
    $form['#attached']['library'][] = 'story_pipeline/map-theme';
    $form['#attached']['drupalSettings']['mapThemes'] = [];
    $form_state->set('node', $node);
    $script = trim(strip_tags((string) ($node->get('field_full_story')->value ?? '')));
    $scene_info = $this->animations->inspectSceneFile($node);
    $map_prompt = $this->animations->currentPrompt('map');
    $form['help'] = [
      '#markup' => '<p>' . $this->t('Choose one animation type. This does not change narration, Flow images, audio, or the final documentary. Map keeps the geographic catalogue. The other types do not.') . '</p>'
        . '<p>' . $this->t('Script source: the Full story field (field_full_story) on this story. A map job does not read a story file from disk.') . '</p>'
        . '<p>' . $this->t('Prompt source: saved map master-prompt revision @id. This job stores that revision and does not replace it with a generic prompt.', ['@id' => (int) ($map_prompt['id'] ?? 0)]) . '</p>',
    ];
    if ($script === '' && empty($scene_info['ok'])) {
      $form['empty'] = [
        '#markup' => '<p><strong>' . $this->t('This story has no complete script yet.') . '</strong></p>',
      ];
      return $form;
    }

    $form['settings'] = [
      '#type' => 'details',
      '#title' => $this->t('Generate animation videos'),
      '#open' => TRUE,
    ];
    $type_options = [];
    foreach (AnimationManager::typeLabels() as $id => $label) {
      $type_options[$id] = $label;
    }
    $form['settings']['animation_type'] = [
      '#type' => 'select',
      '#title' => $this->t('Animation type'),
      '#options' => $type_options,
      '#default_value' => 'map',
    ];
    $form['settings']['renderer'] = [
      '#type' => 'select',
      '#title' => $this->t('Map renderer'),
      '#options' => [
        'maplibre' => 'MapLibre',
        'openlayers' => 'OpenLayers',
      ],
      '#default_value' => 'maplibre',
      '#states' => [
        'visible' => [
          ':input[name="animation_type"]' => ['value' => 'map'],
        ],
      ],
    ];
    $form['settings']['input_mode'] = [
      '#type' => 'radios',
      '#title' => $this->t('Map source'),
      '#options' => [
        'full_story' => $this->t('Full story'),
        'scene_breakdown' => $this->t('Saved scenes'),
      ],
      '#default_value' => 'full_story',
      '#states' => $this->visibleFor(['map']),
    ];
    $scene_status = empty($scene_info['ok'])
      ? (string) ($scene_info['error'] ?? '')
      : $this->t('File: @file. Scenes: @count. Revision: @hash. Updated: @date. Ready.', [
        '@file' => (string) ($scene_info['filename'] ?? 'scene.txt'),
        '@count' => (string) ($scene_info['scene_count'] ?? '0'),
        '@hash' => substr((string) ($scene_info['sha256'] ?? ''), 0, 12),
        '@date' => !empty($scene_info['modified']) ? date('Y-m-d H:i', (int) $scene_info['modified']) : '',
      ]);
    $form['settings']['scene_status'] = [
      '#type' => 'item',
      '#title' => $this->t('Saved scenes'),
      '#markup' => '<p>' . $scene_status . '</p><p>' . $this->t('Scans scenes in order and selects up to 10 scenes where a map helps explain the narration.') . '</p>',
      '#states' => [
        'visible' => [
          ':input[name="animation_type"]' => ['value' => 'map'],
          ':input[name="input_mode"]' => ['value' => 'scene_breakdown'],
        ],
      ],
    ];
    $form['settings']['max_selected_scenes'] = [
      '#type' => 'number',
      '#title' => $this->t('Maximum suitable scenes'),
      '#default_value' => 10,
      '#min' => 1,
      '#max' => 30,
      '#states' => [
        'visible' => [
          ':input[name="animation_type"]' => ['value' => 'map'],
          ':input[name="input_mode"]' => ['value' => 'scene_breakdown'],
        ],
      ],
    ];
    $form['settings']['auto_scene_maps'] = [
      '#type' => 'checkbox',
      '#title' => $this->t('Generate map animations when scenes are ready'),
      '#default_value' => (int) \Drupal::state()->get('story_pipeline.map_auto_scenes.' . (int) $node->id(), 0) === 1,
      '#states' => $this->visibleFor(['map']),
    ];
    $form['settings']['max_clips'] = [
      '#type' => 'item',
      '#title' => $this->t('Clips'),
      '#markup' => $this->t('Full story: up to 3 passages. Saved scenes: the first suitable scenes in story order, up to the maximum above. A scene that needs a location is not replaced by a later scene.'),
      '#states' => $this->visibleFor(['map']),
    ];
    $form['settings']['duration_seconds'] = [
      '#type' => 'number',
      '#title' => $this->t('Target duration per clip (seconds)'),
      '#default_value' => 18,
      '#min' => 6,
      '#max' => 30,
    ];
    $form['settings']['language'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Label language'),
      '#default_value' => 'hi',
      '#size' => 8,
      '#description' => $this->t('Defaults to Hindi unless you override it.'),
    ];
    $theme_catalog = MapThemes::builtins();
    $theme_options = MapThemes::options();
    foreach (\Drupal::service('story_pipeline.map_themes')->customThemes() as $custom) {
      $theme_options[$custom['theme_id']] = $custom['name'];
      $theme_catalog[$custom['theme_id']] = $custom['document'];
    }
    $default_theme = (string) \Drupal::state()->get('story_pipeline.map_theme_default', MapThemes::DEFAULT_ID);
    if (!isset($theme_options[$default_theme])) {
      $default_theme = MapThemes::DEFAULT_ID;
    }
    $form['#attached']['drupalSettings']['mapThemes'] = $theme_catalog;
    $form['settings']['map_theme'] = [
      '#type' => 'radios',
      '#title' => $this->t('Map appearance'),
      '#options' => $theme_options,
      '#default_value' => $default_theme,
      '#states' => $this->visibleFor(['map']),
    ];
    $form['settings']['map_theme_cards'] = $this->themeCards($theme_catalog);
    $form['settings']['map_theme_cards']['#states'] = $this->visibleFor(['map']);
    $form['settings']['map_preview'] = [
      '#type' => 'html_tag',
      '#tag' => 'canvas',
      '#attributes' => [
        'class' => ['map-theme-preview'],
        'width' => '640',
        'height' => '360',
      ],
      '#states' => $this->visibleFor(['map']),
    ];
    $form['settings']['customise'] = [
      '#type' => 'details',
      '#title' => $this->t('Customise appearance'),
      '#open' => FALSE,
      '#tree' => TRUE,
      '#states' => $this->visibleFor(['map']),
    ];
    $selected_document = $theme_catalog[$default_theme]['resolved'] ?? $theme_catalog[$default_theme] ?? [];
    $template = is_array($selected_document) ? $selected_document : [];
    $tokens = is_array($template['tokens'] ?? NULL) ? $template['tokens'] : [];
    $groups = [
      'background' => 'Background and terrain',
      'highlights' => 'Country and region highlights',
      'borders' => 'Borders and glow',
      'marker' => 'Location markers',
      'labels' => 'Labels',
      'callout' => 'Callouts and arrows',
      'dateBanner' => 'Date/title cards',
      'routes' => 'Routes',
    ];
    foreach ($groups as $group => $title) {
      $form['settings']['customise'][$group] = [
        '#type' => 'details',
        '#title' => $this->t($title),
        '#open' => $group === 'background',
      ];
      foreach (($tokens[$group] ?? []) as $key => $value) {
        if (!is_string($value) || str_starts_with($key, 'roles')) {
          continue;
        }
        $form['settings']['customise'][$group][$key] = [
          '#type' => 'textfield',
          '#title' => $key,
          '#default_value' => $value,
          '#size' => 18,
          '#attributes' => ['data-map-token' => $group . '.' . $key],
        ];
      }
    }
    $marker = is_array($template['marker'] ?? NULL) ? $template['marker'] : [];
    $form['settings']['customise']['marker_shape'] = [
      '#type' => 'select',
      '#title' => $this->t('Marker shape'),
      '#options' => [
        'glow_dot' => $this->t('Glowing dot'),
        'pin' => $this->t('Teardrop pin'),
        'ring' => $this->t('Ring'),
      ],
      '#default_value' => (string) ($marker['shape'] ?? 'glow_dot'),
    ];
    $form['settings']['customise']['hole_mode'] = [
      '#type' => 'select',
      '#title' => $this->t('Marker hole'),
      '#options' => [
        'transparent' => $this->t('Transparent cutout'),
        'filled' => $this->t('Filled hole'),
      ],
      '#default_value' => (($marker['hole'] ?? 'transparent') === 'transparent') ? 'transparent' : 'filled',
    ];
    $form['settings']['customise']['marker_height'] = [
      '#type' => 'number',
      '#title' => $this->t('Marker size'),
      '#description' => $this->t('Screen pixels at 1920×1080. The pin tip stays on the place.'),
      '#default_value' => (int) ($marker['height'] ?? 54),
      '#min' => 28,
      '#max' => 72,
      '#step' => 1,
    ];
    $form['settings']['customise']['outline_width'] = [
      '#type' => 'number',
      '#title' => $this->t('Outline width'),
      '#default_value' => (float) ($marker['outline_width'] ?? 2.25),
      '#min' => 0,
      '#max' => 8,
      '#step' => 0.25,
    ];
    $form['settings']['customise']['shadow_strength'] = [
      '#type' => 'number',
      '#title' => $this->t('Shadow strength'),
      '#default_value' => (float) ($marker['shadow_strength'] ?? 0.4),
      '#min' => 0,
      '#max' => 1,
      '#step' => 0.05,
    ];
    $form['settings']['customise']['pulse'] = [
      '#type' => 'checkbox',
      '#title' => $this->t('Pulse marker'),
      '#default_value' => !empty($marker['pulse']),
    ];
    $form['settings']['customise']['reset_theme'] = [
      '#type' => 'html_tag',
      '#tag' => 'button',
      '#value' => $this->t('Reset to template defaults'),
      '#attributes' => [
        'type' => 'button',
        'class' => ['button', 'map-theme-reset'],
      ],
    ];
    $form['settings']['customise']['basemap_mode'] = [
      '#type' => 'select',
      '#title' => $this->t('Basemap'),
      '#options' => [
        'graded_relief' => $this->t('Graded relief. Ocean is the background behind the terrain image. Land colour is a light wash. Grade controls shift the relief; they do not recolour land and ocean independently.'),
        'flat_atlas' => $this->t('Flat atlas. Relief is hidden. Ocean and land colours are drawn directly.'),
      ],
      '#default_value' => 'graded_relief',
    ];
    $font_options = array_combine(MapThemes::fonts(), MapThemes::fonts()) ?: [];
    $form['settings']['customise']['font_latin'] = [
      '#type' => 'select',
      '#title' => $this->t('Latin font'),
      '#options' => $font_options,
      '#default_value' => 'Story Condensed',
    ];
    $form['settings']['customise']['font_devanagari'] = [
      '#type' => 'select',
      '#title' => $this->t('Hindi font'),
      '#options' => $font_options,
      '#default_value' => 'Story Devanagari Bold',
    ];
    $theme_actions = [
      'job' => $this->t('Use for this job only'),
    ];
    if ($this->currentUser()->hasPermission('manage map appearance templates')) {
      $theme_actions['save'] = $this->t('Save as new template');
      $theme_actions['update'] = $this->t('Update this template');
      $theme_actions['default'] = $this->t('Set as default for future map jobs');
    }
    $form['settings']['map_theme_name'] = [
      '#type' => 'textfield',
      '#title' => $this->t('New template name'),
      '#size' => 40,
      '#states' => $this->visibleFor(['map']),
    ];
    $form['settings']['theme_action'] = [
      '#type' => 'select',
      '#title' => $this->t('Theme action'),
      '#options' => $theme_actions,
      '#default_value' => 'job',
      '#states' => $this->visibleFor(['map']),
    ];
    $documentary = array_keys(AnimationManager::DOCUMENTARY_PROMPTS);
    $form['settings']['style_preset'] = [
      '#type' => 'select',
      '#title' => $this->t('Style'),
      '#options' => [
        'cinematic_dark' => $this->t('Cinematic dark'),
        'archival_paper' => $this->t('Archival paper'),
        'clean_editorial' => $this->t('Clean editorial'),
      ],
      '#default_value' => 'cinematic_dark',
      '#states' => $this->visibleFor($documentary),
    ];
    $form['settings']['images'] = [
      '#type' => 'textarea',
      '#title' => $this->t('Image paths, one per line'),
      '#rows' => 4,
      '#states' => $this->visibleFor(['photo_sequences', 'storyboard_reconstructions']),
    ];
    $form['settings']['before_path'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Before image'),
      '#states' => $this->visibleFor(['before_after']),
    ];
    $form['settings']['after_path'] = [
      '#type' => 'textfield',
      '#title' => $this->t('After image'),
      '#states' => $this->visibleFor(['before_after']),
    ];
    $form['settings']['before_label'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Before label'),
      '#default_value' => 'पहले',
      '#states' => $this->visibleFor(['before_after']),
    ];
    $form['settings']['after_label'] = [
      '#type' => 'textfield',
      '#title' => $this->t('After label'),
      '#default_value' => 'बाद में',
      '#states' => $this->visibleFor(['before_after']),
    ];
    $form['settings']['document_path'] = [
      '#type' => 'textfield',
      '#title' => $this->t('PDF or scan'),
      '#states' => $this->visibleFor(['document_highlighting']),
    ];
    $form['settings']['document_page'] = [
      '#type' => 'number',
      '#title' => $this->t('Page'),
      '#default_value' => 1,
      '#min' => 1,
      '#states' => $this->visibleFor(['document_highlighting']),
    ];
    $form['settings']['region'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Highlight region'),
      '#description' => $this->t('x, y, width, height as fractions of the page, for example 0.1, 0.15, 0.8, 0.08'),
      '#states' => $this->visibleFor(['document_highlighting']),
    ];
    $form['settings']['entities'] = [
      '#type' => 'textarea',
      '#title' => $this->t('Entities JSON'),
      '#description' => $this->t('A list of objects with id, label, and type. Labels must appear in the script.'),
      '#rows' => 4,
      '#states' => $this->visibleFor(['relationship_diagrams']),
    ];
    $form['settings']['edges'] = [
      '#type' => 'textarea',
      '#title' => $this->t('Relationships JSON'),
      '#description' => $this->t('A list of objects with from, to, label, and evidence_quote. The quote must name both entities.'),
      '#rows' => 4,
      '#states' => $this->visibleFor(['relationship_diagrams']),
    ];
    $form['settings']['series'] = [
      '#type' => 'textarea',
      '#title' => $this->t('Data JSON'),
      '#description' => $this->t('A list of objects with label, value, and evidence_quote. Values are not invented.'),
      '#rows' => 4,
      '#states' => $this->visibleFor(['data_animations']),
    ];
    $form['settings']['unit'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Unit'),
      '#states' => $this->visibleFor(['data_animations']),
    ];
    $form['settings']['source_label'] = [
      '#type' => 'textfield',
      '#title' => $this->t('Data source label'),
      '#states' => $this->visibleFor(['data_animations']),
    ];
    $form['settings']['submit'] = [
      '#type' => 'submit',
      '#value' => $this->t('Generate animation videos'),
      '#button_type' => 'primary',
    ];
    $form['settings']['submit_scenes'] = [
      '#type' => 'submit',
      '#value' => $this->t('Generate maps from scenes'),
      '#submit' => ['::generateScenes'],
      '#states' => $this->visibleFor(['map']),
    ];

    $current_hash = hash('sha256', $script);
    foreach ($this->animations->jobsForStory((int) $node->id()) as $job) {
      $changed = !hash_equals($current_hash, (string) $job['script_hash']);
      $kind = (string) ($job['animation_type'] ?? 'map');
      $labels = AnimationManager::typeLabels();
      $kind_label = $labels[$kind] ?? $kind;
      $form['job_' . $job['job_id']] = [
        '#type' => 'details',
        '#title' => $this->t('@type job @id — @status', [
          '@type' => $kind_label,
          '@id' => $job['job_id'],
          '@status' => $this->jobStatusLabel($job),
        ]),
        '#open' => TRUE,
      ];
      $job_needs_locations = FALSE;
      $note = $changed
        ? $this->t('Generated from an earlier script revision.')
        : $this->t('Matches the current saved script.');
      $source_note = $this->t('Script source: Full story field. Prompt revision: @id.', [
        '@id' => (string) ($job['prompt_id'] ?? ''),
      ]);
      $form['job_' . $job['job_id']]['meta'] = [
        '#markup' => '<p>' . $this->t('Status: @status. @message', [
          '@status' => $job['status'],
          '@message' => $job['message'] ?: $note,
        ]) . ' ' . $note . ' ' . $source_note . '</p>',
      ];
      if (empty($job['clips'])) {
        continue;
      }
      foreach ($job['clips'] as $clip) {
        $beats = [];
        foreach ($clip['beats'] ?? [] as $beat) {
          $beats[] = $beat['purpose'] ?? '';
        }
        $id = $job['job_id'] . '_' . ($clip['id'] ?? 'clip');
        $form['job_' . $job['job_id']][$id] = [
          '#type' => 'container',
        ];
        $scene_label = '';
        if (!empty($clip['scene_number'])) {
          $scene_label = 'scene_' . (int) $clip['scene_number'];
        }
        elseif (!empty($clip['scene_numbers']) && is_array($clip['scene_numbers'])) {
          $scene_label = 'scene_' . implode('_', $clip['scene_numbers']);
        }
        elseif (!empty($clip['filename'])) {
          $scene_label = (string) $clip['filename'];
        }
        $clip_kind = (string) ($clip['animation_type'] ?? $kind);
        $summary = '';
        if ($clip_kind === 'timeline') {
          $summary = $this->milestoneMarkup($clip['milestones'] ?? []);
        }
        elseif ($clip_kind === 'map') {
          $summary = $this->placeMarkup($clip['places'] ?? []);
        }
        $form['job_' . $job['job_id']][$id]['title'] = [
          '#markup' => '<h3>' . $this->t('@title', ['@title' => $scene_label !== '' ? $scene_label : ($clip['title'] ?? $clip['id'])]) . '</h3>'
            . '<p><strong>' . $this->t('Type:') . '</strong> ' . htmlspecialchars((string) ($labels[$clip_kind] ?? $clip_kind), ENT_QUOTES, 'UTF-8') . '</p>'
            . '<p><strong>' . $this->t('Status:') . '</strong> ' . htmlspecialchars($this->clipStatusLabel($clip), ENT_QUOTES, 'UTF-8') . '</p>'
            . '<p><strong>' . $this->t('Why:') . '</strong> ' . htmlspecialchars((string) ($clip['reason'] ?? ''), ENT_QUOTES, 'UTF-8') . '</p>'
            . $this->timingMarkup($clip)
            . $this->staleSceneMarkup($clip, $scene_info)
            . '<blockquote>' . htmlspecialchars((string) ($clip['source_passage'] ?? ''), ENT_QUOTES, 'UTF-8') . '</blockquote>'
            . '<p>' . htmlspecialchars(implode(' → ', array_filter($beats)), ENT_QUOTES, 'UTF-8') . '</p>'
            . $summary
            . $this->warningMarkup($clip['warnings'] ?? []),
        ];
        if (!empty($clip['error'])) {
          $form['job_' . $job['job_id']][$id]['error'] = [
            '#markup' => '<p>' . htmlspecialchars((string) $clip['error'], ENT_QUOTES, 'UTF-8') . '</p>',
          ];
        }
        if (!empty($clip['poster']) && is_file($clip['poster'])) {
          $poster_url = Url::fromRoute('story_pipeline.animation_file', [
            'node' => $node->id(),
            'job_id' => $job['job_id'],
          ], ['query' => ['file' => $this->relativeToJob($job['job_dir'], $clip['poster'])]])->toString();
          $form['job_' . $job['job_id']][$id]['poster'] = [
            '#markup' => '<p><img src="' . htmlspecialchars($poster_url, ENT_QUOTES, 'UTF-8') . '" width="480" alt="" /></p>',
          ];
        }
        if (!empty($clip['video']) && is_file($clip['video'])) {
          $video_file = (!empty($clip['scene_number']) && str_contains((string) $clip['video'], '/animation/scene_'))
            ? 'published/' . basename((string) $clip['video'])
            : $this->relativeToJob($job['job_dir'], $clip['video']);
          $url = Url::fromRoute('story_pipeline.animation_file', [
            'node' => $node->id(),
            'job_id' => $job['job_id'],
          ], ['query' => ['file' => $video_file]])->toString();
          $form['job_' . $job['job_id']][$id]['video'] = [
            '#markup' => '<video controls width="640" src="' . htmlspecialchars($url, ENT_QUOTES, 'UTF-8') . '"></video>'
              . '<p><a href="' . htmlspecialchars($url, ENT_QUOTES, 'UTF-8') . '">' . $this->t('Download') . '</a></p>',
          ];
        }
        if ($clip_kind === 'map' && $this->appendLocationFields($form, $node, $job, $clip)) {
          $job_needs_locations = TRUE;
        }
        if (($clip['status'] ?? '') !== 'completed') {
          $form['job_' . $job['job_id']][$id]['retry'] = [
            '#type' => 'submit',
            '#value' => $this->t('Retry @id', ['@id' => $clip['id'] ?? '']),
            '#name' => 'retry_' . $job['job_id'] . '_' . ($clip['id'] ?? ''),
            '#submit' => ['::retryClip'],
            '#limit_validation_errors' => [],
            '#job_id' => $job['job_id'],
            '#clip_id' => $clip['id'] ?? '',
          ];
        }
      }
      if ($kind === 'map' && $this->jobHasCompletedClip($job)) {
        $form['job_' . $job['job_id']]['restyle_theme'] = [
          '#type' => 'select',
          '#title' => $this->t('Render with a different theme'),
          '#options' => MapThemes::options(),
          '#default_value' => MapThemes::DEFAULT_ID,
          '#parents' => ['restyle_theme', $job['job_id']],
        ];
        $form['job_' . $job['job_id']]['restyle'] = [
          '#type' => 'submit',
          '#value' => $this->t('Render with a different theme'),
          '#name' => 'restyle_' . $job['job_id'],
          '#submit' => ['::restyleTheme'],
          '#limit_validation_errors' => [['restyle_theme', $job['job_id']]],
          '#job_id' => $job['job_id'],
        ];
      }
      if ($job_needs_locations) {
        $form['job_' . $job['job_id']]['save_locations'] = [
          '#type' => 'submit',
          '#value' => $this->t('Save mappings and resume animation'),
          '#name' => 'save_locations_' . $job['job_id'],
          '#submit' => ['::saveLocations'],
          '#limit_validation_errors' => [['loc']],
          '#job_id' => $job['job_id'],
        ];
      }
    }
    return $form;
  }

  private function warningMarkup(array $warnings): string {
    if ($warnings === []) {
      return '';
    }
    $lines = [];
    foreach ($warnings as $warning) {
      if (!is_string($warning) || $warning === '') {
        continue;
      }
      $lines[] = '<li>' . htmlspecialchars($warning, ENT_QUOTES, 'UTF-8') . '</li>';
    }
    if ($lines === []) {
      return '';
    }
    return '<p><strong>' . $this->t('Warnings') . '</strong></p><ul>' . implode('', $lines) . '</ul>';
  }

  private function placeMarkup(array $places): string {
    if ($places === []) {
      return '';
    }
    $lines = [];
    foreach ($places as $place) {
      if (!is_array($place)) {
        continue;
      }
      $bits = array_filter([
        $place['requested'] ?? $place['name'] ?? '',
        isset($place['name']) ? 'resolved ' . $place['name'] : '',
        $place['level'] ?? '',
        $place['representation'] ?? '',
        $place['state_name'] ?? '',
        $place['status'] ?? '',
        $place['reason'] ?? '',
      ], static fn ($bit) => $bit !== '');
      $lines[] = htmlspecialchars(implode(' · ', $bits), ENT_QUOTES, 'UTF-8');
      foreach ($place['candidates'] ?? [] as $candidate) {
        if (!is_array($candidate)) {
          continue;
        }
        $choice = array_filter([
          $candidate['name'] ?? '',
          $candidate['level'] ?? '',
          $candidate['state_name'] ?? '',
          $candidate['district_name'] ?? '',
          $candidate['representation'] ?? '',
        ]);
        $lines[] = htmlspecialchars('Candidate: ' . implode(', ', $choice), ENT_QUOTES, 'UTF-8');
      }
    }
    return '<ul><li>' . implode('</li><li>', $lines) . '</li></ul>';
  }

  private function milestoneMarkup(array $milestones): string {
    if ($milestones === []) {
      return '';
    }
    $lines = [];
    foreach ($milestones as $milestone) {
      if (!is_array($milestone)) {
        continue;
      }
      $bits = array_filter([
        $milestone['date_label'] ?? '',
        $milestone['caption'] ?? '',
        $milestone['date_precision'] ?? '',
      ], static fn ($bit) => $bit !== '' && $bit !== NULL);
      $lines[] = htmlspecialchars(implode(' — ', $bits), ENT_QUOTES, 'UTF-8');
    }
    if ($lines === []) {
      return '';
    }
    return '<ul><li>' . implode('</li><li>', $lines) . '</li></ul>';
  }

  public function retryClip(array &$form, FormStateInterface $form_state): void {
    $button = $form_state->getTriggeringElement();
    $node = $form_state->get('node');
    try {
      $this->animations->retryClip($node, (string) $button['#job_id'], (string) $button['#clip_id']);
      $this->messenger()->addStatus($this->t('Retry queued. This page returns immediately; refresh for progress.'));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($e->getMessage());
    }
  }

  public function submitForm(array &$form, FormStateInterface $form_state): void {
    $node = $form_state->get('node');
    try {
      $type = $form_state->getValue('animation_type') ?: 'map';
      $job_id = $this->animations->launch($node, $this->currentUser(), [
        'renderer' => $form_state->getValue('renderer'),
        'animation_type' => $type,
        'max_clips' => 3,
        'duration_seconds' => $form_state->getValue('duration_seconds'),
        'language' => $form_state->getValue('language'),
        'inputs' => $this->inputsFromForm($form_state),
        'map_theme_id' => $form_state->getValue('map_theme'),
        'map_theme_overrides' => $type === 'map' ? $this->themeOverrides($form_state) : [],
        'map_theme_action' => $form_state->getValue('theme_action') ?: 'job',
        'map_theme_name' => trim((string) $form_state->getValue('map_theme_name')),
        'auto_scene_maps' => (bool) $form_state->getValue('auto_scene_maps'),
      ]);
      $this->messenger()->addStatus($this->t('Animation job @id queued. Rendering continues in the background.', ['@id' => $job_id]));
    }
    catch (\Throwable $e) {
      $this->messenger()->addError($e->getMessage());
    }
  }

  public function generateScenes(array &$form, FormStateInterface $form_state): void {
    $node = $form_state->get('node');
    try {
      $job_id = $this->animations->launch($node, $this->currentUser(), [
        'input_mode' => 'scene_breakdown',
        'renderer' => $form_state->getValue('renderer'),
        'animation_type' => 'map',
        'max_selected_scenes' => (int) $form_state->getValue('max_selected_scenes'),
        'duration_seconds' => $form_state->getValue('duration_seconds'),
        'language' => $form_state->getValue('language'),
        'inputs' => [],
        'map_theme_id' => $form_state->getValue('map_theme'),
        'map_theme_overrides' => $this->themeOverrides($form_state),
        'map_theme_action' => $form_state->getValue('theme_action') ?: 'job',
        'map_theme_name' => trim((string) $form_state->getValue('map_theme_name')),
        'auto_scene_maps' => (bool) $form_state->getValue('auto_scene_maps'),
      ]);
      $this->messenger()->addStatus($this->t('Scene map job @id queued. Rendering continues in the background and does not change the normal videos.', ['@id' => $job_id]));
    }
    catch (\Throwable $error) {
      $this->messenger()->addError($error->getMessage());
    }
  }

  public function restyleTheme(array &$form, FormStateInterface $form_state): void {
    $button = $form_state->getTriggeringElement();
    $node = $form_state->get('node');
    $job_id = (string) ($button['#job_id'] ?? '');
    $theme_id = (string) ($form_state->getValue(['restyle_theme', $job_id]) ?? '');
    try {
      $hash = $this->animations->restyleJob($node, $job_id, $theme_id, $this->currentUser());
      $this->messenger()->addStatus($this->t('Appearance variant @hash is queued. The original video stays in place.', ['@hash' => $hash]));
    }
    catch (\Throwable $error) {
      $this->messenger()->addError($error->getMessage());
    }
  }

  private function jobHasCompletedClip(array $job): bool {
    foreach ($job['clips'] ?? [] as $clip) {
      if (is_array($clip) && ($clip['status'] ?? '') === 'completed' && !empty($clip['video'])) {
        return TRUE;
      }
    }
    return FALSE;
  }

  private function themeDocument(string $theme_id): array {
    $builtin = MapThemes::resolved($theme_id);
    if (is_array($builtin)) {
      return $builtin;
    }
    foreach (\Drupal::service('story_pipeline.map_themes')->customThemes() as $custom) {
      if ($custom['theme_id'] === $theme_id && is_array($custom['document'])) {
        return $custom['document'];
      }
    }
    return MapThemes::resolved(MapThemes::DEFAULT_ID) ?? [];
  }

  private function themeOverrides(FormStateInterface $form_state): array {
    $theme_id = (string) ($form_state->getValue('map_theme') ?: MapThemes::DEFAULT_ID);
    $resolved = $this->themeDocument($theme_id);
    $tokens = is_array($resolved['tokens'] ?? NULL) ? $resolved['tokens'] : [];
    $customise = $form_state->getValue('customise');
    if (!is_array($customise)) {
      return [];
    }
    $overrides = [];
    foreach ($tokens as $group => $values) {
      if (!is_array($values) || !isset($customise[$group]) || !is_array($customise[$group])) {
        continue;
      }
      foreach ($values as $key => $value) {
        if (!is_string($value)) {
          continue;
        }
        $submitted = trim((string) ($customise[$group][$key] ?? ''));
        if ($submitted !== '' && strcasecmp($submitted, $value) !== 0) {
          $overrides[$group][$key] = $submitted;
        }
      }
    }
    $shape = (string) ($customise['marker_shape'] ?? '');
    $current_shape = (string) (($resolved['marker']['shape'] ?? '') ?: 'glow_dot');
    if ($shape !== '' && $shape !== $current_shape) {
      $overrides['marker_shape'] = $shape;
    }
    $basemap = (string) ($customise['basemap_mode'] ?? '');
    $current_basemap = (string) (($resolved['capabilities']['basemap_mode'] ?? '') ?: 'graded_relief');
    if ($basemap !== '' && $basemap !== $current_basemap) {
      $overrides['basemap_mode'] = $basemap;
    }
    foreach (['font_latin', 'font_devanagari'] as $font_key) {
      $font = (string) ($customise[$font_key] ?? '');
      $current = (string) (($resolved['label'][$font_key] ?? '') ?: '');
      if ($font !== '' && $current !== '' && $font !== $current) {
        $overrides[$font_key] = $font;
      }
    }
    $marker = is_array($resolved['marker'] ?? NULL) ? $resolved['marker'] : [];
    $height = (string) ($customise['marker_height'] ?? '');
    $current_height = (string) ($marker['height'] ?? '54');
    if ($height !== '' && abs((float) $height - (float) $current_height) > 0.01) {
      $overrides['marker_height'] = $height;
    }
    $width = (string) ($customise['outline_width'] ?? '');
    $current_width = (string) ($marker['outline_width'] ?? '2.25');
    if ($width !== '' && abs((float) $width - (float) $current_width) > 0.01) {
      $overrides['outline_width'] = $width;
    }
    $shadow = (string) ($customise['shadow_strength'] ?? '');
    $current_shadow = (string) ($marker['shadow_strength'] ?? '0.4');
    if ($shadow !== '' && abs((float) $shadow - (float) $current_shadow) > 0.01) {
      $overrides['shadow_strength'] = $shadow;
    }
    $hole = (string) ($customise['hole_mode'] ?? '');
    $current_hole = (($marker['hole'] ?? 'transparent') === 'transparent') ? 'transparent' : 'filled';
    if ($hole !== '' && $hole !== $current_hole) {
      $overrides['hole_mode'] = $hole;
    }
    $pulse = !empty($customise['pulse']);
    if ($pulse !== !empty($marker['pulse'])) {
      $overrides['pulse'] = $pulse ? '1' : '0';
    }
    return $overrides;
  }

  private function themeCards(array $catalog): array {
    $cards = [
      '#type' => 'container',
      '#attributes' => ['class' => ['map-theme-cards']],
    ];
    foreach ($catalog as $id => $theme) {
      $tokens = $theme['tokens']['highlights'] ?? ($theme['resolved']['tokens']['highlights'] ?? []);
      $cards[$id] = [
        '#type' => 'container',
        '#attributes' => ['class' => ['map-theme-card']],
        'label' => [
          '#markup' => '<strong>' . htmlspecialchars((string) ($theme['name'] ?? $id), ENT_QUOTES, 'UTF-8') . '</strong> '
            . htmlspecialchars((string) ($theme['description'] ?? ''), ENT_QUOTES, 'UTF-8') . ' ',
        ],
      ];
      foreach (['country', 'primaryRegion', 'secondaryRegion', 'tertiaryRegion', 'activeLocation'] as $key) {
        $color = (string) ($tokens[$key] ?? '#CCCCCC');
        if (!preg_match('/^(#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?|rgba?\\([0-9.,\\s%]+\\))$/', $color)) {
          $color = '#CCCCCC';
        }
        $cards[$id][$key] = [
          '#type' => 'html_tag',
          '#tag' => 'span',
          '#attributes' => [
            'class' => ['map-theme-swatch'],
            'style' => 'background:' . $color,
          ],
        ];
      }
    }
    return $cards;
  }

  private function visibleFor(array $types): array {
    $conditions = [];
    foreach (array_values($types) as $index => $type) {
      if ($index > 0) {
        $conditions[] = 'or';
      }
      $conditions[] = [':input[name="animation_type"]' => ['value' => $type]];
    }
    return ['visible' => $conditions];
  }

  private function inputsFromForm(FormStateInterface $form_state): array {
    $lines = preg_split('/\r\n|\r|\n/', (string) $form_state->getValue('images')) ?: [];
    $images = array_values(array_filter(array_map('trim', $lines)));
    $region = NULL;
    $raw_region = trim((string) $form_state->getValue('region'));
    if ($raw_region !== '') {
      $parts = array_map('trim', explode(',', $raw_region));
      if (count($parts) === 4) {
        $region = [
          'x' => (float) $parts[0],
          'y' => (float) $parts[1],
          'width' => (float) $parts[2],
          'height' => (float) $parts[3],
        ];
      }
    }
    return [
      'style_preset' => $form_state->getValue('style_preset') ?: 'cinematic_dark',
      'images' => $images,
      'before' => trim((string) $form_state->getValue('before_path')),
      'after' => trim((string) $form_state->getValue('after_path')),
      'before_label' => trim((string) $form_state->getValue('before_label')),
      'after_label' => trim((string) $form_state->getValue('after_label')),
      'viewpoints_differ' => TRUE,
      'disclosure' => 'ये अलग दृष्टिकोण हैं।',
      'document' => trim((string) $form_state->getValue('document_path')),
      'page' => (int) $form_state->getValue('document_page'),
      'region' => $region,
      'entities' => $this->jsonList($form_state->getValue('entities')),
      'edges' => $this->jsonList($form_state->getValue('edges')),
      'series' => $this->jsonList($form_state->getValue('series')),
      'unit' => trim((string) $form_state->getValue('unit')),
      'source_label' => trim((string) $form_state->getValue('source_label')),
      'illustrative' => TRUE,
      'provider' => 'local',
    ];
  }

  private function jsonList($value): array {
    $text = trim((string) $value);
    if ($text === '') {
      return [];
    }
    $decoded = json_decode($text, TRUE);
    return is_array($decoded) ? $decoded : [];
  }

  public function validateForm(array &$form, FormStateInterface $form_state): void {
    foreach ([
      'entities' => 'Entities',
      'edges' => 'Relationships',
      'series' => 'Data',
    ] as $name => $label) {
      $text = trim((string) $form_state->getValue($name));
      if ($text !== '' && !is_array(json_decode($text, TRUE))) {
        $form_state->setErrorByName($name, $this->t('@label must be a JSON list.', ['@label' => $label]));
      }
    }
  }

  public function saveLocations(array &$form, FormStateInterface $form_state): void {
    $button = $form_state->getTriggeringElement();
    $node = $form_state->get('node');
    $job_id = (string) ($button['#job_id'] ?? '');
    $rows = $form_state->getValue(['loc', $job_id]) ?? [];
    $selections = [];
    if (is_array($rows)) {
      foreach ($rows as $row) {
        if (!is_array($row)) {
          continue;
        }
        if (!empty($row['resolved']) && empty($row['change']) && empty($row['use_custom'])) {
          continue;
        }
        if (!empty($row['use_custom'])) {
          $selections[] = [
            'request_id' => $row['request_id'] ?? '',
            'source' => 'manual_custom_point',
            'display_name' => $row['custom_name'] ?? '',
            'latitude' => $row['lat'] ?? '',
            'longitude' => $row['lon'] ?? '',
            'remember' => FALSE,
          ];
          continue;
        }
        $place_id = trim((string) ($row['place_id'] ?? ''));
        if ($place_id === '') {
          continue;
        }
        $selections[] = [
          'request_id' => $row['request_id'] ?? '',
          'source' => 'manual_catalogue_selection',
          'place_id' => $place_id,
          'type_correction' => !empty($row['type_correction']),
          'remember' => !empty($row['remember']),
        ];
      }
    }
    try {
      $result = $this->animations->saveLocationMappings($node, $job_id, $selections, (int) $this->currentUser()->id());
      $errors = $result['errors'] ?? [];
      foreach ($errors as $error) {
        if (is_array($error) && !empty($error['error'])) {
          $this->messenger()->addError($error['error']);
        }
      }
      if (!empty($result['resumed'])) {
        $this->messenger()->addStatus($this->t('Mappings saved. The animation is queued for retry.'));
      }
      elseif ($selections === []) {
        $this->messenger()->addError($this->t('Choose a catalogue place or add a custom point before resuming.'));
      }
      else {
        $this->messenger()->addStatus($this->t('Those mappings were already saved. No second render was started.'));
      }
      $remaining = $result['remaining'] ?? [];
      if ($remaining !== []) {
        $this->messenger()->addWarning($this->t('Some locations still need a choice: @ids', [
          '@ids' => implode(', ', $remaining),
        ]));
      }
    }
    catch (\Throwable $error) {
      $this->messenger()->addError($error->getMessage());
    }
  }

  private function appendLocationFields(array &$form, NodeInterface $node, array $job, array $clip): bool {
    $places = $clip['places'] ?? [];
    if (!is_array($places) || $places === []) {
      return FALSE;
    }
    $saved = $this->savedLocationOverrides((string) ($job['job_dir'] ?? ''));
    $clip_id = (string) ($clip['id'] ?? '');
    $search = Url::fromRoute('story_pipeline.location_search', ['node' => $node->id()])->toString();
    $preview = Url::fromRoute('story_pipeline.location_preview', ['node' => $node->id()])->toString();
    $added = FALSE;
    foreach ($places as $index => $place) {
      if (!is_array($place)) {
        continue;
      }
      $supporting = !empty($place['supporting']);
      $resolved = ($place['status'] ?? '') === 'resolved' && !empty($place['id']);
      if ($supporting && !$resolved) {
        continue;
      }
      $added = TRUE;
      $key = $clip_id . '_' . $index;
      $request_id = (string) ($place['request_id'] ?? ($clip_id . ':' . $index));
      if (isset($saved[$request_id]) && is_array($saved[$request_id])) {
        $override = $saved[$request_id];
        $place['id'] = (string) ($override['place_id'] ?? '');
        $place['name'] = (string) ($override['display_name'] ?? $place['id']);
        $place['status'] = 'resolved';
        $place['reason'] = (string) $this->t('Saved mapping @id.', ['@id' => $place['id']]);
        $resolved = $place['id'] !== '';
      }
      if (!isset($form['job_' . $job['job_id']]['locations'])) {
        $form['job_' . $job['job_id']]['locations'] = [
          '#type' => 'details',
          '#title' => $this->t('Resolve locations'),
          '#open' => TRUE,
          '#tree' => TRUE,
          '#parents' => ['loc', $job['job_id']],
          '#description' => $this->t('Required locations stay listed until a catalogue place or a custom point is saved. Optional features that the catalogue cannot draw are omitted with a warning.'),
        ];
      }
      $form['job_' . $job['job_id']]['locations'][$key] = [
        '#type' => 'details',
        '#title' => $this->t('Resolve @name', ['@name' => (string) ($place['requested'] ?? $place['name'] ?? $request_id)]),
        '#open' => !$resolved,
        '#attributes' => ['data-location-request' => '1'],
      ];
      $group = &$form['job_' . $job['job_id']]['locations'][$key];
      $group['summary'] = [
        '#markup' => $this->locationSummary($place, (string) ($clip['source_passage'] ?? '')),
      ];
      $group['request_id'] = ['#type' => 'hidden', '#value' => $request_id];
      $group['resolved'] = ['#type' => 'hidden', '#value' => $resolved ? '1' : '0'];
      if ($resolved) {
        $group['change'] = [
          '#type' => 'checkbox',
          '#title' => $this->t('Change'),
          '#default_value' => 0,
        ];
      }
      $options = ['' => $this->t('Choose a catalogue place')];
      foreach (array_merge($place['suggested'] ?? [], $place['candidates'] ?? []) as $candidate) {
        if (!is_array($candidate) || empty($candidate['id'])) {
          continue;
        }
        $options[$candidate['id']] = implode(' · ', array_filter([
          $candidate['name'] ?? '',
          $candidate['level'] ?? '',
          $candidate['state_name'] ?? '',
          $candidate['district_name'] ?? '',
          $candidate['representation'] ?? '',
          $candidate['feature_type'] ?? '',
        ]));
      }
      if ($resolved) {
        $options[$place['id']] = implode(' · ', array_filter([
          $place['name'] ?? '',
          $place['level'] ?? '',
          $place['state_name'] ?? '',
          $place['id'],
        ]));
      }
      $group['place_id'] = [
        '#type' => 'select',
        '#title' => $this->t('Catalogue place'),
        '#options' => $options,
        '#default_value' => $resolved ? $place['id'] : '',
        // Search results are added in the browser. The submitted id is checked
        // against the catalogue when the mapping is saved.
        '#validated' => TRUE,
        '#attributes' => ['data-location-results' => '1'],
      ];
      $group['search'] = [
        '#type' => 'textfield',
        '#title' => $this->t('Catalogue search'),
        '#description' => $this->t('Hindi or English. Results stay on the server and are limited.'),
        '#attributes' => [
          'data-location-search' => '1',
          'data-search-url' => $search,
          'data-preview-url' => $preview,
        ],
      ];
      $filters = $this->locationFilters();
      $countries = is_array($filters['countries'] ?? NULL) ? $filters['countries'] : [];
      if ($countries !== []) {
        $country_options = ['' => $this->t('Any country')];
        foreach ($countries as $country) {
          if (!is_array($country)) {
            continue;
          }
          $code = (string) ($country['country_code'] ?? '');
          if ($code === '') {
            continue;
          }
          $country_options[$code] = (string) ($country['name'] ?? $code);
        }
        $group['country_filter'] = [
          '#type' => 'select',
          '#title' => $this->t('Country'),
          '#options' => $country_options,
          '#attributes' => ['data-location-country' => '1'],
        ];
      }
      else {
        $group['country_filter'] = [
          '#type' => 'textfield',
          '#title' => $this->t('Country'),
          '#description' => $this->t('The catalogue country list was unavailable. Type a country name.'),
          '#attributes' => ['data-location-country' => '1'],
        ];
      }
      $level_options = ['' => $this->t('Any feature type')];
      $levels = is_array($filters['levels'] ?? NULL) ? $filters['levels'] : [];
      if ($levels === []) {
        $levels = [
          ['id' => 'country', 'label' => 'Country'],
          ['id' => 'state', 'label' => 'State, province, or territory'],
          ['id' => 'district', 'label' => 'District'],
          ['id' => 'city', 'label' => 'City'],
        ];
      }
      foreach ($levels as $level) {
        if (!is_array($level) || empty($level['id'])) {
          continue;
        }
        $level_options[(string) $level['id']] = (string) ($level['label'] ?? $level['id']);
      }
      $group['level_filter'] = [
        '#type' => 'select',
        '#title' => $this->t('Feature type'),
        '#options' => $level_options,
        '#attributes' => ['data-location-level' => '1'],
      ];
      $group['state_filter'] = [
        '#type' => 'textfield',
        '#title' => $this->t('Narrow by state, province, or territory'),
        '#attributes' => ['data-location-state' => '1'],
      ];
      $group['hierarchy'] = [
        '#markup' => '<p data-location-hierarchy="1"></p>',
      ];
      $group['map'] = [
        '#markup' => '<div class="location-map" data-location-map="1"></div>',
      ];
      $group['type_correction'] = [
        '#type' => 'checkbox',
        '#title' => $this->t('The requested feature type was wrong. Use the selected catalogue type.'),
        '#default_value' => 0,
      ];
      $group['remember'] = [
        '#type' => 'checkbox',
        '#title' => $this->t('Remember this spelling for this location.'),
        '#default_value' => 0,
      ];
      $group['use_custom'] = [
        '#type' => 'checkbox',
        '#title' => $this->t('Add custom point'),
        '#description' => $this->t('A manually supplied point. No boundary is created.'),
        '#default_value' => 0,
      ];
      $group['custom_name'] = [
        '#type' => 'textfield',
        '#title' => $this->t('Custom point name'),
      ];
      $group['lat'] = [
        '#type' => 'textfield',
        '#title' => $this->t('Latitude'),
        '#size' => 12,
      ];
      $group['lon'] = [
        '#type' => 'textfield',
        '#title' => $this->t('Longitude'),
        '#size' => 12,
      ];
      $lat_name = 'loc[' . $job['job_id'] . '][' . $key . '][lat]';
      $lon_name = 'loc[' . $job['job_id'] . '][' . $key . '][lon]';
      $group['custom_map'] = [
        '#markup' => '<div class="location-map" data-custom-map="1" data-lat-name="' . htmlspecialchars($lat_name, ENT_QUOTES, 'UTF-8') . '" data-lon-name="' . htmlspecialchars($lon_name, ENT_QUOTES, 'UTF-8') . '"></div>',
      ];
      unset($group);
    }
    return $added;
  }

  /**
   * @return array{countries: array<int, mixed>, levels: array<int, mixed>}
   */
  private function locationFilters(): array {
    if ($this->geographyFilters === NULL) {
      $this->geographyFilters = $this->animations->geographyFilters();
    }
    return $this->geographyFilters;
  }

  /**
   * @return array<string, array<string, mixed>>
   */
  private function savedLocationOverrides(string $job_dir): array {
    if ($job_dir === '') {
      return [];
    }
    $path = $job_dir . '/location-overrides.json';
    if (!is_file($path)) {
      return [];
    }
    $document = json_decode((string) file_get_contents($path), TRUE);
    $rows = [];
    foreach (is_array($document) ? ($document['overrides'] ?? []) : [] as $row) {
      if (is_array($row) && !empty($row['request_id'])) {
        $rows[(string) $row['request_id']] = $row;
      }
    }
    return $rows;
  }

  private function locationSummary(array $place, string $passage): string {
    $bits = [
      $this->t('Original name: @name', ['@name' => (string) ($place['requested'] ?? '')]),
      $this->t('Feature type: @type', ['@type' => (string) ($place['requested_level'] ?? $place['level'] ?? '')]),
      $this->t('Parent or context: @parent', ['@parent' => (string) ($place['parent_name'] ?? '')]),
      $this->t('Status: @status', ['@status' => (string) ($place['status'] ?? '')]),
      (string) ($place['reason'] ?? ''),
    ];
    $fallback = $place['fallback'] ?? [];
    if (is_array($fallback) && !empty($fallback['skipped_reason'])) {
      $bits[] = $this->t('Fallback: @reason', ['@reason' => (string) $fallback['skipped_reason']]);
    }
    $lines = '';
    foreach ($bits as $bit) {
      if ((string) $bit === '') {
        continue;
      }
      $lines .= '<li>' . htmlspecialchars((string) $bit, ENT_QUOTES, 'UTF-8') . '</li>';
    }
    $sentence = $passage !== '' ? '<blockquote>' . htmlspecialchars($passage, ENT_QUOTES, 'UTF-8') . '</blockquote>' : '';
    return $sentence . '<ul>' . $lines . '</ul>';
  }

  private function jobStatusLabel(array $job): string {
    $status = (string) ($job['status'] ?? '');
    foreach ($job['clips'] ?? [] as $clip) {
      if (is_array($clip) && ($clip['location_status'] ?? '') === 'needs_location_selection') {
        return (string) $this->t('Needs location selection');
      }
    }
    return $this->statusText($status);
  }

  private function clipStatusLabel(array $clip): string {
    if (($clip['location_status'] ?? '') === 'needs_location_selection') {
      return (string) $this->t('Needs location selection');
    }
    $status = (string) ($clip['status'] ?? '');
    if (in_array($status, ['needs_geographic_data', 'needs_location_clarification'], TRUE)) {
      return (string) $this->t('Needs location selection');
    }
    return $this->statusText($status);
  }

  private function statusText(string $status): string {
    $labels = [
      'queued' => 'Queued for retry',
      'resolving_geography' => 'Resolving geography',
      'planning_clips' => 'Planning',
      'rendering' => 'Rendering',
      'completed' => 'Completed',
      'failed' => 'Failed',
      'mappings_saved' => 'Mappings saved',
    ];
    return (string) $this->t($labels[$status] ?? $status);
  }

  private function timingMarkup(array $clip): string {
    $timing = $clip['timing'] ?? NULL;
    if (!is_array($timing)) {
      return '';
    }
    $duration = $timing['map_duration_seconds'] ?? '';
    $note = !empty($timing['provisional']) ? (string) $this->t('provisional') : (string) ($timing['timing_source'] ?? '');
    return '<p><strong>' . $this->t('Timing:') . '</strong> ' . htmlspecialchars((string) $duration, ENT_QUOTES, 'UTF-8') . 's, ' . htmlspecialchars($note, ENT_QUOTES, 'UTF-8') . '</p>';
  }

  /**
   * @param array<string, mixed> $scene_info
   */
  private function staleSceneMarkup(array $clip, array $scene_info): string {
    if (empty($clip['scene_number']) || empty($clip['scene_text_hash']) || empty($scene_info['scenes'])) {
      return '';
    }
    foreach ($scene_info['scenes'] as $scene) {
      if ((int) ($scene['number'] ?? 0) === (int) $clip['scene_number']) {
        if (($scene['text_hash'] ?? '') !== $clip['scene_text_hash']) {
          return '<p><strong>' . $this->t('This map was made from an earlier version of scene @n. It is not the current narration.', ['@n' => (string) $clip['scene_number']]) . '</strong></p>';
        }
      }
    }
    return '';
  }

  private function relativeToJob(string $job_dir, string $absolute): string {
    $root = rtrim($job_dir, '/');
    if (str_starts_with($absolute, $root . '/')) {
      return substr($absolute, strlen($root) + 1);
    }
    return basename($absolute);
  }

}
