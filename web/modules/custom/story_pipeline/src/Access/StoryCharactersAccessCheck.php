<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Access;

use Drupal\Core\Access\AccessResult;
use Drupal\Core\Routing\RouteMatchInterface;
use Drupal\Core\Session\AccountInterface;
use Drupal\node\NodeInterface;

/**
 * Access check for story character management routes.
 */
final class StoryCharactersAccessCheck {

  /**
   * Permissions that allow managing story characters.
   */
  public const PERMISSIONS = StoryPipelineStaffAccessCheck::PERMISSIONS;

  /**
   * Route access callback.
   */
  public static function access(RouteMatchInterface $route_match, AccountInterface $account): AccessResult {
    $node = $route_match->getParameter('node');
    if (!$node instanceof NodeInterface || $node->bundle() !== 'story') {
      return AccessResult::forbidden();
    }

    foreach (self::PERMISSIONS as $permission) {
      if ($account->hasPermission($permission)) {
        return AccessResult::allowed()->cachePerPermissions();
      }
    }

    return AccessResult::forbidden()->cachePerPermissions();
  }

}
