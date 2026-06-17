<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Controller;

use Drupal\Core\Controller\ControllerBase;
use Drupal\story_pipeline\Service\CharacterLibrary;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Symfony\Component\HttpFoundation\JsonResponse;
use Symfony\Component\HttpFoundation\Request;

/**
 * Autocomplete controller for character library tagging.
 */
final class CharacterLibraryAutocompleteController extends ControllerBase {

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
   * Return autocomplete matches for library characters.
   */
  public function handle(Request $request): JsonResponse {
    $input = trim((string) $request->query->get('q', ''));
    if ($input === '') {
      return new JsonResponse([]);
    }

    $story_type_tid = $request->query->get('story_type');
    $tid = is_numeric($story_type_tid) ? (int) $story_type_tid : NULL;

    $matches = [];
    foreach ($this->library->searchForAutocomplete($input, $tid) as $record) {
      $label = $this->library->formatAutocompleteLabel($record);
      $matches[] = [
        'value' => $label,
        'label' => $label,
      ];
    }

    return new JsonResponse($matches);
  }

}
