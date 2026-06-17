<?php

declare(strict_types=1);

namespace Drupal\story_pipeline\Access;

use Drupal\Core\Access\AccessResult;
use Drupal\Core\Session\AccountInterface;

/**
 * Access for story pipeline staff tools (OR any pipeline permission).
 */
final class StoryPipelineStaffAccessCheck {

  /**
   * Permissions that grant pipeline staff access.
   */
  public const PERMISSIONS = [
    'manage story characters',
    'run story pipeline jobs',
    'administer story pipeline',
  ];

  /**
   * Route access callback.
   */
  public static function access(AccountInterface $account): AccessResult {
    foreach (self::PERMISSIONS as $permission) {
      if ($account->hasPermission($permission)) {
        return AccessResult::allowed()->cachePerPermissions();
      }
    }
    return AccessResult::forbidden()->cachePerPermissions();
  }

}
